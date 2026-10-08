# Infrastructure

`docker-compose.yml` at the repository root starts PostgreSQL, Redis, Qdrant,
and MinIO for local development. Conversation routes use PostgreSQL when
`DATABASE_URL` is set. The other services stay unconnected.

The PostgreSQL schema is `postgres/migrations/001_initial.sql`. A new Docker
volume applies it on first start. An existing volume needs the file applied
once. The API does not execute the migration.
