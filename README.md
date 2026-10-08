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

Health reports `model_runtime: mock`. `POST /api/v1/chat` runs the orchestrator against that mock. The other stages are pass-throughs. Tool execution, agents, memory, document ingestion, and production authentication are not implemented. The workspace composer does not send messages.

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

Replace the `change-me` passwords in `.env` before starting Docker. Leave the infrastructure URLs blank unless you want the health check to report them as configured. The API does not connect to them.

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

The schema file is `infrastructure/postgres/migrations/001_initial.sql`. The API does not apply it yet.

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

`apps/api` builds a `ProviderRegistry` with `MockModelProvider` and passes it to `RegisteredModelRouter`. `KaiEngineOrchestrator` calls `select`, then `execute`, and passes that text to verification. Tests in `services/model-runtime/tests` and `apps/api/tests/test_model_path.py` cover the path without a network or a database.

## Chat

`POST /api/v1/chat` requires a bearer token. Outside production, `KAI_LOCAL_BEARER_TOKEN`, `KAI_LOCAL_USER_ID`, and `KAI_LOCAL_ORGANIZATION_ID` configure that token and the principal. The body is a message. The response message is the deterministic mock text. Production refuses the local token.

## Next step

Phase 5 adds `POST /api/v1/chat/stream` from `MockModelProvider.stream`. The mock stays the only provider.
