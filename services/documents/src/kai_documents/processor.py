"""Document pipeline boundary.

Upload, extraction, chunking, embeddings, and retrieval are separate ports.
No parser is implemented in Phase 1. The simplest later path is plain text.
"""

from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentKind(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    TXT = "txt"
    IMAGE = "image"
    SOURCE_CODE = "source_code"


PLANNED_DOCUMENT_KINDS: tuple[DocumentKind, ...] = tuple(DocumentKind)


class DocumentRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    kind: DocumentKind
    object_key: str = Field(min_length=1)
    media_type: str = Field(min_length=1)


class ExtractedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: UUID
    organization_id: UUID
    text: str


class DocumentChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: UUID
    organization_id: UUID
    index: int = Field(ge=0)
    text: str


class EmbeddedChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk: DocumentChunk
    vector: list[float]


class RetrievalHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: UUID
    organization_id: UUID
    text: str
    score: float


class DocumentProcessor(Protocol):
    def supports(self, kind: DocumentKind) -> bool:
        """Say whether this processor can read the kind."""

    async def extract(self, document: DocumentRef) -> ExtractedDocument:
        """Extract text. Image understanding is a later provider concern."""


class Chunker(Protocol):
    def chunk(self, document: ExtractedDocument) -> list[DocumentChunk]:
        """Split extracted text. Chunks keep the organization id."""


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts with the configured local model."""


class VectorStore(Protocol):
    async def upsert(self, chunks: list[EmbeddedChunk]) -> None:
        """Store vectors scoped by organization."""

    async def query(
        self,
        vector: list[float],
        *,
        organization_id: UUID,
        limit: int,
    ) -> list[RetrievalHit]:
        """Retrieve chunks from one organization."""
