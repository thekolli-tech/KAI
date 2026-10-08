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

Phase 1 shipped the web app, the API health check, and the contracts below. Phase 2 adds the orchestrator. Phase 3 registers a local mock model. Phase 4 exposes that path at `POST /api/v1/chat`. Phase 5 streams it. The workspace composer calls that stream through a same-origin handler.

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

`handle` and `handle_stream` accept a `CancellationToken`. The orchestrator checks it before every stage, before model execution, and between streamed chunks. Cancelling the token becomes `EngineError` with kind `cancelled`. `handle` raises that error. `handle_stream` emits it as `run.failed`. `asyncio.CancelledError` is not converted into a stage failure; it propagates so the caller's task can cancel. There is no job queue.

### Model boundary

`ModelRouter.select` returns a `ModelChoice`. `handle` stores it, checks cancellation again, then calls `ModelRouter.execute`. `handle_stream` checks cancellation, then calls `ModelRouter.stream` and yields each chunk before verification. The joined text is stored on `ExecutionContext.model_result` and is the candidate passed to verification and response composition. Agent text stays on the context and is not rewritten into that candidate.

`kai_engine` does not import `ModelProvider`, `MockModelProvider`, FastAPI, Starlette, or an SSE library. `RegisteredModelRouter` resolves a provider from an injected `ProviderRegistry` and calls `generate` or `stream`. The model runtime yields text chunks. The engine yields public `RunEvent` values. The HTTP layer serializes those events as SSE.

### Errors from the model path

The router raises `ProviderUnavailableError` when the provider id or model id is not registered, when `health_check` returns false, or when `health_check` itself fails. It raises `ExecutionFailureError` when `generate` or `stream` fails, or when `generate` returns a different provider or model id. The orchestrator records those at the model selection stage. `handle` raises `EngineError`. `handle_stream` emits `run.failed`.

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
- `POST /api/v1/chat`
- `POST /api/v1/chat/stream`

`POST /api/v1/chat` accepts `message` and optional `conversation_id`, `project_id`, and `attachment_ids`. It does not accept an organization id. `LocalDevelopmentAuthenticator` resolves the principal from server settings and only outside production. The route then calls `organization_boundary` and `KaiEngineOrchestrator.handle`. The HTTP body is the `EngineResponse`. Typed engine failures use `EngineError.to_public_dict()`. Any other exception is a generic 500 with no exception text.

`POST /api/v1/chat/stream` uses that same authentication, organization boundary, `ChatRequest` validation, request id, and engine request. The client cannot supply the organization id. The response is `text/event-stream` with `Cache-Control: no-cache` and `X-Accel-Buffering: no`. The HTTP layer encodes public `RunEvent` values. `ModelProvider` does not format SSE.

Public events are `run.started`, `message.delta`, `message.completed`, `run.completed`, and `run.failed`. Each data object includes `request_id`, `run_id`, and `organization_id`. Deltas are the provider chunks. Joining them reconstructs `provider_id:model_id:message`. For the registered mock that text is `mock:mock-text:<message>`. `message.completed` and `run.completed` carry the response message, model id, provider id, and `verified`.

`verified` is the verification result. `AcceptingVerifier` still accepts every candidate because no verification policy exists. Finishing the stream does not set `verified`. A rejected `VerificationResult` is `run.failed` with kind `verification_failure` and does not emit `run.completed`.

Authentication and validation failures happen before the body and use the same HTTP statuses as `POST /api/v1/chat`. After the stream starts, failures are `run.failed`. Typed failures use `EngineError.to_public_dict()`. Any other exception is `{"message":"The request could not be completed."}` with no exception text, traceback, or secret. The connection then closes.

A client disconnect cancels the request `CancellationToken` and closes the provider stream. A cancellation the engine observes between chunks is `run.failed` with kind `cancelled`. It is not an HTTP 500. There is no task queue.

The stages beside the model router are pass-throughs in the API composition root. They do not classify, search, retrieve documents, execute tools, or write an agent reply. The response message is the mock provider's text. `MockModelProvider` remains the only provider. Health still reports `model_runtime: mock` and `engine: interface_only`. This is not production inference.

