"""
Pipeline Runner Contracts - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.17: Top-Level Production Runtime Composition & Execution Contracts.

Defines:
- PipelineRunnerConfig: High-level configuration governing runner runtime composition and batch policies.
- PipelineRunReport: Typed, immutable aggregated execution report.
- Exception hierarchy for top-level pipeline runner errors.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.batch_coordinator import (
    BatchCandidateOutcome,
    BatchRunConfig,
    BatchRunSummary,
    CandidateOrderingPolicy,
)
from schemas.pipeline_factory import (
    PipelineRuntimeConfig,
    RuntimeEnvironment,
)


# =============================================================================
# Exception Hierarchy
# =============================================================================

class PipelineRunnerError(Exception):
    """Base exception for Stage 8.17 runner operations."""
    pass


class PipelineRunnerConfigurationError(PipelineRunnerError):
    """Raised when pipeline runner configuration violates invariants."""
    pass


class PipelineRunnerExecutionError(PipelineRunnerError):
    """Raised when an unrecoverable runtime execution error occurs."""
    pass


# =============================================================================
# Runner Configuration
# =============================================================================

class PipelineRunnerConfig(BaseModel):
    """
    Top-level configuration governing EditorialPipelineRunner composition and execution.
    Wraps authoritative PipelineRuntimeConfig with batch coordination policies.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_config: PipelineRuntimeConfig = Field(
        ...,
        description="Underlying runtime configuration for PipelineFactory assembly",
    )
    dry_run: bool = Field(
        default=False,
        description="When true, executes in fail-closed dry-run mode (zero publication side effects)",
    )
    max_candidates: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Deterministic ceiling on candidates processed in each batch run",
    )
    ordering_policy: CandidateOrderingPolicy = Field(
        default=CandidateOrderingPolicy.CANDIDATE_ID,
        description="Deterministic ordering policy for candidate processing sequence",
    )
    dry_run_channel_id: Optional[str] = Field(
        default=None,
        description="Target mock channel ID for dry-run publishing receipts",
    )

    def resolve_dry_run_channel_id(self) -> str:
        """Resolves target dry run channel ID fail-closed."""
        if self.dry_run_channel_id and str(self.dry_run_channel_id).strip():
            return str(self.dry_run_channel_id).strip()
        if self.runtime_config.telegram_test_channel_id:
            return self.runtime_config.telegram_test_channel_id
        return "-100_dry_run_channel"

    def to_batch_config(
        self,
        run_id: str,
        dry_run_override: Optional[bool] = None,
        max_candidates_override: Optional[int] = None,
        ordering_policy_override: Optional[CandidateOrderingPolicy] = None,
    ) -> BatchRunConfig:
        """
        Synthesizes a BatchRunConfig for an editorial execution pass.
        """
        return BatchRunConfig(
            run_id=run_id,
            environment=self.runtime_config.environment,
            max_candidates=max_candidates_override if max_candidates_override is not None else self.max_candidates,
            dry_run=self.dry_run if dry_run_override is None else dry_run_override,
            ordering_policy=ordering_policy_override if ordering_policy_override is not None else self.ordering_policy,
        )

    @classmethod
    def create_offline(
        cls,
        state_dir: Path,
        ledger_file: Path,
        dry_run: bool = False,
        max_candidates: int = 20,
        ordering_policy: CandidateOrderingPolicy = CandidateOrderingPolicy.CANDIDATE_ID,
        **kwargs: Any,
    ) -> PipelineRunnerConfig:
        """Convenience constructor for OFFLINE testing configuration."""
        runtime_config = PipelineRuntimeConfig(
            environment=RuntimeEnvironment.OFFLINE,
            state_dir=state_dir,
            ledger_file=ledger_file,
            use_mock_providers=True,
            **kwargs,
        )
        return cls(
            runtime_config=runtime_config,
            dry_run=dry_run,
            max_candidates=max_candidates,
            ordering_policy=ordering_policy,
        )

    @classmethod
    def create_test(
        cls,
        state_dir: Path,
        ledger_file: Path,
        test_channel_id: str = "-100_test_channel",
        dry_run: bool = False,
        max_candidates: int = 20,
        ordering_policy: CandidateOrderingPolicy = CandidateOrderingPolicy.CANDIDATE_ID,
        **kwargs: Any,
    ) -> PipelineRunnerConfig:
        """Convenience constructor for TEST environment configuration."""
        runtime_config = PipelineRuntimeConfig(
            environment=RuntimeEnvironment.TEST,
            state_dir=state_dir,
            ledger_file=ledger_file,
            telegram_test_channel_id=test_channel_id,
            use_mock_providers=True,
            **kwargs,
        )
        return cls(
            runtime_config=runtime_config,
            dry_run=dry_run,
            max_candidates=max_candidates,
            ordering_policy=ordering_policy,
        )


# =============================================================================
# Pipeline Run Report
# =============================================================================

class PipelineRunReport(BaseModel):
    """
    Typed, immutable ephemeral report summarizing a complete pipeline run.
    Contains aggregated operational telemetry and per-candidate outcomes.
    In-memory representation; does not replace authoritative ledger or state stores.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(..., description="Unique run identifier")
    environment: RuntimeEnvironment = Field(..., description="Target runtime environment")
    is_dry_run: bool = Field(default=False, description="Whether the run was a dry run")
    started_at: datetime = Field(..., description="Execution start timestamp")
    completed_at: datetime = Field(..., description="Execution completion timestamp")
    total_candidates_provided: int = Field(..., ge=0, description="Total candidates in handoff")
    total_candidates_processed: int = Field(..., ge=0, description="Total candidates processed")
    published_count: int = Field(..., ge=0, description="Count of successfully published items")
    held_count: int = Field(..., ge=0, description="Count of held items")
    rejected_count: int = Field(..., ge=0, description="Count of rejected items")
    failed_count: int = Field(..., ge=0, description="Count of failed items")
    qualified_candidates_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total candidates qualified under entity resolution",
    )
    outcomes: list[BatchCandidateOutcome] = Field(
        default_factory=list,
        description="Ordered list of per-candidate execution outcomes",
    )
    batch_summary: Optional[BatchRunSummary] = Field(
        default=None,
        description="Underlying BatchRunSummary from the coordinator",
    )
    execution_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total wall-clock execution time in milliseconds",
    )

    @property
    def is_success(self) -> bool:
        """True if no candidates suffered unhandled pipeline failures."""
        return self.failed_count == 0

    @property
    def has_publications(self) -> bool:
        """True if at least one candidate reached publication or dry-run publication."""
        return self.published_count > 0

    @property
    def summary(self) -> Optional[BatchRunSummary]:
        """Convenience property accessing the underlying BatchRunSummary."""
        return self.batch_summary

    @classmethod
    def from_batch_summary(
        cls,
        summary: BatchRunSummary,
        execution_time_ms: float = 0.0,
    ) -> PipelineRunReport:
        """Builds a PipelineRunReport from a BatchRunSummary."""
        return cls(
            run_id=summary.run_id,
            environment=summary.environment,
            is_dry_run=summary.is_dry_run,
            started_at=summary.started_at,
            completed_at=summary.completed_at,
            total_candidates_provided=summary.total_candidates_provided,
            total_candidates_processed=summary.total_candidates_processed,
            published_count=summary.published_count,
            held_count=summary.held_count,
            rejected_count=summary.rejected_count,
            failed_count=summary.failed_count,
            qualified_candidates_count=summary.qualified_candidates_count,
            outcomes=list(summary.outcomes),
            batch_summary=summary,
            execution_time_ms=execution_time_ms,
        )
