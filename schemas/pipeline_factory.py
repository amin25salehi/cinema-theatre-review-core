"""
Pipeline Factory & Composition Contracts - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.15: Production Runtime Composition & Candidate Ingestion Boundary.

Defines:
- RuntimeEnvironment: OFFLINE, TEST, PRODUCTION
- PipelineRuntimeConfig: Strict Pydantic v2 configuration for factory assembly
- CandidateOrchestrationBundle: Typed argument bundle passed into EditorialPipelineOrchestrator.run_pipeline
- Exception hierarchy: BridgeValidationError, RuntimeConfigurationError, EnvironmentMismatchError
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.decision_card import ContentType, PublicationFormat
from schemas.evidence_card import (
    Claim,
    EntityReference,
    EvidenceItem,
    ImageEvidenceItem,
)
from schemas.normalized_item import NormalizedItem
from schemas.publication_ledger import PublishEnvironment
from schemas.publication_readiness import MediaProvenanceReference


# =============================================================================
# Exceptions
# =============================================================================

class PipelineCompositionError(Exception):
    """Base exception for Stage 8.15 composition and boundary operations."""
    pass


class BridgeValidationError(PipelineCompositionError):
    """Raised when Candidate or NormalizedItem fails validation during ingestion bridging."""
    pass


class RuntimeConfigurationError(PipelineCompositionError):
    """Raised when runtime environment configuration violates invariants."""
    pass


class EnvironmentMismatchError(PipelineCompositionError):
    """Raised when operational environment and configuration channels or tokens conflict."""
    pass


# =============================================================================
# Runtime Environment Enum
# =============================================================================

class RuntimeEnvironment(str, Enum):
    OFFLINE = "offline"
    TEST = "test"
    PRODUCTION = "production"


# =============================================================================
# Pipeline Runtime Configuration Contract
# =============================================================================

class PipelineRuntimeConfig(BaseModel):
    """
    Configuration model for constructing the complete editorial pipeline runtime.
    Guarantees strict separation of OFFLINE, TEST, and PRODUCTION environments.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: RuntimeEnvironment = Field(
        ...,
        description="Target runtime execution environment (OFFLINE, TEST, PRODUCTION)",
    )
    config_dir: Path = Field(
        default=Path("config"),
        description="Path to canonical JSON configuration directory",
    )
    sources_dir: Path = Field(
        default=Path("config/sources"),
        description="Path to canonical source registry directory",
    )
    entities_dir: Path = Field(
        default=Path("config/entities"),
        description="Path to canonical entity registry directory",
    )
    state_dir: Path = Field(
        default=Path("data"),
        description="Path to directory housing subsystem state files",
    )
    ledger_file: Path = Field(
        default=Path("data/publication_ledger.json"),
        description="Path to publication ledger JSON file",
    )
    telegram_bot_token: Optional[str] = Field(
        default=None,
        description="Telegram bot API token (required for live delivery in TEST/PRODUCTION)",
    )
    telegram_test_channel_id: Optional[str] = Field(
        default=None,
        description="Target Telegram chat ID for test channel",
    )
    telegram_production_channel_id: Optional[str] = Field(
        default=None,
        description="Target Telegram chat ID for authoritative production channel",
    )
    telegram_production_enabled: bool = Field(
        default=False,
        description="Explicit master boolean guard for production Telegram publishing",
    )
    use_mock_providers: bool = Field(
        default=True,
        description="Whether to instantiate mock LLM and Draft providers (forced True in OFFLINE)",
    )

    @model_validator(mode="after")
    def validate_environment_invariants(self) -> PipelineRuntimeConfig:
        """
        Enforces strict fail-closed configuration invariants across environments.
        """
        # Production Invariant: Cannot configure PRODUCTION without explicit master switch, channel, and token
        if self.environment == RuntimeEnvironment.PRODUCTION:
            if not self.telegram_production_enabled:
                raise RuntimeConfigurationError(
                    "Cannot configure PRODUCTION runtime environment when telegram_production_enabled is False. "
                    "Fail-closed guard prevents unverified production setup."
                )
            if not self.telegram_production_channel_id or not str(self.telegram_production_channel_id).strip():
                raise RuntimeConfigurationError(
                    "telegram_production_channel_id is required and non-empty for PRODUCTION runtime environment."
                )
            if not self.telegram_bot_token or not str(self.telegram_bot_token).strip():
                raise RuntimeConfigurationError(
                    "telegram_bot_token is required for PRODUCTION runtime environment."
                )

        # Test Invariant: TEST environment must not be configured with production channel ID
        if self.environment == RuntimeEnvironment.TEST:
            if self.telegram_production_channel_id and (
                self.telegram_production_channel_id == self.telegram_test_channel_id
            ):
                raise EnvironmentMismatchError(
                    "telegram_test_channel_id and telegram_production_channel_id must not be identical."
                )

        return self


