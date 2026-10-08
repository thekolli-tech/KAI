# KAI

KAI by THEKOLLI is a provider-agnostic AI intelligence platform. This repository is the Phase 1 architecture: a Next.js workspace, a FastAPI modular monolith, and engine boundaries that do not call a hosted model.

The model runtime is an interface. OpenAI, Anthropic, Gemini, and Perplexity are not integrated. A later phase can add a mock provider, then a self-hosted runtime, without rewriting the workspace or the engine contracts.

## What runs in this phase

- Web workspace at `apps/web`
- API health checks at `GET /api/v1/health` and `GET /health`
- Shared TypeScript contracts in `packages/`
- Python interfaces for the engine, models, tools, agents, memory, search, and documents
- PostgreSQL schema and Docker Compose for PostgreSQL, Redis, Qdrant, and MinIO

Chat, tool execution, agents, memory, document ingestion, and authentication are not implemented. The interface does not pretend they are.

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

Replace the `change-me` passwords in `.env` before starting Docker. Leave the infrastructure URLs blank unless you want the health check to report them as configured. Phase 1 still does not connect to them.

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

## Next step

Phase 2 wires the KAI Engine interfaces into a real intake-to-response pipeline, still without a model provider. Phase 3 adds `MockModelProvider`.
