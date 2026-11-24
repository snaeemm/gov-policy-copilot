# Changelog
All notable changes to this project are documented here (Keep a Changelog, SemVer).

## [Unreleased]
### Added
- M1: project skeleton, typed provider-swappable settings, `/healthz`, CI (ruff, mypy, pytest).
- M2: Doc Intelligence layout ingestion (F0-aware slicing + rasterization), Arabic-aware chunker, bilingual AI Search index (ar.microsoft + en.microsoft + HNSW vector), hybrid RRF retrieval, pluggable reranker (none | cross-encoder | Azure semantic).
- M3: Semantic Kernel agent (plan -> search_policies -> answer -> verify_citation -> respond or escalate_to_human), versioned prompts, cost/token accounting, OpenTelemetry spans; FastAPI with SSE streaming, Entra ID JWT + RBAC (Viewer/Reviewer/Admin), per-user rate limiting, SQLite review queue; bilingual RTL chat UI with citations and reviewer console.
