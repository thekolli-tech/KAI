# KAI architecture

KAI is the intelligence layer in the THEKOLLI ecosystem. KORA, KERP, and KAB are out of scope. They will call KAI later. They are not part of this repository.

## Shape

```
User
  → KAI web app (apps/web)
  → KAI API (apps/api)
  → KAI Engine (services/kai-engine)
  → models, tools, memory, documents, search
```

Phase 1 shipped the web app, the API health check, and the contracts below. Phase 2 adds the orchestrator. Phase 3 registers a local mock model and calls it through `ModelRouter`. The API still does not expose a chat route.

The API is a modular monolith. `services/*` are Python packages imported by that process. They are not separate network services. Split them only when a boundary has its own scaling or security reason.

## Engine stages

`KaiEngineOrchestrator.handle` is the entry. It is constructed with the stage protocols and calls them in this order:

1. Request intake validates an `EngineRequest`.
2. Intent detection classifies the message.
3. Context construction assembles organization-scoped memory and document ids.
4. Planning produces a `TaskPlan`.
5. Model selection chooses a provider id and model id, then the router executes that model.
6. Tool selection chooses tool names.
7. Agent execution delegates once to an agent.
8. Memory retrieval returns memory ids for the caller's organization.
9. Tool execution runs each selected tool, or none when the selection is empty.
10. Verification accepts or rejects the model router's text.
11. Response composition returns an `EngineResponse`.

The orchestrator stores each result on an `ExecutionContext` and passes that context into the next stage. It does not classify, plan, or write the answer. There are still no product implementations of the individual stages. Tests supply doubles. A stage that raised `NotImplementedError` and was registered as a real capability would look like a product feature, so none is registered.

`ExecutionContext` carries the request id, run id, user id, organization id, conversation id, raw input, normalized request, intent, context bundle, plan, selected model, model result, selected tools, selected agents, memory ids, tool results, agent text, verification, and response. A field is `None` until that stage has run. An empty tuple or string means the stage ran and produced nothing.

The candidate passed to verification is the model router's text. It is an empty string when the router returns an empty string. Tool results and agent text stay on the context. They are not rewritten into a prompt.

### Dependency injection

```python
KaiEngineOrchestrator(
    intake=...,
    intent=...,
    context=...,
    planner=...,
    model_router=...,
    tool_router=...,
    agent=...,
    memory=...,
    verifier=...,
    responder=...,
)
```

Every argument is a protocol from `kai_engine.interfaces`. The orchestrator does not construct providers, tools, or stores.

### Errors

A failure stops the pipeline. `EngineError` carries the kind, the stage, the request id, the run id, and the organization id. `str(error)` and `to_public_dict()` omit the causing exception, so an API can return them without a stack trace. The cause stays on `__cause__` for server logs.

Kinds are `invalid_input`, `unavailable_dependency`, `stage_failure`, `provider_unavailable`, `execution_failure`, `verification_failure`, and `cancelled`. Stages raise the matching `EngineStageError` subclass. A rejected `VerificationResult` is a verification failure and does not call response composition. A tool result with `succeeded` false is an execution failure. A context bundle for another organization stops the run.

### Cancellation

`handle` accepts a `CancellationToken`. The orchestrator checks it before every stage and before returning a response. Cancelling the token raises `EngineError` with kind `cancelled`. `asyncio.CancelledError` is not converted into a stage failure; it propagates so the caller's task can cancel. There is no job queue.

### Model boundary

`ModelRouter.select` returns a `ModelChoice`. The orchestrator stores it, checks cancellation again, then calls `ModelRouter.execute`. The returned text is stored on `ExecutionContext.model_result` and is the candidate passed to verification and response composition. Agent text stays on the context and is not rewritten into that candidate.

`kai_engine` does not import `ModelProvider` or `MockModelProvider`. `RegisteredModelRouter` in the API resolves a provider from an injected `ProviderRegistry` and calls `generate`. `handle` does not emit stream events. `ModelProvider.stream` remains the local streaming port for a later SSE adapter.

### Errors from the model path

The router raises `ProviderUnavailableError` when the provider id or model id is not registered, when `health_check` returns false, or when `health_check` itself fails. It raises `ExecutionFailureError` when `generate` fails or returns a different provider or model id. The orchestrator records those at the model selection stage and stops the pipeline.

## Model runtime

`ModelProvider` requires:

- `generate()`
- `stream()`
- `get_capabilities()`
- `health_check()`

`MockModelProvider` implements that protocol locally. Output is a configured fixture for the prompt, or the deterministic text `provider_id:model_id:prompt`. `stream` yields fixed-size slices of that same text and does not sleep. Capabilities are `text` and `stream`. Tool calling and vision are absent. There is no embeddings capability on the contract. `health_check` returns the configured boolean. The class does not open a socket and does not read an API key.

`ProviderRegistry` maps an explicit provider id to an injected `ModelProvider`. `resolve(provider_id, model_id)` checks `get_capabilities()`. An unknown provider or model raises `UnknownProviderError` or `UnknownModelError`. The registry is constructed by the caller. It is not a process-wide singleton, and the router does not construct providers.

The API composition root builds one registry containing `MockModelProvider` (`provider_id=mock`, `model_id=mock-text`) and a `RegisteredModelRouter` around it. Health reports `model_runtime: mock`. An empty registry reports `model_runtime: interface_only`. `mock` means a local development stand-in, not production inference. The engine check stays `interface_only` because the orchestrator is not mounted on a route.

