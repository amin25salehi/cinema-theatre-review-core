"""
Operational Pipeline Controller Contracts - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.18: Top-Level Multi-Phase Operational Execution & Telemetry Contracts.

Defines:
- OperationalStatus: Canonical operational exit status (SUCCESS, NO_WORK, PARTIAL_SUCCESS, FAILED).
- OperationalRunConfig: Typed, immutable configuration governing acquisition and editorial execution.
- OperationalRunReport: Aggregated multi-phase execution report with atomic persistence support.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.batch_coordinator import CandidateOrderingPolicy
from schemas.pipeline_factory import PipelineRuntimeConfig, RuntimeEnvironment
from schemas.pipeline_runner import PipelineRunnerConfig, PipelineRunReport


# =============================================================================
# Operational Status
# =============================================================================

class OperationalStatus(str, Enum):
    """
    Authoritative exit status of an operational pipeline run.
    """
    SUCCESS = "SUCCESS"                 # Completed normally; Gate 4 HOLD / REJECT are normal outcomes (Exit 0)
    NO_WORK = "NO_WORK"                 # Acquisition produced 0 candidates (Exit 0)
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS" # Batch completed, but 1+ candidates suffered unhandled errors (Exit 2)
    FAILED = "FAILED"                   # Operational crash, invalid config, or all candidates failed (Exit 1)


# =============================================================================
# Operational Run Configuration
# =============================================================================

class OperationalRunConfig(BaseModel):
    """
    Configuration governing the multi-phase execution of GenericCollectorEngine
    and EditorialPipelineRunner under EditorialPipelineController.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: RuntimeEnvironment = Field(
        default=RuntimeEnvironment.OFFLINE,
        description="Target runtime environment (OFFLINE, TEST, PRODUCTION)",
    )
    dry_run: bool = Field(
        default=True,
        description="Operational/editorial dry-run: fail-closed zero publication side-effects",
    )
    collector_dry_run: bool = Field(
        default=False,
        description="Collector plan-only mode (zero network reads when True)",
    )
    use_mock_providers: bool = Field(
        default=True,
        description="Whether to use mock LLM and Draft providers (defaults to True)",
    )
    max_candidates: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Ceiling on candidates processed during editorial batch execution",
    )
    ordering_policy: CandidateOrderingPolicy = Field(
        default=CandidateOrderingPolicy.CANDIDATE_ID,
        description="Candidate sorting policy for deterministic batch processing",
    )
    source_id: Optional[str] = Field(
        default=None,
        description="Optional filter limiting acquisition to a single source ID (None = all eligible sources)",
    )
    max_sources: Optional[int] = Field(
        default=None,
        ge=1,
        description="Optional ceiling on number of sources evaluated during acquisition",
    )
    save_report: bool = Field(
        default=True,
        description="Whether to persist OperationalRunReport JSON to report_dir",
    )
    report_dir: Path = Field(
        default=Path("data/run_reports"),
        description="Directory for persisted operational run reports",
    )
    state_dir: Optional[Path] = Field(
        default=None,
        description="Optional override directory for state stores (defaults to data/)",
    )
    ledger_file: Optional[Path] = Field(
        default=None,
        description="Optional override path for publication ledger",
    )
    test_channel_id: str = Field(
        default="-100_test_channel",
        description="Telegram channel ID for TEST environment execution",
    )
    verbose: bool = Field(
        default=False,
        description="Enable detailed telemetry output",
    )

    def to_runner_config(self) -> PipelineRunnerConfig:
        """
        Synthesizes authoritative PipelineRunnerConfig for EditorialPipelineRunner.
        """
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        test_channel = os.getenv("TELEGRAM_TEST_CHANNEL_ID") or self.test_channel_id

        use_mock = self.use_mock_providers if self.environment != RuntimeEnvironment.OFFLINE else True
        if self.dry_run:
            use_mock = True

        runtime_config = PipelineRuntimeConfig(
            environment=self.environment,
            state_dir=self.state_dir or Path("data"),
            ledger_file=self.ledger_file or Path("data/publication_ledger.json"),
            telegram_bot_token=bot_token,
            telegram_test_channel_id=test_channel if self.environment == RuntimeEnvironment.TEST else None,
            use_mock_providers=use_mock,
        )
        return PipelineRunnerConfig(
            runtime_config=runtime_config,
            dry_run=self.dry_run,
            max_candidates=self.max_candidates,
            ordering_policy=self.ordering_policy,
            dry_run_channel_id=test_channel,
        )


