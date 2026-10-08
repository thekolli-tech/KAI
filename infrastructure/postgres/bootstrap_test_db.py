"""Create the PostgreSQL database used by the conversation tests.

The tests open ``postgresql://kai:kai-local-password@127.0.0.1:5432/kai_test``
unless ``KAI_TEST_DATABASE_URL`` is set. This script prepares that database on a
server that is already running. It applies ``001_initial.sql`` when the
conversations table is missing, then checks that ``kai_app`` exists and that
row-level security is forced on conversations.

Start PostgreSQL first. Either command is enough:

    docker compose up -d postgres

``POSTGRES_PASSWORD`` must be ``kai-local-password`` so the default test URL
can log in. Compose creates the ``kai`` database; this script creates
``kai_test``. Or start a local PostgreSQL server and rerun this script. It
uses the local ``postgres`` superuser to create the ``kai`` role when TCP login
is not available yet.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "infrastructure" / "postgres" / "migrations" / "001_initial.sql"
DEFAULT_URL = "postgresql://kai:kai-local-password@127.0.0.1:5432/kai_test"
ADMIN_URL = "postgresql://kai:kai-local-password@127.0.0.1:5432/postgres"
ROLE_SQL = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kai') THEN
    CREATE ROLE kai LOGIN SUPERUSER PASSWORD 'kai-local-password';
  ELSE
    ALTER ROLE kai WITH LOGIN SUPERUSER PASSWORD 'kai-local-password';
  END IF;
END
$$;
SELECT 'CREATE DATABASE kai_test OWNER kai'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'kai_test')\\gexec
"""


def main() -> None:
    url = os.environ.get("KAI_TEST_DATABASE_URL", DEFAULT_URL).strip() or DEFAULT_URL
    if _database_ready(url):
        print("kai_test is ready for conversation tests.")
        return
    if url != DEFAULT_URL:
        _fail(
            "KAI_TEST_DATABASE_URL is set, and that database could not be opened. "
            "Start PostgreSQL and apply infrastructure/postgres/migrations/001_initial.sql."
        )
    if not _port_open():
        _fail(
            "PostgreSQL is not accepting connections on 127.0.0.1:5432.\n"
            "Start it, then rerun this script:\n"
            "  docker compose up -d postgres\n"
            "Set POSTGRES_PASSWORD=kai-local-password before that command. "
            "A local PostgreSQL 16 server on port 5432 also works."
        )
    if _provision_with_kai_admin() or _provision_with_local_superuser():
        if _database_ready(url):
            print("kai_test is ready for conversation tests.")
            return
    _fail(
        "PostgreSQL is running, but kai_test is not available to the conversation tests. "
        "Use POSTGRES_PASSWORD=kai-local-password, or set KAI_TEST_DATABASE_URL to a "
        "superuser URL that can SET ROLE kai_app."
    )


def _database_ready(url: str) -> bool:
    try:
        connection = psycopg.connect(url, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError:
        return False
    with connection:
        _apply_schema(connection)
        _verify_tenant_role(connection)
    return True


def _apply_schema(connection: psycopg.Connection) -> None:
    found = connection.execute("SELECT to_regclass('public.conversations')").fetchone()
    if found is not None and found[0] is not None:
        return
    script = SCHEMA.read_text(encoding="utf-8")
    with psycopg.ClientCursor(connection) as cursor:
        cursor.execute(script)


def _verify_tenant_role(connection: psycopg.Connection) -> None:
    row = connection.execute(
        """
        SELECT r.rolcanlogin, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_roles AS r
        CROSS JOIN pg_class AS c
        WHERE r.rolname = 'kai_app'
          AND c.relname = 'conversations'
          AND c.relkind = 'r'
        """
    ).fetchone()
    if row != (False, True, True):
        _fail("kai_app is missing, or conversations row-level security is not forced.")
    connection.execute("SET ROLE kai_app")
    current = connection.execute("SELECT current_user").fetchone()
    connection.execute("RESET ROLE")
    if current != ("kai_app",):
        _fail("The test database role cannot SET ROLE kai_app.")


def _provision_with_kai_admin() -> bool:
    try:
        connection = psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError:
        return False
    with connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'kai_test'"
        ).fetchone()
        if exists is None:
            connection.execute("CREATE DATABASE kai_test OWNER kai")
    return True


def _provision_with_local_superuser() -> bool:
    probe = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", "postgres", "-tAc", "SELECT 1"],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        return False
    created = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-d", "postgres"],
        input=ROLE_SQL,
        text=True,
        check=False,
    )
    return created.returncode == 0


def _port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=3):
            return True
    except OSError:
        return False


def _fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
