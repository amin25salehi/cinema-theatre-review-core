"""
Evidence Card Cross-Reference Validator - Cinema & Theatre Review Editorial OS v1.0.1
Enforces deterministic referential integrity, foreign key validation, and scope-level ID uniqueness.
"""

from schemas.entity_registry import EntityProfile
from schemas.evidence_card import EvidenceCard
from schemas.source_registry import SourceProfile


class EvidenceCardValidationError(ValueError):
    """Raised when an EvidenceCard fails deterministic cross-reference validation."""
    pass


class EvidenceCardValidator:
    @staticmethod
    def validate_card(
        card: EvidenceCard,
        entities: dict[str, EntityProfile],
        sources: dict[str, SourceProfile],
    ) -> tuple[bool, list[str]]:
        """
        Deterministically validates all internal and external references within an EvidenceCard.
        Returns (is_valid, errors).
        """
        errors: list[str] = []

        # 1. ID uniqueness within card scope
        claim_ids: set[str] = set()
        for idx, claim in enumerate(card.claims):
            if claim.claim_id in claim_ids:
                errors.append(f"Duplicate claim_id '{claim.claim_id}' found in claims at index {idx}.")
            claim_ids.add(claim.claim_id)

        evidence_ids: set[str] = set()
        for idx, ev in enumerate(card.evidence):
            if ev.evidence_id in evidence_ids:
                errors.append(f"Duplicate evidence_id '{ev.evidence_id}' found in evidence at index {idx}.")
            evidence_ids.add(ev.evidence_id)

        conflict_ids: set[str] = set()
        for idx, conf in enumerate(card.conflicts):
            if conf.conflict_id in conflict_ids:
                errors.append(f"Duplicate conflict_id '{conf.conflict_id}' found in conflicts at index {idx}.")
            conflict_ids.add(conf.conflict_id)

        asset_ids: set[str] = set()
        for idx, img in enumerate(card.image_evidence):
            if img.asset_id in asset_ids:
                errors.append(f"Duplicate asset_id '{img.asset_id}' found in image_evidence at index {idx}.")
            asset_ids.add(img.asset_id)

        # 2. Entity references: entities[], claims[].subject_entity_id, claims[].object_entity_id
        for ent_ref in card.entities:
            if ent_ref.entity_id not in entities:
                errors.append(
                    f"Entity reference '{ent_ref.entity_id}' in card.entities does not exist in Entity Registry."
                )

        for claim in card.claims:
            if claim.subject_entity_id not in entities:
                errors.append(
                    f"Claim '{claim.claim_id}' subject_entity_id '{claim.subject_entity_id}' does not exist in Entity Registry."
                )
            if claim.object_entity_id and claim.object_entity_id not in entities:
                errors.append(
                    f"Claim '{claim.claim_id}' object_entity_id '{claim.object_entity_id}' does not exist in Entity Registry."
                )

        # 3. Evidence references: claims[].evidence_refs, conflicts[].evidence_refs -> card.evidence
        for claim in card.claims:
            for ev_ref in claim.evidence_refs:
                if ev_ref not in evidence_ids:
                    errors.append(
                        f"Claim '{claim.claim_id}' references evidence_id '{ev_ref}' which does not exist in card.evidence."
                    )

        for conf in card.conflicts:
            for ev_ref in conf.evidence_refs:
                if ev_ref not in evidence_ids:
                    errors.append(
                        f"Conflict '{conf.conflict_id}' references evidence_id '{ev_ref}' which does not exist in card.evidence."
                    )

        # 4. Source references: evidence[].source_id, image_evidence[].source_id, authority_resolution[].preferred_source_id
        for ev in card.evidence:
            if ev.source_id not in sources:
                errors.append(
                    f"Evidence '{ev.evidence_id}' references source_id '{ev.source_id}' which does not exist in Source Registry."
                )

        for img in card.image_evidence:
            if img.source_id not in sources:
                errors.append(
                    f"Image asset '{img.asset_id}' references source_id '{img.source_id}' which does not exist in Source Registry."
                )

        for auth in card.authority_resolution:
            if auth.preferred_source_id and auth.preferred_source_id not in sources:
                errors.append(
                    f"Authority resolution for claim '{auth.claim_id}' references preferred_source_id '{auth.preferred_source_id}' which does not exist in Source Registry."
                )

        # 5. Claim references: evidence[].claim_refs, conflicts[].claim_id, authority_resolution[].claim_id -> card.claims
        for ev in card.evidence:
            for clm_ref in ev.claim_refs:
                if clm_ref not in claim_ids:
                    errors.append(
                        f"Evidence '{ev.evidence_id}' references claim_id '{clm_ref}' which does not exist in card.claims."
                    )

        for conf in card.conflicts:
            if conf.claim_id not in claim_ids:
                errors.append(
                    f"Conflict '{conf.conflict_id}' references claim_id '{conf.claim_id}' which does not exist in card.claims."
                )

        for auth in card.authority_resolution:
            if auth.claim_id not in claim_ids:
                errors.append(
                    f"Authority resolution references claim_id '{auth.claim_id}' which does not exist in card.claims."
                )

        is_valid = len(errors) == 0
        return is_valid, errors

    @classmethod
    def assert_valid(
        cls,
        card: EvidenceCard,
        entities: dict[str, EntityProfile],
        sources: dict[str, SourceProfile],
    ) -> None:
        """Raises EvidenceCardValidationError if validation fails."""
        is_valid, errors = cls.validate_card(card, entities, sources)
        if not is_valid:
            joined = "\n  - ".join(errors)
            raise EvidenceCardValidationError(
                f"EvidenceCard '{card.identity.card_id}' failed referential integrity validation:\n  - {joined}"
            )
