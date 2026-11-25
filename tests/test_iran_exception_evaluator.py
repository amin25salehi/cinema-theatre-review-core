"""
Tests for Iranian Exception Evaluator
Verifies deterministic matching of allowed international exceptions with source tier ceilings
and immediate rejection of domestic/disallowed topics regardless of entity stature.
"""

from editorial.iran_exception_evaluator import IranianExceptionEvaluator
from evidence.claim_builder import ClaimBuilder
from evidence.evidence_builder import EvidenceBuilder
from evidence.evidence_card_builder import EvidenceCardBuilder
from loaders.config_loader import ConfigLoader
from loaders.source_loader import SourceLoader
from schemas.evidence_card import (
    ClaimStatus,
    EntityReference,
    EvidenceRelation,
)


def test_iran_exception_rejects_disallowed_category():
    config_loader = ConfigLoader()
    policy = config_loader.load_iran_exceptions()
    sources = SourceLoader().load_all_sources()
    authority_map = config_loader.load_authority_map()
    builder = EvidenceCardBuilder(authority_map, sources)

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_box_office",
        claim_type="festival_selection",
        subject_entity_id="director_abbas_kiarostami",
        claim_text="Domestic box office milestone.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com",
        evidence_type="news",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_box_office"],
        excerpt="Box office report.",
    )
    # Target topic contains disallowed keyword 'domestic_box_office'
    card = builder.build_card(
        card_id="ec_iran_disallowed",
        story_id="story_ir_01",
        headline_working="Domestic Box Office Milestone",
        target_topic="domestic_box_office",
        entities=[EntityReference(entity_id="director_abbas_kiarostami", name="Abbas Kiarostami", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )

    evaluator = IranianExceptionEvaluator(policy, sources)
    eval_res = evaluator.evaluate(card, is_iranian_context=True)

    assert eval_res.matched is False
    assert any("disallowed category" in note for note in eval_res.evaluation_notes)


def test_iran_exception_qualifies_major_international_award_with_tier_1_source():
    config_loader = ConfigLoader()
    policy = config_loader.load_iran_exceptions()
    sources = SourceLoader().load_all_sources()
    authority_map = config_loader.load_authority_map()
    builder = EvidenceCardBuilder(authority_map, sources)

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_palme_dor",
        claim_type="award_conferral",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Palme d'Or awarded at 50th Cannes Film Festival.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    # Tier 1 source: src_cannes_official
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_palme_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/palme-1997",
        evidence_type="official_communique",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_palme_dor"],
        excerpt="Taste of Cherry awarded Palme d'Or.",
    )
    card = builder.build_card(
        card_id="ec_iran_palme",
        story_id="story_ir_palme",
        headline_working="Taste of Cherry Wins Palme d'Or",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )

    evaluator = IranianExceptionEvaluator(policy, sources)
    eval_res = evaluator.evaluate(card, is_iranian_context=True)

    assert eval_res.matched is True
    assert eval_res.exception_code == "major_international_award"
    assert eval_res.required_tier == 1


def test_iran_exception_rejects_when_source_tier_is_insufficient():
    config_loader = ConfigLoader()
    policy = config_loader.load_iran_exceptions()
    sources = SourceLoader().load_all_sources()
    authority_map = config_loader.load_authority_map()
    builder = EvidenceCardBuilder(authority_map, sources)

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_palme_weak_src",
        claim_type="award_conferral",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Palme d'Or awarded at Cannes.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    # src_theatre_record is Tier 3 (not Tier 1)
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_weak_tier",
        source_id="src_theatre_record",
        source_url="https://theatrerecord.org",
        evidence_type="review",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_palme_weak_src"],
        excerpt="Mention of award.",
    )
    card = builder.build_card(
        card_id="ec_iran_weak_tier",
        story_id="story_ir_weak",
        headline_working="Award with Weak Tier Source",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )

    evaluator = IranianExceptionEvaluator(policy, sources)
    eval_res = evaluator.evaluate(card, is_iranian_context=True)

    # Must NOT match because required tier is 1, but source tier is 3
    assert eval_res.matched is False
