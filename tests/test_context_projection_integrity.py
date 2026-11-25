"""
Tests for LLM Context Projection Integrity and Trust Boundaries
Verifies trust boundary enforcement, deterministic excerpt and item bounds, and conflict survival.
"""

from evidence.claim_builder import ClaimBuilder
from evidence.evidence_builder import EvidenceBuilder
from evidence.evidence_card_builder import EvidenceCardBuilder
from loaders.config_loader import ConfigLoader
from loaders.entity_loader import EntityLoader
from loaders.source_loader import SourceLoader
from projection.llm_context import LLMContextProjectionBuilder, ProjectionBounds
from schemas.evidence_card import (
    ClaimStatus,
    EntityReference,
    EvidenceRelation,
)


def test_projection_trust_boundary_unverified_claims_never_in_trusted_facts():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    sources = SourceLoader().load_all_sources()
    entities = EntityLoader().load_all_entities()

    card_builder = EvidenceCardBuilder(authority_map, sources)
    proj_builder = LLMContextProjectionBuilder(sources, entities)

    c_verified = ClaimBuilder.create_claim(
        claim_id="clm_verified",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry was officially screened in Cannes 1997.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    c_unverified = ClaimBuilder.create_claim(
        claim_id="clm_unverified",
        claim_type="production_commencement",
        subject_entity_id="director_abbas_kiarostami",
        claim_text="Unconfirmed rumor that director started a new secret production.",
        status=ClaimStatus.UNVERIFIED,
        material=True,
    )
    c_contradicted = ClaimBuilder.create_claim(
        claim_id="clm_contra",
        claim_type="award_conferral",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Contested claim about award jury votes.",
        status=ClaimStatus.CONTRADICTED,
        material=True,
    )

    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com",
        evidence_type="press_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_verified"],
        excerpt="Official selection confirmed.",
    )
    ev_contra = EvidenceBuilder.create_evidence(
        evidence_id="ev_contra",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/correction",
        evidence_type="official_statement",
        relation=EvidenceRelation.CONTRADICTS,
        claim_refs=["clm_contra"],
        excerpt="Official statement contradicting the award jury claim.",
    )

    card = card_builder.build_card(
        card_id="ec_trust_test",
        story_id="story_tt1",
        headline_working="Trust Boundary Test",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c_verified, c_unverified, c_contradicted],
        evidence=[ev1, ev_contra],
    )

    projection = proj_builder.project("proj_trust_test", card)

    trusted_ids = [fact["claim_id"] for fact in projection.prompt_boundary.trusted_structured_facts]
    unresolved_ids = [fact["claim_id"] for fact in projection.prompt_boundary.unresolved_claims]
    conflicted_ids = [fact["claim_id"] for fact in projection.prompt_boundary.conflicted_claims]

    # TRUST BOUNDARY INVARIANT:
    # Only SUPPORTED claims enter trusted_structured_facts!
    assert "clm_verified" in trusted_ids
    assert "clm_unverified" not in trusted_ids
    assert "clm_contra" not in trusted_ids

    # Unverified appears in unresolved_claims
    assert "clm_unverified" in unresolved_ids

    # Contradicted appears in conflicted_claims
    assert "clm_contra" in conflicted_ids


def test_projection_bounds_enforcement():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    sources = SourceLoader().load_all_sources()
    entities = EntityLoader().load_all_entities()

    card_builder = EvidenceCardBuilder(authority_map, sources)
    proj_builder = LLMContextProjectionBuilder(sources, entities)

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_b1",
        claim_type="critical_assessment",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Deep structural analysis.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )

    # 1200-character excerpt
    long_excerpt = "A" * 1200
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_long_01",
        source_id="src_cahiers_du_cinema",
        source_url="https://cahiersducinema.com/review",
        evidence_type="essay",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_b1"],
        excerpt=long_excerpt,
    )

    card = card_builder.build_card(
        card_id="ec_bounds_test",
        story_id="story_bt1",
        headline_working="Bounds Test",
        target_topic="discourse_criticism",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )

    # Tight bounds: max 200 chars per source excerpt
    custom_bounds = ProjectionBounds(
        max_excerpt_chars_per_source=200,
        max_total_excerpt_chars=500,
        max_evidence_items=5,
        max_claims=5,
    )

    projection = proj_builder.project("proj_bounds_test", card, bounds=custom_bounds)

    assert len(projection.prompt_boundary.untrusted_source_excerpts) == 1
    projected_content = projection.prompt_boundary.untrusted_source_excerpts[0].content

    # Must be truncated to at most 200 + length of suffix
    assert len(projected_content) <= 225
    assert "[truncated]" in projected_content
