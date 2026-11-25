"""
Stage 8.10 — Editorial Decision Engine & Decision Cards Test Suite
Covers:
1. Input integrity & EvidenceCard consumption
2. Hard gates evaluation & non-negotiability (overriding LLM)
3. LLM independence (pure advisory role, omission safety)
4. Story identity & change logic (new, update, correction, retraction)
5. Publication planning & character budgets
6. Human override support & bounds (hard gate non-bypass)
7. Determinism (identical inputs produce bitwise identical checksums)
8. Immutability & canonical schema invariants
"""

import pytest
from editorial.decision_engine import EditorialDecisionEngine, determine_story_action
from editorial.decision_validator import DecisionValidator
from editorial.rule_engine import EditorialRuleEngine
from evidence.claim_builder import ClaimBuilder
from evidence.evidence_builder import EvidenceBuilder
from evidence.evidence_card_builder import EvidenceCardBuilder
from loaders.config_loader import ConfigLoader
from loaders.entity_loader import EntityLoader
from loaders.source_loader import SourceLoader
from schemas.decision_card import (
    CharacterBudget,
    ContentType,
    EditorialDecisionCard,
    EditorialDecisionType,
    EditorialSignals,
    GateResult,
    GateStatus,
    HardGatesEvaluation,
    HumanOverride,
    LLMAssessment,
    PublicationFormat,
    PublicationPlan,
    StoryActionType,
    StoryStateType,
    ValidationSummary,
)
from schemas.evidence_card import (
    ClaimStatus,
    ConflictStatus,
    EntityReference,
    EvidenceRelation,
)


@pytest.fixture
def test_environment():
    config_loader = ConfigLoader()
    rules = config_loader.load_editorial_rules()
    iran_exceptions = config_loader.load_iran_exceptions()
    entities = EntityLoader().load_all_entities()
    sources = SourceLoader().load_all_sources()
    authority_map = config_loader.load_authority_map()

    builder = EvidenceCardBuilder(authority_map, sources)
    rule_engine = EditorialRuleEngine(
        editorial_rules=rules,
        iran_exceptions=iran_exceptions,
        entities=entities,
    )
    engine = EditorialDecisionEngine(rule_engine=rule_engine)
    return {
        "builder": builder,
        "engine": engine,
        "sources": sources,
        "authority_map": authority_map,
    }


def make_sample_card(builder, card_id="ec_stage810_sample", unverified=False, conflict=False):
    status = ClaimStatus.UNVERIFIED if unverified else ClaimStatus.SUPPORTED
    claim = ClaimBuilder.create_claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry won Palme d'Or.",
        status=status,
        material=True,
    )
    if unverified:
        # Insufficient confirmation (single secondary source requires 2x) -> remains UNVERIFIED
        ev = EvidenceBuilder.create_evidence(
            evidence_id="ev_01",
            source_id="crit_cahiers",
            source_url="https://cahiersducinema.com/taste-of-cherry",
            evidence_type="review",
            relation=EvidenceRelation.SUPPORTS,
            claim_refs=["clm_01"],
            excerpt="Taste of Cherry mentioned at Cannes.",
        )
    else:
        ev = EvidenceBuilder.create_evidence(
            evidence_id="ev_01",
            source_id="src_cannes_official",
            source_url="https://festival-cannes.com/palme",
            evidence_type="official",
            relation=EvidenceRelation.SUPPORTS,
            claim_refs=["clm_01"],
            excerpt="Palme d'Or awarded to Taste of Cherry.",
        )
    card = builder.build_card(
        card_id=card_id,
        story_id="story_cannes_palme",
        headline_working="Taste of Cherry Palme d'Or",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[claim],
        evidence=[ev],
    )
    if conflict:
        # Inject an unresolved conflict using ConflictItem
        from schemas.evidence_card import ConflictItem
        conf_item = ConflictItem(
            conflict_id="conf_01",
            claim_id="clm_01",
            type="factual_contradiction",
            evidence_refs=["ev_01", "ev_01"],
            status=ConflictStatus.UNRESOLVED,
        )
        card = card.model_copy(
            update={
                "conflicts": [conf_item]
            }
        )
    return card


# --- 1. Input Integrity ---
def test_input_integrity_and_card_consumption(test_environment):
    builder = test_environment["builder"]
    engine = test_environment["engine"]

    card = make_sample_card(builder, "ec_input_integrity")
    decision_card = engine.evaluate(
        card=card,
        card_id="dc_input_integrity",
        story_id="story_cannes_palme",
        story_state=StoryStateType.NEW,
    )

    assert isinstance(decision_card, EditorialDecisionCard)
    assert decision_card.card_id == "dc_input_integrity"
    assert decision_card.evidence_card_id == "ec_input_integrity"
    assert decision_card.evidence_card_version == card.identity.version
    assert decision_card.story_id == "story_cannes_palme"
    assert decision_card.validation.is_valid is True
    assert decision_card.audit.deterministic_checksum is not None


