"""
Tests for Editorial Rules, Hard Gates, and Story Action Consistency
Verifies dynamic gate configuration, source class requirements, story action mappings,
and ValidationSummary truthfulness.
"""

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
    EditorialDecisionType,
    GateStatus,
    StoryActionType,
    StoryStateType,
)
from schemas.evidence_card import (
    ClaimStatus,
    EntityReference,
    EvidenceRelation,
)


def test_hard_gate_disabled_in_config_becomes_not_applicable():
    config_loader = ConfigLoader()
    rules = config_loader.load_editorial_rules().model_dump()
    iran_exceptions = config_loader.load_iran_exceptions().model_dump()
    entities = EntityLoader().load_all_entities()
    sources = SourceLoader().load_all_sources()
    authority_map = config_loader.load_authority_map()

    # Disable commercial only gate in config
    rules["hard_gates"]["commercial_only_filter"]["enabled"] = False

    rule_engine = EditorialRuleEngine(rules, iran_exceptions, entities)
    builder = EvidenceCardBuilder(authority_map, sources)

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Screened in competition.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com",
        evidence_type="official",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_01"],
        excerpt="Confirmed.",
    )
    card = builder.build_card(
        card_id="ec_gate_test",
        story_id="story_g1",
        headline_working="Gate Test",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )

    # Even if is_commercial_only=True, the gate was disabled in config, so it must be NOT_APPLICABLE
    gates = rule_engine.evaluate_hard_gates(card, is_commercial_only=True)
    assert gates.commercial_only.status == GateStatus.NOT_APPLICABLE


def test_gate_6_source_requirement_fails_on_zero_sources():
    config_loader = ConfigLoader()
    rules = config_loader.load_editorial_rules()
    iran_exceptions = config_loader.load_iran_exceptions().model_dump()
    entities = EntityLoader().load_all_entities()
    sources = SourceLoader().load_all_sources()
    authority_map = config_loader.load_authority_map()

    rule_engine = EditorialRuleEngine(rules, iran_exceptions, entities)
    builder = EvidenceCardBuilder(authority_map, sources)

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_nosrc_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Rumored selection without sources.",
        status=ClaimStatus.UNVERIFIED,
        material=True,
    )
    # No evidence provided
    card = builder.build_card(
        card_id="ec_nosrc_test",
        story_id="story_ns1",
        headline_working="No Source Story",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[],
    )

    gates = rule_engine.evaluate_hard_gates(card)
    assert gates.source_requirement.status == GateStatus.FAIL
    assert "Zero sources provided" in gates.source_requirement.reason


def test_story_action_consistency_mapping():
    # Publish decisions
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.NEW) == StoryActionType.NEW_POST
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.UPDATE, update_as_reply=False) == StoryActionType.EDIT_EXISTING
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.UPDATE, update_as_reply=True) == StoryActionType.REPLY
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.FOLLOW_UP) == StoryActionType.REPLY
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.CORRECTION) == StoryActionType.CORRECTION_NOTICE
    assert determine_story_action(EditorialDecisionType.PUBLISH, StoryStateType.RETRACTION) == StoryActionType.RETRACTION_NOTICE

    # Hold / Reject decisions
    assert determine_story_action(EditorialDecisionType.HOLD, StoryStateType.NEW) == StoryActionType.NO_PUBLICATION
    assert determine_story_action(EditorialDecisionType.REJECT, StoryStateType.NEW) == StoryActionType.NO_PUBLICATION
    assert determine_story_action(EditorialDecisionType.HOLD, StoryStateType.RETRACTION) == StoryActionType.RETRACTION_NOTICE


def test_validation_summary_truthfulness():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    sources = SourceLoader().load_all_sources()
    entities = EntityLoader().load_all_entities()
    editorial_rules = config_loader.load_editorial_rules()
    iran_exceptions = config_loader.load_iran_exceptions().model_dump()

    builder = EvidenceCardBuilder(authority_map, sources)
    rule_engine = EditorialRuleEngine(editorial_rules, iran_exceptions, entities)
    decision_engine = EditorialDecisionEngine(rule_engine)

    # Card with unverified claim
    c1 = ClaimBuilder.create_claim(
        claim_id="clm_unv_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Unverified claim.",
        status=ClaimStatus.UNVERIFIED,
        material=True,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_theatre_record",
        source_url="https://theatrerecord.org",
        evidence_type="notice",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_unv_01"],
        excerpt="Excerpt.",
    )
    card = builder.build_card(
        card_id="ec_truth_test",
        story_id="story_t1",
        headline_working="Truth Test",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )

    decision_card = decision_engine.evaluate(card, card_id="dc_truth_test")

    # Truthfulness invariant: is_valid must be False because policy_valid and evidence_sufficient are False
    assert decision_card.validation.is_valid is False
    assert decision_card.validation.policy_valid is False
    assert decision_card.validation.evidence_sufficient is False
    assert decision_card.validation.publication_plan_valid is True  # True because plan is None for non-publish
