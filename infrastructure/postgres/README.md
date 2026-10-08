# PostgreSQL

`migrations/001_initial.sql` is the schema. Apply it once as a role that can
create tables. The API then sets the session role to `kai_app` and sets
`kai.organization_id` and `kai.user_id` from the authenticated principal.
Do not point `DATABASE_URL` at a superuser without that role change: superusers
bypass row level security.

## Conversation tests

The conversation tests open a real PostgreSQL database. They are not mocked.
The default URL is `postgresql://kai:kai-local-password@127.0.0.1:5432/kai_test`.
`KAI_TEST_DATABASE_URL` overrides it. The connection role must be able to
`SET ROLE kai_app`.

Start PostgreSQL, then bootstrap the test database:

```bash
# .env: POSTGRES_PASSWORD=kai-local-password
docker compose up -d postgres
scripts/py infrastructure/postgres/bootstrap_test_db.py
```

Compose creates the `kai` database. The bootstrap creates `kai_test` when it
is missing, applies the schema, and checks `kai_app` plus forced row-level
security. A local PostgreSQL 16 server on port 5432 can be used instead of
Docker. The script creates the `kai` login through the local `postgres`
superuser when TCP login is not available yet.

GitHub Actions starts the same database as a `postgres:16` service and runs
the bootstrap before pytest. The API does not run migrations.
