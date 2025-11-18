"""
Review Queue
============

Stores low-confidence or schema-incomplete extractions for manual review (Fase 4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _default_storage_path() -> Path:
    """Return the canonical path for the JSON queue (`data/review_queue.json`)."""
    base_dir = Path(__file__).resolve().parents[2] / "data"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "review_queue.json"


@dataclass
class ReviewItem:
    """Representation of an entity or relationship awaiting expert validation."""

    item_id: str
    item_type: str  # "entity" | "relationship"
    payload: Dict[str, Any]
    reason: str
    source_segment: str
    llm_model: Optional[str]
    created_at: str

    @staticmethod
    def new(
        item_type: str,
        payload: Dict[str, Any],
        reason: str,
        source_segment: str,
        llm_model: Optional[str],
    ) -> "ReviewItem":
        return ReviewItem(
            item_id=str(uuid4()),
            item_type=item_type,
            payload=payload,
            reason=reason,
            source_segment=source_segment,
            llm_model=llm_model,
            created_at=datetime.utcnow().isoformat(),
        )


class ReviewQueue:
    """Simple persistence layer (JSON file) for review items."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or _default_storage_path()
        self._items: List[ReviewItem] = []

        if self.storage_path.exists():
            self._load()

    def enqueue(self, item: ReviewItem) -> None:
        self._items.append(item)
        self._persist()

    def snapshot(self) -> List[ReviewItem]:
        return list(self._items)

    def pending_count(self) -> int:
        return len(self._items)

    def _persist(self) -> None:
        serialized = [asdict(item) for item in self._items]
        self.storage_path.write_text(json.dumps(serialized, ensure_ascii=False, indent=2))

    def _load(self) -> None:
        try:
            raw_items = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            raw_items = []
        for raw in raw_items:
            self._items.append(
                ReviewItem(
                    item_id=raw.get("item_id", str(uuid4())),
                    item_type=raw.get("item_type", "entity"),
                    payload=raw.get("payload", {}),
                    reason=raw.get("reason", ""),
                    source_segment=raw.get("source_segment", ""),
                    llm_model=raw.get("llm_model"),
                    created_at=raw.get("created_at", datetime.utcnow().isoformat()),
                )
            )