# --- 2. Hard Gates Evaluation & Non-Negotiability ---
def test_hard_gate_failure_prohibits_publish_even_with_llm_publish_recommendation(test_environment):
    builder = test_environment["builder"]
    engine = test_environment["engine"]

    card = make_sample_card(builder, "ec_duplicate_test")
    advisory_llm = LLMAssessment(
        recommended_action=EditorialDecisionType.PUBLISH,
        editorial_rationale="The story is high quality and impactful.",
        uncertainties=[],
    )

    decision_card = engine.evaluate(
        card=card,
        card_id="dc_duplicate_test",
        is_duplicate=True,  # Hard gate fails
        llm_assessment=advisory_llm,
    )

    # Invariant: Must REJECT, cannot publish despite LLM advice
    assert decision_card.hard_gates.duplicate.status == GateStatus.FAIL
    assert decision_card.decision == EditorialDecisionType.REJECT
    assert decision_card.publication_plan is None
    assert decision_card.story_action == StoryActionType.NO_PUBLICATION
    assert decision_card.validation.is_valid is False
    assert any("OVERRIDDEN" in note for note in decision_card.validation.overrides_applied)


def test_schema_invariant_raises_if_hard_gate_fails_and_publish_attempted(test_environment):
    builder = test_environment["builder"]
    card = make_sample_card(builder, "ec_invariant_direct")
    now_iso = "2026-09-20T00:00:00Z"

    with pytest.raises(ValueError, match="Deterministic hard gate failure prohibits Editorial Decision 'publish'"):
        EditorialDecisionCard(
            card_id="dc_illegal_publish",
            evidence_card_id="ec_invariant_direct",
            evidence_card_version=1,
            story_id="story_cannes_palme",
            policy_versions={
                "editorial_rules_version": "1.0.0",
                "authority_map_version": "1.0.0",
                "iran_exceptions_version": "1.0.0",
                "content_taxonomy_version": "1.0.0",
                "source_registry_version": "1.0.0",
                "entity_registry_version": "1.0.0",
            },
            hard_gates=HardGatesEvaluation(
                duplicate=GateResult(status=GateStatus.FAIL, reason="Duplicate detected", checked_at=now_iso),
                commercial_only=GateResult(status=GateStatus.PASS_, reason="Non-commercial", checked_at=now_iso),
                iranian_daily_news=GateResult(status=GateStatus.PASS_, reason="International", checked_at=now_iso),
                unverified_claim=GateResult(status=GateStatus.PASS_, reason="Verified", checked_at=now_iso),
                image_provenance=GateResult(status=GateStatus.PASS_, reason="Valid provenance", checked_at=now_iso),
                source_requirement=GateResult(status=GateStatus.PASS_, reason="Sources satisfied", checked_at=now_iso),
            ),
            editorial_signals=EditorialSignals(
                evidence_strength=0.9,
                editorial_fit=0.9,
                recency=0.8,
                major_festival=True,
                major_award=False,
                major_retrospective=False,
            ),
            rule_evaluations=[],
            decision=EditorialDecisionType.PUBLISH,  # Illegal!
            decision_reason="Attempted bypass",
            publication_plan=PublicationPlan(
                content_type=ContentType.CINEMA,
                format=PublicationFormat.NEWS_BRIEF,
                character_budget=CharacterBudget(min=100, target=200, max=300),
            ),
            story_action=StoryActionType.NEW_POST,
            story_state=StoryStateType.NEW,
            validation=ValidationSummary(
                is_valid=False,
                policy_valid=False,
                evidence_sufficient=True,
                decision_consistent=False,
                publication_plan_valid=True,
                character_budget_valid=True,
                conflicts_resolved=True,
            ),
            audit={
                "evaluated_at": "2026-09-20T00:00:00Z",
                "editorial_rules_version": "1.0.0",
                "authority_map_version": "1.0.0",
                "source_registry_version": "1.0.0",
                "entity_registry_version": "1.0.0",
                "content_taxonomy_version": "1.0.0",
                "iran_exceptions_version": "1.0.0",
                "deterministic_checksum": "dummy_chk",
            },
        )


# --- 3. LLM Independence ---
def test_llm_omission_safe_fallback(test_environment):
    builder = test_environment["builder"]
    engine = test_environment["engine"]

    card = make_sample_card(builder, "ec_no_llm")
    decision_card = engine.evaluate(
        card=card,
        card_id="dc_no_llm",
        llm_assessment=None,  # No LLM provided
    )

    # Engine deterministically decides based on editorial signals and gates
    assert decision_card.llm_assessment is None
    assert decision_card.decision == EditorialDecisionType.PUBLISH
    assert decision_card.validation.is_valid is True


