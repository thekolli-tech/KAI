# Infrastructure

`docker-compose.yml` at the repository root starts PostgreSQL, Redis, Qdrant,
and MinIO for local development. Conversation routes use PostgreSQL when
`DATABASE_URL` is set. The other services stay unconnected.

The PostgreSQL schema is `postgres/migrations/001_initial.sql`. A new Docker
volume applies it on first start. An existing volume needs the file applied
once. The API does not execute the migration.

Conversation tests use database `kai_test`. `postgres/bootstrap_test_db.py`
creates that database, applies the schema, and checks the `kai_app` role.
`POSTGRES_PASSWORD` must be `kai-local-password` for the default test URL.