Routes that are specified for later phases and are intentionally absent:

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

Authentication is a port (`Authenticator`). Chat attaches `LocalDevelopmentAuthenticator`, which reads a server-configured principal and is disabled in production. It is not a membership directory. A client-supplied organization header is not a source of identity.

`organization_boundary` is the rule already implemented: a principal may act only in its own organization. Product routes must use it, or the later `Authorizer`, before they read tenant data.

Rate limiting and audit logging are ports. There is no limiter that allows every request and calls that enforcement. Audit storage is append-only in the schema: `kai_app` can insert and select `audit_logs`, not update or delete them.

Tool permissions are declared on each tool spec. The engine `SecurityEngine` is the later place to refuse a tool the principal cannot hold.

CORS allows the configured web origin only.

## Multi-tenancy

The schema uses UUIDs. Tenant tables carry `organization_id`. Child rows use composite foreign keys so a message cannot point at a conversation in another organization.

Row level security is forced. The application role is `kai_app`. It must not be a superuser, because superusers bypass row level security. Before queries run, the server sets `kai.organization_id` and `kai.user_id` from the authenticated membership.

The schema is `infrastructure/postgres/migrations/001_initial.sql`. The API does not open a database connection yet, so a missing database does not look healthy. An empty URL is `not_configured`. A set URL is `configured_unchecked`.

## Web workspace

The workspace is a dark graphite surface with champagne gold and silver. It shows the brand, reserved quick actions, the composer, and the live health check.

Quick actions are disabled. The composer submits to the same-origin stream. Projects, knowledge, agents, and tools render empty states that say those capabilities are not running. Settings does not save an account. The assistant label is Local Mock Provider. KAI currently uses `MockModelProvider`. It is not a production model.

Design-system components live under `apps/web/src/components`. shadcn/ui supplies button, input, dialog, and dropdown primitives. Product components wrap those primitives where the product name differs (modal, dropdown).

## Dependency direction

```
apps/web → packages/shared, packages/types, packages/config
apps/api → composition → ModelRouter → ModelProvider → MockModelProvider
kai_engine → ModelRouter protocol only
model-runtime → its own provider, mock, and registry contracts
```

`kai_engine` does not import the model runtime, tool, agent, memory, search, or document packages, and it does not import a web framework, an SSE library, or a database client. The API composition root constructs the registry and the router. Chat and the SSE route call the orchestrator through that router. The other stages are pass-throughs.

## Streaming

`POST /api/v1/chat/stream` is the streaming chat route. The path is the workspace, then the same-origin handler, then authentication and the organization boundary, then `KaiEngineOrchestrator.handle_stream`, then `RegisteredModelRouter.stream`, then `ModelProvider.stream`, then `MockModelProvider.stream`, then SSE back to the browser. The route does not construct a provider. `kai_engine` does not import `MockModelProvider`. The web app does not import the provider, the registry, or the engine.

Public events are `run.started`, `message.delta`, `message.completed`, `run.completed`, and `run.failed`. Each one carries `request_id`, `run_id`, and `organization_id`. The browser appends `message.delta` as it arrives. `verified` is still the accepting verifier's result. A `run.failed` event shows the public message. Stack traces, paths, and secrets are not shown.

The same-origin handler reads `KAI_LOCAL_BEARER_TOKEN` and `KAI_API_ORIGIN`. Those values are not `NEXT_PUBLIC_` settings. Stop generation aborts the browser fetch. The API sees the disconnect, cancels the `CancellationToken`, and closes the provider stream. Cancellation is not an HTTP 500.

`POST /api/conversations` creates a server-generated conversation id in the workspace process. The transcript can be listed and loaded until that process stops. It is not the PostgreSQL schema. The API still does not open a database connection.

## Next step

Persist conversations and messages in PostgreSQL through the existing schema and organization boundary. Keep `MockModelProvider` as the only provider. Do not add a hosted model.
