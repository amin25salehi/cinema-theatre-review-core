"""
LLM Editorial Assessment Schemas - Cinema & Theatre Review Editorial OS v1.0.1
Strict Pydantic v2 data contract for Stage 8.9 LLM Analysis & Editorial Assessment.

INVARIANTS:
1. LLM Output is strictly ADVISORY.
2. LLM cannot make publication decisions (publish/reject/hold).
3. LLM cannot modify Evidence, Authority, Claim Status, or Editorial Policy.
4. LLM cannot resolve factual conflicts.
5. All references must link to valid projection items (claim_refs, evidence_refs, entity_refs).
6. No pseudo-objective artistic scores or popularity inferences.
"""

from enum import Enum
import re
from typing import Any

from pydantic import Field, field_validator, model_validator

from schemas.context_projection import ID_PATTERN
from schemas.decision_card import ContentType, EditorialDecisionType, PublicationFormat
from schemas.source_registry import StrictModel


class AssessmentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    INVALID = "invalid"
    FAILED = "failed"


class FailureReason(str, Enum):
    NONE = "none"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    AUTHENTICATION_FAILURE = "authentication_failure"
    MALFORMED_OUTPUT = "malformed_output"
    SCHEMA_VALIDATION_FAILURE = "schema_validation_failure"
    CONTENT_POLICY_REFUSAL = "content_policy_refusal"


class SuggestedStoryForm(str, Enum):
    NEWS_BRIEF = "news_brief"
    FESTIVAL_UPDATE = "festival_update"
    BOOK_NOTE = "book_note"
    CRITICAL_NOTE = "critical_note"
    HISTORICAL_NOTE = "historical_note"
    ARCHIVE_NOTE = "archive_note"
    THEATRE_PERFORMANCE = "theatre_performance"
    AWARD_UPDATE = "award_update"
    OBITUARY = "obituary"


class ModelMetadata(StrictModel):
    model_config = {"protected_namespaces": ()}

    provider: str = Field(..., description="LLM provider name (e.g. gemini, mock, anthropic)")
    model_id: str = Field(..., description="Model identifier used for analysis")
    model_version: str | None = Field(default=None, description="Model release version if available")
    prompt_version: str = Field(default="editorial_assessment:v1", description="Versioned prompt contract")
    request_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of execution")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=2048, ge=64, le=8192)


class ScopeAssessment(StrictModel):
    scope_fit: bool = Field(..., description="Whether story fits documented editorial scope")
    suggested_domain: ContentType = Field(..., description="Canonical content taxonomy domain")
    relevance_explanation: str = Field(..., description="Grounded rationale for domain and scope fit")


class EvidenceSufficientContext(StrictModel):
    is_sufficient: bool = Field(..., description="Whether verified facts provide adequate context")
    missing_context: list[str] = Field(default_factory=list, description="Specific factual context gaps")
    key_claims_addressed: list[str] = Field(default_factory=list, description="Claim IDs analyzed")


class ConflictObservation(StrictModel):
    conflict_id: str = Field(..., description="Reference to projected conflict")
    claim_id: str = Field(..., description="Reference to contested claim")
    disagreement_summary: str = Field(..., description="Neutral summary of factual divergence")
    requires_editorial_attention: bool = Field(
        default=True,
        description="Must be True; LLM cannot resolve conflict and must flag for editorial attention",
    )

    @field_validator("conflict_id", "claim_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v


class GroundedAssertion(StrictModel):
    statement: str = Field(..., description="Interpretive analysis statement")
    claim_refs: list[str] = Field(default_factory=list, description="Referenced projected claim IDs")
    evidence_refs: list[str] = Field(default_factory=list, description="Referenced projected evidence IDs")
    entity_refs: list[str] = Field(default_factory=list, description="Referenced projected entity IDs")


class AdvisoryRecommendation(StrictModel):
    advisory_action: EditorialDecisionType = Field(
        ...,
        description="Advisory suggestion only. Downstream EditorialRuleEngine remains authoritative.",
    )
    suggested_format: PublicationFormat = Field(..., description="Suggested canonical publication format")
    rationale: str = Field(..., description="Analytical justification based strictly on projection")
    caveats: list[str] = Field(default_factory=list, description="Uncertainties or unverified elements")

    @field_validator("advisory_action")
    @classmethod
    def validate_advisory_action(cls, v: EditorialDecisionType) -> EditorialDecisionType:
        # Advisory action can only be PUBLISH, HOLD, or REJECT
        if v not in (EditorialDecisionType.PUBLISH, EditorialDecisionType.HOLD, EditorialDecisionType.REJECT):
            raise ValueError(f"Invalid advisory action: {v}")
        return v


class LLMEditorialAssessment(StrictModel):
    """
    Structured analytical assessment produced by an LLM from an LLMContextProjection.
    Strictly ADVISORY.
    """

    model_config = {"protected_namespaces": ()}

    schema_version: str = Field(default="llm_assessment:v1")
    assessment_id: str = Field(..., description="Unique assessment ID (e.g. asm_cannes_2026_palme)")
    projection_id: str = Field(..., description="Target projection ID")
    evidence_card_id: str = Field(..., description="Target evidence card ID")
    evidence_card_version: int = Field(..., ge=1)
    status: AssessmentStatus = Field(default=AssessmentStatus.COMPLETED)
    is_advisory: bool = Field(
        default=True,
        description="MANDATORY INVARIANT: Must be True. LLM is analytical and advisory only.",
    )
    model_metadata: ModelMetadata = Field(...)
    scope_assessment: ScopeAssessment = Field(...)
    evidence_sufficiency: EvidenceSufficientContext = Field(...)
    conflict_observations: list[ConflictObservation] = Field(default_factory=list)
    suggested_story_form: SuggestedStoryForm = Field(...)
    suggested_angle: str = Field(..., description="Recommended editorial angle grounded in facts")
    grounded_assertions: list[GroundedAssertion] = Field(default_factory=list)
    advisory_recommendation: AdvisoryRecommendation = Field(...)
    uncertainties: list[str] = Field(default_factory=list)
    assessment_hash: str = Field(..., description="Canonical hash of the assessment payload")

    @field_validator("assessment_id", "projection_id", "evidence_card_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    @model_validator(mode="after")
    def validate_advisory_invariant(self) -> "LLMEditorialAssessment":
        if not self.is_advisory:
            raise ValueError("Invariant violation: LLMEditorialAssessment must have is_advisory=True")
        return self


class AssessmentRecord(StrictModel):
    """
    Persistent audit record for an LLM assessment execution.
    """

    record_id: str = Field(...)
    assessment_id: str = Field(...)
    projection_id: str = Field(...)
    evidence_card_id: str = Field(...)
    status: AssessmentStatus = Field(...)
    failure_reason: FailureReason = Field(default=FailureReason.NONE)
    error_message: str | None = None
    created_at: str = Field(...)
    assessment: LLMEditorialAssessment | None = None
    raw_response: str | None = None
    assessment_hash: str = Field(...)
