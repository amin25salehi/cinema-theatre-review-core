"""
Unit Tests - Evidence Card
Tests evidence card assembly, integrity hashes, and conflict detection.
"""

from evidence.claim_builder import ClaimBuilder
from evidence.evidence_builder import EvidenceBuilder
from evidence.evidence_card_builder import EvidenceCardBuilder
from loaders.config_loader import ConfigLoader
from loaders.source_loader import SourceLoader
from schemas.evidence_card import (
    ClaimStatus,
    ConflictStatus,
    EntityReference,
    EvidenceRelation,
)


def test_evidence_card_building_and_integrity_hash():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    sources = SourceLoader().load_all_sources()

    builder = EvidenceCardBuilder(authority_map, sources)

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry was officially screened in competition.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )

    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/selection/1997",
        evidence_type="official_press_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_01"],
        excerpt="Official Cannes Selection: Taste of Cherry by Abbas Kiarostami.",
    )

    entities = [
        EntityReference(
            entity_id="film_taste_of_cherry",
            name="Taste of Cherry",
            role="subject",
        )
    ]

    card = builder.build_card(
        card_id="ec_taste_of_cherry_cannes",
        story_id="story_toc_1997",
        headline_working="Taste of Cherry in Cannes Competition",
        target_topic="cinema_festival",
        entities=entities,
        claims=[c1],
        evidence=[ev1],
    )

    assert card.identity.card_id == "ec_taste_of_cherry_cannes"
    assert card.integrity.card_hash is not None
    assert len(card.integrity.card_hash) == 64  # SHA-256
    assert card.integrity.source_count == 1
    assert len(card.authority_resolution) == 1
    assert card.authority_resolution[0].claim_id == "clm_01"


def test_conflict_detection():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    sources = SourceLoader().load_all_sources()

    builder = EvidenceCardBuilder(authority_map, sources)

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_date_01",
        claim_type="book_publication_date",
        subject_entity_id="play_waiting_for_godot",
        claim_text="The critical monograph was released in October 2026.",
        material=True,
    )

    ev_supp = EvidenceBuilder.create_evidence(
        evidence_id="ev_s1",
        source_id="src_bloomsbury_methuen",
        source_url="https://bloomsbury.com/book/godot",
        evidence_type="catalog",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_date_01"],
        excerpt="Publication scheduled for October 2026.",
    )

    ev_contra = EvidenceBuilder.create_evidence(
        evidence_id="ev_c1",
        source_id="src_faber_drama",
        source_url="https://faber.co.uk/news",
        evidence_type="press_release",
        relation=EvidenceRelation.CONTRADICTS,
        claim_refs=["clm_date_01"],
        excerpt="Publication was delayed to 2027.",
    )

    card = builder.build_card(
        card_id="ec_conflict_test",
        story_id="story_conflict",
        headline_working="Publication date conflict test",
        target_topic="theatre_publication",
        entities=[],
        claims=[c1],
        evidence=[ev_supp, ev_contra],
    )

    assert len(card.conflicts) == 1
    assert card.conflicts[0].claim_id == "clm_date_01"
    assert card.conflicts[0].status == ConflictStatus.UNRESOLVED
