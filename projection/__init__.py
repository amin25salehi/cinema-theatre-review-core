"""
Cinema & Theatre Review - Projection Package
Stage 8.8 — LLM Context Projection
"""

from projection.llm_context import (
    LLMContextProjectionBuilder,
    LLMContextProjector,
    ProjectionBounds,
)
from projection.validator import (
    LLMContextProjectionValidator,
    ProjectionValidationError,
)

__all__ = [
    "LLMContextProjectionBuilder",
    "LLMContextProjector",
    "ProjectionBounds",
    "LLMContextProjectionValidator",
    "ProjectionValidationError",
]
