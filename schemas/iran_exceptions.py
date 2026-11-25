"""
Iran Exceptions Schema - Cinema & Theatre Review Editorial OS v1.0.1
Strict Pydantic v2 data contract for international exceptions to Iranian cinema coverage.
"""

from pydantic import Field

from schemas.source_registry import StrictModel


class IranExceptionCategory(StrictModel):
    code: str = Field(..., description="Unique exception code (e.g. major_international_award)")
    name: str = Field(..., description="Human-readable category name")
    description: str = Field(..., description="Detailed criteria for exception qualification")
    required_minimum_tier: int = Field(..., ge=1, le=5, description="Maximum allowable source tier (1=premier only, 2=major)")


class IranExceptionsPolicy(StrictModel):
    version: str = Field(...)
    policy_name: str = Field(...)
    description: str = Field(...)
    default_action: str = Field(default="reject")
    allowed_exception_categories: list[IranExceptionCategory] = Field(..., min_length=1)
    disallowed_categories: list[str] = Field(..., min_length=1)