`KAI_MODEL_PROVIDER` is still reserved. A vendor name in that variable is not echoed and does not change the registered provider.

Planned implementations that do not exist yet:

- `LocalModelProvider`
- `OllamaProvider`
- `VLLMProvider`

## Tools

`Tool` carries a name, description, JSON input schema, permissions, and `execute()`. `ToolRegistry` only contains objects that implement `execute()`. It starts empty.

The planned catalog is data, with `implemented: false`:

- calculator
- web_search
- web_fetch
- file_read
- file_search

There is no shell, bash, or code-execution tool. A later code tool has to run in a sandbox and still has to go through the permission check. The model must not receive a way to start a host process.

`web_search` and `web_fetch` will call `SearchProvider`. That port is the seam for a self-hosted search layer. Phase 1 does not fetch the web.

## Agents

`Agent` carries a name, description, capabilities, tools, permissions, and `execute()`.

Planned agents, all `implemented: false`:

- ResearchAgent
- CodingAgent
- DataAgent
- DocumentAgent

An agent may only call tools listed on its spec, and only when the principal holds the tool's permissions. Autonomous loops are a later design, not a hidden behavior.

## Memory

`MemoryStore` has `save`, `search`, `update`, and `delete`.

Scopes are short-term conversation memory, long-term user memory, and project memory. Every call carries `organization_id`. `delete` also takes the organization id so a memory id alone cannot cross tenants.

PostgreSQL will store the records. Qdrant will store vectors. A deletion request has to remove both. Phase 1 does not write either store, and it does not collect memory.

## Documents

The later path is:

```
Upload → processor → extraction → chunking → embeddings → vector store → retrieval → KAI
```

The ports are `DocumentProcessor`, `Chunker`, `EmbeddingProvider`, and `VectorStore`. Kinds on the contract are PDF, DOCX, XLSX, PPTX, TXT, images, and source code. No parser is implemented. The first working parser should be plain text.

Object bytes belong in MinIO. PostgreSQL stores the object key and metadata, not the file body.

## API

Versioned routes that exist:

- `GET /api/v1/health`
- `GET /health` for a process probe

Routes that are specified for later phases and are intentionally absent:

- `POST /api/v1/chat`
- `POST /api/v1/chat/stream`
- conversation CRUD
- `POST /api/v1/files`
- `POST /api/v1/search`
- `POST /api/v1/agents/run`
- `GET /api/v1/models`
- `GET /api/v1/tools`

The OpenAPI document is generated from the FastAPI app. Browser code parses health responses with `parseHealthReport` in `@kai/types`. Product version and phase come from `packages/config/kai.config.json`, which the API reads at startup.

## Security

Secrets are environment variables. `.env.example` lists the names. The health payload does not include URLs, keys, or the configured provider name. `NEXT_PUBLIC_KAI_API_URL` is the only browser-facing setting, and it is an origin, not a credential.

Request ids are accepted only when they match a short token pattern. Anything else is replaced.

Authentication is a port (`Authenticator`). It is not attached to a route. When it is attached, the principal's organization must come from a membership row on the server. A client-supplied organization header is not a source of identity.

`organization_boundary` is the rule already implemented: a principal may act only in its own organization. Product routes must use it, or the later `Authorizer`, before they read tenant data.

Rate limiting and audit logging are ports. There is no limiter that allows every request and calls that enforcement. Audit storage is append-only in the schema: `kai_app` can insert and select `audit_logs`, not update or delete them.

Tool permissions are declared on each tool spec. The engine `SecurityEngine` is the later place to refuse a tool the principal cannot hold.

CORS allows the configured web origin only.

## Multi-tenancy

The schema uses UUIDs. Tenant tables carry `organization_id`. Child rows use composite foreign keys so a message cannot point at a conversation in another organization.

Row level security is forced. The application role is `kai_app`. It must not be a superuser, because superusers bypass row level security. Before queries run, the server sets `kai.organization_id` and `kai.user_id` from the authenticated membership.

The schema is `infrastructure/postgres/migrations/001_initial.sql`. The API does not open a database connection yet, so a missing database does not look healthy. An empty URL is `not_configured`. A set URL is `configured_unchecked`.

## Web workspace

The workspace is a dark graphite surface with champagne gold and silver. It shows the brand, reserved quick actions, a disabled composer, and the live health check.

Quick actions are disabled. The composer does not submit. Chats, projects, knowledge, agents, and tools render empty states that say those capabilities are not running. Settings does not save an account.

Design-system components live under `apps/web/src/components`. shadcn/ui supplies button, input, dialog, and dropdown primitives. Product components wrap those primitives where the product name differs (modal, dropdown).

## Dependency direction

```
apps/web → packages/shared, packages/types, packages/config
apps/api → composition → ModelRouter → ModelProvider → MockModelProvider
kai_engine → ModelRouter protocol only
model-runtime → its own provider, mock, and registry contracts
```

`kai_engine` does not import the model runtime, tool, agent, memory, search, or document packages, and it does not import a web framework or a database client. The API constructs the registry and the router. It still does not mount the orchestrator on a chat route, because the other stages have no product implementations.

## Phase 4

Add `POST /api/v1/chat` at the composition root. Inject `KaiEngineOrchestrator` with `RegisteredModelRouter` and explicit stage implementations for the stages that are still doubles in tests. Return the engine response. Keep `MockModelProvider` as the only provider. Do not add a hosted model, and do not put provider construction inside `kai_engine`. Streaming SSE can follow that route once the mock text is returned on the request path.
