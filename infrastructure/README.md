# Infrastructure

`docker-compose.yml` at the repository root starts PostgreSQL, Redis, Qdrant,
and MinIO for local development. The API does not connect to them in Phase 1.

The PostgreSQL schema is `postgres/migrations/001_initial.sql`. Apply it when
conversation persistence begins. It is not executed by the API.
