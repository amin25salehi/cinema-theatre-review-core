"""
Collector Run & Execution Schemas - Cinema & Theatre Review Editorial OS v1.0.1
Data contracts for collector execution, context, checkpoints, and structured run results.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CollectorRunStatus(str, Enum):
    """Execution status of a collector run."""
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class CollectorErrorType(str, Enum):
    """Controlled taxonomy of collector and transport error categories."""
    TRANSPORT_ERROR = "transport_error"
    TIMEOUT = "timeout"
    DNS_ERROR = "dns_error"
    TLS_ERROR = "tls_error"
    HTTP_ERROR = "http_error"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_REQUIRED = "authentication_required"
    ACCESS_DENIED = "access_denied"
    PARSE_ERROR = "parse_error"
    SCHEMA_ERROR = "schema_error"
    NORMALIZATION_ERROR = "normalization_error"
    DEDUP_ERROR = "dedup_error"
    CHECKPOINT_ERROR = "checkpoint_error"
    UNEXPECTED_ERROR = "unexpected_error"


class CollectorErrorInfo(StrictModel):
    """Structured diagnostic record for an acquisition or transport error."""
    error_type: CollectorErrorType = Field(
        ...,
        description="Controlled category of the collector error",
    )
    message: str = Field(
        ...,
        description="Sanitized error description (credentials/secrets stripped)",
    )
    source_id: str = Field(
        ...,
        description="Source identifier where the error occurred",
    )
    run_id: str | None = Field(
        default=None,
        description="Collector run identifier associated with this error",
    )
    http_status: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="HTTP status code if applicable",
    )
    retryable: bool = Field(
        default=False,
        description="Whether this error is eligible for exponential backoff retry",
    )
    occurred_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the error occurred",
    )


class CheckpointCursor(StrictModel):
    """Represents a collector resume cursor across runs."""
    strategy: str = Field(
        ...,
        description="Cursor strategy: page, cursor, offset, since, last_seen_id, last_seen_timestamp",
    )
    value: str = Field(
        ...,
        description="Serialized cursor value or position",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the cursor was saved",
    )

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        valid_strategies = {
            "page",
            "cursor",
            "offset",
            "since",
            "last_seen_id",
            "last_seen_timestamp",
        }
        if v not in valid_strategies:
            raise ValueError(f"Invalid cursor strategy '{v}'. Expected one of {sorted(valid_strategies)}")
        return v


class CollectionContext(StrictModel):
    """
    Execution context provided to a collector.
    Must NOT contain any editorial policy, scoring, or decision objects.
    """
    source_id: str = Field(
        ...,
        description="Source identifier from the canonical Source Registry",
    )
    run_id: str = Field(
        ...,
        description="Unique execution run identifier",
    )
    cursor: str | None = Field(
        default=None,
        description="Optional pagination or resume cursor string",
    )
    checkpoint: CheckpointCursor | None = Field(
        default=None,
        description="Last verified checkpoint cursor if resuming",
    )
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the collection run was initiated",
    )
    max_items: int | None = Field(
        default=None,
        gt=0,
        description="Optional maximum items to retrieve in this run",
    )
    request_budget: int | None = Field(
        default=None,
        gt=0,
        description="Maximum HTTP/API requests permitted in this execution",
    )
    force: bool = Field(
        default=False,
        description="Whether to bypass local freshness/checkpoint caches",
    )
    dry_run: bool = Field(
        default=False,
        description="Whether to simulate retrieval without persisting state",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_editorial_context(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = {"editorial_rules", "authority_map", "editorial_policy", "decision"}
            found = forbidden.intersection(data.keys())
            if found:
                raise ValueError(f"CollectionContext must not contain editorial policies: {sorted(found)}")
        return data


class CollectorRunResult(StrictModel):
    """
    Structured outcome of a collector execution run.
    Enforces internal count consistency and transparent status reporting.
    """
    run_id: str = Field(
        ...,
        description="Unique execution run identifier",
    )
    source_id: str = Field(
        ...,
        description="Source identifier from the canonical Source Registry",
    )
    collector_type: str = Field(
        ...,
        description="Collector family type (e.g. rss, api, sitemap, web_index, press_area, static_page)",
    )
    started_at: datetime = Field(
        ...,
        description="UTC timestamp when the run began",
    )
    finished_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the run concluded",
    )
    status: CollectorRunStatus = Field(
        ...,
        description="Terminal execution status: completed, partial, failed, rate_limited, blocked",
    )
    items_seen: int = Field(
        default=0,
        ge=0,
        description="Total source entries inspected during collection",
    )
    items_new: int = Field(
        default=0,
        ge=0,
        description="Items newly acquired and persisted in this run",
    )
    items_updated: int = Field(
        default=0,
        ge=0,
        description="Existing items with modified content or updated metadata",
    )
    items_unchanged: int = Field(
        default=0,
        ge=0,
        description="Items inspected whose content fingerprint matched existing records",
    )
    items_skipped: int = Field(
        default=0,
        ge=0,
        description="Items skipped due to filter, schema mismatch, or budget",
    )
    errors: list[CollectorErrorInfo] = Field(
        default_factory=list,
        description="Structured errors or warnings encountered during the run",
    )
    checkpoint: CheckpointCursor | None = Field(
        default=None,
        description="Terminal cursor state achieved at end of run",
    )

    @model_validator(mode="after")
    def validate_count_consistency(self) -> "CollectorRunResult":
        # Logical count consistency checks
        if self.items_seen < self.items_new:
            raise ValueError(
                f"items_seen ({self.items_seen}) cannot be less than items_new ({self.items_new})"
            )
        categorized_sum = self.items_new + self.items_updated + self.items_unchanged + self.items_skipped
        if self.items_seen < categorized_sum:
            raise ValueError(
                f"items_seen ({self.items_seen}) is less than sum of categorized items ({categorized_sum})"
            )
        return self


class EngineRunResult(StrictModel):
    """
    Auditable structured result of an engine execution run across one or more sources.
    Encapsulates high-level lifecycle metrics, per-source CollectorRunResult models,
    and ingestion candidate counts without exposing secrets or making editorial decisions.
    """
    run_id: str = Field(..., description="Unique engine execution identifier")
    started_at: datetime = Field(..., description="Run initialization timestamp")
    finished_at: datetime = Field(..., description="Run completion timestamp")
    dry_run: bool = Field(default=False, description="Whether this run was executed in dry-run mode")
    total_sources: int = Field(default=0, ge=0, description="Total sources evaluated in the matrix")
    executed_count: int = Field(default=0, ge=0, description="Count of sources actually executed")
    skipped_count: int = Field(default=0, ge=0, description="Count of sources skipped due to policy or filter")
    successful_count: int = Field(default=0, ge=0, description="Count of sources completing with COMPLETED status")
    partial_count: int = Field(default=0, ge=0, description="Count of sources completing with PARTIAL status")
    failed_count: int = Field(default=0, ge=0, description="Count of sources completing with FAILED/BLOCKED/RATE_LIMITED status")
    total_raw_items: int = Field(default=0, ge=0, description="Total raw items acquired across all sources")
    total_normalized_items: int = Field(default=0, ge=0, description="Total normalized items created")
    total_candidates: int = Field(default=0, ge=0, description="Total Candidate units passed to ingestion boundary")
    total_unchanged: int = Field(default=0, ge=0, description="Total items recognized as unchanged by deduplicator")
    total_updated: int = Field(default=0, ge=0, description="Total items recognized as updated by deduplicator")
    source_results: dict[str, CollectorRunResult] = Field(default_factory=dict, description="Per-source execution results")
    candidates: list[Any] = Field(default_factory=list, description="Ingestion Candidate objects produced by this run")
    skipped_reasons: dict[str, str] = Field(default_factory=dict, description="Diagnostic reasons why sources were skipped")
    failure_summaries: list[dict[str, Any]] = Field(default_factory=list, description="Sanitized diagnostic error summaries")
