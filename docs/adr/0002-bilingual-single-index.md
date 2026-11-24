# ADR-0002: One bilingual index with per-language analyzers and multilingual vectors

Status: Accepted

**Context.** Documents exist in Arabic and English. Arabic needs morphological analysis (prefixes such as ال، و، ب; broken plurals), and normalization of orthographic variants (أ/إ/آ → ا, ى → ي, tatweel, diacritics).

**Decision.** Single index; each chunk writes its text into `content_en` (`en.microsoft` analyzer) **or** `content_ar` (`ar.microsoft` analyzer); original text kept in non-searchable `content` for display/citation. App-side `normalize_arabic` is applied to both indexed Arabic text and queries. One `text-embedding-3-small` vector field gives cross-lingual retrieval. The planner emits ≥1 English and ≥1 Arabic query. Code: `retrieval/index.py`, `ingestion/text.py`.

**Consequences.** + Arabic question can retrieve English passages and vice versa. + One index fits the Free tier (3 indexes max). − Normalization is lossy for display, hence the separate `content` field.

**Alternatives.** Index per language (doubles cost/ops, no cross-lingual fusion); machine-translate everything to English (translation errors on legal text, extra cost).