# =============================================================================
# Candidate Orchestration Bundle Contract
# =============================================================================

class CandidateOrchestrationBundle(BaseModel):
    """
    Immutable parameter bundle produced by CandidateBridge and ingested by
    EditorialPipelineOrchestrator.run_pipeline().
    Enforces strict alignment with the frozen Stage 8.14 pipeline orchestrator signature.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    item: NormalizedItem = Field(
        ...,
        description="The normalized item entering the editorial pipeline",
    )
    candidate_id: str = Field(
        ...,
        description="Unique identifier of the originating candidate",
    )
    headline_working: str = Field(
        ...,
        description="Deterministic source-derived working headline in primary editorial language",
    )
    target_topic: str = Field(
        ...,
        description="Primary topic taxonomy category derived deterministically",
    )
    content_type: ContentType = Field(
        default=ContentType.CINEMA,
        description="Target medium content type (CINEMA or THEATRE)",
    )
    format_type: PublicationFormat = Field(
        default=PublicationFormat.NEWS_BRIEF,
        description="Editorial publication format",
    )
    claims: list[Claim] = Field(
        ...,
        min_length=1,
        description="Source-derived initial atomic claim(s) with status UNVERIFIED",
    )
    evidence: list[EvidenceItem] = Field(
        ...,
        min_length=1,
        description="Raw evidence items referencing the source material",
    )
    entities: list[EntityReference] = Field(
        default_factory=list,
        description="Deterministically resolved known canonical entity references",
    )
    structured_claim: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional structured claim metadata for identity resolution",
    )
    images: Optional[list[ImageEvidenceItem]] = Field(
        default=None,
        description="Optional image evidence items extracted from normalized payload",
    )
    media_assets: Optional[list[MediaProvenanceReference]] = Field(
        default=None,
        description="Optional media provenance references evaluated during QA",
    )
    require_media: bool = Field(
        default=False,
        description="Whether media assets are required for publication readiness",
    )
    publish_environment: PublishEnvironment = Field(
        default=PublishEnvironment.TEST,
        description="Target publication ledger and transport environment",
    )
    is_commercial_only: bool = Field(
        default=False,
        description="Commercial-only gate flag (evaluated by decision engine)",
    )
    is_iranian_daily_news: bool = Field(
        default=False,
        description="Iranian daily news flag (evaluated by decision engine)",
    )
    iran_exception_matched: Optional[str] = Field(
        default=None,
        description="Identifier of matched Iran exception if applicable",
    )

    def to_orchestrator_kwargs(self) -> dict[str, Any]:
        """
        Maps bundle fields exactly to the keyword arguments of
        EditorialPipelineOrchestrator.run_pipeline().
        """
        return {
            "item": self.item,
            "claims": self.claims,
            "evidence": self.evidence,
            "entities": self.entities,
            "headline_working": self.headline_working,
            "target_topic": self.target_topic,
            "content_type": self.content_type,
            "format_type": self.format_type,
            "structured_claim": self.structured_claim,
            "images": self.images,
            "media_assets": self.media_assets,
            "require_media": self.require_media,
            "publish_environment": self.publish_environment,
            "is_duplicate": False,
            "is_commercial_only": self.is_commercial_only,
            "is_iranian_daily_news": self.is_iranian_daily_news,
            "iran_exception_matched": self.iran_exception_matched,
        }