# =============================================================================
# Operational Run Report
# =============================================================================

class OperationalRunReport(BaseModel):
    """
    Typed, immutable aggregated operational report combining acquisition metrics,
    handoff metadata, and editorial batch execution outcomes.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(..., description="Authoritative run identifier from acquisition")
    status: OperationalStatus = Field(..., description="Canonical exit status")
    environment: RuntimeEnvironment = Field(..., description="Runtime environment")
    started_at: datetime = Field(..., description="Pipeline execution start timestamp")
    completed_at: datetime = Field(..., description="Pipeline execution completion timestamp")
    execution_time_ms: float = Field(default=0.0, ge=0.0, description="Total wall-clock duration in ms")
    collector_dry_run: bool = Field(default=False, description="Whether collector ran in plan-only mode")
    editorial_dry_run: bool = Field(default=True, description="Whether editorial ran in dry-run mode")
    source_id: Optional[str] = Field(default=None, description="Target source ID filter if applied")

    # Metrics
    raw_items_count: int = Field(default=0, ge=0, description="Raw items fetched by collector")
    normalized_items_count: Optional[int] = Field(default=None, ge=0, description="Normalized items produced from raw items")
    candidates_acquired_count: int = Field(default=0, ge=0, description="Candidates produced by collector")
    qualified_candidates_count: Optional[int] = Field(default=None, ge=0, description="Candidates qualifying under entity resolution")
    story_linked_candidates_count: Optional[int] = Field(default=None, ge=0, description="Candidates with deterministic story link")
    corroborated_candidates_count: Optional[int] = Field(default=None, ge=0, description="Candidates with verified multi-source or primary corroboration")
    candidates_processed_count: int = Field(default=0, ge=0, description="Candidates processed in editorial pass")
    published_count: int = Field(default=0, ge=0, description="Published (or dry-run published) candidates")
    held_count: int = Field(default=0, ge=0, description="Held candidates (Gate 4 HOLD)")
    rejected_count: int = Field(default=0, ge=0, description="Rejected candidates")
    failed_count: int = Field(default=0, ge=0, description="Failed candidates (unhandled errors)")

    error_message: Optional[str] = Field(default=None, description="Fatal or diagnostic error summary")
    editorial_report: Optional[PipelineRunReport] = Field(
        default=None,
        description="Detailed underlying PipelineRunReport from EditorialPipelineRunner",
    )
    report_path: Optional[str] = Field(default=None, description="File path where JSON report was persisted")

    @property
    def exit_code(self) -> int:
        """
        Maps OperationalStatus to process exit code:
        - SUCCESS (0)
        - NO_WORK (0)
        - PARTIAL_SUCCESS (2)
        - FAILED (1)
        """
        if self.status in (OperationalStatus.SUCCESS, OperationalStatus.NO_WORK):
            return 0
        if self.status == OperationalStatus.PARTIAL_SUCCESS:
            return 2
        return 1

    @classmethod
    def create_empty(
        cls,
        run_id: str,
        config: OperationalRunConfig,
        started_at: datetime,
        status: OperationalStatus = OperationalStatus.NO_WORK,
        error_message: Optional[str] = None,
        raw_items_count: int = 0,
        candidates_acquired_count: int = 0,
    ) -> OperationalRunReport:
        """Convenience builder for acquisition-only or no-work outcomes."""
        now = datetime.now(timezone.utc)
        ms = (now - started_at).total_seconds() * 1000.0
        return cls(
            run_id=run_id,
            status=status,
            environment=config.environment,
            started_at=started_at,
            completed_at=now,
            execution_time_ms=ms,
            collector_dry_run=config.collector_dry_run,
            editorial_dry_run=config.dry_run,
            source_id=config.source_id,
            raw_items_count=raw_items_count,
            candidates_acquired_count=candidates_acquired_count,
            error_message=error_message,
        )
