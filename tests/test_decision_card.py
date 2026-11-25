"""
Unit Tests - Editorial Decision Card
Tests deterministic hard gates, signal calculations, character budgets,
and the key invariant: LLM recommendation != Final Decision.
"""

from editorial.decision_engine import EditorialDecisionEngine
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
    LLMAssessment,
)
from schemas.evidence_card import ClaimStatus, EvidenceRelation


def test_llm_cannot_override_failed_hard_gate():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    editorial_rules = config_loader.load_editorial_rules()
    iran_exceptions = config_loader.load_iran_exceptions()
    sources = SourceLoader().load_all_sources()
    entities = EntityLoader().load_all_entities()

    builder = EvidenceCardBuilder(authority_map, sources)
    rule_engine = EditorialRuleEngine(editorial_rules, iran_exceptions, entities)
    decision_engine = EditorialDecisionEngine(rule_engine)

    # Claim is unverified (status = UNVERIFIED)
    unverified_claim = ClaimBuilder.create_claim(
        claim_id="clm_unverified_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Unverified festival rumor.",
        status=ClaimStatus.UNVERIFIED,
        material=True,
        verification_required=True,
    )

    ev_weak = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_theatre_record",
        source_url="https://example.com",
        evidence_type="blog",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_unverified_01"],
        excerpt="Rumored festival inclusion.",
    )

    card = builder.build_card(
        card_id="ec_unverified_story",
        story_id="story_unverified",
        headline_working="Rumored Story",
        target_topic="cinema_festival",
        entities=[],
        claims=[unverified_claim],
        evidence=[ev_weak],
    )

    # LLM mistakenly hallucinates / recommends PUBLISH
    llm_assessment = LLMAssessment(
        recommended_action=EditorialDecisionType.PUBLISH,
        editorial_rationale="This looks exciting and high profile!",
        uncertainties=[],
    )

    decision_card = decision_engine.evaluate(
        card=card,
        card_id="dc_unverified_story",
        llm_assessment=llm_assessment,
    )

    # INVARIANT ENFORCED: Final decision CANNOT be publish!
    assert decision_card.decision != EditorialDecisionType.PUBLISH
    assert decision_card.hard_gates.unverified_claim.status == GateStatus.FAIL
    assert len(decision_card.validation.overrides_applied) > 0


def test_iranian_daily_news_rejection_and_exception_pass():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    editorial_rules = config_loader.load_editorial_rules()
    iran_exceptions = config_loader.load_iran_exceptions()
    sources = SourceLoader().load_all_sources()
    entities = EntityLoader().load_all_entities()

    builder = EvidenceCardBuilder(authority_map, sources)
    rule_engine = EditorialRuleEngine(editorial_rules, iran_exceptions, entities)
    decision_engine = EditorialDecisionEngine(rule_engine)

    claim = ClaimBuilder.create_claim(
        claim_id="clm_iran_01",
        claim_type="festival_selection",
        subject_entity_id="person_asghar_farhadi",
        claim_text="Asghar Farhadi new feature selected at Cannes.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )

    ev = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/selection",
        evidence_type="official",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_iran_01"],
        excerpt="Farhadi in competition.",
    )

    card = builder.build_card(
        card_id="ec_farhadi_cannes",
        story_id="story_farhadi",
        headline_working="Farhadi in Cannes",
        target_topic="cinema_festival",
        entities=[],
        claims=[claim],
        evidence=[ev],
    )

    # 1. Without exception matched -> Rejected by policy
    decision_rejected = decision_engine.evaluate(
        card=card,
        card_id="dc_farhadi_rejected",
        is_iranian_daily_news=True,
        iran_exception_matched=None,
    )
    assert decision_rejected.decision == EditorialDecisionType.REJECT
    assert decision_rejected.hard_gates.iranian_daily_news.status == GateStatus.FAIL

    # 2. With verified exception -> Allowed to pass gate!
    decision_passed = decision_engine.evaluate(
        card=card,
        card_id="dc_farhadi_passed",
        is_iranian_daily_news=True,
        iran_exception_matched="major_festival_selection",
    )
    assert decision_passed.hard_gates.iranian_daily_news.status == GateStatus.PASS_
    assert decision_passed.decision == EditorialDecisionType.PUBLISH
    assert decision_passed.publication_plan is not None
    assert decision_passed.publication_plan.character_budget.target == 350
