"""
Publication Ledger & Telegram Publishing Schemas - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.13: Telegram Publishing & Publication Ledger.

Strict Pydantic v2 data contracts enforcing:
- Exclusive acceptance of PublicationReadyArtifact.
- Hard architectural separation between Editorial Decision (WHAT) and Publisher (EXECUTION).
- Zero-LLM, zero-rewriting, zero-truncation, zero-browsing execution invariants.
- Strict isolation between TEST and PRODUCTION environments (defaulting to TEST).
- Deterministic idempotency key computation preventing duplicate publication.
- UNKNOWN outcome handling that blocks automatic retries.
- Authoritative execution ledger with tamper-evident SHA-256 hashes.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any, Optional

from pydantic import Field, field_validator

from schemas.decision_card import StoryActionType
from schemas.source_registry import StrictModel
from utils.canonical_hash import compute_canonical_hash

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class PublishEnvironment(str, Enum):
    """Execution environment for publication target."""
    TEST = "TEST"
    PRODUCTION = "PRODUCTION"


class PublicationStatus(str, Enum):
    """Lifecycle states of a publication request."""
    PENDING = "PENDING"
    SENDING = "SENDING"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    NOT_PUBLISHED = "NOT_PUBLISHED"


class TelegramErrorCode(str, Enum):
    """Standardized failure and error taxonomy for Telegram transport & publishing."""
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    BOT_FORBIDDEN = "BOT_FORBIDDEN"
    CHAT_NOT_FOUND = "CHAT_NOT_FOUND"
    MESSAGE_NOT_MODIFIED = "MESSAGE_NOT_MODIFIED"
    BAD_REQUEST = "BAD_REQUEST"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    SERVER_ERROR = "SERVER_ERROR"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
    PAYLOAD_SIZE_EXCEEDED = "PAYLOAD_SIZE_EXCEEDED"
    INVALID_ARTIFACT = "INVALID_ARTIFACT"
    TARGET_MESSAGE_MISSING = "TARGET_MESSAGE_MISSING"
    PUBLISH_NOT_READY = "PUBLISH_NOT_READY"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    PRODUCTION_DISABLED = "PRODUCTION_DISABLED"


class PublicationIdentity(StrictModel):
    """
    Immutable publication fingerprint used for local duplicate protection.
    Derived deterministically from environment, target channel, artifact, and action.
    """
    environment: PublishEnvironment = Field(..., description="Target environment (TEST or PRODUCTION)")
    channel_id: str = Field(..., description="Target Telegram channel/chat ID")
    artifact_id: str = Field(..., description="ID of the certified PublicationReadyArtifact")
    artifact_hash: str = Field(..., description="Canonical SHA-256 hash of the artifact")
    story_id: str | None = Field(default=None, description="Canonical Story ID if assigned")
    publication_action: StoryActionType = Field(..., description="Publication action to execute")
    idempotency_key: str = Field(..., description="Deterministic idempotency key")


class PublicationRequest(StrictModel):
    """
    Internal execution request payload constructed strictly from PublicationReadyArtifact
    and environment configuration.
    """
    request_id: str = Field(..., description="Unique request identifier (e.g. req_pub_...)")
    artifact_id: str = Field(..., description="ID of the certified PublicationReadyArtifact")
    environment: PublishEnvironment = Field(..., description="Target environment")
    target_channel_id: str = Field(..., description="Resolved channel ID (from environment config)")
    publication_action: StoryActionType = Field(..., description="Action (NEW_POST, EDIT_EXISTING, REPLY, NO_PUBLICATION)")
    text: str = Field(..., description="Exact approved Persian text payload to transmit")
    story_id: str | None = Field(default=None, description="Associated Story ID")
    candidate_id: str = Field(..., description="Associated candidate ID")
    idempotency_key: str = Field(..., description="Deterministic idempotency key")
    artifact_hash: str = Field(..., description="Canonical hash of the artifact")
    target_message_id: int | None = Field(default=None, description="Target message ID for EDIT_EXISTING")
    reply_to_message_id: int | None = Field(default=None, description="Target message ID for REPLY")
    parse_mode: str | None = Field(default=None, description="Telegram parse mode if specified")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
    request_hash: str = Field(default="", description="Deterministic SHA-256 hash of request payload")

    @field_validator("request_id", "artifact_id", "candidate_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    def compute_request_hash(self) -> str:
        """Computes deterministic canonical hash of the publication request."""
        data = self.model_dump()
        return compute_canonical_hash(data, exclude_fields={"request_hash", "created_at"})


class TelegramTransportResponse(StrictModel):
    """
    Standardized response from the Telegram transport layer.
    Contains only sanitized metadata, never credentials or sensitive tokens.
    """
    success: bool = Field(..., description="Whether Telegram accepted and confirmed the operation")
    status: PublicationStatus = Field(..., description="Resulting publication status")
    telegram_message_id: int | None = Field(default=None, description="Message ID returned by Telegram")
    telegram_chat_id: str | None = Field(default=None, description="Chat ID confirmed by Telegram")
    date: int | None = Field(default=None, description="Telegram Unix epoch timestamp")
    error_code: TelegramErrorCode | None = Field(default=None, description="Classified error code if unsuccessful")
    error_message_sanitized: str | None = Field(default=None, description="Sanitized error description with redacted secrets")
    raw_response_hash: str | None = Field(default=None, description="Hash of raw API response for audit")
    is_retryable: bool = Field(default=False, description="Whether retry is permitted (known pre-send failure)")
    is_unknown_outcome: bool = Field(default=False, description="True if response outcome could not be determined")


class PublicationLedgerEntry(StrictModel):
    """
    Persistent authoritative record of a publication attempt or completion.
    Stored in data/publication_ledger.json.
    """
    ledger_id: str = Field(..., description="Unique ledger entry ID (e.g. led_...)")
    idempotency_key: str = Field(..., description="Deterministic idempotency key")
    environment: PublishEnvironment = Field(..., description="Execution environment")
    channel_id: str = Field(..., description="Target Telegram channel ID")
    artifact_id: str = Field(..., description="ID of the certified PublicationReadyArtifact")
    artifact_hash: str = Field(..., description="Canonical hash of the artifact")
    story_id: str | None = Field(default=None, description="Associated Story ID")
    candidate_id: str = Field(..., description="Associated candidate ID")
    publication_action: StoryActionType = Field(..., description="Publication action")
    status: PublicationStatus = Field(..., description="Current publication status")
    telegram_message_id: int | None = Field(default=None, description="Telegram message ID if sent/confirmed")
    telegram_chat_id: str | None = Field(default=None, description="Telegram chat ID if sent/confirmed")
    telegram_response_hash: str | None = Field(default=None, description="Hash of Telegram response")
    error_code: TelegramErrorCode | None = Field(default=None, description="Error code if failed or unknown")
    error_message_sanitized: str | None = Field(default=None, description="Sanitized error explanation")
    attempts: int = Field(default=1, ge=1, description="Number of execution attempts")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 UTC update timestamp")
    entry_hash: str = Field(default="", description="Deterministic SHA-256 hash of this ledger entry")

    @field_validator("ledger_id", "artifact_id", "candidate_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    def compute_entry_hash(self) -> str:
        """Computes deterministic canonical hash of the substantive ledger entry."""
        data = self.model_dump()
        return compute_canonical_hash(data, exclude_fields={"entry_hash", "updated_at"})


class PublicationReceipt(StrictModel):
    """
    Immutable execution receipt delivered to callers upon publishing or duplicate resolution.
    Does NOT alter editorial content.
    """
    receipt_id: str = Field(..., description="Unique receipt ID (e.g. rcp_...)")
    ledger_id: str = Field(..., description="Associated PublicationLedgerEntry ID")
    idempotency_key: str = Field(..., description="Deterministic idempotency key")
    status: PublicationStatus = Field(..., description="Final publication status")
    environment: PublishEnvironment = Field(..., description="Publication environment")
    channel_id: str = Field(..., description="Target Telegram channel ID")
    telegram_message_id: int | None = Field(default=None, description="Telegram message ID if confirmed/sent")
    telegram_chat_id: str | None = Field(default=None, description="Telegram chat ID if confirmed/sent")
    artifact_id: str = Field(..., description="Certified artifact ID")
    artifact_hash: str = Field(..., description="Artifact hash")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
    receipt_hash: str = Field(default="", description="Deterministic SHA-256 hash of this receipt")

    @field_validator("receipt_id", "ledger_id", "artifact_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v

    def compute_receipt_hash(self) -> str:
        """Computes deterministic canonical hash of the receipt."""
        data = self.model_dump()
        return compute_canonical_hash(data, exclude_fields={"receipt_hash", "created_at"})
