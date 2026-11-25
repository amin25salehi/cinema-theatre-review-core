"""
Tests for Evidence Card Integrity and Cross-Reference Validation
Enforces strict immutability (Pydantic frozen models) and deterministic referential integrity.
"""

import pytest
from pydantic import ValidationError

from evidence.card_validator import EvidenceCardValidationError, EvidenceCardValidator
from evidence.claim_builder import ClaimBuilder
from evidence.evidence_builder import EvidenceBuilder
from evidence.evidence_card_builder import EvidenceCardBuilder
from loaders.config_loader import ConfigLoader
from loaders.entity_loader import EntityLoader
from loaders.source_loader import SourceLoader
from schemas.evidence_card import (
    ClaimStatus,
    EntityReference,
    EvidenceRelation,
)


@pytest.fixture
def test_setup():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    sources = SourceLoader().load_all_sources()
    entities = EntityLoader().load_all_entities()
    builder = EvidenceCardBuilder(authority_map, sources)
    return authority_map, sources, entities, builder


def test_evidence_card_strict_immutability(test_setup):
    _, sources, _, builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_imm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry screened in competition.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_imm_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/1997",
        evidence_type="official_selection",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_imm_01"],
        excerpt="Official selection confirmed.",
    )
    entities = [
        EntityReference(
            entity_id="film_taste_of_cherry",
            name="Taste of Cherry",
            role="subject",
        )
    ]

    card = builder.build_card(
        card_id="ec_imm_test",
        story_id="story_imm_01",
        headline_working="Immutability Verification",
        target_topic="cinema_festival",
        entities=entities,
        claims=[c1],
        evidence=[ev1],
    )

    # Attempting to modify any field on frozen model must raise ValidationError
    with pytest.raises(ValidationError):
        card.story_context = None

    with pytest.raises(ValidationError):
        card.identity.version = 99

    with pytest.raises(ValidationError):
        card.integrity.card_hash = "tampered_hash"


def test_evidence_card_cross_reference_validator_success(test_setup):
    _, sources, entities, builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_valid_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry in Cannes.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_valid_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/1997",
        evidence_type="official_selection",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_valid_01"],
        excerpt="Official selection confirmed.",
    )
    ent_refs = [
        EntityReference(
            entity_id="film_taste_of_cherry",
            name="Taste of Cherry",
            role="subject",
        )
    ]

    card = builder.build_card(
        card_id="ec_valid_test",
        story_id="story_valid_01",
        headline_working="Valid Card",
        target_topic="cinema_festival",
        entities=ent_refs,
        claims=[c1],
        evidence=[ev1],
    )

    is_valid, errors = EvidenceCardValidator.validate_card(card, entities, sources)
    assert is_valid is True
    assert len(errors) == 0


def test_evidence_card_cross_reference_validator_fails_invalid_entity(test_setup):
    _, sources, entities, builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_err_01",
        claim_type="festival_selection",
        subject_entity_id="film_nonexistent_xyz",  # Does NOT exist in Entity Registry
        claim_text="Nonexistent film in Cannes.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_err_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/1997",
        evidence_type="official_selection",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_err_01"],
        excerpt="Selection confirmed.",
    )
    ent_refs = [
        EntityReference(
            entity_id="film_nonexistent_xyz",
            name="Nonexistent Film",
            role="subject",
        )
    ]

    card = builder.build_card(
        card_id="ec_err_ent_test",
        story_id="story_err_01",
        headline_working="Invalid Entity Card",
        target_topic="cinema_festival",
        entities=ent_refs,
        claims=[c1],
        evidence=[ev1],
    )

    with pytest.raises(EvidenceCardValidationError) as exc_info:
        EvidenceCardValidator.assert_valid(card, entities, sources)

    assert "film_nonexistent_xyz" in str(exc_info.value)


def test_evidence_card_cross_reference_validator_fails_invalid_source(test_setup):
    _, sources, entities, builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_err_02",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry in Cannes.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_err_02",
        source_id="src_fictional_unregistered_outlet",  # Does NOT exist in Source Registry
        source_url="https://fictional.org/1997",
        evidence_type="blog",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_err_02"],
        excerpt="Selection reported.",
    )
    ent_refs = [
        EntityReference(
            entity_id="film_taste_of_cherry",
            name="Taste of Cherry",
            role="subject",
        )
    ]

    card = builder.build_card(
        card_id="ec_err_src_test",
        story_id="story_err_02",
        headline_working="Invalid Source Card",
        target_topic="cinema_festival",
        entities=ent_refs,
        claims=[c1],
        evidence=[ev1],
    )

    with pytest.raises(EvidenceCardValidationError) as exc_info:
        EvidenceCardValidator.assert_valid(card, entities, sources)

    assert "src_fictional_unregistered_outlet" in str(exc_info.value)


def test_evidence_card_cross_reference_validator_fails_broken_claim_evidence_ref(test_setup):
    _, sources, entities, builder = test_setup

    # Claim points to nonexistent evidence id
    c1 = ClaimBuilder.create_claim(
        claim_id="clm_err_03",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry in Cannes.",
        status=ClaimStatus.SUPPORTED,
        material=True,
        evidence_refs=["ev_ghost_999"],  # Does NOT exist in card.evidence
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_real_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/1997",
        evidence_type="official_selection",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_err_03"],
        excerpt="Selection reported.",
    )
    ent_refs = [
        EntityReference(
            entity_id="film_taste_of_cherry",
            name="Taste of Cherry",
            role="subject",
        )
    ]

    card = builder.build_card(
        card_id="ec_err_evref_test",
        story_id="story_err_03",
        headline_working="Broken Evidence Ref Card",
        target_topic="cinema_festival",
        entities=ent_refs,
        claims=[c1],
        evidence=[ev1],
    )

    broken_claim = card.claims[0].model_copy(update={"evidence_refs": ["ev_ghost_999"]})
    broken_card = card.model_copy(update={"claims": [broken_claim]})

    is_valid, errors = EvidenceCardValidator.validate_card(broken_card, entities, sources)
    assert is_valid is False
    assert any("ev_ghost_999" in err for err in errors)
