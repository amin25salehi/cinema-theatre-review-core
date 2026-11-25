"""
Editorial Decision Engine - Cinema & Theatre Review Editorial OS v1.0.1
Constructs Editorial Decision Cards.
INVARIANT: LLM Recommendation != Final Decision.
Enforces deterministic policy invariants, truthful validation summaries,
complete audit metadata, and canonical checksums.
"""

from datetime import datetime, timezone
from typing import Any

from editorial.decision_validator import DecisionValidator
from editorial.iran_exception_evaluator import IranianExceptionEvaluator
from editorial.rule_engine import EditorialRuleEngine
from schemas.decision_card import (
    CharacterBudget,
    ContentType,
    DecisionAuditMetadata,
    EditorialDecisionCard,
    EditorialDecisionType,
    HumanOverride,
    LLMAssessment,
    PolicyVersions,
    PublicationFormat,
    PublicationPlan,
    StoryActionType,
    StoryStateType,
)
from schemas.evidence_card import EvidenceCard
from utils.canonical_hash import compute_canonical_hash


def determine_story_action(
    decision: EditorialDecisionType,
    story_state: StoryStateType,
    update_as_reply: bool = False,
) -> StoryActionType:
    """
    Deterministically maps story state and final decision to a compliant StoryActionType.
    """
    if decision in (EditorialDecisionType.HOLD, EditorialDecisionType.REJECT):
        if story_state == StoryStateType.RETRACTION:
            return StoryActionType.RETRACTION_NOTICE
        return StoryActionType.NO_PUBLICATION

    if story_state == StoryStateType.NEW:
        return StoryActionType.NEW_POST
    elif story_state == StoryStateType.UPDATE:
        return StoryActionType.REPLY if update_as_reply else StoryActionType.EDIT_EXISTING
    elif story_state == StoryStateType.FOLLOW_UP:
        return StoryActionType.REPLY
    elif story_state == StoryStateType.CORRECTION:
        return StoryActionType.CORRECTION_NOTICE
    elif story_state == StoryStateType.RETRACTION:
        return StoryActionType.RETRACTION_NOTICE

    return StoryActionType.NO_PUBLICATION


