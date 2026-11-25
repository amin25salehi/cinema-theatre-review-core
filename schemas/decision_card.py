"""
Editorial Decision Card Schema - Cinema & Theatre Review Editorial OS v1.0
Strict Pydantic v2 data contract for the final editorial decision record.
Decision Card is strictly separated from Evidence Card and LLM Context Projection.
INVARIANT: LLM Recommendation != Final Decision.
Deterministic hard gates cannot be overridden by LLM.
"""

import re
from enum import Enum

from pydantic import Field, field_validator, model_validator

from schemas.source_registry import StrictModel

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class EditorialDecisionType(str, Enum):
    PUBLISH = "publish"
    HOLD = "hold"
    REJECT = "reject"
    UPDATE_EXISTING = "update_existing"


class GateStatus(str, Enum):
    PASS_ = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class PublicationFormat(str, Enum):
    NEWS_BRIEF = "news_brief"
    FESTIVAL_UPDATE = "festival_update"
    BOOK_NOTE = "book_note"
    CRITICAL_NOTE = "critical_note"
    HISTORICAL_NOTE = "historical_note"
    ARCHIVE_NOTE = "archive_note"
    THEATRE_PERFORMANCE = "theatre_performance"
    AWARD_UPDATE = "award_update"
    OBITUARY = "obituary"


class ContentType(str, Enum):
    CINEMA = "cinema"
    THEATRE = "theatre"
    BOOK = "book"
    ARCHIVE = "archive"
    CRITICISM = "criticism"
    FESTIVAL = "festival"


class StoryActionType(str, Enum):
    NEW_POST = "new_post"
    EDIT_EXISTING = "edit_existing"
    REPLY = "reply"
    NO_PUBLICATION = "no_publication"
    CORRECTION_NOTICE = "correction_notice"
    RETRACTION_NOTICE = "retraction_notice"


class StoryStateType(str, Enum):
    NEW = "new"
    UPDATE = "update"
    CORRECTION = "correction"
    FOLLOW_UP = "follow_up"
    RETRACTION = "retraction"


class PolicyVersions(StrictModel):
    editorial_rules_version: str = Field(...)
    authority_map_version: str = Field(...)
    iran_exceptions_version: str = Field(...)
    content_taxonomy_version: str = Field(default="1.0.0")
    source_registry_version: str = Field(default="1.0.0")
    entity_registry_version: str = Field(default="1.0.0")


class GateResult(StrictModel):
    status: GateStatus = Field(...)
    reason: str = Field(...)
    checked_at: str = Field(...)


class HardGatesEvaluation(StrictModel):
    duplicate: GateResult = Field(...)
    commercial_only: GateResult = Field(...)
    iranian_daily_news: GateResult = Field(...)
    unverified_claim: GateResult = Field(...)
    image_provenance: GateResult = Field(...)
    source_requirement: GateResult = Field(...)


class EditorialSignals(StrictModel):
    evidence_strength: float = Field(..., ge=0.0, le=1.0)
    editorial_fit: float = Field(..., ge=0.0, le=1.0)
    recency: float = Field(..., ge=0.0, le=1.0)
    major_festival: bool = Field(default=False)
    major_award: bool = Field(default=False)
    major_retrospective: bool = Field(default=False)
    restoration: bool = Field(default=False)
    archival_significance: bool = Field(default=False)
    academic_significance: bool = Field(default=False)
    important_book: bool = Field(default=False)
    important_play: bool = Field(default=False)
    reference_entity: bool = Field(default=False)
    emerging_entity: bool = Field(default=False)
    independent_critical_attention: bool = Field(default=False)
    iran_exception: bool = Field(default=False)


class RuleEvaluationResult(StrictModel):
    rule_id: str = Field(...)
    rule_name: str = Field(...)
    outcome: str = Field(..., description="pass, fail, flag")
    detail: str = Field(...)


class LLMAssessment(StrictModel):
    recommended_action: EditorialDecisionType = Field(..., description="Advisory recommendation only")
    editorial_rationale: str = Field(..., description="LLM generated reasoning")
    uncertainties: list[str] = Field(default_factory=list, description="Explicit caveats identified by LLM")


