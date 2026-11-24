"""Azure AI Search index definition.

Bilingual design: one index, separate text fields per language so each gets the right
linguistic analyzer (ar.microsoft does Arabic stemming/lemmatization, en.microsoft for English).
A single vector field (text-embedding-3-small, multilingual) enables cross-lingual retrieval:
an Arabic question can match an English passage and vice versa.
"""

from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from gov_copilot.ingestion.text import normalize_arabic
from gov_copilot.models import Chunk

VECTOR_PROFILE = "hnsw-cosine"
SEMANTIC_CONFIG = "default"


def build_index(name: str, dimensions: int) -> SearchIndex:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(
            name="doc_id", type=SearchFieldDataType.String, filterable=True, facetable=True
        ),
        SearchableField(
            name="title", type=SearchFieldDataType.String, analyzer_name="standard.lucene"
        ),
        SimpleField(
            name="language", type=SearchFieldDataType.String, filterable=True, facetable=True
        ),
        SearchableField(name="section", type=SearchFieldDataType.String),
        SimpleField(name="page", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
        SimpleField(name="source_url", type=SearchFieldDataType.String),
        # Original text for display/citation (not searched).
        SimpleField(name="content", type=SearchFieldDataType.String),
        SearchableField(
            name="content_en", type=SearchFieldDataType.String, analyzer_name="en.microsoft"
        ),
        SearchableField(
            name="content_ar", type=SearchFieldDataType.String, analyzer_name="ar.microsoft"
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=dimensions,
            vector_search_profile_name=VECTOR_PROFILE,
        ),
    ]
    return SearchIndex(
        name=name,
        fields=fields,
        vector_search=VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="hnsw",
                    parameters=HnswParameters(m=4, ef_construction=400, metric="cosine"),
                )
            ],
            profiles=[
                VectorSearchProfile(name=VECTOR_PROFILE, algorithm_configuration_name="hnsw")
            ],
        ),
        # Defined but only used when RERANKER=azure_semantic (not available on Free tier).
        semantic_search=SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name=SEMANTIC_CONFIG,
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="title"),
                        content_fields=[
                            SemanticField(field_name="content_en"),
                            SemanticField(field_name="content_ar"),
                        ],
                    ),
                )
            ]
        ),
    )


def to_search_doc(chunk: Chunk, vector: list[float]) -> dict[str, object]:
    searchable = chunk.content if chunk.language == "en" else normalize_arabic(chunk.content)
    return {
        **chunk.model_dump(),
        "content_en": searchable if chunk.language == "en" else "",
        "content_ar": searchable if chunk.language == "ar" else "",
        "content_vector": vector,
    }
