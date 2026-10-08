# KAI

KAI by THEKOLLI is a provider-agnostic AI intelligence platform. This repository has a Next.js workspace, a FastAPI modular monolith, and a KAI Engine orchestrator that calls stage protocols. It does not call a hosted model.

The model runtime registers `MockModelProvider`, a deterministic local stand-in for development and tests. It is not a production intelligence provider. OpenAI, Anthropic, Gemini, and Perplexity are not integrated.

## What runs in this phase

- Web workspace at `apps/web`
- API health checks at `GET /api/v1/health` and `GET /health`
- Shared TypeScript contracts in `packages/`
- Python interfaces for the engine, models, tools, agents, memory, search, and documents
- `KaiEngineOrchestrator`, which runs those stage protocols when they are injected
- `MockModelProvider` and `RegisteredModelRouter`, composed by the API and kept out of `kai_engine`
- PostgreSQL schema and Docker Compose for PostgreSQL, Redis, Qdrant, and MinIO

Health reports `model_runtime: mock`. `POST /api/v1/chat` and `POST /api/v1/chat/stream` run the orchestrator against that mock. The workspace composer streams through a same-origin handler. The browser does not receive the local bearer token. The other stages are pass-throughs. Tool execution, agents, memory, document ingestion, and production authentication are not implemented. Conversations and messages are stored in PostgreSQL for the authenticated organization.

## Layout

```
apps/web          Next.js workspace
apps/api          FastAPI application
apps/admin        Reserved. No application yet.
packages/shared   Brand and route constants
packages/types    Browser-side API contracts
packages/config   Shared product config
services/*        Engine and capability boundaries, imported by the API
infrastructure/   Schema and local dependency notes
```

The API is one process. Service folders are libraries, not separate deployable services.

## Requirements

- Node.js 22
- pnpm 10
- Python 3.12

Docker is only required when you want the local infrastructure containers.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pnpm install
cp .env.example .env
cp apps/web/.env.example apps/web/.env.local
```

Replace the `change-me` passwords in `.env` before starting Docker. Leave the infrastructure URLs blank unless you want the health check to report them as configured. Set `DATABASE_URL` and apply `infrastructure/postgres/migrations/001_initial.sql` before using conversations. The API reads and writes conversations as `kai_app`.

## Run

```bash
source .venv/bin/activate
pnpm dev:api
```

```bash
pnpm dev:web
```

- Workspace: http://localhost:3000
- API health: http://localhost:8000/api/v1/health
- API docs: http://localhost:8000/api/v1/docs

## Infrastructure

```bash
docker compose up -d
```

The schema file is `infrastructure/postgres/migrations/001_initial.sql`. Apply it to the database in `DATABASE_URL`. A fresh Docker volume applies it on first start. The API does not run the migration itself.

Conversation tests need a real PostgreSQL database named `kai_test` on `127.0.0.1:5432`. Set `POSTGRES_PASSWORD=kai-local-password` in `.env`, start Compose, then bootstrap:

```bash
docker compose up -d postgres
scripts/py infrastructure/postgres/bootstrap_test_db.py
```

The bootstrap creates `kai_test`, applies the schema, and checks `SET ROLE kai_app` with forced row-level security. A local PostgreSQL 16 server can replace Docker. `KAI_TEST_DATABASE_URL` overrides the default test URL. GitHub Actions starts this database for the API job.

## Checks

```bash
source .venv/bin/activate
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Python commands use `scripts/py`, which prefers `.venv`.

## Local model path

`apps/api` builds a `ProviderRegistry` with `MockModelProvider` and passes it to `RegisteredModelRouter`. `KaiEngineOrchestrator.handle` calls `select`, then `execute`. `handle_stream` calls `select`, then `stream`. Both pass the model text to verification. The model-path tests do not need a network. Conversation tests need PostgreSQL.

## Chat

`POST /api/v1/chat` and `POST /api/v1/chat/stream` require a bearer token. Outside production, `KAI_LOCAL_BEARER_TOKEN`, `KAI_LOCAL_USER_ID`, and `KAI_LOCAL_ORGANIZATION_ID` configure that token and the principal. The body is a message. The client cannot set the organization id. Production refuses the local token.

The JSON route returns the deterministic mock text. The stream route is `text/event-stream` and is not cached. Events are `run.started`, `message.delta`, `message.completed`, `run.completed`, and `run.failed`. Joining the deltas produces `mock:mock-text:<message>`. `verified` comes from the current verifier, which accepts text because no verification policy exists. Authentication and validation errors stay HTTP errors. After the stream starts, failures are `run.failed` with no traceback or secret. Disconnect cancels the run and closes the mock stream.

## Workspace

The composer posts to the same-origin route `/api/chat/stream`. That route attaches `KAI_LOCAL_BEARER_TOKEN` on the server and calls `POST /api/v1/chat/stream`. The browser never sees the token. Deltas update the assistant message as they arrive. Stop generation aborts the browser request so the API can cancel the provider stream. The label is Local Mock Provider. KAI is not using a production model.

`POST /api/conversations` asks the API to create a conversation for the authenticated organization. The user message is stored before the mock runs. One assistant message is stored when the run completes. A failed or cancelled run does not store a completed assistant message. Reload and a Next.js restart both read the transcript from PostgreSQL.

## Next step

The local development credential is still not a production identity system. Keep `MockModelProvider` as the only provider. Do not add a hosted model.
