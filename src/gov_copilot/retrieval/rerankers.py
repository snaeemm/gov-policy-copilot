"""Pluggable re-rankers.

- NoopReranker: keep hybrid (RRF) order.
- CrossEncoderReranker: open-source multilingual cross-encoder (runs locally / in container, $0).
- Azure semantic ranker is applied inside the search query itself (see retriever), so its
  "reranker" here is a pass-through that orders by Azure's reranker score.
"""

import asyncio
from typing import Any, Protocol

from gov_copilot.config import RerankerKind, Settings
from gov_copilot.models import RetrievedChunk


class Reranker(Protocol):
    async def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_n: int
    ) -> list[RetrievedChunk]: ...


class NoopReranker:
    async def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_n: int
    ) -> list[RetrievedChunk]:
        return chunks[:top_n]


class ScoreReranker:
    """Orders by a score already attached (used for Azure semantic ranker)."""

    async def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_n: int
    ) -> list[RetrievedChunk]:
        return sorted(chunks, key=lambda c: c.rerank_score or 0.0, reverse=True)[:top_n]


class CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import CrossEncoder  # optional dependency

            self._model = CrossEncoder(self._model_name, max_length=512)
        return self._model

    async def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_n: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        model = self._load()
        pairs = [(query, c.content) for c in chunks]
        scores = await asyncio.to_thread(model.predict, pairs)
        for c, s in zip(chunks, scores, strict=True):
            c.rerank_score = float(s)
        return sorted(chunks, key=lambda c: c.rerank_score or 0.0, reverse=True)[:top_n]


def make_reranker(s: Settings) -> Reranker:
    if s.reranker is RerankerKind.CROSS_ENCODER:
        return CrossEncoderReranker(s.reranker_model)
    if s.reranker is RerankerKind.AZURE_SEMANTIC:
        return ScoreReranker()
    return NoopReranker()
