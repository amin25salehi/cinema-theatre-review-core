"""
Batch Coordinator Contracts - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.16: Acquisition Handoff and Editorial Batch Coordination.

Defines:
- CandidateOrderingPolicy: Ordering strategy for candidate execution queue
- AcquisitionHandoff: Authoritative container pairing Candidate and NormalizedItem
- BatchRunConfig: Ephemeral configuration governing batch execution limits and mode
- BatchCandidateOutcome: Typed, immutable per-candidate execution outcome envelope
- BatchRunSummary: Aggregated ephemeral batch run telemetry
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from pipeline.orchestrator import PipelineStage, PipelineStatus
from schemas.candidate import Candidate
from schemas.decision_card import EditorialDecisionType
from schemas.normalized_item import NormalizedItem
from schemas.pipeline_factory import RuntimeEnvironment
from schemas.publication_ledger import PublicationStatus
from schemas.publication_readiness import PublicationReadinessStatus


class CandidateOrderingPolicy(str, Enum):
    """Deterministic ordering policy for batch candidate queues."""
    CANDIDATE_ID = "candidate_id"
    DISCOVERY_TIMESTAMP = "discovery_timestamp"
    ACQUISITION_ORDER = "acquisition_order"


class AcquisitionHandoff(BaseModel):
    """
    Authoritative handoff container pairing ingestion candidates with
    their corresponding NormalizedItem instances for downstream bridging.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(..., description="Unique acquisition run identifier")
    candidates: list[Candidate] = Field(
        default_factory=list,
        description="List of candidates produced during acquisition",
    )
    items_by_id: dict[str, NormalizedItem] = Field(
        default_factory=dict,
        description="Lookup mapping item_id to canonical NormalizedItem",
    )

    def get_item_for_candidate(self, candidate: Candidate) -> NormalizedItem | None:
        """Resolves the primary NormalizedItem for a candidate fail-closed."""
        if not candidate.normalized_item_refs:
            return None
        return self.items_by_id.get(candidate.normalized_item_refs[0])


class BatchRunConfig(BaseModel):
    """
    Ephemeral configuration governing a single editorial batch execution run.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(..., description="Unique ephemeral batch run identifier")
    environment: RuntimeEnvironment = Field(
        default=RuntimeEnvironment.OFFLINE,
        description="Target runtime execution environment (OFFLINE, TEST, PRODUCTION)",
    )
    max_candidates: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Deterministic ceiling on candidates processed in this batch",
    )
    dry_run: bool = Field(
        default=False,
        description="When true, halts before publication and inhibits ledger mutation",
    )
    ordering_policy: CandidateOrderingPolicy = Field(
        default=CandidateOrderingPolicy.CANDIDATE_ID,
        description="Deterministic ordering policy for candidate processing sequence",
    )


class BatchCandidateOutcome(BaseModel):
    """
    Typed, immutable result envelope representing a single candidate's
    execution outcome within a batch run.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    item_id: str
    status: PipelineStatus
    stage_reached: PipelineStage
    title: Optional[str] = None
    canonical_entity_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    source_domains: list[str] = Field(default_factory=list)
    primary_source_count: int = Field(default=0, ge=0)
    secondary_source_count: int = Field(default=0, ge=0)
    required_primary_count: Optional[int] = None
    required_secondary_count: Optional[int] = None
    authority_status: Optional[str] = None
    corroboration_status: Optional[str] = None
    missing_requirement: Optional[str] = None
    editorial_decision: Optional[EditorialDecisionType] = None
    decision_status: Optional[str] = None
    decision_reason: Optional[str] = None
    reason_codes: list[str] = Field(default_factory=list)
    triggered_rule_ids: list[str] = Field(default_factory=list)
    evidence_gap_summary: Optional[str] = None
    qa_status: Optional[PublicationReadinessStatus] = None
    publication_status: Optional[PublicationStatus] = None
    telegram_message_id: Optional[int] = None
    idempotency_key: Optional[str] = None
    error_message: Optional[str] = None
    execution_time_ms: float = Field(default=0.0, ge=0.0)


class BatchRunSummary(BaseModel):
    """
    Aggregated operational telemetry summarizing the results of an editorial batch run.
    Ephemeral projection; does not replace authoritative state stores.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    environment: RuntimeEnvironment
    is_dry_run: bool = False
    started_at: datetime
    completed_at: datetime
    total_candidates_provided: int
    total_candidates_processed: int
    published_count: int
    held_count: int
    rejected_count: int
    failed_count: int
    qualified_candidates_count: Optional[int] = None
    outcomes: list[BatchCandidateOutcome] = Field(default_factory=list)
