"""
Unit & Integration Tests - Stage 8.8 LLM Context Projection
Validates:
1. Story Context metadata projection.
2. Distinct claims partition (trusted_claims, unresolved_claims, contradicted_claims).
3. Provenance and conflict preservation.
4. Bounding metadata and truncation limits.
5. Strict validation via LLMContextProjectionValidator.
6. Forbidden editorial fields rejection.
7. Determinism and canonical hash stability.
"""

import pytest
from evidence.claim_builder import ClaimBuilder
from evidence.evidence_builder import EvidenceBuilder
from evidence.evidence_card_builder import EvidenceCardBuilder
from loaders.config_loader import ConfigLoader
from loaders.entity_loader import EntityLoader
from loaders.source_loader import SourceLoader
from projection import (
    LLMContextProjectionBuilder,
    LLMContextProjector,
    LLMContextProjectionValidator,
    ProjectionBounds,
    ProjectionValidationError,
)
from schemas.context_projection import (
    BoundingMetadata,
    LLMContextProjection,
    ProjectedStoryContext,
    ProjectionTaskType,
)
from schemas.evidence_card import (
    ClaimStatus,
    ConflictItem,
    ConflictStatus,
    EntityReference,
    EvidenceRelation,
)


@pytest.fixture
def test_setup():
    config_loader = ConfigLoader()
    authority_map = config_loader.load_authority_map()
    sources = SourceLoader().load_all_sources()
    entities = EntityLoader().load_all_entities()
    card_builder = EvidenceCardBuilder(authority_map, sources)
    return authority_map, sources, entities, card_builder


def test_story_context_and_claim_partitions(test_setup):
    _, sources, entities, card_builder = test_setup

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
        subject_entity_id="person_abbas_kiarostami",
        claim_text="Unconfirmed rumor that director started a new production.",
        status=ClaimStatus.UNVERIFIED,
        material=True,
    )
    c_contra = ClaimBuilder.create_claim(
        claim_id="clm_contra",
        claim_type="award_conferral",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Disputed award outcome.",
        status=ClaimStatus.CONTRADICTED,
        material=False,
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
        excerpt="Official festival statement disputing the award outcome.",
    )

    card = card_builder.build_card(
        card_id="ec_story_claims_test",
        story_id="story_cannes_97",
        headline_working="Taste of Cherry at Cannes",
        target_topic="cinema_festival",
        entities=[
            EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject"),
            EntityReference(entity_id="person_abbas_kiarostami", name="Abbas Kiarostami", role="director"),
        ],
        claims=[c_verified, c_unverified, c_contra],
        evidence=[ev1, ev_contra],
    )

    proj = LLMContextProjector.project_card(
        evidence_card=card,
        sources=sources,
        entities=entities,
    )

    # 1. Story Context check
    assert isinstance(proj.story_context, ProjectedStoryContext)
    assert proj.story_context.story_id == "story_cannes_97"
    assert proj.story_context.headline_working == "Taste of Cherry at Cannes"
    assert proj.story_context.target_topic == "cinema_festival"
    assert proj.story_context.created_at == card.identity.created_at

    # 2. Separated claims lists check
    trusted_ids = {c.claim_id for c in proj.trusted_claims}
    unresolved_ids = {c.claim_id for c in proj.unresolved_claims}
    contradicted_ids = {c.claim_id for c in proj.contradicted_claims}

    assert trusted_ids == {"clm_verified"}
    assert unresolved_ids == {"clm_unverified"}
    assert contradicted_ids == {"clm_contra"}

    # Disjointness
    assert len(trusted_ids & unresolved_ids) == 0
    assert len(trusted_ids & contradicted_ids) == 0
    assert len(unresolved_ids & contradicted_ids) == 0

    # 3. Provenance on claims check
    verified_proj_claim = proj.trusted_claims[0]
    assert "ev_01" in verified_proj_claim.provenance_evidence_ids
    assert verified_proj_claim.authority_status == "confirmed"

    # 4. Validator check
    valid, errors = LLMContextProjectionValidator.validate_projection(proj, sources, entities)
    assert valid, f"Validation errors: {errors}"


