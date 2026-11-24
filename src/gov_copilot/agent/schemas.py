"""Agent I/O contracts."""

from enum import StrEnum

from pydantic import BaseModel, Field

from gov_copilot.models import Language

NOT_FOUND = {
    "en": "I couldn't find this in the available UAE policy documents, so I can't answer reliably.",
    "ar": "لم أجد هذه المعلومة في وثائق السياسات الإماراتية المتاحة، لذا لا يمكنني الإجابة بشكل موثوق.",
}
OUT_OF_SCOPE = {
    "en": "I can only answer questions about the public UAE government policy documents I have "
    "(AI Charter, AI policy, AI ethics, personal data protection).",
    "ar": "يمكنني فقط الإجابة عن الأسئلة المتعلقة بوثائق السياسات الحكومية الإماراتية العامة المتاحة لدي.",
}
ESCALATED = {
    "en": "I'm not confident this answer is fully supported by the sources, so it has been sent to a "
    "human reviewer.",
    "ar": "لست واثقاً من أن هذه الإجابة مدعومة بالكامل بالمصادر، لذا تمت إحالتها إلى مراجع بشري.",
}


class Outcome(StrEnum):
    ANSWERED = "answered"
    NOT_FOUND = "not_found"
    OUT_OF_SCOPE = "out_of_scope"
    ESCALATED = "escalated"
    BLOCKED = "blocked"


class Plan(BaseModel):
    language: Language = "en"
    in_scope: bool = True
    search_queries: list[str] = Field(default_factory=list, max_length=3)


class Verification(BaseModel):
    groundedness: float = Field(default=0.0, ge=0, le=1)
    citations_valid: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    n: int
    doc_id: str
    title: str
    page: int
    section: str
    source_url: str
    snippet: str


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    embedding_tokens: int = 0
    cost_usd: float = 0.0


class AgentResult(BaseModel):
    request_id: str
    question: str
    answer: str
    language: Language
    outcome: Outcome
    citations: list[Citation] = Field(default_factory=list)
    verification: Verification | None = None
    review_id: str | None = None
    prompt_version: str
    model: str
    latency_ms: int = 0
    usage: Usage = Field(default_factory=Usage)
