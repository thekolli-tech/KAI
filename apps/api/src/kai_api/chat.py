"""Chat routes. Both calls share authentication, validation, and the engine."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.requests import ClientDisconnect

from kai_api.access import AuthenticationFailed
from kai_api.security.contracts import RequestCredentials
from kai_api.sse import encode_run_event
from kai_engine.context import CancellationToken
from kai_engine.contracts import EngineRequest, EngineResponse
from kai_engine.errors import EngineError, EngineErrorKind
from kai_engine.events import RunEvent, RunEventType

logger = logging.getLogger("kai_api.chat")

_STATUS = {
    EngineErrorKind.INVALID_INPUT: 422,
    EngineErrorKind.UNAVAILABLE_DEPENDENCY: 503,
    EngineErrorKind.STAGE_FAILURE: 500,
    EngineErrorKind.PROVIDER_UNAVAILABLE: 503,
    EngineErrorKind.EXECUTION_FAILURE: 502,
    EngineErrorKind.VERIFICATION_FAILURE: 422,
    EngineErrorKind.CANCELLED: 409,
}

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}

_GENERIC_FAILURE = "The request could not be completed."


class ChatRequest(BaseModel):
    """Caller fields for one chat turn. Identity is not part of this body."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=32_000)
    conversation_id: UUID | None = None
    project_id: UUID | None = None
    attachment_ids: list[UUID] = Field(default_factory=list)


class AuthorizationRefused(Exception):
    """The principal may not act in the requested organization."""


def install_chat(router: APIRouter) -> None:
    router.add_api_route("/chat", post_chat, methods=["POST"], response_model=EngineResponse)
    router.add_api_route(
        "/chat/stream",
        post_chat_stream,
        methods=["POST"],
        response_model=None,
        responses={
            200: {
                "description": "Server-sent events for one chat run.",
                "content": {"text/event-stream": {"schema": {"type": "string"}}},
            }
        },
    )


async def post_chat(body: ChatRequest, request: Request) -> EngineResponse:
    engine_request = await _accepted_request(body, request)
    response = await request.app.state.engine.handle(engine_request)
    return cast(EngineResponse, response)


async def post_chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    """Stream one chat run as SSE.

    Events are ``run.started``, ``message.delta``, ``message.completed``,
    ``run.completed``, and ``run.failed``. Each data object carries
    ``request_id``, ``run_id``, and ``organization_id``. Deltas are model
    chunks. ``verified`` is the existing verification result. Completing
    the stream does not mark a run verified.

    Authentication and validation failures use the same HTTP errors as
    ``POST /api/v1/chat``. After the first frame, failures are
    ``run.failed``. A client disconnect cancels the run and closes the
    provider stream. It is not an HTTP 500.
    """

    engine_request = await _accepted_request(body, request)
    token = CancellationToken()
    run_id = uuid4()
    frames = _sse_frames(request, engine_request, token, run_id)
    return StreamingResponse(frames, media_type="text/event-stream", headers=_SSE_HEADERS)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(EngineError)
    async def engine_error(_request: Request, exc: EngineError) -> JSONResponse:
        logger.info("engine error kind=%s stage=%s", exc.kind.value, exc.stage.value)
        return JSONResponse(status_code=_STATUS[exc.kind], content=exc.to_public_dict())

    @app.exception_handler(AuthenticationFailed)
    async def authentication_failed(
        _request: Request,
        _exc: AuthenticationFailed,
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"message": "Authentication is required."})

    @app.exception_handler(AuthorizationRefused)
    async def authorization_refused(
        _request: Request,
        _exc: AuthorizationRefused,
    ) -> JSONResponse:
        message = "The organization boundary refused the request."
        return JSONResponse(status_code=403, content={"message": message})

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API failure", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"message": _GENERIC_FAILURE},
        )


async def _accepted_request(body: ChatRequest, request: Request) -> EngineRequest:
    credentials = _credentials(request.headers.get("authorization"))
    principal = await request.app.state.authenticator.authenticate(credentials)
    decision = await request.app.state.authorizer.authorize(
        principal,
        action="chat",
        organization_id=principal.organization_id,
    )
    if not decision.allowed:
        raise AuthorizationRefused
    header_request_id = getattr(request.state, "request_id", "")
    return EngineRequest(
        request_id=_engine_request_id(str(header_request_id)),
        principal=principal,
        conversation_id=body.conversation_id,
        project_id=body.project_id,
        message=body.message,
        attachment_ids=list(body.attachment_ids),
    )


async def _sse_frames(
    request: Request,
    engine_request: EngineRequest,
    token: CancellationToken,
    run_id: UUID,
) -> AsyncIterator[str]:
    watch: asyncio.Task[bool] | None = None
    pull: asyncio.Task[tuple[str, RunEvent | None]] | None = None
    stream: AsyncIterator[RunEvent] | None = None
    try:
        if await request.is_disconnected():
            token.cancel()
            return
        stream = request.app.state.engine.handle_stream(
            engine_request,
            cancellation=token,
            run_id=run_id,
        )
        watch = asyncio.create_task(_watch_disconnect(request))
        while True:
            pull = asyncio.create_task(_pull_event(stream))
            done, _pending = await asyncio.wait(
                {pull, watch},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if watch in done:
                error = _done_error(watch)
                token.cancel()
                await _stop(pull)
                pull = None
                if error is not None:
                    raise error
                break
            kind, event = await pull
            pull = None
            if kind == "done" or event is None:
                break
            yield encode_run_event(event)
    except asyncio.CancelledError:
        token.cancel()
        raise
    except ClientDisconnect:
        token.cancel()
        return
    except Exception as exc:
        logger.error("stream failed type=%s", type(exc).__name__)
        yield encode_run_event(_generic_failure(engine_request, run_id))
    finally:
        if watch is not None:
            watch.cancel()
            await _stop(watch)
        if pull is not None:
            await _stop(pull)
        if stream is not None:
            closer = getattr(stream, "aclose", None)
            if closer is not None:
                await closer()


async def _pull_event(stream: AsyncIterator[RunEvent]) -> tuple[str, RunEvent | None]:
    try:
        return ("event", await anext(stream))
    except StopAsyncIteration:
        return ("done", None)


async def _watch_disconnect(request: Request) -> bool:
    try:
        while True:
            message = await request.receive()
            if message["type"] == "http.disconnect":
                return True
    except ClientDisconnect:
        return True


def _done_error(task: asyncio.Task[object]) -> BaseException | None:
    if task.cancelled():
        return None
    error = task.exception()
    if isinstance(error, asyncio.CancelledError | ClientDisconnect):
        return None
    return error


async def _stop(task: asyncio.Task[object]) -> None:
    if not task.done():
        task.cancel()
    with contextlib.suppress(Exception, asyncio.CancelledError):
        await task


def _generic_failure(engine_request: EngineRequest, run_id: UUID) -> RunEvent:
    return RunEvent(
        type=RunEventType.FAILED,
        request_id=engine_request.request_id,
        run_id=run_id,
        organization_id=engine_request.principal.organization_id,
        error={"message": _GENERIC_FAILURE},
    )


def _credentials(header: str | None) -> RequestCredentials:
    if header is None or not header.startswith("Bearer "):
        raise AuthenticationFailed
    token = header.removeprefix("Bearer ").strip()
    try:
        return RequestCredentials(scheme="bearer", token=token)
    except ValidationError as exc:
        raise AuthenticationFailed from exc


def _engine_request_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        return uuid4()
