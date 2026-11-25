"""
Editorial Decision Validator - Cinema & Theatre Review Editorial OS v1.0.1
Enforces deterministic policy invariants:
1. Hard gates can NEVER be overridden by LLM.
2. Unresolved material factual conflicts produce HOLD.
3. If any material claim is unverified, action CANNOT be publish.
4. ValidationSummary must be truthful and derived from explicit validation check flags.
"""

from schemas.decision_card import (
    CharacterBudget,
    EditorialDecisionType,
    GateStatus,
    HardGatesEvaluation,
    HumanOverride,
    LLMAssessment,
    PublicationPlan,
    ValidationSummary,
)
from schemas.evidence_card import ClaimStatus, ConflictStatus, EvidenceCard


class DecisionValidator:
    @staticmethod
    def validate_and_enforce(
        proposed_decision: EditorialDecisionType,
        hard_gates: HardGatesEvaluation,
        card: EvidenceCard,
        llm_assessment: LLMAssessment | None = None,
        publication_plan: PublicationPlan | None = None,
        character_budget: CharacterBudget | None = None,
        human_override: HumanOverride | None = None,
    ) -> tuple[EditorialDecisionType, str, ValidationSummary]:
        validator_notes: list[str] = []
        overrides: list[str] = []
        final_decision = proposed_decision
        final_reason = "Decision validated against all deterministic policy rules."

        # 1. Check all hard gates
        gate_statuses = {
            "duplicate": hard_gates.duplicate.status,
            "commercial_only": hard_gates.commercial_only.status,
            "iranian_daily_news": hard_gates.iranian_daily_news.status,
            "unverified_claim": hard_gates.unverified_claim.status,
            "image_provenance": hard_gates.image_provenance.status,
            "source_requirement": hard_gates.source_requirement.status,
        }

        has_gate_failure = any(status == GateStatus.FAIL for status in gate_statuses.values())
        policy_valid = not has_gate_failure

        if has_gate_failure:
            if proposed_decision == EditorialDecisionType.PUBLISH:
                overrides.append(
                    "Proposed 'publish' decision was OVERRIDDEN because deterministic hard gates failed."
                )

            if (
                gate_statuses["duplicate"] == GateStatus.FAIL
                or gate_statuses["commercial_only"] == GateStatus.FAIL
                or gate_statuses["iranian_daily_news"] == GateStatus.FAIL
            ):
                final_decision = EditorialDecisionType.REJECT
                failed_names = [k for k, v in gate_statuses.items() if v == GateStatus.FAIL]
                failed_details = [
                    f"{k} ({getattr(hard_gates, k).reason})"
                    if getattr(hard_gates, k, None) and getattr(hard_gates, k).reason
                    else k
                    for k in failed_names
                ]
                final_reason = f"Deterministic rejection: hard gate(s) failed [{'; '.join(failed_details)}]."
            else:
                final_decision = EditorialDecisionType.HOLD
                failed_names = [k for k, v in gate_statuses.items() if v == GateStatus.FAIL]
                failed_details = [
                    f"{k} ({getattr(hard_gates, k).reason})"
                    if getattr(hard_gates, k, None) and getattr(hard_gates, k).reason
                    else k
                    for k in failed_names
                ]
                final_reason = f"Placed on HOLD: factual verification required [{'; '.join(failed_details)}]."

        # 2. Check material claim verification
        material_claims = [c for c in card.claims if c.material and c.verification_required]
        unverified_material = [c for c in material_claims if c.status != ClaimStatus.SUPPORTED]
        evidence_sufficient = (len(unverified_material) == 0 and len(material_claims) > 0) or (len(material_claims) == 0 and not has_gate_failure)

        if unverified_material and final_decision == EditorialDecisionType.PUBLISH:
            overrides.append(
                f"Cannot publish with {len(unverified_material)} unverified material claim(s)."
            )
            final_decision = EditorialDecisionType.HOLD
            final_reason = f"Placed on HOLD: {len(unverified_material)} material claim(s) require verification."

        # 3. Check unresolved conflicts
        unresolved_conflicts = [
            conf for conf in card.conflicts if conf.status == ConflictStatus.UNRESOLVED
        ]
        conflicts_resolved = len(unresolved_conflicts) == 0

        if unresolved_conflicts and final_decision == EditorialDecisionType.PUBLISH:
            overrides.append(
                f"Cannot publish with {len(unresolved_conflicts)} unresolved conflict(s)."
            )
            final_decision = EditorialDecisionType.HOLD
            final_reason = "Placed on HOLD: unresolved factual conflicts must be resolved before publishing."

        # 4. Check LLM recommendation boundary
        if llm_assessment:
            if llm_assessment.recommended_action == EditorialDecisionType.PUBLISH and final_decision != EditorialDecisionType.PUBLISH:
                validator_notes.append(
                    f"LLM advised '{llm_assessment.recommended_action.value}', but deterministic validation enforced '{final_decision.value}'."
                )

        # 5. Check Human Override
        if human_override:
            if human_override.overridden_decision == EditorialDecisionType.PUBLISH and has_gate_failure:
                validator_notes.append(
                    f"Human editor '{human_override.overridden_by}' attempted to override to 'publish', but hard gate failure prevented it."
                )
                overrides.append(
                    "Human override to 'publish' REJECTED because deterministic hard gates failed."
                )
                # Keep final_decision as HOLD or REJECT
            else:
                overrides.append(
                    f"Human editor '{human_override.overridden_by}' applied override: "
                    f"'{human_override.original_decision.value}' -> '{human_override.overridden_decision.value}' "
                    f"[Reason: {human_override.override_reason}]."
                )
                final_decision = human_override.overridden_decision
                final_reason = f"Human override applied by {human_override.overridden_by}: {human_override.override_reason}"

        # 5. Check decision consistency
        if final_decision == EditorialDecisionType.PUBLISH:
            decision_consistent = policy_valid and evidence_sufficient and conflicts_resolved
        else:
            decision_consistent = True

        # 6. Check publication plan validity and character budget
        if final_decision == EditorialDecisionType.PUBLISH:
            publication_plan_valid = publication_plan is not None
            character_budget_valid = (
                character_budget is not None
                and character_budget.min <= character_budget.target <= character_budget.max
            )
        else:
            publication_plan_valid = publication_plan is None
            character_budget_valid = True

        # Truthful derivation of is_valid
        is_valid = (
            policy_valid
            and evidence_sufficient
            and decision_consistent
            and publication_plan_valid
            and character_budget_valid
            and conflicts_resolved
        )

        summary = ValidationSummary(
            is_valid=is_valid,
            policy_valid=policy_valid,
            evidence_sufficient=evidence_sufficient,
            decision_consistent=decision_consistent,
            publication_plan_valid=publication_plan_valid,
            character_budget_valid=character_budget_valid,
            conflicts_resolved=conflicts_resolved,
            validator_notes=validator_notes,
            overrides_applied=overrides,
        )

        return final_decision, final_reason, summary