class EditorialDecisionEngine:
    def __init__(
        self,
        rule_engine: EditorialRuleEngine,
        iran_exception_evaluator: IranianExceptionEvaluator | None = None,
        editorial_rules_version: str = "1.0.0",
        authority_map_version: str = "1.0.0",
        iran_exceptions_version: str = "1.0.0",
        content_taxonomy_version: str = "1.0.0",
        source_registry_version: str = "1.0.0",
        entity_registry_version: str = "1.0.0",
        decision_engine_version: str = "1.0.1",
        pipeline_version: str = "1.0.1",
    ):
        self.rule_engine = rule_engine
        self.iran_exception_evaluator = iran_exception_evaluator
        self.editorial_rules_version = editorial_rules_version
        self.authority_map_version = authority_map_version
        self.iran_exceptions_version = iran_exceptions_version
        self.content_taxonomy_version = content_taxonomy_version
        self.source_registry_version = source_registry_version
        self.entity_registry_version = entity_registry_version
        self.decision_engine_version = decision_engine_version
        self.pipeline_version = pipeline_version

    def evaluate(
        self,
        card: EvidenceCard,
        card_id: str,
        is_duplicate: bool = False,
        is_commercial_only: bool = False,
        is_iranian_daily_news: bool = False,
        iran_exception_matched: str | None = None,
        llm_assessment: LLMAssessment | None = None,
        llm_model: str | None = None,
        llm_prompt_version: str | None = None,
        content_type: ContentType = ContentType.CINEMA,
        format_type: PublicationFormat = PublicationFormat.NEWS_BRIEF,
        story_state: StoryStateType = StoryStateType.NEW,
        story_id: str | None = None,
        update_as_reply: bool = False,
        human_override: HumanOverride | None = None,
        evaluated_at: str | None = None,
    ) -> EditorialDecisionCard:
        now_iso = evaluated_at or datetime.now(timezone.utc).isoformat()

        # Deterministically evaluate Iranian exception if evaluator available and not pre-specified
        matched_exception_code = iran_exception_matched
        if is_iranian_daily_news and self.iran_exception_evaluator and not matched_exception_code:
            eval_result = self.iran_exception_evaluator.evaluate(card, is_iranian_context=True)
            if eval_result.matched:
                matched_exception_code = eval_result.exception_code

        # 1. Evaluate deterministic hard gates
        hard_gates = self.rule_engine.evaluate_hard_gates(
            card=card,
            is_duplicate=is_duplicate,
            is_commercial_only=is_commercial_only,
            is_iranian_daily_news=is_iranian_daily_news,
            iran_exception_matched=matched_exception_code,
            evaluated_at=now_iso,
        )

        # 2. Calculate editorial signals
        signals = self.rule_engine.calculate_signals(
            card=card, iran_exception_matched=matched_exception_code
        )

        # 3. Form initial proposal (from LLM if provided, or from signals)
        if llm_assessment:
            proposed_decision = llm_assessment.recommended_action
        else:
            if signals.editorial_fit >= 0.6 and signals.evidence_strength >= 0.7:
                proposed_decision = EditorialDecisionType.PUBLISH
            elif signals.evidence_strength < 0.5:
                proposed_decision = EditorialDecisionType.HOLD
            else:
                proposed_decision = EditorialDecisionType.HOLD

        # Prepare character budget from config
        budgets = self.rule_engine.editorial_rules.get("character_budgets", {})
        format_budget_raw = budgets.get(
            format_type.value, {"min": 150, "target": 350, "max": 600}
        )
        character_budget = CharacterBudget(
            min=format_budget_raw["min"],
            target=format_budget_raw["target"],
            max=format_budget_raw["max"],
        )

        # Tentative publication plan for validation check
        tentative_pub_plan = PublicationPlan(
            content_type=content_type,
            format=format_type,
            language="fa",
            character_budget=character_budget,
            schedule=now_iso,
        )

        # 4. Deterministic validation and enforcement
        final_decision, decision_reason, validation = DecisionValidator.validate_and_enforce(
            proposed_decision=proposed_decision,
            hard_gates=hard_gates,
            card=card,
            llm_assessment=llm_assessment,
            publication_plan=tentative_pub_plan if proposed_decision == EditorialDecisionType.PUBLISH else None,
            character_budget=character_budget,
            human_override=human_override,
        )

        # 5. Structure publication plan and story action according to final decision
        if final_decision == EditorialDecisionType.PUBLISH:
            pub_plan = tentative_pub_plan
        else:
            pub_plan = None

        story_action = determine_story_action(
            decision=final_decision,
            story_state=story_state,
            update_as_reply=update_as_reply,
        )

        # 6. Re-evaluate validation summary to guarantee alignment with final constructed plan
        _, _, final_validation = DecisionValidator.validate_and_enforce(
            proposed_decision=final_decision,
            hard_gates=hard_gates,
            card=card,
            llm_assessment=llm_assessment,
            publication_plan=pub_plan,
            character_budget=character_budget if pub_plan else None,
            human_override=human_override,
        )

        # Merge notes and overrides from initial validation
        combined_overrides = list(dict.fromkeys(validation.overrides_applied + final_validation.overrides_applied))
        combined_notes = list(dict.fromkeys(validation.validator_notes + final_validation.validator_notes))
        final_validation = final_validation.model_copy(
            update={"overrides_applied": combined_overrides, "validator_notes": combined_notes}
        )

        # 7. Compute deterministic canonical checksum of decision payload
        policy_versions = PolicyVersions(
            editorial_rules_version=self.editorial_rules_version,
            authority_map_version=self.authority_map_version,
            iran_exceptions_version=self.iran_exceptions_version,
            content_taxonomy_version=self.content_taxonomy_version,
            source_registry_version=self.source_registry_version,
            entity_registry_version=self.entity_registry_version,
        )

        effective_story_id = story_id or getattr(card, "story_id", None) or card.identity.card_id

        payload_for_checksum = {
            "card_id": card_id,
            "evidence_card_id": card.identity.card_id,
            "evidence_card_version": card.identity.version,
            "story_id": effective_story_id,
            "decision": final_decision.value,
            "decision_reason": decision_reason,
            "story_action": story_action.value,
            "story_state": story_state.value,
            "hard_gates": hard_gates.model_dump(),
            "editorial_signals": signals.model_dump(),
            "policy_versions": policy_versions.model_dump(),
            "publication_plan": pub_plan.model_dump() if pub_plan else None,
            "human_override": human_override.model_dump() if human_override else None,
            "validation": final_validation.model_dump(),
        }

        deterministic_checksum = compute_canonical_hash(
            payload_for_checksum, exclude_fields={"deterministic_checksum"}
        )

        audit = DecisionAuditMetadata(
            evaluated_at=now_iso,
            pipeline_version=self.pipeline_version,
            decision_engine_version=self.decision_engine_version,
            editorial_rules_version=self.editorial_rules_version,
            authority_map_version=self.authority_map_version,
            source_registry_version=self.source_registry_version,
            entity_registry_version=self.entity_registry_version,
            content_taxonomy_version=self.content_taxonomy_version,
            iran_exceptions_version=self.iran_exceptions_version,
            llm_model=llm_model,
            llm_prompt_version=llm_prompt_version,
            human_override=human_override,
            deterministic_checksum=deterministic_checksum,
        )

        return EditorialDecisionCard(
            card_id=card_id,
            evidence_card_id=card.identity.card_id,
            evidence_card_version=card.identity.version,
            story_id=effective_story_id,
            policy_versions=policy_versions,
            hard_gates=hard_gates,
            editorial_signals=signals,
            rule_evaluations=[],
            llm_assessment=llm_assessment,
            decision=final_decision,
            decision_reason=decision_reason,
            publication_plan=pub_plan,
            story_action=story_action,
            story_state=story_state,
            validation=final_validation,
            audit=audit,
        )
