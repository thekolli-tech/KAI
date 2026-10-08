"""POST /api/v1/chat. The route calls the composed engine and returns its response."""

import logging
from typing import cast
from uuid import UUID, uuid4

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kai_api.access import AuthenticationFailed
from kai_api.security.contracts import RequestCredentials
from kai_engine.contracts import EngineRequest, EngineResponse
from kai_engine.errors import EngineError, EngineErrorKind

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


async def post_chat(body: ChatRequest, request: Request) -> EngineResponse:
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
    engine_request = EngineRequest(
        request_id=_engine_request_id(str(header_request_id)),
        principal=principal,
        conversation_id=body.conversation_id,
        project_id=body.project_id,
        message=body.message,
        attachment_ids=list(body.attachment_ids),
    )
    response = await request.app.state.engine.handle(engine_request)
    return cast(EngineResponse, response)


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
            content={"message": "The request could not be completed."},
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