def test_unverified_material_claims_force_hold_even_if_llm_advises_publish(test_environment):
    builder = test_environment["builder"]
    engine = test_environment["engine"]

    card = make_sample_card(builder, "ec_unverified_claim", unverified=True)
    advisory_llm = LLMAssessment(
        recommended_action=EditorialDecisionType.PUBLISH,
        editorial_rationale="Sounds reasonable.",
        uncertainties=[],
    )

    decision_card = engine.evaluate(
        card=card,
        card_id="dc_unverified_hold",
        llm_assessment=advisory_llm,
    )

    assert decision_card.decision == EditorialDecisionType.HOLD
    assert decision_card.publication_plan is None
    assert decision_card.validation.evidence_sufficient is False
    assert decision_card.validation.is_valid is False
    all_notes = decision_card.validation.validator_notes + decision_card.validation.overrides_applied
    assert any("hold" in note.lower() or "overridden" in note.lower() for note in all_notes)


def test_unresolved_conflicts_force_hold(test_environment):
    builder = test_environment["builder"]
    engine = test_environment["engine"]

    card = make_sample_card(builder, "ec_conflict_card", conflict=True)
    decision_card = engine.evaluate(
        card=card,
        card_id="dc_conflict_hold",
    )

    assert decision_card.decision == EditorialDecisionType.HOLD
    assert decision_card.validation.conflicts_resolved is False
    assert decision_card.validation.is_valid is False


# --- 4. Story Identity & Change Logic ---
def test_story_action_mapping_for_various_states():
    # New story
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.NEW) == StoryActionType.NEW_POST
    assert determine_story_action(EditorialDecisionType.HOLD, StoryStateType.NEW) == StoryActionType.NO_PUBLICATION
    assert determine_story_action(EditorialDecisionType.REJECT, StoryStateType.NEW) == StoryActionType.NO_PUBLICATION

    # Update story
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.UPDATE, update_as_reply=False) == StoryActionType.EDIT_EXISTING
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.UPDATE, update_as_reply=True) == StoryActionType.REPLY

    # Correction & Retraction
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.CORRECTION) == StoryActionType.CORRECTION_NOTICE
    assert determine_story_action(EditorialDecisionType.HOLD, StoryStateType.RETRACTION) == StoryActionType.RETRACTION_NOTICE


# --- 5. Publication Planning & Budgets ---
def test_publication_plan_character_budget(test_environment):
    builder = test_environment["builder"]
    engine = test_environment["engine"]

    card = make_sample_card(builder, "ec_plan_test")
    decision_card = engine.evaluate(
        card=card,
        card_id="dc_plan_test",
        format_type=PublicationFormat.NEWS_BRIEF,
    )

    assert decision_card.decision == EditorialDecisionType.PUBLISH
    assert decision_card.publication_plan is not None
    budget = decision_card.publication_plan.character_budget
    assert budget.min <= budget.target <= budget.max
    assert decision_card.validation.publication_plan_valid is True
    assert decision_card.validation.character_budget_valid is True


# --- 6. Human Override Support & Invariants ---
def test_human_override_applies_when_gates_pass(test_environment):
    builder = test_environment["builder"]
    engine = test_environment["engine"]

    card = make_sample_card(builder, "ec_override_test")
    override = HumanOverride(
        overridden_by="editor_sarah",
        overridden_at="2026-09-20T10:00:00Z",
        original_decision=EditorialDecisionType.PUBLISH,
        overridden_decision=EditorialDecisionType.HOLD,
        override_reason="Pending editorial board verification of filmmaker quotes.",
    )

    decision_card = engine.evaluate(
        card=card,
        card_id="dc_override_test",
        human_override=override,
    )

    assert decision_card.decision == EditorialDecisionType.HOLD
    assert decision_card.audit.human_override is not None
    assert decision_card.audit.human_override.overridden_by == "editor_sarah"
    assert "Human override applied" in decision_card.decision_reason


def test_human_override_cannot_bypass_hard_gates_to_force_publish(test_environment):
    builder = test_environment["builder"]
    engine = test_environment["engine"]

    card = make_sample_card(builder, "ec_override_gate_test")
    override = HumanOverride(
        overridden_by="rogue_editor",
        overridden_at="2026-09-20T10:00:00Z",
        original_decision=EditorialDecisionType.REJECT,
        overridden_decision=EditorialDecisionType.PUBLISH,
        override_reason="I want to publish this anyway.",
        allow_hard_gate_override=False,
    )

    decision_card = engine.evaluate(
        card=card,
        card_id="dc_override_gate_test",
        is_duplicate=True,  # Hard gate fails!
        human_override=override,
    )

    # Invariant: Human override to 'publish' is rejected because hard gates failed
    assert decision_card.decision == EditorialDecisionType.REJECT
    assert any("REJECTED" in o for o in decision_card.validation.overrides_applied)


# --- 7. Determinism ---
def test_decision_determinism(test_environment):
    builder = test_environment["builder"]
    engine = test_environment["engine"]

    card = make_sample_card(builder, "ec_determinism_test")
    fixed_time = "2026-09-20T12:00:00Z"

    d1 = engine.evaluate(
        card=card,
        card_id="dc_determinism_test",
        evaluated_at=fixed_time,
    )
    d2 = engine.evaluate(
        card=card,
        card_id="dc_determinism_test",
        evaluated_at=fixed_time,
    )

    assert d1.audit.deterministic_checksum == d2.audit.deterministic_checksum
    assert d1.model_dump() == d2.model_dump()
