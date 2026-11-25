"""
Evidence State Store - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.7: Evidence Acquisition & Evidence Cards.

Maintains isolated runtime state for:
- Persisted Evidence Cards snapshots (card_id, version, story_id, card_hash)
- Story-to-card mappings and latest versions
- Audit history of evidence state transitions

Strict Invariants:
- Dedicated namespace (default: data/evidence_state.json)
- Does NOT mutate source_acquisition_matrix.json
- Does NOT mutate pilot_collector_state.json
- Does NOT mutate production_batch_collector_state.json
- Does NOT mutate story_identity_state.json
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Optional

DEFAULT_EVIDENCE_STATE_FILE = "data/evidence_state.json"


@dataclass
class EvidenceCardStateEntry:
    card_id: str
    version: int
    story_id: str
    card_hash: str
    claims_count: int
    evidence_count: int
    has_conflicts: bool
    created_at: str
    snapshot_json: Optional[str] = None


@dataclass
class StoryEvidenceIndexEntry:
    story_id: str
    card_ids: list[str] = field(default_factory=list)
    latest_card_id: Optional[str] = None
    latest_version: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvidenceStateStore:
    """
    Isolated state store tracking Evidence Cards and story-to-card versions across runs.
    """

    def __init__(self, state_file: str | Path = DEFAULT_EVIDENCE_STATE_FILE):
        self.state_file = Path(state_file)
        self.version = "1.0.0"
        self.cards: dict[str, EvidenceCardStateEntry] = {}
        self.story_index: dict[str, StoryEvidenceIndexEntry] = {}

    def get_card(self, card_id: str) -> Optional[EvidenceCardStateEntry]:
        return self.cards.get(card_id)

    def get_cards_for_story(self, story_id: str) -> list[EvidenceCardStateEntry]:
        story_entry = self.story_index.get(story_id)
        if not story_entry:
            return []
        return [self.cards[cid] for cid in story_entry.card_ids if cid in self.cards]

    def register_card(
        self,
        card_id: str,
        version: int,
        story_id: str,
        card_hash: str,
        claims_count: int,
        evidence_count: int,
        has_conflicts: bool,
        snapshot_json: Optional[str] = None,
    ) -> EvidenceCardStateEntry:
        """
        Records or updates an evidence card snapshot entry in state.
        """
        now = datetime.now(timezone.utc).isoformat()
        entry = EvidenceCardStateEntry(
            card_id=card_id,
            version=version,
            story_id=story_id,
            card_hash=card_hash,
            claims_count=claims_count,
            evidence_count=evidence_count,
            has_conflicts=has_conflicts,
            created_at=now,
            snapshot_json=snapshot_json,
        )
        self.cards[card_id] = entry

        # Update story index
        story_entry = self.story_index.get(story_id)
        if story_entry is None:
            story_entry = StoryEvidenceIndexEntry(
                story_id=story_id,
                card_ids=[card_id],
                latest_card_id=card_id,
                latest_version=version,
                updated_at=now,
            )
            self.story_index[story_id] = story_entry
        else:
            if card_id not in story_entry.card_ids:
                story_entry.card_ids.append(card_id)
            if version >= story_entry.latest_version:
                story_entry.latest_version = version
                story_entry.latest_card_id = card_id
            story_entry.updated_at = now

        return entry

    def load(self) -> None:
        """Loads state from disk if file exists."""
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.version = data.get("version", "1.0.0")
            self.cards = {
                k: EvidenceCardStateEntry(**v)
                for k, v in data.get("cards", {}).items()
            }
            self.story_index = {
                k: StoryEvidenceIndexEntry(**v)
                for k, v in data.get("story_index", {}).items()
            }
        except Exception:
            # Revert to clean state on corruption
            self.cards = {}
            self.story_index = {}

    def save(self) -> None:
        """Persists state to disk atomically using temporary file and atomic replace."""
        target = self.state_file
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": self.version,
            "cards": {k: asdict(v) for k, v in self.cards.items()},
            "story_index": {k: asdict(v) for k, v in self.story_index.items()},
        }
        with tempfile.NamedTemporaryFile("w", dir=target.parent, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2, ensure_ascii=False)
            tf.flush()
            os.fsync(tf.fileno())
            temp_path = tf.name
        os.replace(temp_path, target)
