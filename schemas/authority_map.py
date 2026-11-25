"""
Authority Map Schema - Cinema & Theatre Review Editorial OS v1.0
Strict Pydantic v2 data contract for claim-specific authority rules.
Authority is claim-specific and structurally defined.
"""

import re
from enum import Enum

from pydantic import Field, field_validator

from schemas.source_registry import SourceClass, StrictModel

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class ConflictPolicy(str, Enum):
    HOLD_ON_UNRESOLVED = "hold_on_unresolved"
    PREFER_PRIMARY = "prefer_primary"
    PROHIBIT_PUBLICATION = "prohibit_publication"
    ALLOW_QUALIFIED_DISCOURSE = "allow_qualified_discourse"


class MinimumConfirmation(StrictModel):
    primary_count: int = Field(default=1, ge=0, description="Minimum number of primary source confirmations required")
    secondary_count: int = Field(default=0, ge=0, description="Minimum number of secondary source confirmations required if primary unavailable")
    require_independent_sources: bool = Field(default=True, description="Whether confirming sources must be from distinct domains/organizations")


class AuthorityRule(StrictModel):
    claim_type: str = Field(..., description="Unique claim identifier, matching ^[a-z0-9_]+$")
    description: str = Field(..., description="Clear explanation of the claim semantics")
    primary_authority_classes: list[SourceClass] = Field(..., min_length=1, description="Source classes that hold primary direct authority")
    secondary_authority_classes: list[SourceClass] = Field(default_factory=list, description="Source classes that hold secondary corroborating authority")
    discovery_only_classes: list[SourceClass] = Field(default_factory=list, description="Source classes that may discover but never verify this claim")
    preferred_source_ids: list[str] = Field(default_factory=list, description="Explicit preferred source IDs in priority order")
    minimum_confirmation: MinimumConfirmation = Field(default_factory=MinimumConfirmation, description="Structural confirmation threshold")
    conflict_policy: ConflictPolicy = Field(default=ConflictPolicy.HOLD_ON_UNRESOLVED, description="Policy triggered when sources disagree")

    @field_validator("claim_type")
    @classmethod
    def validate_claim_type(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"claim_type '{v}' must match ^[a-z0-9_]+$")
        return v

    @field_validator("preferred_source_ids")
    @classmethod
    def validate_source_ids(cls, v: list[str]) -> list[str]:
        for sid in v:
            if not ID_PATTERN.match(sid):
                raise ValueError(f"preferred_source_id '{sid}' must match ^[a-z0-9_]+$")
        return v


class AuthorityMap(StrictModel):
    version: str = Field(..., description="Version of the authority map")
    updated_at: str = Field(..., description="ISO datetime of last update")
    rules: dict[str, AuthorityRule] = Field(..., description="Mapping from claim_type to AuthorityRule")
