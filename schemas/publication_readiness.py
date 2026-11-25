"""
Publication Readiness & QA Schemas - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.12: Editorial QA & Publication Readiness.

Strict Pydantic v2 data contracts enforcing:
- Hard architectural certification boundary between EditorialDraft and Future Publisher.
- Deterministic 13-gate QA evaluation (Zero LLM, Zero Network).
- Complete referential integrity, claim trace verification, character budget, format compliance,
  publication-plan alignment, and media provenance checks.
- Structured PublicationReadinessResult with typed issues, gates, and statuses.
- Immutable PublicationReadyArtifact handoff contract with deterministic SHA-256 hashes.
- Local idempotency protection preventing duplicate publication handoffs.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any, Literal, Optional

from pydantic import Field, field_validator, model_validator

from schemas.decision_card import ContentType, EditorialDecisionType, PublicationFormat, StoryActionType
from schemas.editorial_draft import DraftClaimTrace, EditorialDraft, GenerationContext
from schemas.evidence_card import ImageOfficiality
from schemas.source_registry import StrictModel
from schemas.story_identity import EditorialChangeType
from utils.canonical_hash import compute_canonical_hash

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class PublicationReadinessStatus(str, Enum):
    READY = "ready"
    NOT_READY = "not_ready"
    NEEDS_REVIEW = "needs_review"
    INVALID = "invalid"


class PublicationQAGateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class PublicationQAIssueSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class PublicationIdentityState(str, Enum):
    NEW = "new"
    ALREADY_READY = "already_ready"
    ALREADY_PUBLISHED = "already_published"
    CONFLICT = "conflict"


class PublicationQAIssueCode(str, Enum):
    # Gate 1: Artifact Integrity
    ARTIFACT_INTEGRITY_FAIL = "artifact_integrity_fail"
    INVALID_IDENTIFIER = "invalid_identifier"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    MALFORMED_HASH = "malformed_hash"

    # Gate 2: Decision Integrity
    DECISION_INTEGRITY_FAIL = "decision_integrity_fail"
    DECISION_HASH_MISMATCH = "decision_hash_mismatch"
    DECISION_NOT_PUBLISHABLE = "decision_not_publishable"
    POLICY_VERSION_MISSING = "policy_version_missing"

    # Gate 3: Draft Integrity
    DRAFT_INTEGRITY_FAIL = "draft_integrity_fail"
    DRAFT_VALIDATION_STATUS_INVALID = "draft_validation_status_invalid"
    DRAFT_MUTATED_AFTER_VALIDATION = "draft_mutated_after_validation"
    DRAFT_CHECKSUM_MISMATCH = "draft_checksum_mismatch"

    # Gate 4: Decision/Draft Compatibility
    DECISION_DRAFT_INCOMPATIBLE = "decision_draft_incompatible"
    CANDIDATE_ID_MISMATCH = "candidate_id_mismatch"
    STORY_ID_MISMATCH = "story_id_mismatch"
    FORMAT_MISMATCH = "format_mismatch"
    CHANGE_TYPE_MISMATCH = "change_type_mismatch"

    # Gate 5: Story/Change Consistency
    STORY_IDENTITY_INCONSISTENT = "story_identity_inconsistent"
    STORY_LINK_UNRESOLVED = "story_link_unresolved"
    DUPLICATE_STORY_PROHIBITED = "duplicate_story_prohibited"
    STORY_DRIFT = "story_drift"
    MISSING_UPDATE_STORY_TARGET = "missing_update_story_target"
    CORRECTION_SEMANTICS_VIOLATION = "correction_semantics_violation"

    # Gate 6: Evidence/Provenance Completeness
    EVIDENCE_MISSING = "evidence_missing"
    OBSOLETE_EVIDENCE = "obsolete_evidence"
    AUTHORITY_STATUS_INVALID = "authority_status_invalid"
    PROVENANCE_MISSING = "provenance_missing"

    # Gate 7: Claim Trace Completeness
    UNKNOWN_CLAIM = "unknown_claim"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    UNKNOWN_SOURCE = "unknown_source"
    UNKNOWN_ENTITY = "unknown_entity"
    MISSING_TRACE = "missing_trace"
    FABRICATED_REFERENCE = "fabricated_reference"

    # Gate 8: Character Budget
    CHARACTER_BUDGET_HARD_FAIL = "character_budget_hard_fail"
    CHARACTER_BUDGET_SOFT_FAIL = "character_budget_soft_fail"

    # Gate 9: Format Compliance
    FORMAT_INCOMPATIBLE = "format_incompatible"
    PERSIAN_FORMAT_VIOLATION = "persian_format_violation"
    MISSING_BODY = "missing_body"
    FORBIDDEN_STRUCTURAL_FIELD = "forbidden_structural_field"
    FORMATTING_SPAN_LIMIT_EXCEEDED = "formatting_span_limit_exceeded"
    PARAGRAPH_FORMATTING_DENSITY_EXCEEDED = "paragraph_formatting_density_exceeded"
    LINK_POLICY_VIOLATION = "link_policy_violation"
    UNAPPROVED_URL = "unapproved_url"

    # Gate 10: Publication Plan Compliance
    PUBLICATION_PLAN_INCOMPATIBLE = "publication_plan_incompatible"
    PUBLICATION_PLAN_NO_PUBLICATION = "publication_plan_no_publication"
    MISSING_STORY_FOR_PLAN = "missing_story_for_plan"
    REQUIRED_MEDIA_UNSATISFIED = "required_media_unsatisfied"

    # Gate 11: Media / Image Readiness
    REQUIRED_MEDIA_MISSING = "required_media_missing"
    MEDIA_POLICY_VIOLATION = "media_policy_violation"
    UNAPPROVED_MEDIA_ASSET = "unapproved_media_asset"
    MEDIA_PROVENANCE_INVALID = "media_provenance_invalid"
    MEDIA_OFFICIALITY_UNKNOWN = "media_officiality_unknown"
    MEDIA_ASSET_REJECTED = "media_asset_rejected"
    MEDIA_CREDIT_MISSING = "media_credit_missing"

    # Gate 12: Duplicate / Idempotency Protection
    DUPLICATE_PUBLICATION_ARTIFACT = "duplicate_publication_artifact"
    ALREADY_PUBLISHED = "already_published"
    PUBLICATION_IDENTITY_CONFLICT = "publication_identity_conflict"

    # Gate 13: Final Readiness
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    GATES_FAILED = "gates_failed"


class MediaProvenanceReference(StrictModel):
    """
    Image/Media provenance reference evaluated during publication readiness.
    Validates metadata without network or image download.
    """
    asset_id: str = Field(..., description="Unique image asset identifier")
    source_id: str = Field(..., description="Source registry foreign key")
    url: str = Field(..., description="Direct image URL")
    provenance: str = Field(..., description="Provenance chain description")
    officiality_status: ImageOfficiality = Field(..., description="Officiality tier")
    credit: str | None = Field(default=None, description="Credit line")
    is_rejected: bool = Field(default=False, description="Whether asset is explicitly rejected")

    @field_validator("asset_id", "source_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v


class PublicationQAIssue(StrictModel):
    """
    Structured issue record produced by a QA gate.
    """
    issue_id: str = Field(..., description="Unique issue identifier")
    gate_id: str = Field(..., description="Gate identifier where issue arose")
    severity: Literal["ERROR", "WARNING"] = Field(..., description="ERROR is fatal/blocking; WARNING requires review")
    code: PublicationQAIssueCode = Field(..., description="Standardized issue code")
    message: str = Field(..., description="Descriptive explanation of the issue")
    refs: list[str] = Field(default_factory=list, description="Referenced entity, claim, evidence, or artifact IDs")


class PublicationQAGate(StrictModel):
    """
    Result of a single deterministic QA gate evaluation.
    """
    gate_id: str = Field(..., description="Unique gate identifier (e.g. gate_1_artifact_integrity)")
    gate_name: str = Field(..., description="Human-readable gate name")
    status: Literal["PASS", "FAIL", "NOT_APPLICABLE"] = Field(..., description="Gate outcome")
    issues: list[str] = Field(default_factory=list, description="IDs of issues discovered during this gate")


class PublicationReadinessResult(StrictModel):
    """
    Auditable certificate of the complete 13-gate QA evaluation.
    Answers definitively: Is this draft structurally and evidentially ready to be published?
    """
    readiness_id: str = Field(..., description="Unique readiness evaluation ID (e.g. prr_dc_cannes_palme)")
    decision_id: str = Field(..., description="Target EditorialDecisionCard ID")
    draft_id: str = Field(..., description="Target EditorialDraft ID")
    candidate_id: str = Field(..., description="Target candidate item ID")
    story_id: str | None = Field(default=None, description="Associated canonical Story identity")
    status: PublicationReadinessStatus = Field(..., description="Overall readiness certification status")
    gates: list[PublicationQAGate] = Field(default_factory=list, description="Ordered results of all 13 gates")
    failures: list[PublicationQAIssue] = Field(default_factory=list, description="Hard failures (severity=ERROR)")
    warnings: list[PublicationQAIssue] = Field(default_factory=list, description="Soft issues (severity=WARNING)")
    decision_hash: str = Field(..., description="Deterministic checksum of EditorialDecisionCard evaluated")
    draft_hash: str = Field(..., description="Deterministic checksum of EditorialDraft evaluated")
    publication_identity: str = Field(..., description="Deterministic publication fingerprint for idempotency")
    evaluated_at: str = Field(..., description="ISO 8601 UTC timestamp of evaluation")
    readiness_hash: str = Field(default="", description="Deterministic SHA-256 hash of this result")

    @property
    def issues(self) -> list[PublicationQAIssue]:
        """Convenience property returning all failures and warnings."""
        return self.failures + self.warnings

    @field_validator("readiness_id", "decision_id", "draft_id", "candidate_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    def compute_readiness_hash(self) -> str:
        """Computes deterministic canonical checksum over substantive readiness result."""
        data = self.model_dump()
        return compute_canonical_hash(data, exclude_fields={"readiness_hash", "evaluated_at"})


class PublicationReadyArtifact(StrictModel):
    """
    Immutable certified publication package handed off to the future publisher.
    Created ONLY when PublicationReadinessStatus is READY.
    """
    artifact_id: str = Field(..., description="Unique publication artifact ID (e.g. pub_art_cannes_palme)")
    readiness_id: str = Field(..., description="ID of the certifying PublicationReadinessResult")
    decision_id: str = Field(..., description="ID of the originating EditorialDecisionCard")
    draft_id: str = Field(..., description="ID of the certified EditorialDraft")
    story_id: str | None = Field(default=None, description="Story identity ID")
    candidate_id: str = Field(..., description="Target candidate item ID")
    publication_action: StoryActionType = Field(..., description="Publication action (NEW_POST, EDIT_EXISTING, REPLY)")
    story_action: StoryActionType = Field(..., description="Story action from decision card")
    change_type: EditorialChangeType = Field(..., description="Editorial change type")
    format: PublicationFormat = Field(..., description="Target publication format")
    title: str | None = Field(default=None, description="Headline/Title in Persian")
    body: str = Field(..., description="Approved text body in Persian")
    character_count: int = Field(..., description="Canonical Unicode character count")
    claim_traces: list[DraftClaimTrace] = Field(default_factory=list, description="Claim and evidence traces")
    source_refs: list[str] = Field(default_factory=list, description="Approved source references")
    entity_refs: list[str] = Field(default_factory=list, description="Approved entity references")
    media_assets: list[MediaProvenanceReference] = Field(default_factory=list, description="Certified media metadata")
    decision_hash: str = Field(..., description="Checksum of the originating EditorialDecisionCard")
    draft_hash: str = Field(..., description="Checksum of the certified EditorialDraft")
    readiness_hash: str = Field(..., description="Checksum of the certifying PublicationReadinessResult")
    publication_identity: str = Field(..., description="Deterministic publication fingerprint for idempotency")
    artifact_hash: str = Field(default="", description="Deterministic SHA-256 hash of this artifact")
    created_at: str = Field(..., description="ISO 8601 UTC timestamp of artifact certification")

    @field_validator("artifact_id", "readiness_id", "decision_id", "draft_id", "candidate_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    def compute_artifact_hash(self) -> str:
        """Computes deterministic canonical checksum over substantive artifact."""
        data = self.model_dump()
        return compute_canonical_hash(data, exclude_fields={"artifact_hash", "created_at"})
