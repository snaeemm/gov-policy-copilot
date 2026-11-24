"""Human-in-the-loop review queue (SQLite).

SQLite keeps this $0 and dependency-free. In production this would move to Cosmos DB
(free tier) or Azure SQL - the ReviewQueue interface stays the same (see ADR).
"""

import asyncio
import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewItem(BaseModel):
    id: str
    created_at: str
    request_id: str
    question_masked: str
    draft_answer: str
    reason: str
    groundedness: float | None
    citations: list[dict[str, object]]
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer: str | None = None
    final_answer: str | None = None
    decided_at: str | None = None


class ReviewQueue:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = asyncio.Lock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
        )
        self._conn.commit()

    async def _run[T](self, fn: Callable[[], T]) -> T:
        async with self._lock:
            return await asyncio.to_thread(fn)

    async def add(
        self,
        *,
        request_id: str,
        question_masked: str,
        draft_answer: str,
        reason: str,
        groundedness: float | None,
        citations: list[dict[str, object]],
    ) -> ReviewItem:
        item = ReviewItem(
            id=uuid.uuid4().hex[:12],
            created_at=datetime.now(UTC).isoformat(),
            request_id=request_id,
            question_masked=question_masked,
            draft_answer=draft_answer,
            reason=reason,
            groundedness=groundedness,
            citations=citations,
        )

        def write() -> None:
            self._conn.execute(
                "INSERT INTO reviews VALUES (?, ?)", (item.id, item.model_dump_json())
            )
            self._conn.commit()

        await self._run(write)
        return item

    async def list(self, status: ReviewStatus | None = None) -> list[ReviewItem]:
        rows = await self._run(lambda: self._conn.execute("SELECT body FROM reviews").fetchall())
        items = [ReviewItem(**json.loads(r[0])) for r in rows]
        if status:
            items = [i for i in items if i.status is status]
        return sorted(items, key=lambda i: i.created_at, reverse=True)

    async def get(self, review_id: str) -> ReviewItem | None:
        row = await self._run(
            lambda: self._conn.execute(
                "SELECT body FROM reviews WHERE id = ?", (review_id,)
            ).fetchone()
        )
        return ReviewItem(**json.loads(row[0])) if row else None

    async def decide(
        self, review_id: str, *, approve: bool, reviewer: str, final_answer: str | None = None
    ) -> ReviewItem | None:
        item = await self.get(review_id)
        if item is None:
            return None
        item.status = ReviewStatus.APPROVED if approve else ReviewStatus.REJECTED
        item.reviewer = reviewer
        item.final_answer = final_answer or (item.draft_answer if approve else None)
        item.decided_at = datetime.now(UTC).isoformat()

        def write() -> None:
            self._conn.execute(
                "UPDATE reviews SET body = ? WHERE id = ?", (item.model_dump_json(), item.id)
            )
            self._conn.commit()

        await self._run(write)
        return item
