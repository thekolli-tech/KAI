from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = REPO_ROOT / "infrastructure" / "postgres" / "migrations" / "001_initial.sql"

TENANT_TABLES = (
    "organizations",
    "users",
    "memberships",
    "projects",
    "conversations",
    "messages",
    "files",
    "memories",
    "agents",
    "tools",
    "usage_events",
    "audit_logs",
)

ORG_SCOPED_TABLES = (
    "memberships",
    "projects",
    "conversations",
    "messages",
    "files",
    "memories",
    "agents",
    "tools",
    "usage_events",
    "audit_logs",
)


def test_initial_schema_defines_tenant_tables_and_rls() -> None:
    sql = SCHEMA.read_text(encoding="utf-8").lower()
    for table in TENANT_TABLES:
        assert f"create table {table} " in sql
        assert f"alter table {table} enable row level security" in sql
        assert f"alter table {table} force row level security" in sql
    for table in ORG_SCOPED_TABLES:
        create = sql.split(f"create table {table} ", maxsplit=1)[1]
        body = create.split("create table ", maxsplit=1)[0]
        assert "organization_id uuid not null" in body
    assert "gen_random_uuid()" in sql
    assert "grant select, insert on audit_logs to kai_app" in sql
    assert "update, delete on audit_logs" not in sql
