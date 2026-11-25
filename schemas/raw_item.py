"""
Raw Item Schema - Cinema & Theatre Review Editorial OS v1.0.1
Data contract for directly retrieved source artifacts.
Represents an immutable observation of fetched source data without storing
giant raw payloads directly inside the metadata record.
"""

from datetime import datetime
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RawPayloadMetadata(StrictModel):
    """Metadata describing the raw retrieved payload."""
    storage_ref: str | None = Field(
        default=None,
        description="Optional path or URI to transient blob storage in cache/",
    )
    content_type: str = Field(
        default="text/html; charset=utf-8",
        description="MIME type of the raw retrieved artifact",
    )
    content_length: int = Field(
        default=0,
        ge=0,
        description="Byte length of the raw retrieved artifact",
    )
    content_hash: str = Field(
        ...,
        description="Deterministic SHA-256 hash of the raw payload content",
    )

    @field_validator("content_hash")
    @classmethod
    def validate_hash_format(cls, v: str) -> str:
        if not re.match(r"^[0-9a-f]{64}$", v.lower()):
            raise ValueError("content_hash must be a 64-character lowercase SHA-256 hex digest")
        return v.lower()


class TransportMetadata(StrictModel):
    """Transport-layer diagnostics and HTTP metadata."""
    http_status: int | None = Field(
        default=200,
        ge=100,
        le=599,
        description="HTTP status code returned by the server",
    )
    final_url: str | None = Field(
        default=None,
        description="Final destination URL after any redirects",
    )
    etag: str | None = Field(
        default=None,
        description="HTTP ETag header value if present",
    )
    last_modified: str | None = Field(
        default=None,
        description="HTTP Last-Modified header value if present",
    )
    response_time_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Round-trip transport response time in milliseconds",
    )


class RawItem(BaseModel):
    """
    Directly retrieved source artifact.
    Immutable observation of source output at retrieved_at timestamp.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_item_id: str = Field(
        ...,
        description="Unique identifier for this raw item instance (e.g. raw_src_run_hash)",
    )
    run_id: str = Field(
        ...,
        description="Identifier of the collector run that fetched this item",
    )
    source_id: str = Field(
        ...,
        description="Identifier of the source in the canonical Source Registry",
    )
    native_id: str | None = Field(
        default=None,
        description="Source-native identifier (entry ID, post ID, DOI, etc.) if provided",
    )
    source_url: str = Field(
        ...,
        description="URL from which the item was fetched",
    )
    retrieved_at: datetime = Field(
        ...,
        description="UTC timestamp when the item was retrieved from transport",
    )
    payload: RawPayloadMetadata = Field(
        ...,
        description="Metadata describing payload content, length, and SHA-256 hash",
    )
    transport: TransportMetadata = Field(
        default_factory=TransportMetadata,
        description="Transport-level metadata and diagnostic headers",
    )

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("source_url must be an HTTP or HTTPS URL")
        return v
