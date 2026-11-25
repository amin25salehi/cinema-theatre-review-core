"""
Evidence Card Builder - Cinema & Theatre Review Editorial OS v1.0
Assembles auditable Evidence Cards from claims, evidence items, and authority resolutions.
"""

import hashlib
from datetime import datetime, timezone

from evidence.authority_evaluator import AuthorityEvaluator
from schemas.authority_map import AuthorityMap
from schemas.evidence_card import (
    AuthorityResolutionItem,
    AuthorityStatus,
    Claim,
    ClaimStatus,
    ConflictItem,
    ConflictStatus,
    EntityReference,
    EvidenceCard,
    EvidenceCardIdentity,
    EvidenceIntegrityMetadata,
    EvidenceItem,
    EvidenceRelation,
    ImageEvidenceItem,
    StoryContext,
)
from schemas.source_registry import SourceProfile
from utils.canonical_hash import compute_canonical_hash


class EvidenceCardBuilder:
    def __init__(
        self,
        authority_map: AuthorityMap,
        sources: dict[str, SourceProfile],
        entity_registry_version: str = "1.0.0",
        source_registry_version: str = "1.0.0",
        content_taxonomy_version: str = "1.0.0",
        editorial_rules_version: str = "1.0.0",
        iran_exceptions_version: str = "1.0.0",
    ):
        self.authority_map = authority_map
        self.sources = sources
        self.entity_registry_version = entity_registry_version
        self.source_registry_version = source_registry_version
        self.content_taxonomy_version = content_taxonomy_version
        self.editorial_rules_version = editorial_rules_version
        self.iran_exceptions_version = iran_exceptions_version
        self.authority_evaluator = AuthorityEvaluator(authority_map, sources)

    def resolve_claim_authority(
        self, claim: Claim, evidence_items: list[EvidenceItem]
    ) -> AuthorityResolutionItem:
        """
        Delegates authority evaluation to the deterministic AuthorityEvaluator.
        Enforces minimum confirmation counts, source independence, and conflict policies.
        """
        return self.authority_evaluator.evaluate_claim(claim, evidence_items)

    def detect_conflicts(
        self, claims: list[Claim], evidence_items: list[EvidenceItem]
    ) -> list[ConflictItem]:
        conflicts: list[ConflictItem] = []
        for claim in claims:
            related_ev = [ev for ev in evidence_items if claim.claim_id in ev.claim_refs]
            contradicting = [ev for ev in related_ev if ev.relation == EvidenceRelation.CONTRADICTS]
            supporting = [ev for ev in related_ev if ev.relation == EvidenceRelation.SUPPORTS]

            if contradicting and supporting:
                conflict_id = f"conf_{claim.claim_id}"
                conflicts.append(
                    ConflictItem(
                        conflict_id=conflict_id,
                        claim_id=claim.claim_id,
                        type="factual_contradiction",
                        evidence_refs=[ev.evidence_id for ev in related_ev],
                        status=ConflictStatus.UNRESOLVED,
                        preferred_source_id=None,
                        resolution_method=None,
                    )
                )
        return conflicts

    def build_card(
        self,
        card_id: str,
        story_id: str,
        headline_working: str,
        target_topic: str,
        entities: list[EntityReference],
        claims: list[Claim],
        evidence: list[EvidenceItem],
        images: list[ImageEvidenceItem] | None = None,
        conflicts: list[ConflictItem] | None = None,
        summary_draft: str | None = None,
        version: int = 1,
        created_at: str | None = None,
    ) -> EvidenceCard:
        now_iso = created_at or datetime.now(timezone.utc).isoformat()

        # Resolve authority for each claim
        auth_resolutions = [
            self.resolve_claim_authority(c, evidence) for c in claims
        ]

        # Detect conflicts or use explicit conflicts
        detected_conflicts = self.detect_conflicts(claims, evidence)
        actual_conflicts = conflicts if conflicts is not None else detected_conflicts

        # Deterministic status promotion per Stage 8.21 Contract 10
        auth_by_claim_id = {a.claim_id: a for a in auth_resolutions}
        promoted_claims: list[Claim] = []

        for c in claims:
            ar = auth_by_claim_id.get(c.claim_id)
            has_unresolved_conflict = any(
                conf.claim_id == c.claim_id and conf.status == ConflictStatus.UNRESOLVED
                for conf in actual_conflicts
            )
            has_direct_negation = any(
                c.claim_id in ev.claim_refs and ev.relation == EvidenceRelation.CONTRADICTS
                for ev in evidence
            )

            if (
                ar is not None
                and ar.status in (AuthorityStatus.CONFIRMED, AuthorityStatus.SECONDARY_CONFIRMED)
                and not has_unresolved_conflict
                and not has_direct_negation
            ):
                new_status = ClaimStatus.SUPPORTED
            elif (
                ar is not None
                and ar.status == AuthorityStatus.CONFLICTED
                and has_direct_negation
            ):
                new_status = ClaimStatus.CONTRADICTED
            else:
                new_status = ClaimStatus.UNVERIFIED

            matching_ev_ids = [ev.evidence_id for ev in evidence if c.claim_id in ev.claim_refs]
            promoted_claim = c.model_copy(
                update={
                    "status": new_status,
                    "evidence_refs": matching_ev_ids or c.evidence_refs,
                }
            )
            promoted_claims.append(promoted_claim)

        # Compute source diversity
        used_source_ids = {ev.source_id for ev in evidence}
        domains = {
            self.sources[sid].domain
            for sid in used_source_ids
            if sid in self.sources and self.sources[sid].domain
        }

        # Intermediate dictionary of card payload for canonical hashing
        payload_for_hash = {
            "identity": {
                "card_id": card_id,
                "version": version,
                "created_at": now_iso,
                "story_id": story_id,
            },
            "story_context": {
                "headline_working": headline_working,
                "language": "fa",
                "target_topic": target_topic,
                "summary_draft": summary_draft,
            },
            "entities": [e.model_dump() for e in entities],
            "claims": [c.model_dump() for c in promoted_claims],
            "evidence": [ev.model_dump() for ev in evidence],
            "authority_resolution": [a.model_dump() for a in auth_resolutions],
            "conflicts": [conf.model_dump() for conf in actual_conflicts],
            "image_evidence": [img.model_dump() for img in (images or [])],
            "integrity_versions": {
                "schema_version": "1.0.0",
                "pipeline_version": "1.0.0",
                "entity_registry_version": self.entity_registry_version,
                "source_registry_version": self.source_registry_version,
                "authority_map_version": self.authority_map.version,
                "content_taxonomy_version": self.content_taxonomy_version,
                "editorial_rules_version": self.editorial_rules_version,
                "iran_exceptions_version": self.iran_exceptions_version,
                "generated_at": now_iso,
                "source_count": len(used_source_ids),
                "independent_source_count": len(domains),
            },
        }

        card_hash = compute_canonical_hash(payload_for_hash, exclude_fields={"card_hash"})

        integrity = EvidenceIntegrityMetadata(
            schema_version="1.0.0",
            pipeline_version="1.0.0",
            entity_registry_version=self.entity_registry_version,
            source_registry_version=self.source_registry_version,
            authority_map_version=self.authority_map.version,
            content_taxonomy_version=self.content_taxonomy_version,
            editorial_rules_version=self.editorial_rules_version,
            iran_exceptions_version=self.iran_exceptions_version,
            generated_at=now_iso,
            source_count=len(used_source_ids),
            independent_source_count=len(domains),
            card_hash=card_hash,
        )

        return EvidenceCard(
            identity=EvidenceCardIdentity(
                card_id=card_id,
                version=version,
                created_at=now_iso,
                story_id=story_id,
            ),
            story_context=StoryContext(
                headline_working=headline_working,
                language="fa",
                target_topic=target_topic,
                summary_draft=summary_draft,
            ),
            entities=entities,
            claims=promoted_claims,
            evidence=evidence,
            authority_resolution=auth_resolutions,
            conflicts=actual_conflicts,
            image_evidence=images or [],
            integrity=integrity,
        )
