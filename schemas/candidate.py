"""
Candidate Schema - Cinema & Theatre Review Editorial OS v1.0.1
Data contract for candidate ingestion units entering the Editorial Core.
A Candidate has passed acquisition, normalization, and item deduplication
but has NOT yet received an editorial decision.
"""

from datetime import datetime
from enum import Enum
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.story_identity import CandidateIdentity, ChangeRecord, StoryLink


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscoveryReasonCode(str, Enum):
    """Controlled diagnostic reason codes indicating why a candidate entered ingestion."""
    OFFICIAL_SOURCE = "official_source"
    MAJOR_FESTIVAL = "major_festival"
    REFERENCE_ENTITY = "reference_entity"
    NEW_BOOK = "new_book"
    ACADEMIC_DISCOVERY = "academic_discovery"
    CRITICAL_PUBLICATION = "critical_publication"
    ARCHIVE_UPDATE = "archive_update"
    THEATRE_PRODUCTION = "theatre_production"
    AWARD = "award"
    EDITORIAL_WATCHLIST = "editorial_watchlist"


class CandidateStatus(str, Enum):
    """Ingestion status of a Candidate."""
    PENDING_EDITORIAL = "pending_editorial"
    INGESTED = "ingested"


class Candidate(StrictModel):
    """
    Ingestion unit passed from ingestion boundary into Editorial OS.
    MUST NOT contain editorial decisions, scores, or publication verdicts.
    """
    candidate_id: str = Field(
        ...,
        description="Unique identifier for the candidate unit (e.g. cand_sha256)",
    )
    normalized_item_refs: list[str] = Field(
        ...,
        min_length=1,
        description="References to NormalizedItem identifiers comprising this candidate",
    )
    source_refs: list[str] = Field(
        ...,
        min_length=1,
        description="Source identifiers from which normalized items originated",
    )
    discovery_reason_codes: list[DiscoveryReasonCode] = Field(
        ...,
        min_length=1,
        description="Controlled diagnostic reasons why this item was discovered",
    )
    story_hint: str | None = Field(
        default=None,
        description="Non-editorial clue or preliminary topic tag (e.g. Cannes 2026 Selection)",
    )
    status: CandidateStatus = Field(
        default=CandidateStatus.PENDING_EDITORIAL,
        description="Current ingestion state of the candidate",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when this Candidate was assembled by the ingestion boundary",
    )
    identity: Optional[CandidateIdentity] = Field(
        default=None,
        description="Stage 8.6 Candidate identity metadata",
    )
    story_link: Optional[StoryLink] = Field(
        default=None,
        description="Stage 8.6 Story linking resolution",
    )
    change_record: Optional[ChangeRecord] = Field(
        default=None,
        description="Stage 8.6 Change detection record",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_editorial_leakage(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden_keys = {
                "important",
                "publish",
                "editorial_fit",
                "evidence_strength",
                "editorial_score",
                "editorial_decision",
                "gate_status",
            }
            intersection = forbidden_keys.intersection(data.keys())
            if intersection:
                raise ValueError(
                    f"Candidate boundary violation: editorial keys {sorted(intersection)} "
                    f"must not be present on ingestion Candidates."
                )
        return data
