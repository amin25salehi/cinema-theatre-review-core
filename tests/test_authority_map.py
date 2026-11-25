"""
Unit Tests - Authority Map
Tests claim-level authority resolution, preferred sources, and primary vs secondary classes.
"""

from evidence.claim_builder import ClaimBuilder
from evidence.evidence_builder import EvidenceBuilder
from evidence.evidence_card_builder import EvidenceCardBuilder
from loaders.config_loader import ConfigLoader
from loaders.source_loader import SourceLoader
from schemas.evidence_card import AuthorityStatus, ClaimStatus, EvidenceRelation


def test_authority_resolution_primary():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    sources = SourceLoader().load_all_sources()

    builder = EvidenceCardBuilder(authority_map, sources)

    claim = ClaimBuilder.create_claim(
        claim_id="clm_cannes_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry was in official Cannes competition.",
        status=ClaimStatus.SUPPORTED,
    )

    # Official Cannes festival source (primary authority)
    ev_cannes = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/archive/1997",
        evidence_type="festival_catalog",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_cannes_01"],
        excerpt="Taste of Cherry directed by Abbas Kiarostami in official competition.",
    )

    resolution = builder.resolve_claim_authority(claim, [ev_cannes])
    assert resolution.status == AuthorityStatus.CONFIRMED
    assert resolution.preferred_source_id == "src_cannes_official"


def test_authority_resolution_insufficient():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    sources = SourceLoader().load_all_sources()

    builder = EvidenceCardBuilder(authority_map, sources)

    claim = ClaimBuilder.create_claim(
        claim_id="clm_restoration_01",
        claim_type="archival_restoration",
        subject_entity_id="film_taste_of_cherry",
        claim_text="A new 4K restoration is premiering.",
    )

    # If evidence only comes from an unauthoritative source class (e.g. general publisher)
    ev_pub = EvidenceBuilder.create_evidence(
        evidence_id="ev_02",
        source_id="src_bloomsbury_methuen",
        source_url="https://bloomsbury.com/book",
        evidence_type="publisher_announcement",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_restoration_01"],
        excerpt="Restoration mentioned in book footnote.",
    )

    resolution = builder.resolve_claim_authority(claim, [ev_pub])
    assert resolution.status == AuthorityStatus.INSUFFICIENT
