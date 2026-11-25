"""
LLM Context Projection Validator - Cinema & Theatre Review Editorial OS v1.0.1
Enforces Stage 8.8 architectural and security boundaries:
1. Schema correctness & versioning (llm_context:v1).
2. Referential integrity (FK checks to source and entity registries).
3. Provenance completeness (every trusted claim must have supporting evidence).
4. Trust & uncertainty consistency (supported ≠ unresolved ≠ contradicted).
5. Unresolved conflict preservation.
6. Bounds & truncation metadata accuracy.
7. Canonical hash integrity verification.
8. Complete absence of editorial decision / publication / scoring fields.
"""

import re
from typing import Any

from schemas.context_projection import LLMContextProjection
from schemas.entity_registry import EntityProfile
from schemas.source_registry import SourceProfile
from utils.canonical_hash import compute_canonical_hash

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")

FORBIDDEN_EDITORIAL_FIELDS = {
    "publication_decision",
    "editorial_decision",
    "publish",
    "reject",
    "hold_as_editorial_action",
    "editorial_fit",
    "artistic_score",
    "quality_score",
    "importance_score",
    "telegram_text",
    "draft",
    "caption",
    "recommendation",
}


class ProjectionValidationError(Exception):
    """Raised when an LLMContextProjection violates structural, trust, or boundary invariants."""

    pass