def test_conflict_preservation_and_bounding_metadata(test_setup):
    _, sources, entities, card_builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_conflict",
        claim_type="award_conferral",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry won the Palme d'Or unanimously.",
        status=ClaimStatus.SUPPORTED,
        material=True,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_conf_1",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com/palme",
        evidence_type="press_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_conflict"],
        excerpt="Palme d'Or awarded jointly with Unagi.",
    )
    ev2 = EvidenceBuilder.create_evidence(
        evidence_id="ev_conf_2",
        source_id="src_cahiers_du_cinema",
        source_url="https://cahiersducinema.com/cannes-palme",
        evidence_type="article",
        relation=EvidenceRelation.CONTRADICTS,
        claim_refs=["clm_conflict"],
        excerpt="The jury was split; award was not unanimous.",
    )

    conflict = ConflictItem(
        conflict_id="conf_01",
        claim_id="clm_conflict",
        type="factual_contradiction",
        evidence_refs=["ev_conf_1", "ev_conf_2"],
        status=ConflictStatus.UNRESOLVED,
    )

    card = card_builder.build_card(
        card_id="ec_conflict_test",
        story_id="story_conflict_test",
        headline_working="Palme d'Or Decision",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1, ev2],
        conflicts=[conflict],
    )

    proj = LLMContextProjector.project_card(
        evidence_card=card,
        sources=sources,
        entities=entities,
    )

    # Because conflict is unresolved on clm_conflict, it MUST NOT be trusted!
    assert len(proj.trusted_claims) == 0
    assert len(proj.unresolved_claims) == 1
    assert proj.unresolved_claims[0].claim_id == "clm_conflict"

    # Check projected conflicts
    assert len(proj.relevant_conflicts) == 1
    p_conf = proj.relevant_conflicts[0]
    assert p_conf.conflict_id == "conf_01"
    assert p_conf.claim_id == "clm_conflict"
    assert p_conf.conflict_status == "unresolved"
    assert set(p_conf.source_ids) == {"src_cannes_official", "src_cahiers_du_cinema"}

    # Bounding metadata
    assert isinstance(proj.bounding_metadata, BoundingMetadata)
    assert proj.bounding_metadata.conflicts_projected == 1
    assert proj.bounding_metadata.claims_projected == 1
    assert proj.bounding_metadata.evidence_projected == 2
    assert proj.bounding_metadata.truncated is False
    assert proj.bounding_metadata.total_context_chars > 0

    # Validator passes
    LLMContextProjectionValidator.assert_valid(proj, sources, entities)


def test_validator_detects_tampered_checksum(test_setup):
    _, sources, entities, card_builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Film selected.",
        status=ClaimStatus.SUPPORTED,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com",
        evidence_type="press_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_01"],
        excerpt="Confirmed.",
    )
    card = card_builder.build_card(
        card_id="ec_tamper_test",
        story_id="story_tamper",
        headline_working="Headline",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )
    proj = LLMContextProjector.project_card(card, sources, entities)

    # Tamper with checksum
    tampered_proj = proj.model_copy(update={"integrity_checksum": "tampered_hash_value"})
    valid, errors = LLMContextProjectionValidator.validate_projection(
        tampered_proj, sources, entities
    )
    assert not valid
    assert any("Checksum mismatch" in err for err in errors)

    with pytest.raises(ProjectionValidationError):
        LLMContextProjectionValidator.assert_valid(tampered_proj, sources, entities)


