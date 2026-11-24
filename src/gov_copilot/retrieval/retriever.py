"""Hybrid retrieval: BM25 (per-language analyzers) + vector, fused by Azure AI Search with RRF."""

from typing import Any

from azure.identity.aio import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery

from gov_copilot.config import RerankerKind, Settings, get_settings
from gov_copilot.ingestion.text import normalize_arabic
from gov_copilot.llm.clients import embed
from gov_copilot.models import RetrievedChunk
from gov_copilot.retrieval.index import SEMANTIC_CONFIG
from gov_copilot.retrieval.rerankers import Reranker, make_reranker

SELECT = [
    "id",
    "doc_id",
    "title",
    "language",
    "section",
    "page",
    "chunk_index",
    "content",
    "source_url",
]


def search_client(s: Settings) -> SearchClient:
    cred: Any
    if s.azure_search_api_key:
        from azure.core.credentials import AzureKeyCredential

        cred = AzureKeyCredential(s.azure_search_api_key.get_secret_value())
    else:
        cred = DefaultAzureCredential()
    return SearchClient(s.azure_search_endpoint, s.azure_search_index, cred)


class HybridRetriever:
    def __init__(self, settings: Settings | None = None, reranker: Reranker | None = None) -> None:
        self.s = settings or get_settings()
        self.reranker = reranker or make_reranker(self.s)

    async def retrieve(
        self, query: str, top_n: int | None = None, language: str | None = None
    ) -> list[RetrievedChunk]:
        s = self.s
        [vector] = await embed([query])
        # Normalize Arabic the same way the index did, then search both language fields.
        text = normalize_arabic(query)
        kwargs: dict[str, Any] = {
            "search_text": text,
            "search_fields": ["content_en", "content_ar", "title"],
            "vector_queries": [
                VectorizedQuery(
                    vector=vector, k_nearest_neighbors=s.retrieval_top_k, fields="content_vector"
                )
            ],
            "select": SELECT,
            "top": s.retrieval_top_k,
        }
        if language:
            kwargs["filter"] = f"language eq '{language}'"
        if s.reranker is RerankerKind.AZURE_SEMANTIC:
            kwargs |= {"query_type": "semantic", "semantic_configuration_name": SEMANTIC_CONFIG}
        results: list[RetrievedChunk] = []
        async with search_client(s) as client:
            async for r in await client.search(**kwargs):
                results.append(
                    RetrievedChunk(
                        **{k: r[k] for k in SELECT},
                        score=float(r["@search.score"]),
                        rerank_score=r.get("@search.reranker_score"),
                    )
                )
        return await self.reranker.rerank(query, results, top_n or s.rerank_top_n)