class LLMContextProjectionValidator:
    """
    Validates LLMContextProjection against Stage 8.8 architectural invariants.
    """

    @classmethod
    def validate_projection(
        cls,
        projection: LLMContextProjection,
        sources: dict[str, SourceProfile],
        entities: dict[str, EntityProfile],
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []

        # 1. Schema version
        if projection.schema_version != "llm_context:v1":
            errors.append(
                f"Invalid schema_version '{projection.schema_version}', expected 'llm_context:v1'"
            )

        # 2. Identifiers
        if not ID_PATTERN.match(projection.projection_id):
            errors.append(f"Invalid projection_id '{projection.projection_id}'")
        if not ID_PATTERN.match(projection.evidence_card_id):
            errors.append(f"Invalid evidence_card_id '{projection.evidence_card_id}'")

        # 3. Entity FK integrity
        for ent in projection.resolved_entities:
            if ent.entity_id not in entities:
                errors.append(
                    f"Entity FK violation: '{ent.entity_id}' not found in Entity Registry"
                )

        # 4. Evidence Source FK integrity
        for ev in projection.authoritative_evidence:
            if ev.source_id not in sources:
                errors.append(
                    f"Source FK violation: '{ev.source_id}' not found in Source Registry"
                )

        # 5. Provenance completeness:
        # Every trusted claim must have at least one supporting evidence item in authoritative_evidence
        projected_ev_map = {ev.evidence_id: ev for ev in projection.authoritative_evidence}
        for tc in projection.trusted_claims:
            supporting_ev = [
                ev
                for ev in projection.authoritative_evidence
                if tc.claim_id in ev.claim_refs and ev.relation == "supports"
            ]
            if not supporting_ev:
                errors.append(
                    f"Provenance failure: Trusted claim '{tc.claim_id}' has no supporting evidence item in projection"
                )

        # 6. Trust & Uncertainty consistency
        trusted_ids = {c.claim_id for c in projection.trusted_claims}
        unresolved_ids = {c.claim_id for c in projection.unresolved_claims}
        contradicted_ids = {c.claim_id for c in projection.contradicted_claims}

        overlap_tu = trusted_ids & unresolved_ids
        overlap_tc = trusted_ids & contradicted_ids
        overlap_uc = unresolved_ids & contradicted_ids

        if overlap_tu:
            errors.append(f"Claims present in both trusted and unresolved: {sorted(overlap_tu)}")
        if overlap_tc:
            errors.append(f"Claims present in both trusted and contradicted: {sorted(overlap_tc)}")
        if overlap_uc:
            errors.append(f"Claims present in both unresolved and contradicted: {sorted(overlap_uc)}")

        for tc in projection.trusted_claims:
            if tc.status != "supported":
                errors.append(
                    f"Trust boundary violation: Trusted claim '{tc.claim_id}' has status '{tc.status}', expected 'supported'"
                )
            if tc.authority_status != "confirmed":
                errors.append(
                    f"Trust boundary violation: Trusted claim '{tc.claim_id}' has authority_status '{tc.authority_status}', expected 'confirmed'"
                )

        for cc in projection.contradicted_claims:
            if cc.status != "contradicted":
                errors.append(
                    f"Status consistency violation: Contradicted claim '{cc.claim_id}' has status '{cc.status}', expected 'contradicted'"
                )

        # Unresolved conflicts cannot affect trusted claims
        for conf in projection.relevant_conflicts:
            if conf.conflict_status == "unresolved" and conf.claim_id in trusted_ids:
                errors.append(
                    f"Trust boundary violation: Claim '{conf.claim_id}' has unresolved conflict '{conf.conflict_id}' but is marked as trusted"
                )

        # 7. Conflict consistency
        relevant_claim_ids = {c.claim_id for c in projection.relevant_claims}
        for conf in projection.relevant_conflicts:
            if conf.claim_id not in relevant_claim_ids:
                errors.append(
                    f"Conflict inconsistency: Conflict '{conf.conflict_id}' references unknown claim '{conf.claim_id}'"
                )
            for ref_ev_id in conf.conflicting_evidence_ids:
                if ref_ev_id not in projected_ev_map:
                    errors.append(
                        f"Conflict inconsistency: Conflict '{conf.conflict_id}' references missing evidence '{ref_ev_id}'"
                    )

        # 8. Bounds & Truncation validation
        if projection.bounding_metadata is not None:
            bm = projection.bounding_metadata
            if len(projection.relevant_claims) > bm.max_claims:
                errors.append(
                    f"Bounds violation: {len(projection.relevant_claims)} claims exceed max_claims {bm.max_claims}"
                )
            if len(projection.authoritative_evidence) > bm.max_evidence_items:
                errors.append(
                    f"Bounds violation: {len(projection.authoritative_evidence)} evidence items exceed max_evidence_items {bm.max_evidence_items}"
                )
            if len(projection.relevant_conflicts) > bm.max_conflicts:
                errors.append(
                    f"Bounds violation: {len(projection.relevant_conflicts)} conflicts exceed max_conflicts {bm.max_conflicts}"
                )
            if len(projection.resolved_entities) > bm.max_entities:
                errors.append(
                    f"Bounds violation: {len(projection.resolved_entities)} entities exceed max_entities {bm.max_entities}"
                )
            if bm.claims_projected != len(projection.relevant_claims):
                errors.append(
                    f"Truncation metadata mismatch: claims_projected ({bm.claims_projected}) != len(relevant_claims) ({len(projection.relevant_claims)})"
                )
            if bm.evidence_projected != len(projection.authoritative_evidence):
                errors.append(
                    f"Truncation metadata mismatch: evidence_projected ({bm.evidence_projected}) != len(authoritative_evidence) ({len(projection.authoritative_evidence)})"
                )

        # 9. Forbidden editorial fields check
        serialized = projection.model_dump()
        found_forbidden = cls._find_forbidden_keys(serialized)
        if found_forbidden:
            errors.append(f"Forbidden editorial fields found in projection: {sorted(found_forbidden)}")

        # 10. Integrity Checksum verification
        recomputed_hash = compute_canonical_hash(
            serialized, exclude_fields={"integrity_checksum"}
        )
        if recomputed_hash != projection.integrity_checksum:
            errors.append(
                f"Checksum mismatch: expected '{projection.integrity_checksum}', recomputed '{recomputed_hash}'"
            )

        return (len(errors) == 0, errors)

    @classmethod
    def assert_valid(
        cls,
        projection: LLMContextProjection,
        sources: dict[str, SourceProfile],
        entities: dict[str, EntityProfile],
    ) -> None:
        valid, errors = cls.validate_projection(projection, sources, entities)
        if not valid:
            raise ProjectionValidationError(
                f"LLMContextProjection validation failed with {len(errors)} error(s):\n - "
                + "\n - ".join(errors)
            )

    @classmethod
    def _find_forbidden_keys(cls, obj: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in FORBIDDEN_EDITORIAL_FIELDS:
                    found.add(k)
                found |= cls._find_forbidden_keys(v)
        elif isinstance(obj, list):
            for item in obj:
                found |= cls._find_forbidden_keys(item)
        return found