def test_validator_detects_unknown_entity_and_source(test_setup):
    _, sources, entities, card_builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Film selected.",
        status=ClaimStatus.SUPPORTED,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com",
        evidence_type="press_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_01"],
        excerpt="Confirmed.",
    )
    card = card_builder.build_card(
        card_id="ec_fk_test",
        story_id="story_fk",
        headline_working="Headline",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )
    proj = LLMContextProjector.project_card(card, sources, entities)

    # Validate against empty entities registry
    valid, errors = LLMContextProjectionValidator.validate_projection(proj, sources, {})
    assert not valid
    assert any("Entity FK violation" in err for err in errors)

    # Validate against empty sources registry
    valid, errors = LLMContextProjectionValidator.validate_projection(proj, {}, entities)
    assert not valid
    assert any("Source FK violation" in err for err in errors)


def test_deterministic_projection_stability(test_setup):
    _, sources, entities, card_builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Film selected.",
        status=ClaimStatus.SUPPORTED,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com",
        evidence_type="press_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_01"],
        excerpt="Confirmed.",
    )
    card = card_builder.build_card(
        card_id="ec_stable_test",
        story_id="story_stable",
        headline_working="Headline",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )

    proj1 = LLMContextProjector.project_card(card, sources, entities)
    proj2 = LLMContextProjector.project_card(card, sources, entities)

    assert proj1.integrity_checksum == proj2.integrity_checksum
    assert proj1.model_dump() == proj2.model_dump()


def test_validator_rejects_forbidden_editorial_fields(test_setup):
    _, sources, entities, card_builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Film selected.",
        status=ClaimStatus.SUPPORTED,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com",
        evidence_type="press_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_01"],
        excerpt="Confirmed.",
    )
    card = card_builder.build_card(
        card_id="ec_forbidden_test",
        story_id="story_forbidden",
        headline_working="Headline",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )
    proj = LLMContextProjector.project_card(card, sources, entities)

    # Test static validator function for forbidden fields
    assert LLMContextProjectionValidator._find_forbidden_keys({"publication_decision": "PUBLISH"}) == {"publication_decision"}
    assert LLMContextProjectionValidator._find_forbidden_keys({"nested": {"editorial_fit": 0.9}}) == {"editorial_fit"}
    assert LLMContextProjectionValidator._find_forbidden_keys({"quality_score": 10}) == {"quality_score"}


def test_validator_detects_provenance_failure(test_setup):
    _, sources, entities, card_builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Film selected.",
        status=ClaimStatus.SUPPORTED,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com",
        evidence_type="press_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_01"],
        excerpt="Confirmed.",
    )
    card = card_builder.build_card(
        card_id="ec_provenance_test",
        story_id="story_provenance",
        headline_working="Headline",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )
    proj = LLMContextProjector.project_card(card, sources, entities)

    # Remove all authoritative evidence to trigger provenance failure
    broken_proj = proj.model_copy(update={"authoritative_evidence": []})
    valid, errors = LLMContextProjectionValidator.validate_projection(broken_proj, sources, entities)
    assert not valid
    assert any("Provenance failure" in err for err in errors)


def test_truncation_flag_and_bounds_metadata(test_setup):
    _, sources, entities, card_builder = test_setup

    c1 = ClaimBuilder.create_claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Film selected.",
        status=ClaimStatus.SUPPORTED,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes_official",
        source_url="https://festival-cannes.com",
        evidence_type="press_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_01"],
        excerpt="A" * 600,
    )
    card = card_builder.build_card(
        card_id="ec_trunc_test",
        story_id="story_trunc",
        headline_working="Headline",
        target_topic="cinema_festival",
        entities=[EntityReference(entity_id="film_taste_of_cherry", name="Taste of Cherry", role="subject")],
        claims=[c1],
        evidence=[ev1],
    )
    bounds = ProjectionBounds(max_excerpt_chars_per_source=100)
    proj = LLMContextProjector.project_card(card, sources, entities, bounds=bounds)

    assert proj.bounding_metadata.excerpts_truncated is True
    assert proj.bounding_metadata.truncated is True
