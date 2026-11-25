"""
Unit Tests - Core Schemas
Validates Pydantic v2 models, strict extra="forbid" behavior, and identifier regex.
"""

import pytest
from pydantic import ValidationError

from schemas.entity_registry import (
    EntityProfile,
    EntityStatus,
    EntityType,
    IdentityStatus,
)
from schemas.evidence_card import Claim, ClaimStatus
from schemas.source_registry import SourceProfile, SourceRole


def test_source_profile_id_validation():
    # Valid source ID
    profile = SourceProfile(
        source_id="src_cannes_official",
        name="Cannes Film Festival",
        domain="festival-cannes.com",
        source_class="festival_primary",
        tier=1,
        region="europe",
        language="fr",
        roles=[SourceRole.AUTHORITY],
        authoritative_claims=["festival_selection"],
        not_authoritative_for=[],
        acquisition_method="rss",
        canonical_url="https://festival-cannes.com",
    )
    assert profile.source_id == "src_cannes_official"

    # Invalid source ID (spaces or uppercase)
    with pytest.raises(ValidationError):
        SourceProfile(
            source_id="src Cannes Invalid",
            name="Cannes",
            domain="cannes.com",
            source_class="festival_primary",
            tier=1,
            region="europe",
            language="fr",
            roles=[SourceRole.AUTHORITY],
            authoritative_claims=[],
            not_authoritative_for=[],
            acquisition_method="rss",
            canonical_url="https://cannes.com",
        )


def test_schema_strictness_extra_forbid():
    # Attempting to pass extra fields must raise ValidationError
    with pytest.raises(ValidationError):
        SourceProfile(
            source_id="src_test",
            name="Test",
            domain="test.com",
            source_class="critical_journal",
            tier=1,
            region="europe",
            language="en",
            roles=[SourceRole.AUTHORITY],
            authoritative_claims=[],
            not_authoritative_for=[],
            acquisition_method="rss",
            canonical_url="https://test.com",
            unauthorized_field="unexpected_value",
        )


def test_entity_profile_provenance_requirement():
    # A reference entity without provenance must fail validation
    with pytest.raises(ValidationError) as exc_info:
        EntityProfile(
            entity_id="person_test_director",
            name="Test Director",
            entity_type=EntityType.FILMMAKER,
            status=EntityStatus.REFERENCE,
            identity_status=IdentityStatus.CONFIRMED,
            provenance=[],  # Empty provenance for reference entity!
        )
    assert "provenance" in str(exc_info.value)

    # A local entity without provenance is allowed
    local_ent = EntityProfile(
        entity_id="local_person_999",
        name="Local Stage Actor",
        entity_type=EntityType.ACTOR,
        status=EntityStatus.LOCAL,
        identity_status=IdentityStatus.PROVISIONAL,
        provenance=[],
    )
    assert local_ent.status == EntityStatus.LOCAL


def test_claim_model():
    claim = Claim(
        claim_id="clm_01",
        claim_type="festival_selection",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Taste of Cherry was selected for the Cannes competition in 1997.",
        status=ClaimStatus.SUPPORTED,
        material=True,
        verification_required=True,
        evidence_refs=["ev_01"],
    )
    assert claim.material is True
    assert claim.status == ClaimStatus.SUPPORTED
