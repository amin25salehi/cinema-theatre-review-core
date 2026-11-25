"""
Normalized Item Schema - Cinema & Theatre Review Editorial OS v1.0.1
Common structured representation of an acquired source item after normalization.
Normalization is deterministic transformation, not editorial interpretation.
"""

from datetime import datetime
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NormalizedMediaRef(StrictModel):
    """Media reference extracted from normalized content."""
    media_type: str = Field(
        ...,
        description="Type of media resource: image, video, audio, document",
    )
    url: str = Field(
        ...,
        description="Direct URL to media resource",
    )
    caption: str | None = Field(
        default=None,
        description="Caption or alternative text accompanying the media",
    )
    width: int | None = Field(
        default=None,
        ge=0,
        description="Width in pixels if known",
    )
    height: int | None = Field(
        default=None,
        ge=0,
        description="Height in pixels if known",
    )


class NormalizedItem(StrictModel):
    """
    Common normalized representation of an acquired source item.
    Enforces strict distinction between published_at, updated_at, and retrieved_at.
    """
    item_id: str = Field(
        ...,
        description="Canonical identity of the normalized item (e.g. norm_sha256)",
    )
    raw_item_id: str = Field(
        ...,
        description="Foreign reference to the immutable RawItem observation",
    )
    source_id: str = Field(
        ...,
        description="Identifier of the origin source in the canonical Source Registry",
    )
    native_id: str | None = Field(
        default=None,
        description="Source-native identifier (DOI, ISBN, entry ID, external ID) if available",
    )
    canonical_url: str = Field(
        ...,
        description="Deterministically canonicalized item URL",
    )
    title: str = Field(
        ...,
        description="Clean, normalized item title",
    )
    summary: str | None = Field(
        default=None,
        description="Extracted summary or abstract from source, if provided",
    )
    content_text: str = Field(
        ...,
        description="Normalized plain text content stripped of HTML tags and formatting wrappers",
    )
    language: str | None = Field(
        default=None,
        description="ISO 639-1 language code if detected or declared",
    )
    published_at: datetime | None = Field(
        default=None,
        description="Original publication timestamp as stated by the source (never inferred from retrieved_at)",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Source modification timestamp if explicitly provided",
    )
    retrieved_at: datetime = Field(
        ...,
        description="UTC timestamp when the raw source item was retrieved",
    )
    authors: list[str] = Field(
        default_factory=list,
        description="List of extracted author or contributor names",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="List of raw source category or tag labels",
    )
    media: list[NormalizedMediaRef] = Field(
        default_factory=list,
        description="List of media attachments or images referenced by the item",
    )
    entity_mentions: list[str] = Field(
        default_factory=list,
        description="Extracted entity mentions or explicit tag references",
    )
    fingerprints: dict[str, str] = Field(
        default_factory=dict,
        description="Deterministic cryptographic fingerprints (e.g. text_sha256, title_sha256)",
    )

    @field_validator("canonical_url")
    @classmethod
    def validate_canonical_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("canonical_url must be an HTTP or HTTPS URL")
        return v
