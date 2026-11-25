"""
Evidence Card Schema - Cinema & Theatre Review Editorial OS v1.0
Strict Pydantic v2 data contract for the canonical, auditable evidence record.
Evidence Card is NOT the editorial decision and NOT the LLM prompt.
"""

import re
from enum import Enum

from pydantic import ConfigDict, Field, field_validator

from schemas.source_registry import StrictModel

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class ImmutableStrictModel(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONTRADICTED = "contradicted"
    UNVERIFIED = "unverified"
    OBSOLETE = "obsolete"


class EvidenceRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    CONTEXT = "context"


class AuthorityStatus(str, Enum):
    CONFIRMED = "confirmed"
    SECONDARY_CONFIRMED = "secondary_confirmed"
    INSUFFICIENT = "insufficient"
    CONFLICTED = "conflicted"
    HOLD = "hold"


class ConflictStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class ImageOfficiality(str, Enum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNKNOWN = "unknown"
    REJECTED = "rejected"


class EvidenceCardIdentity(ImmutableStrictModel):
    card_id: str = Field(..., description="Unique card identifier (e.g. ec_cannes_2026_palme)")
    version: int = Field(default=1, ge=1, description="Sequential snapshot version")
    created_at: str = Field(..., description="ISO timestamp of creation")
    story_id: str = Field(..., description="Stable story grouping identifier")

    @field_validator("card_id", "story_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v


class StoryContext(ImmutableStrictModel):
    headline_working: str = Field(..., description="Working headline in primary editorial language")
    language: str = Field(default="fa", description="Target editorial language")
    target_topic: str = Field(..., description="Primary topic category from content taxonomy")
    summary_draft: str | None = Field(default=None, description="Initial descriptive synopsis")


class EntityReference(ImmutableStrictModel):
    entity_id: str = Field(..., description="Entity foreign key matching entity_registry")
    role: str = Field(..., description="Role in story (e.g. subject, award_winner, director, venue)")
    name: str = Field(..., description="Name representation for this context")
    name_persian: str | None = Field(default=None, description="Persian translation/transliteration")

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"entity_id '{v}' must match ^[a-z0-9_]+$")
        return v


class Claim(ImmutableStrictModel):
    claim_id: str = Field(..., description="Atomic claim identifier (e.g. clm_01)")
    claim_type: str = Field(..., description="Claim predicate type (e.g. festival_selection, won_award)")
    subject_entity_id: str = Field(..., description="Entity ID of claim subject")
    object_entity_id: str | None = Field(default=None, description="Entity ID of claim object (if entity)")
    object_value: str | None = Field(default=None, description="Literal normalized value (if scalar)")
    claim_text: str = Field(..., description="Clear atomic statement of the claim")
    status: ClaimStatus = Field(default=ClaimStatus.UNVERIFIED, description="Current verification state")
    material: bool = Field(default=True, description="Whether this claim is material to publishing")
    verification_required: bool = Field(default=True, description="Whether policy mandates verification before publishing")
    evidence_refs: list[str] = Field(default_factory=list, description="IDs of evidence objects supporting or contradicting this claim")

    @field_validator("claim_id", "claim_type", "subject_entity_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    @field_validator("object_entity_id")
    @classmethod
    def validate_object_entity(cls, v: str | None) -> str | None:
        if v is not None and not ID_PATTERN.match(v):
            raise ValueError(f"object_entity_id '{v}' must match ^[a-z0-9_]+$")
        return v


class EvidenceItem(ImmutableStrictModel):
    evidence_id: str = Field(..., description="Unique evidence identifier (e.g. ev_01)")
    source_id: str = Field(..., description="Foreign key reference to source_registry")
    source_url: str = Field(..., description="Precise URL where evidence was retrieved")
    evidence_type: str = Field(..., description="Format/type (e.g. official_press_release, catalogue_entry, article)")
    relation: EvidenceRelation = Field(..., description="Relation to associated claims (supports/contradicts/qualifies/context)")
    claim_refs: list[str] = Field(..., min_length=1, description="Claim IDs this evidence pertains to")
    excerpt: str = Field(..., description="Direct citation excerpt from the source")
    locator: str | None = Field(default=None, description="CSS selector, page number, or paragraph locator")
    published_at: str | None = Field(default=None, description="ISO timestamp of source publication")
    retrieved_at: str = Field(..., description="ISO timestamp when evidence was fetched")
    content_hash: str = Field(..., description="SHA-256 hash of the retrieved text/payload for snapshot auditing")

    @field_validator("evidence_id", "source_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"source_url '{v}' must be a valid HTTP/HTTPS URL")
        return v


class AuthorityResolutionItem(ImmutableStrictModel):
    claim_id: str = Field(..., description="Target claim ID")
    claim_type: str = Field(..., description="Claim predicate type")
    preferred_authority_classes: list[str] = Field(default_factory=list, description="Authoritative source classes required")
    preferred_source_id: str | None = Field(default=None, description="Specific preferred source ID if applicable")
    status: AuthorityStatus = Field(..., description="Authority verification status")
    rule_applied: str = Field(..., description="Identifier or name of authority rule applied")

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"claim_id '{v}' must match ^[a-z0-9_]+$")
        return v


class ConflictItem(ImmutableStrictModel):
    conflict_id: str = Field(..., description="Unique conflict identifier")
    claim_id: str = Field(..., description="Contested claim ID")
    type: str = Field(..., description="Nature of conflict (factual_contradiction, date_discrepancy, attribution)")
    evidence_refs: list[str] = Field(..., min_length=2, description="Evidence item IDs that conflict")
    status: ConflictStatus = Field(default=ConflictStatus.UNRESOLVED, description="Conflict status")
    preferred_source_id: str | None = Field(default=None, description="Source ID chosen as definitive, if resolved")
    resolution_method: str | None = Field(default=None, description="Method used to resolve or justification")

    @field_validator("conflict_id", "claim_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v


class ImageEvidenceItem(ImmutableStrictModel):
    asset_id: str = Field(..., description="Unique image asset identifier")
    url: str = Field(..., description="Direct URL of the image")
    source_id: str = Field(..., description="Source registry foreign key")
    provenance: str = Field(..., description="Provenance chain description (e.g. official press kit, festival archive)")
    asset_type: str = Field(..., description="Classification (e.g. film_still, poster, portrait, rehearsal_photo)")
    officiality_status: ImageOfficiality = Field(..., description="Officiality tier")
    credit: str | None = Field(default=None, description="Official photographer or agency credit")
    retrieved_at: str = Field(..., description="ISO retrieval timestamp")

    @field_validator("asset_id", "source_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"url '{v}' must be a valid HTTP/HTTPS URL")
        return v


class EvidenceIntegrityMetadata(ImmutableStrictModel):
    schema_version: str = Field(default="1.0.0")
    pipeline_version: str = Field(default="1.0.0")
    entity_registry_version: str = Field(...)
    source_registry_version: str = Field(...)
    authority_map_version: str = Field(...)
    content_taxonomy_version: str = Field(default="1.0.0")
    editorial_rules_version: str = Field(default="1.0.0")
    iran_exceptions_version: str = Field(default="1.0.0")
    generated_at: str = Field(..., description="ISO timestamp of card synthesis")
    source_count: int = Field(..., ge=0)
    independent_source_count: int = Field(..., ge=0)
    card_hash: str = Field(..., description="Deterministic hash of the complete evidence card contents")


class EvidenceCard(ImmutableStrictModel):
    identity: EvidenceCardIdentity = Field(...)
    story_context: StoryContext = Field(...)
    entities: list[EntityReference] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    authority_resolution: list[AuthorityResolutionItem] = Field(default_factory=list)
    conflicts: list[ConflictItem] = Field(default_factory=list)
    image_evidence: list[ImageEvidenceItem] = Field(default_factory=list)
    integrity: EvidenceIntegrityMetadata = Field(...)
