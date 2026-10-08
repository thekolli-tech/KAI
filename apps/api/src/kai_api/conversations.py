"""Conversation routes. Ownership comes from the authenticated principal."""

import json
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from kai_api.chat import principal_from_request
from kai_api.persistence import (
    ConversationStore,
    PersistenceUnavailable,
    StoredConversation,
    StoredTranscript,
)

_INVALID = "The request is invalid."
_MISSING = "That conversation is not available."
_UNAVAILABLE = "A required dependency is unavailable."


def install_conversations(router: APIRouter) -> None:
    router.add_api_route("/conversations", list_conversations, methods=["GET"])
    router.add_api_route("/conversations", create_conversation, methods=["POST"])
    router.add_api_route("/conversations/{conversation_id}", get_conversation, methods=["GET"])


async def list_conversations(request: Request) -> JSONResponse:
    principal = await principal_from_request(request, action="conversation")
    store = _store(request)
    conversations = await store.list(principal)
    return JSONResponse(
        {"conversations": [_summary(item) for item in conversations]},
        headers={"Cache-Control": "no-store"},
    )


async def create_conversation(request: Request) -> JSONResponse:
    principal = await principal_from_request(request, action="conversation")
    if not await _empty_body(request):
        return JSONResponse(status_code=422, content={"message": _INVALID})
    store = _store(request)
    conversation = await store.create(principal)
    return JSONResponse(
        _summary(conversation),
        status_code=201,
        headers={"Cache-Control": "no-store"},
    )


async def get_conversation(conversation_id: UUID, request: Request) -> JSONResponse:
    principal = await principal_from_request(request, action="conversation")
    store = _store(request)
    transcript = await store.get(principal, conversation_id)
    if transcript is None:
        return JSONResponse(status_code=404, content={"message": _MISSING})
    return JSONResponse(_detail(transcript), headers={"Cache-Control": "no-store"})


def _store(request: Request) -> ConversationStore:
    store = getattr(request.app.state, "conversations", None)
    if not isinstance(store, ConversationStore):
        raise PersistenceUnavailable
    return store


async def _empty_body(request: Request) -> bool:
    raw = await request.body()
    if raw.strip() == b"":
        return True
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and len(payload) == 0


def _summary(conversation: StoredConversation) -> dict[str, str]:
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "updatedAt": conversation.updated_at.isoformat(),
    }


def _detail(transcript: StoredTranscript) -> dict[str, object]:
    return {
        **_summary(
            StoredConversation(
                id=transcript.id,
                title=transcript.title,
                updated_at=transcript.updated_at,
            )
        ),
        "messages": [
            {
                "id": str(message.id),
                "role": message.role,
                "content": message.content,
                "status": "completed",
                "providerLabel": None,
                "error": None,
            }
            for message in transcript.messages
        ],
    }
