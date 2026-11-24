"""Shared domain models."""

from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["en", "ar"]
Classification = Literal["public", "internal", "confidential"]


class SourceDocument(BaseModel):
    doc_id: str
    file: str
    language: Language
    title: str
    publisher: str
    year: int
    source_url: str
    classification: Classification = "public"


class Chunk(BaseModel):
    id: str
    doc_id: str
    title: str
    language: Language
    section: str = ""
    page: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    content: str
    source_url: str
    classification: Classification = "public"


class RetrievedChunk(Chunk):
    score: float = 0.0
    rerank_score: float | None = None
