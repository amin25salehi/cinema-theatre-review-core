"""
Evidence Builder - Cinema & Theatre Review Editorial OS v1.0
Constructs auditable evidence snapshot records with deterministic content hashing.
"""

import hashlib
from datetime import datetime, timezone

from schemas.evidence_card import EvidenceItem, EvidenceRelation


class EvidenceBuilder:
    @staticmethod
    def compute_content_hash(text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    @classmethod
    def create_evidence(
        cls,
        evidence_id: str,
        source_id: str,
        source_url: str,
        evidence_type: str,
        relation: EvidenceRelation,
        claim_refs: list[str],
        excerpt: str,
        locator: str | None = None,
        published_at: str | None = None,
        retrieved_at: str | None = None,
    ) -> EvidenceItem:
        if not retrieved_at:
            retrieved_at = datetime.now(timezone.utc).isoformat()

        content_hash = cls.compute_content_hash(excerpt)

        return EvidenceItem(
            evidence_id=evidence_id,
            source_id=source_id,
            source_url=source_url,
            evidence_type=evidence_type,
            relation=relation,
            claim_refs=claim_refs,
            excerpt=excerpt,
            locator=locator,
            published_at=published_at,
            retrieved_at=retrieved_at,
            content_hash=content_hash,
        )