class LinkPolicy(str, Enum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"
    OMIT = "omit"


class MediaPolicy(str, Enum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"
    OMIT = "omit"


class CharacterBudget(StrictModel):
    min: int = Field(..., ge=0, description="Minimum characters required")
    target: int = Field(..., ge=0, description="Target character length")
    max: int = Field(..., ge=0, description="Strict maximum character ceiling")

    @model_validator(mode="after")
    def validate_budget_bounds(self) -> "CharacterBudget":
        if self.min > self.target:
            raise ValueError(f"Character budget min ({self.min}) cannot exceed target ({self.target})")
        if self.target > self.max:
            raise ValueError(f"Character budget target ({self.target}) cannot exceed max ({self.max})")
        return self


class PublicationPlan(StrictModel):
    content_type: ContentType = Field(...)
    format: PublicationFormat = Field(...)
    language: str = Field(default="fa")
    character_budget: CharacterBudget = Field(...)
    link_policy: LinkPolicy = Field(default=LinkPolicy.OPTIONAL, description="Authoritative link policy from editorial decision")
    media_policy: MediaPolicy = Field(default=MediaPolicy.OPTIONAL, description="Authoritative media policy from editorial decision")
    schedule: str | None = Field(default=None, description="ISO timestamp or publish immediately indicator")


class ValidationSummary(StrictModel):
    is_valid: bool = Field(..., description="True only if all required validation checks pass")
    policy_valid: bool = Field(default=True, description="Whether policy and hard gate evaluations are valid")
    evidence_sufficient: bool = Field(default=True, description="Whether evidence meets minimum verification thresholds")
    decision_consistent: bool = Field(default=True, description="Whether final decision is consistent with gates and evidence")
    publication_plan_valid: bool = Field(default=True, description="Whether publication plan is present and valid if publishing, or absent if hold/reject")
    character_budget_valid: bool = Field(default=True, description="Whether character budget constraints are satisfied")
    conflicts_resolved: bool = Field(default=True, description="Whether material conflicts have been resolved or properly held")
    validator_notes: list[str] = Field(default_factory=list)
    overrides_applied: list[str] = Field(default_factory=list, description="Instances where deterministic code overrode LLM advice")

    @model_validator(mode="after")
    def validate_truthfulness(self) -> "ValidationSummary":
        expected_valid = (
            self.policy_valid
            and self.evidence_sufficient
            and self.decision_consistent
            and self.publication_plan_valid
            and self.character_budget_valid
            and self.conflicts_resolved
        )
        if self.is_valid != expected_valid:
            raise ValueError(
                f"ValidationSummary.is_valid ({self.is_valid}) is inconsistent with validation check flags "
                f"(expected {expected_valid}). is_valid must be strictly derived from the individual checks."
            )
        return self


class HumanOverride(StrictModel):
    """
    Audit record for explicit human editorial intervention.
    Enforces that human overrides are explicitly tracked with editor identity,
    timestamp, prior decision, overridden decision, and mandatory rationale.
    """
    overridden_by: str = Field(..., description="Unique identifier or username of authorized human editor")
    overridden_at: str = Field(..., description="ISO 8601 UTC timestamp of override")
    original_decision: EditorialDecisionType = Field(..., description="Original decision prior to override")
    overridden_decision: EditorialDecisionType = Field(..., description="Final decision enforced by human editor")
    override_reason: str = Field(..., description="Mandatory detailed editorial justification for override")
    allow_hard_gate_override: bool = Field(
        default=False,
        description="Whether this override attempts to bypass hard gates (STRICTLY FORBIDDEN: will fail validation)",
    )

    @field_validator("override_reason")
    @classmethod
    def validate_override_reason(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Human override must provide a non-empty override_reason")
        return v.strip()


class DecisionAuditMetadata(StrictModel):
    evaluated_at: str = Field(...)
    pipeline_version: str = Field(default="1.0.0")
    decision_engine_version: str = Field(default="1.0.0")
    editorial_rules_version: str = Field(...)
    authority_map_version: str = Field(...)
    source_registry_version: str = Field(...)
    entity_registry_version: str = Field(...)
    content_taxonomy_version: str = Field(...)
    iran_exceptions_version: str = Field(...)
    llm_model: str | None = Field(default=None)
    llm_prompt_version: str | None = Field(default=None)
    human_override: HumanOverride | None = Field(default=None, description="Audit of human intervention if applied")
    deterministic_checksum: str = Field(...)


class EditorialDecisionCard(StrictModel):
    card_id: str = Field(..., description="Decision card ID (e.g. dc_cannes_2026_palme)")
    evidence_card_id: str = Field(..., description="Target Evidence Card ID")
    evidence_card_version: int = Field(..., ge=1, description="Target Evidence Card version")
    story_id: str | None = Field(default=None, description="Associated canonical Story identity")
    policy_versions: PolicyVersions = Field(...)
    hard_gates: HardGatesEvaluation = Field(...)
    editorial_signals: EditorialSignals = Field(...)
    rule_evaluations: list[RuleEvaluationResult] = Field(default_factory=list)
    llm_assessment: LLMAssessment | None = Field(default=None, description="Advisory assessment from LLM")
    decision: EditorialDecisionType = Field(..., description="Final binding decision")
    decision_reason: str = Field(...)
    publication_plan: PublicationPlan | None = Field(default=None)
    story_action: StoryActionType = Field(...)
    story_state: StoryStateType = Field(...)
    validation: ValidationSummary = Field(...)
    audit: DecisionAuditMetadata = Field(...)

    @field_validator("card_id", "evidence_card_id")
    @classmethod
    def validate_card_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    @model_validator(mode="after")
    def validate_hard_gate_invariance(self) -> "EditorialDecisionCard":
        # INVARIANT: If any hard gate failed, final decision CANNOT be publish
        gate_statuses = [
            self.hard_gates.duplicate.status,
            self.hard_gates.commercial_only.status,
            self.hard_gates.iranian_daily_news.status,
            self.hard_gates.unverified_claim.status,
            self.hard_gates.image_provenance.status,
            self.hard_gates.source_requirement.status,
        ]
        if GateStatus.FAIL in gate_statuses and self.decision == EditorialDecisionType.PUBLISH:
            raise ValueError(
                "Deterministic hard gate failure prohibits Editorial Decision 'publish'. "
                "Invariant violated: Hard gates are non-negotiable."
            )

        # Publication plan invariants
        if self.decision == EditorialDecisionType.PUBLISH and self.publication_plan is None:
            raise ValueError("Editorial decision 'publish' requires an active publication_plan.")

        if self.decision in (EditorialDecisionType.HOLD, EditorialDecisionType.REJECT) and self.publication_plan is not None:
            raise ValueError(
                f"Editorial decision '{self.decision.value}' must not have an active publication_plan."
            )

        # Story action consistency
        if (
            self.decision in (EditorialDecisionType.HOLD, EditorialDecisionType.REJECT)
            and self.story_action != StoryActionType.NO_PUBLICATION
            and self.story_state != StoryStateType.RETRACTION
        ):
            raise ValueError(
                f"Editorial decision '{self.decision.value}' requires story_action 'no_publication'."
            )

        if (
            self.story_state == StoryStateType.NEW
            and self.decision == EditorialDecisionType.PUBLISH
            and self.story_action != StoryActionType.NEW_POST
        ):
            raise ValueError("New story with decision 'publish' must have story_action 'new_post'.")

        if (
            self.story_state == StoryStateType.UPDATE
            and self.decision == EditorialDecisionType.PUBLISH
            and self.story_action not in (StoryActionType.EDIT_EXISTING, StoryActionType.REPLY, StoryActionType.NEW_POST)
        ):
            raise ValueError("Update story with decision 'publish' must have an update-compatible story_action.")

        if (
            self.story_state == StoryStateType.CORRECTION
            and self.story_action not in (StoryActionType.CORRECTION_NOTICE, StoryActionType.EDIT_EXISTING, StoryActionType.NO_PUBLICATION)
        ):
            raise ValueError(
                f"Correction story must have a correction-compatible story_action, got '{self.story_action.value}'."
            )

        if (
            self.story_state == StoryStateType.RETRACTION
            and self.story_action not in (StoryActionType.RETRACTION_NOTICE, StoryActionType.NO_PUBLICATION)
        ):
            raise ValueError(
                f"Retraction story must have story_action 'retraction_notice' or 'no_publication', got '{self.story_action.value}'."
            )

        # Human override invariants
        if self.audit.human_override is not None:
            if GateStatus.FAIL in gate_statuses and self.decision == EditorialDecisionType.PUBLISH:
                raise ValueError(
                    "Human override cannot bypass deterministic hard gates to force 'publish'."
                )
            if self.audit.human_override.allow_hard_gate_override:
                raise ValueError(
                    "allow_hard_gate_override=True is strictly prohibited by editorial policy."
                )

        return self
