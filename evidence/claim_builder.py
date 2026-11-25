"""
Claim Builder - Cinema & Theatre Review Editorial OS v1.0
Constructs atomic claims. Enforces non-compound claims, typed predicates,
and distinct materiality/verification flags.
"""


from schemas.evidence_card import Claim, ClaimStatus


class ClaimBuilder:
    @staticmethod
    def create_claim(
        claim_id: str,
        claim_type: str,
        subject_entity_id: str,
        claim_text: str,
        object_entity_id: str | None = None,
        object_value: str | None = None,
        status: ClaimStatus = ClaimStatus.UNVERIFIED,
        material: bool = True,
        verification_required: bool = True,
        evidence_refs: list[str] | None = None,
    ) -> Claim:
        """
        Builds a single atomic claim.
        INVARIANT: Claims must be atomic; compound statements must be split.
        """
        return Claim(
            claim_id=claim_id,
            claim_type=claim_type,
            subject_entity_id=subject_entity_id,
            object_entity_id=object_entity_id,
            object_value=object_value,
            claim_text=claim_text,
            status=status,
            material=material,
            verification_required=verification_required,
            evidence_refs=evidence_refs or [],
        )
