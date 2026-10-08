"""PostgreSQL conversations and messages.

Tenant queries run as ``kai_app`` inside a transaction. ``SET LOCAL`` applies
the authenticated principal, and row level security hides every other
organization. The client does not choose the organization id.

The connection user may be the database owner so it can assume ``kai_app``.
Superusers bypass row level security, so the role change is required.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import psycopg
from psycopg import AsyncConnection

from kai_engine.contracts import Principal

logger = logging.getLogger("kai_api.persistence")

NEW_CONVERSATION_TITLE = "New chat"
TITLE_LIMIT = 48


class ConversationNotFound(Exception):
    """The conversation is missing or belongs to another organization."""


class PersistenceUnavailable(Exception):
    """PostgreSQL cannot be used for this request."""


@dataclass(frozen=True)
class StoredConversation:
    id: UUID
    title: str
    updated_at: datetime


@dataclass(frozen=True)
class StoredMessage:
    id: UUID
    role: str
    content: str


@dataclass(frozen=True)
class StoredTranscript:
    id: UUID
    title: str
    updated_at: datetime
    messages: tuple[StoredMessage, ...]


class ConversationStore:
    def __init__(self, database_url: str) -> None:
        self._url = database_url

    async def create(self, principal: Principal) -> StoredConversation:
        await self._ensure_membership(principal)
        async with self._tenant(principal) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO conversations (organization_id, title, created_by)
                VALUES (%s, %s, %s)
                RETURNING id, title, updated_at
                """,
                (principal.organization_id, NEW_CONVERSATION_TITLE, principal.user_id),
            )
            row = await cursor.fetchone()
            if row is None:
                raise PersistenceUnavailable
            return _conversation(row)

    async def list(self, principal: Principal) -> tuple[StoredConversation, ...]:
        await self._ensure_membership(principal)
        async with self._tenant(principal) as conn:
            cursor = await conn.execute(
                """
                SELECT id, title, updated_at
                FROM conversations
                WHERE organization_id = %s
                ORDER BY updated_at DESC, id DESC
                """,
                (principal.organization_id,),
            )
            rows = await cursor.fetchall()
            return tuple(_conversation(row) for row in rows)

    async def get(self, principal: Principal, conversation_id: UUID) -> StoredTranscript | None:
        await self._ensure_membership(principal)
        async with self._tenant(principal) as conn:
            cursor = await conn.execute(
                """
                SELECT id, title, updated_at
                FROM conversations
                WHERE id = %s AND organization_id = %s
                """,
                (conversation_id, principal.organization_id),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            conversation = _conversation(row)
            messages = await conn.execute(
                """
                SELECT id, role, content
                FROM messages
                WHERE conversation_id = %s AND organization_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (conversation_id, principal.organization_id),
            )
            stored = tuple(_message(item) for item in await messages.fetchall())
            return StoredTranscript(
                id=conversation.id,
                title=conversation.title,
                updated_at=conversation.updated_at,
                messages=stored,
            )

    async def append_user(
        self,
        principal: Principal,
        conversation_id: UUID,
        content: str,
    ) -> bool:
        title = content[:TITLE_LIMIT]
        return await self._append(
            principal,
            conversation_id,
            "user",
            content,
            title=title,
        )

    async def append_assistant(
        self,
        principal: Principal,
        conversation_id: UUID,
        content: str,
    ) -> bool:
        return await self._append(principal, conversation_id, "assistant", content, title=None)

    async def _append(
        self,
        principal: Principal,
        conversation_id: UUID,
        role: str,
        content: str,
        *,
        title: str | None,
    ) -> bool:
        await self._ensure_membership(principal)
        async with self._tenant(principal) as conn:
            if title is None:
                cursor = await conn.execute(
                    """
                    UPDATE conversations
                    SET title = title
                    WHERE id = %s AND organization_id = %s
                    RETURNING id
                    """,
                    (conversation_id, principal.organization_id),
                )
            else:
                cursor = await conn.execute(
                    """
                    UPDATE conversations
                    SET title = CASE WHEN title = %s THEN %s ELSE title END
                    WHERE id = %s AND organization_id = %s
                    RETURNING id
                    """,
                    (NEW_CONVERSATION_TITLE, title, conversation_id, principal.organization_id),
                )
            if await cursor.fetchone() is None:
                return False
            await conn.execute(
                """
                INSERT INTO messages (organization_id, conversation_id, role, content)
                VALUES (%s, %s, %s, %s)
                """,
                (principal.organization_id, conversation_id, role, content),
            )
            return True

    async def _ensure_membership(self, principal: Principal) -> None:
        email = f"local-{principal.user_id}@kai.local"
        slug = f"org-{principal.organization_id}"
        try:
            async with await AsyncConnection.connect(self._url) as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO organizations (id, name, slug)
                        VALUES (%s, 'Local development', %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (principal.organization_id, slug),
                    )
                    await conn.execute(
                        """
                        INSERT INTO users (id, email, display_name)
                        VALUES (%s, %s, 'Local development')
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (principal.user_id, email),
                    )
                    await conn.execute(
                        """
                        INSERT INTO memberships (organization_id, user_id, role)
                        VALUES (%s, %s, 'owner')
                        ON CONFLICT (organization_id, user_id) DO NOTHING
                        """,
                        (principal.organization_id, principal.user_id),
                    )
        except psycopg.Error as exc:
            raise _unavailable(exc) from None

    @asynccontextmanager
    async def _tenant(self, principal: Principal) -> AsyncIterator[AsyncConnection]:
        try:
            conn = await AsyncConnection.connect(self._url)
        except psycopg.Error as exc:
            raise _unavailable(exc) from None
        try:
            async with conn.transaction():
                try:
                    await conn.execute("SET LOCAL ROLE kai_app")
                    await conn.execute(
                        "SELECT set_config('kai.organization_id', %s, true)",
                        (str(principal.organization_id),),
                    )
                    await conn.execute(
                        "SELECT set_config('kai.user_id', %s, true)",
                        (str(principal.user_id),),
                    )
                except psycopg.Error as exc:
                    raise _unavailable(exc) from None
                try:
                    yield conn
                except psycopg.Error as exc:
                    raise _unavailable(exc) from None
        finally:
            await conn.close()


def open_store(database_url: str) -> ConversationStore | None:
    url = database_url.strip()
    if url == "":
        return None
    return ConversationStore(url)


def _unavailable(exc: psycopg.Error) -> PersistenceUnavailable:
    logger.error("postgres unavailable type=%s", type(exc).__name__)
    return PersistenceUnavailable()


def _conversation(row: tuple[object, ...]) -> StoredConversation:
    if len(row) != 3:
        raise PersistenceUnavailable
    updated_at = row[2]
    if not isinstance(updated_at, datetime):
        raise PersistenceUnavailable
    title = row[1] if isinstance(row[1], str) and row[1] != "" else NEW_CONVERSATION_TITLE
    return StoredConversation(id=_uuid(row[0]), title=title, updated_at=updated_at)


def _message(row: tuple[object, ...]) -> StoredMessage:
    if len(row) != 3:
        raise PersistenceUnavailable
    content = row[2]
    if not isinstance(content, str):
        raise PersistenceUnavailable
    return StoredMessage(id=_uuid(row[0]), role=_text(row[1]), content=content)


def _uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        return UUID(value)
    raise PersistenceUnavailable


def _text(value: object) -> str:
    if isinstance(value, str) and value != "":
        return value
    raise PersistenceUnavailable
