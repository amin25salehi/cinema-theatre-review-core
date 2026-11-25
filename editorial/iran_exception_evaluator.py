"""
Iranian Exception Evaluator - Cinema & Theatre Review Editorial OS v1.0.1
Deterministically evaluates candidates against Iran Exceptions Policy (config/iran_exceptions.json).
Enforces: Entity importance alone NEVER bypasses Iranian cinema policy.
"""

from schemas.evidence_card import ClaimStatus, EvidenceCard, EvidenceRelation
from schemas.iran_exceptions import IranExceptionsPolicy
from schemas.source_registry import SourceProfile, StrictModel


class IranianExceptionEvaluation(StrictModel):
    matched: bool
    exception_code: str | None = None
    basis: str | None = None
    required_tier: int | None = None
    evaluation_notes: list[str] = []


class IranianExceptionEvaluator:
    def __init__(
        self,
        policy: IranExceptionsPolicy,
        sources: dict[str, SourceProfile],
    ):
        self.policy = policy
        self.sources = sources

    def evaluate(
        self,
        card: EvidenceCard,
        is_iranian_context: bool = True,
    ) -> IranianExceptionEvaluation:
        """
        Deterministically evaluates if an Iranian cultural story qualifies for international coverage.
        """
        if not is_iranian_context:
            return IranianExceptionEvaluation(
                matched=False,
                evaluation_notes=["Candidate is not an Iranian domestic/cultural story."],
            )

        notes: list[str] = []

        # 1. Check for explicitly disallowed categories
        topic = card.story_context.target_topic.lower()
        headline = card.story_context.headline_working.lower()

        for disallowed in self.policy.disallowed_categories:
            if disallowed in topic or disallowed in headline:
                notes.append(f"Candidate matches disallowed category: '{disallowed}'.")
                return IranianExceptionEvaluation(
                    matched=False,
                    evaluation_notes=notes,
                )

        # 2. Check each allowed exception category in policy
        cat_map = {c.code: c for c in self.policy.allowed_exception_categories}

        # Collect supported claims and their supporting source tiers
        supported_claims = [c for c in card.claims if c.status == ClaimStatus.SUPPORTED]

        for claim in supported_claims:
            # Map supporting sources
            supporting_evidence = [
                ev for ev in card.evidence
                if claim.claim_id in ev.claim_refs and ev.relation == EvidenceRelation.SUPPORTS
            ]
            supporting_sources = [
                self.sources[ev.source_id]
                for ev in supporting_evidence
                if ev.source_id in self.sources
            ]
            best_tier = min((s.tier for s in supporting_sources), default=99)

            # Check Category: major_international_award
            if claim.claim_type == "award_conferral" and "major_international_award" in cat_map:
                cat = cat_map["major_international_award"]
                if best_tier <= cat.required_minimum_tier:
                    return IranianExceptionEvaluation(
                        matched=True,
                        exception_code=cat.code,
                        basis=f"Supported award claim '{claim.claim_id}' verified by Tier {best_tier} source.",
                        required_tier=cat.required_minimum_tier,
                        evaluation_notes=[f"Qualified under policy category '{cat.name}'."],
                    )
                else:
                    notes.append(
                        f"Award claim '{claim.claim_id}' has best source tier {best_tier}, "
                        f"which fails required Tier {cat.required_minimum_tier} ceiling."
                    )

            # Check Category: major_festival_selection
            if claim.claim_type == "festival_selection" and "major_festival_selection" in cat_map:
                cat = cat_map["major_festival_selection"]
                if best_tier <= cat.required_minimum_tier:
                    return IranianExceptionEvaluation(
                        matched=True,
                        exception_code=cat.code,
                        basis=f"Supported festival selection claim '{claim.claim_id}' verified by Tier {best_tier} source.",
                        required_tier=cat.required_minimum_tier,
                        evaluation_notes=[f"Qualified under policy category '{cat.name}'."],
                    )
                else:
                    notes.append(
                        f"Festival selection claim '{claim.claim_id}' has best source tier {best_tier}, "
                        f"which fails required Tier {cat.required_minimum_tier} ceiling."
                    )

            # Check Category: historical_international_event
            if claim.claim_type == "archival_restoration" and "historical_international_event" in cat_map:
                cat = cat_map["historical_international_event"]
                if best_tier <= cat.required_minimum_tier:
                    return IranianExceptionEvaluation(
                        matched=True,
                        exception_code=cat.code,
                        basis=f"Supported archival restoration claim '{claim.claim_id}' verified by Tier {best_tier} source.",
                        required_tier=cat.required_minimum_tier,
                        evaluation_notes=[f"Qualified under policy category '{cat.name}'."],
                    )
                else:
                    notes.append(
                        f"Archival restoration claim '{claim.claim_id}' has best source tier {best_tier}, "
                        f"which fails required Tier {cat.required_minimum_tier} ceiling."
                    )

            # Check Category: international_cultural_significance
            if claim.claim_type in ("critical_assessment", "theatre_premiere") and "international_cultural_significance" in cat_map:
                cat = cat_map["international_cultural_significance"]
                if best_tier <= cat.required_minimum_tier:
                    return IranianExceptionEvaluation(
                        matched=True,
                        exception_code=cat.code,
                        basis=f"Supported cultural claim '{claim.claim_id}' verified by Tier {best_tier} source.",
                        required_tier=cat.required_minimum_tier,
                        evaluation_notes=[f"Qualified under policy category '{cat.name}'."],
                    )

        notes.append("No supported claim met the strict criteria and source tier ceilings for Iranian international exceptions.")
        return IranianExceptionEvaluation(
            matched=False,
            evaluation_notes=notes,
        )
