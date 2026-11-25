"""
Editorial Rules Schema - Cinema & Theatre Review Editorial OS v1.0.1
Strict Pydantic v2 data contract for deterministic editorial rules, hard gates,
character budgets, and signal weightings.
"""

from pydantic import Field

from schemas.source_registry import StrictModel


class HardGateConfig(StrictModel):
    enabled: bool = Field(default=True, description="Whether this hard gate is actively enforced")
    policy: str = Field(..., description="Machine identifier or explanation of the policy")


class CharacterBudgetRange(StrictModel):
    min: int = Field(..., ge=0, description="Minimum allowable character count")
    target: int = Field(..., ge=0, description="Target optimal character count")
    max: int = Field(..., ge=0, description="Hard ceiling for character count")


class EditorialSignalWeights(StrictModel):
    evidence_strength_weight: float = Field(..., ge=0.0, le=1.0)
    editorial_fit_weight: float = Field(..., ge=0.0, le=1.0)
    recency_weight: float = Field(..., ge=0.0, le=1.0)


class EditorialRules(StrictModel):
    version: str = Field(...)
    name: str = Field(...)
    description: str = Field(...)
    invariants: list[str] = Field(default_factory=list)
    hard_gates: dict[str, HardGateConfig] = Field(...)
    character_budgets: dict[str, CharacterBudgetRange] = Field(...)
    signals: EditorialSignalWeights = Field(...)
