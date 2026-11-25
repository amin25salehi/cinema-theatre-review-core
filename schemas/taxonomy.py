"""
Content Taxonomy Schema - Cinema & Theatre Review Editorial OS v1.0.1
Strict Pydantic v2 data contract for domains and claim types.
"""

import re

from pydantic import Field, field_validator

from schemas.source_registry import StrictModel

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class TaxonomyDomain(StrictModel):
    id: str = Field(..., description="Unique domain identifier (e.g. cinema, theatre)")
    name_persian: str = Field(..., description="Persian display name for the domain")
    description: str = Field(..., description="Editorial scope of this domain")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Domain id '{v}' must match ^[a-z0-9_]+$")
        return v


class TaxonomyClaimType(StrictModel):
    code: str = Field(..., description="Unique claim type predicate (e.g. festival_selection)")
    domain: str = Field(..., description="Parent domain foreign key")
    description: str = Field(..., description="Detailed description of what this claim asserts")

    @field_validator("code", "domain")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"Identifier '{v}' must match ^[a-z0-9_]+$")
        return v


class ContentTaxonomy(StrictModel):
    version: str = Field(..., description="Taxonomy version format")
    name: str = Field(..., description="Taxonomy configuration name")
    description: str = Field(..., description="Descriptive summary")
    domains: list[TaxonomyDomain] = Field(..., min_length=1)
    claim_types: list[TaxonomyClaimType] = Field(..., min_length=1)
