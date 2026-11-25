"""
Editorial Draft & Content Generation Schemas - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.11: Editorial Content Generation & Draft Validation.

Strict Pydantic v2 data contracts enforcing:
- Hard architectural separation between Decision (WHAT) and Generation (HOW) and Validation (WHETHER).
- Bounded GenerationContext containing only approved claims, entities, and sources.
- Non-negotiable decision gates (only PUBLISH / UPDATE_EXISTING can generate publication drafts).
- Grounded claim traceability and hallucination rejection.
- Canonical Persian-first formatting rules and character budgets.
- Immutable, audit-trailed EditorialDraft artifacts with deterministic SHA-256 hashing.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any, Literal, Optional

from pydantic import Field, field_validator, model_validator

from schemas.decision_card import (
    ContentType,
    EditorialDecisionType,
    LinkPolicy,
    MediaPolicy,
    PublicationFormat,
)
from schemas.source_registry import StrictModel
from schemas.story_identity import EditorialChangeType
from utils.canonical_hash import compute_canonical_hash

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


def count_characters(body: str, title: str | None = None) -> int:
    """
    Canonical Unicode character count function across the entire editorial system.
    Counts characters in body, plus title (and single newline separator) if title is provided.
    """
    total = len(body)
    if title and title.strip():
        total += len(title.strip()) + 1  # title + newline separator
    return total


class ApprovedClaim(StrictModel):
    """
    Grounded claim approved by upstream Evidence & Decision Card.
    Only claims with status 'SUPPORTED' or 'QUALIFIED' are admitted into the generator's factual pool.
    Unverified, contradicted, or obsolete claims are strictly forbidden.
    """
    claim_id: str = Field(..., description="Unique claim identifier")
    statement: str = Field(..., description="Approved factual statement")
    raw_statement: str | None = Field(default=None, description="Original unedited source statement retained strictly for provenance/auditing")
    claim_type_id: str = Field(..., description="Taxonomy claim type ID")
    predicate: str | None = Field(default=None, description="Canonical predicate identifier")
    subject_entity_id: str | None = Field(default=None, description="Subject entity identifier")
    object_entity_id: str | None = Field(default=None, description="Object entity identifier")
    object_value: str | None = Field(default=None, description="Normalized scalar/composite object value")
    evidence_refs: list[str] = Field(default_factory=list, description="Associated evidence IDs")
    source_refs: list[str] = Field(default_factory=list, description="Associated source IDs")
    status: Literal["SUPPORTED", "QUALIFIED"] = Field(..., description="Verification status")
    qualification: str | None = Field(default=None, description="Qualification note if QUALIFIED")

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"claim_id '{v}' must match ^[a-z0-9_]+$")
        return v


class ApprovedEntity(StrictModel):
    """
    Entity approved and resolved in the story context.
    """
    entity_id: str = Field(..., description="Entity identifier from entity registry")
    name: str = Field(..., description="Official or canonical name")
    name_persian: str | None = Field(default=None, description="Standard Persian transliteration/name")
    entity_type: str | None = Field(default=None, description="Entity type from taxonomy")
    role: str = Field(default="subject", description="Role in story (e.g. subject, director, venue)")

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"entity_id '{v}' must match ^[a-z0-9_]+$")
        return v


class SourceReference(StrictModel):
    """
    Source reference supporting approved evidence.
    """
    source_id: str = Field(..., description="Source ID from source registry")
    source_name: str = Field(..., description="Human-readable source name")
    source_class: str = Field(..., description="Taxonomy source class")
    source_url: str | None = Field(default=None, description="Originating URL")

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"source_id '{v}' must match ^[a-z0-9_]+$")
        return v


class ChangeContext(StrictModel):
    """
    Context for stories that represent updates, follow-ups, or corrections.
    """
    change_type: EditorialChangeType = Field(..., description="Editorial change classification")
    previous_story_headline: str | None = Field(default=None, description="Headline of previous version")
    previous_post_reference: str | None = Field(default=None, description="Internal message/post ID of previous published post")
    change_summary: str | None = Field(default=None, description="Summary of new facts or corrections")
    is_correction: bool = Field(default=False, description="Whether this publication is an explicit correction")
    is_update: bool = Field(default=False, description="Whether this publication is an update or follow-up")


class ClaimRestriction(StrictModel):
    """
    Explicit negative boundary: facts, topics, or claims forbidden from appearing in the draft.
    """
    restriction_id: str = Field(..., description="Unique restriction identifier")
    description: str = Field(..., description="Human and machine readable restriction directive")
    target_field: str | None = Field(default=None, description="Optional target dimension (e.g. date, box_office, biography)")


class DraftLink(StrictModel):
    url: str = Field(..., description="Grounded, approved URL")
    text: str = Field(default="", description="Anchor text used in draft")
    source_id: str | None = Field(default=None, description="Foreign key to approved source")

    @model_validator(mode="before")
    @classmethod
    def handle_anchor_text_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "anchor_text" in data and ("text" not in data or not data["text"]):
                data["text"] = data.pop("anchor_text")
            elif "anchor_text" in data:
                data.pop("anchor_text")
        return data


class DraftMediaAsset(StrictModel):
    asset_id: str = Field(..., description="Approved media asset ID")
    caption: str | None = Field(default=None, description="Optional caption")
    credit: str | None = Field(default=None, description="Mandatory official photographer/agency credit")


class FormatInstructions(StrictModel):
    """
    Structural and character budget instructions for draft formatting.
    """
    format: PublicationFormat = Field(..., description="Approved publication format")
    content_type: ContentType = Field(..., description="Cinema, Theatre, etc.")
    min_characters: int = Field(..., ge=50, description="Soft lower bound for characters")
    target_characters: int = Field(..., ge=100, description="Target character count")
    max_characters: int = Field(..., ge=150, description="Soft upper bound for characters")
    hard_max_characters: int = Field(default=2000, description="Hard maximum character ceiling")
    target_language: str = Field(default="fa", description="Target language (Persian)")
    structural_guidelines: list[str] = Field(default_factory=list, description="Format-specific layout guidance")
    link_policy: LinkPolicy = Field(default=LinkPolicy.OPTIONAL, description="Authoritative link policy from publication plan")
    media_policy: MediaPolicy = Field(default=MediaPolicy.OPTIONAL, description="Authoritative media policy from publication plan")


class GenerationContext(StrictModel):
    """
    Strict, bounded projection specifically curated for content generation.
    Contains ONLY information approved for the story.
    Does NOT contain raw payloads or untrusted instructions.
    """
    context_id: str = Field(..., description="Unique context identifier (e.g. gctx_cannes_palme)")
    story_id: str | None = Field(default=None, description="Canonical Story ID")
    story_summary: str = Field(..., description="Approved editorial summary of the event")
    approved_claims: list[ApprovedClaim] = Field(default_factory=list, description="Approved factual claims")
    approved_entities: list[ApprovedEntity] = Field(default_factory=list, description="Approved entities")
    approved_sources: list[SourceReference] = Field(default_factory=list, description="Approved source references")
    approved_media_asset_ids: list[str] = Field(default_factory=list, description="Approved media asset IDs available for selection")
    approved_urls: list[str] = Field(default_factory=list, description="Approved grounded URLs available for selection")
    change_context: ChangeContext | None = Field(default=None, description="Change context if update/correction")
    editorial_angle: str = Field(..., description="Approved focus or editorial angle")
    prohibited_claims: list[ClaimRestriction] = Field(default_factory=list, description="Explicit restrictions")
    format_instructions: FormatInstructions = Field(..., description="Format & character budget instructions")
    checksum: str = Field(default="", description="Deterministic SHA-256 hash of substantive context")

    @field_validator("context_id")
    @classmethod
    def validate_context_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"context_id '{v}' must match ^[a-z0-9_]+$")
        return v

    def compute_context_checksum(self) -> str:
        """Computes deterministic canonical checksum over substantive context fields."""
        data = self.model_dump()
        return compute_canonical_hash(data, exclude_fields={"checksum"})


class ContentGenerationRequest(StrictModel):
    """
    Authoritative request envelope passed into the Content Generator.
    Ties the GenerationContext to the upstream EditorialDecisionCard.
    """
    request_id: str = Field(..., description="Unique request identifier")
    decision_id: str = Field(..., description="Card ID of originating EditorialDecisionCard")
    candidate_id: str = Field(..., description="Target candidate item ID")
    story_id: str | None = Field(default=None, description="Story identity ID")
    decision: EditorialDecisionType = Field(..., description="Decision from EditorialDecisionCard")
    change_type: EditorialChangeType = Field(..., description="Change classification")
    generation_context: GenerationContext = Field(..., description="Bounded generation context")
    format: PublicationFormat = Field(..., description="Target publication format")
    max_characters: int = Field(..., description="Character budget ceiling")
    evidence_refs: list[str] = Field(default_factory=list, description="Approved evidence IDs")
    claim_refs: list[str] = Field(default_factory=list, description="Approved claim IDs")
    entity_refs: list[str] = Field(default_factory=list, description="Approved entity IDs")
    policy_version: str = Field(default="1.0.0", description="Policy version")
    prompt_version: str = Field(default="editorial_content_generation:v1", description="Prompt contract version")
    decision_hash: str = Field(..., description="Deterministic checksum of the originating EditorialDecisionCard")

    @field_validator("request_id", "decision_id", "candidate_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v


class DraftClaimTrace(StrictModel):
    """
    Structured traceability link connecting a draft assertion or paragraph to approved claims & evidence.
    """
    draft_claim_id: str = Field(..., description="Identifier for this assertion in draft")
    claim_refs: list[str] = Field(..., description="IDs of approved claims this assertion grounds on")
    evidence_refs: list[str] = Field(..., description="IDs of approved evidence supporting this assertion")
    assertion_text: str | None = Field(default=None, description="Optional excerpt of assertion text")


class DraftGenerationStatus(str, Enum):
    GENERATED = "generated"
    FAILED = "failed"
    INVALID = "invalid"


class DraftValidationStatus(str, Enum):
    PENDING = "pending"
    VALID = "valid"
    NEEDS_REVIEW = "needs_review"
    INVALID = "invalid"


class DraftFailureReason(str, Enum):
    NONE = "none"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AUTHENTICATION_FAILURE = "authentication_failure"
    MALFORMED_OUTPUT = "malformed_output"
    SCHEMA_VALIDATION_FAILURE = "schema_validation_failure"
    CONTENT_POLICY_REFUSAL = "content_policy_refusal"
    DECISION_GATED = "decision_gated"


class DraftValidationIssueCode(str, Enum):
    UNSUPPORTED_DRAFT_ASSERTION = "unsupported_draft_assertion"
    UNKNOWN_ENTITY = "unknown_entity"
    UNKNOWN_SOURCE = "unknown_source"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    FABRICATED_CLAIM = "fabricated_claim"
    UNSUPPORTED_NUMBER = "unsupported_number"
    UNSUPPORTED_DATE = "unsupported_date"
    UNSUPPORTED_ATTRIBUTION = "unsupported_attribution"
    DECISION_DRIFT = "decision_drift"
    STORY_DRIFT = "story_drift"
    SCOPE_DRIFT = "scope_drift"
    DECISION_CONTEXT_MISMATCH = "decision_context_mismatch"
    CONTEXT_CHECKSUM_MISMATCH = "context_checksum_mismatch"
    CHARACTER_BUDGET_HARD_FAIL = "character_budget_hard_fail"
    CHARACTER_BUDGET_SOFT_FAIL = "character_budget_soft_fail"
    PERSIAN_FORMAT_VIOLATION = "persian_format_violation"
    BANNED_HYPE_VOCABULARY = "banned_hype_vocabulary"
    PROHIBITED_CLAIM_VIOLATION = "prohibited_claim_violation"
    DUPLICATE_GENERATION_PROHIBITED = "duplicate_generation_prohibited"
    DECISION_NOT_PUBLISHABLE = "decision_not_publishable"
    FORMATTING_SPAN_LIMIT_EXCEEDED = "formatting_span_limit_exceeded"
    PARAGRAPH_FORMATTING_DENSITY_EXCEEDED = "paragraph_formatting_density_exceeded"
    LINK_POLICY_VIOLATION = "link_policy_violation"
    UNAPPROVED_URL = "unapproved_url"
    MEDIA_POLICY_VIOLATION = "media_policy_violation"
    UNAPPROVED_MEDIA_ASSET = "unapproved_media_asset"


class DraftValidationIssue(StrictModel):
    code: DraftValidationIssueCode = Field(..., description="Standardized issue code")
    message: str = Field(..., description="Descriptive explanation of the validation issue")
    severity: Literal["FATAL", "REVIEW"] = Field(..., description="FATAL causes INVALID, REVIEW causes NEEDS_REVIEW")
    field: str | None = Field(default=None, description="Relevant field in draft")


class DraftValidationSummary(StrictModel):
    """
    Validation audit summary produced by the DraftValidator.
    """
    status: DraftValidationStatus = Field(..., description="Overall validation status")
    is_valid: bool = Field(..., description="True only if status is VALID")
    character_count_valid: bool = Field(..., description="True if within acceptable character budget")
    grounding_valid: bool = Field(..., description="True if all claims, entities, and sources are grounded")
    decision_consistent: bool = Field(..., description="True if decision and context hashes match")
    format_valid: bool = Field(..., description="True if Persian format and layout rules are respected")
    issues: list[DraftValidationIssue] = Field(default_factory=list, description="All recorded issues")
    review_reasons: list[str] = Field(default_factory=list, description="Specific triggers requiring human review")
    validated_at: str = Field(..., description="ISO 8601 UTC timestamp of validation")


class EditorialDraft(StrictModel):
    """
    Immutable, fully auditable editorial draft ready for human review or publication scheduling.
    """
    draft_id: str = Field(..., description="Unique draft identifier (e.g. drf_cannes_palme_v1)")
    decision_id: str = Field(..., description="Card ID of originating EditorialDecisionCard")
    candidate_id: str = Field(..., description="Originating candidate ID")
    story_id: str | None = Field(default=None, description="Story identity ID")
    change_type: EditorialChangeType = Field(..., description="Change classification")
    format: PublicationFormat = Field(..., description="Publication format")
    title: str | None = Field(default=None, description="Optional draft headline")
    body: str = Field(..., description="Draft text body in Persian")
    character_count: int = Field(..., description="Canonical Unicode character count")
    claim_traces: list[DraftClaimTrace] = Field(default_factory=list, description="Claim and evidence grounding traces")
    links: list[DraftLink] = Field(default_factory=list, description="Grounded links included in the draft")
    media: list[DraftMediaAsset] = Field(default_factory=list, description="Selected approved media assets")
    source_refs: list[str] = Field(default_factory=list, description="Referenced source IDs")
    entity_refs: list[str] = Field(default_factory=list, description="Referenced entity IDs")
    prompt_version: str = Field(default="editorial_content_generation:v1")
    model: str = Field(..., description="Model identifier used for generation")
    generation_status: DraftGenerationStatus = Field(..., description="Generation execution status")
    validation_status: DraftValidationStatus = Field(default=DraftValidationStatus.PENDING)
    decision_hash: str = Field(..., description="Checksum of the originating EditorialDecisionCard")
    context_checksum: str = Field(..., description="Checksum of the generation context")
    parent_draft_id: str | None = Field(default=None, description="Parent draft ID if this is a revision")
    revision_number: int = Field(default=1, ge=1, description="Sequential revision counter")
    validation_summary: DraftValidationSummary | None = Field(default=None)
    generation_checksum: str = Field(default="", description="Deterministic SHA-256 hash of substantive draft")
    validation_checksum: str | None = Field(default=None, description="Deterministic SHA-256 hash of validation")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")

    @field_validator("draft_id", "decision_id", "candidate_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    def compute_generation_checksum(self) -> str:
        """Computes deterministic canonical checksum over substantive draft content."""
        data = self.model_dump()
        return compute_canonical_hash(
            data,
            exclude_fields={"generation_checksum", "validation_checksum", "validation_summary", "validation_status"}
        )
