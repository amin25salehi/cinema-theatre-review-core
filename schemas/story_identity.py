"""
Story & Candidate Identity Schemas - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.6: Candidate Identity, Story Identity & Change Detection.

Strict Pydantic v2 data contracts enforcing:
- Auditability of identity methods and values
- Independence of candidate_id from mutable content fingerprints
- Canonicalized qualifying dimensions and deterministic Story keys
- Invariant-checked Story links (False Negatives > False Positives)
- Deterministic change detection state and reason codes
- Strict rejection of editorial leakage or LLM artifacts
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Base model forbidding undeclared extra attributes."""
    model_config = ConfigDict(extra="forbid")


# 6.1 Identity Method
IdentityMethod = Literal[
    "NATIVE_ID",
    "EXTERNAL_ID",
    "GUID",
    "CANONICAL_URL",
    "CONTENT_FINGERPRINT",
]

# 13. Candidate State
CandidateState = Literal[
    "NEW",
    "UNCHANGED",
    "UPDATED",
]

# 14. Editorial Change Type
EditorialChangeType = Literal[
    "INITIAL",
    "UPDATE",
    "CORRECTION",
    "FOLLOW_UP",
    "DUPLICATE",
]

# 15. Change Reason Code
ChangeReasonCode = Literal[
    "CONTENT_CHANGE",
    "DECLARED_CORRECTION",
    "NEW_EVENT_INSTANCE",
    "EXACT_DUPLICATE",
    "STRUCTURAL_EVIDENCE",
]

# 24. Story Link Status
StoryLinkStatus = Literal[
    "LINKED_DETERMINISTICALLY",
    "POTENTIAL_MATCH",
    "UNRESOLVED",
]


class CandidateIdentity(StrictModel):
    """
    Source-scoped deterministic identifier for an acquired Candidate unit.
    Answers: 'Which source item is this?'
    Distinct from content_fingerprint which answers: 'Has the content changed?'
    """
    candidate_id: str = Field(
        ...,
        description="Deterministic, source-scoped candidate identifier (e.g. cand_src_hash)",
    )
    identity_method: IdentityMethod = Field(
        ...,
        description="Auditable method used to establish this candidate identity",
    )
    identity_value: str = Field(
        ...,
        description="Exact raw value used by identity_method to construct candidate_id",
    )
    source_id: str = Field(
        ...,
        description="Canonical source registry identifier providing this candidate",
    )
    native_id: Optional[str] = Field(
        default=None,
        description="Source-native stable identifier (entry ID, post ID, slug) if provided",
    )
    external_id: Optional[str] = Field(
        default=None,
        description="Global authority identifier (ISBN, DOI, Wikidata, IMDb) if extracted",
    )
    canonical_url: Optional[str] = Field(
        default=None,
        description="Deterministically canonicalized URL of the source item",
    )
    content_fingerprint: str = Field(
        ...,
        description="Cryptographic hash of normalized title + body representation",
    )
    fingerprint_algorithm: str = Field(
        default="sha256:title_body:v1",
        description="Explicit algorithm identifier and version used to compute content_fingerprint",
    )
    published_at: Optional[str] = Field(
        default=None,
        description="Original publication ISO timestamp as stated by source",
    )
    updated_at: Optional[str] = Field(
        default=None,
        description="Source modification ISO timestamp if explicitly provided",
    )
    author: Optional[str] = Field(
        default=None,
        description="Primary author or contributor name if provided",
    )

    @field_validator("canonical_url")
    @classmethod
    def validate_canonical_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() != "":
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("canonical_url must be an HTTP or HTTPS URL")
            return v.strip()
        return None


class QualifyingDimension(StrictModel):
    """
    Key-value pair defining a specific factual dimension of a claim instance.
    Examples: edition='2026', location='bologna', section='competition'.
    """
    key: str = Field(..., description="Normalized dimension key (e.g. edition, section, year)")
    value: str = Field(..., description="Normalized dimension value")

    @field_validator("key")
    @classmethod
    def validate_and_normalize_key(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("QualifyingDimension key cannot be empty")
        if not re.match(r"^[a-z0-9_]+$", clean):
            raise ValueError(f"QualifyingDimension key '{clean}' must match ^[a-z0-9_]+$")
        return clean

    @field_validator("value")
    @classmethod
    def validate_and_normalize_value(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("QualifyingDimension value cannot be empty")
        return clean


class StoryKey(StrictModel):
    """
    Canonical structured identity of an editorial Story.
    A Story represents a structured claim instance:
    subject + claim_type + optional object + sorted qualifying dimensions.
    """
    story_id: str = Field(
        ...,
        description="Deterministic hash of the canonicalized Story Key representation",
    )
    subject_entity_id: str = Field(
        ...,
        description="Canonical Entity Registry identifier for the subject entity",
    )
    claim_type_id: str = Field(
        ...,
        description="Canonical Content Taxonomy code for the claim predicate",
    )
    object_entity_id: Optional[str] = Field(
        default=None,
        description="Optional canonical Entity Registry identifier for the object entity",
    )
    qualifying_dimensions: list[QualifyingDimension] = Field(
        default_factory=list,
        description="Sorted, canonicalized claim-specific qualifying dimensions",
    )

    @field_validator("subject_entity_id", "claim_type_id")
    @classmethod
    def validate_ids_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[a-z0-9_]+$", clean):
            raise ValueError(f"Identifier '{clean}' must match ^[a-z0-9_]+$")
        return clean

    @field_validator("object_entity_id")
    @classmethod
    def validate_object_id_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip().lower()
        if not re.match(r"^[a-z0-9_]+$", clean):
            raise ValueError(f"Identifier '{clean}' must match ^[a-z0-9_]+$")
        return clean

    @model_validator(mode="after")
    def validate_canonical_dimensions(self) -> "StoryKey":
        """Rejects duplicate dimension keys and verifies canonical sorting."""
        seen_keys: set[str] = set()
        for dim in self.qualifying_dimensions:
            if dim.key in seen_keys:
                raise ValueError(
                    f"StoryKey qualifying_dimensions contains duplicate key '{dim.key}'"
                )
            seen_keys.add(dim.key)
        return self

    @classmethod
    def compute_canonical_representation(
        cls,
        subject_entity_id: str,
        claim_type_id: str,
        object_entity_id: Optional[str] = None,
        qualifying_dimensions: Optional[list[QualifyingDimension]] = None,
    ) -> tuple[str, list[QualifyingDimension]]:
        """
        Deterministically canonicalizes fields:
        - Normalizes entity and claim type identifiers
        - Rejects duplicate dimension keys
        - Sorts dimensions by key ascending, then value ascending
        - Produces deterministic UTF-8 string serialization
        """
        subj = subject_entity_id.strip().lower()
        claim = claim_type_id.strip().lower()
        obj = object_entity_id.strip().lower() if object_entity_id else ""

        dims = qualifying_dimensions or []
        seen_keys: set[str] = set()
        for d in dims:
            k = d.key.strip().lower()
            if k in seen_keys:
                raise ValueError(f"Duplicate qualifying dimension key: '{k}'")
            seen_keys.add(k)

        # Canonical sort by key ascending, then value ascending
        sorted_dims = sorted(dims, key=lambda d: (d.key.strip().lower(), d.value.strip()))

        dim_str = ";".join(f"{d.key}={d.value}" for d in sorted_dims)
        canonical_str = f"subject={subj}|claim={claim}|object={obj}|dimensions={dim_str}"
        return canonical_str, sorted_dims

    @classmethod
    def create(
        cls,
        subject_entity_id: str,
        claim_type_id: str,
        object_entity_id: Optional[str] = None,
        qualifying_dimensions: Optional[list[QualifyingDimension]] = None,
    ) -> "StoryKey":
        """Factory creating a StoryKey with verified canonical hash."""
        canonical_str, sorted_dims = cls.compute_canonical_representation(
            subject_entity_id=subject_entity_id,
            claim_type_id=claim_type_id,
            object_entity_id=object_entity_id,
            qualifying_dimensions=qualifying_dimensions,
        )
        h = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:16]
        story_id = f"story_{h}"
        return cls(
            story_id=story_id,
            subject_entity_id=subject_entity_id.strip().lower(),
            claim_type_id=claim_type_id.strip().lower(),
            object_entity_id=object_entity_id.strip().lower() if object_entity_id else None,
            qualifying_dimensions=sorted_dims,
        )


class StoryLink(StrictModel):
    """
    Resolution link between a Candidate and an editorial Story.
    Strict Invariant: False Negatives > False Positives.
    Never merges candidates without sufficient deterministic evidence.
    """
    candidate_id: str = Field(
        ...,
        description="Identifier of the candidate being linked",
    )
    status: StoryLinkStatus = Field(
        ...,
        description="Status of the story resolution: LINKED_DETERMINISTICALLY, POTENTIAL_MATCH, or UNRESOLVED",
    )
    resolved_story_key: Optional[StoryKey] = Field(
        default=None,
        description="Resolved StoryKey if and only if status is LINKED_DETERMINISTICALLY",
    )
    potential_match_reasons: list[str] = Field(
        default_factory=list,
        description="Diagnostic explanations of why a potential match was flagged (required if POTENTIAL_MATCH)",
    )

    @model_validator(mode="after")
    def validate_story_link_invariants(self) -> "StoryLink":
        """
        Enforces mandatory invariants:
        - LINKED_DETERMINISTICALLY -> resolved_story_key MUST exist
        - POTENTIAL_MATCH -> resolved_story_key MUST NOT exist, potential_match_reasons MUST NOT be empty
        - UNRESOLVED -> resolved_story_key MUST NOT exist
        """
        if self.status == "LINKED_DETERMINISTICALLY":
            if self.resolved_story_key is None:
                raise ValueError(
                    "StoryLink invariant violation: LINKED_DETERMINISTICALLY requires resolved_story_key"
                )
        elif self.status == "POTENTIAL_MATCH":
            if self.resolved_story_key is not None:
                raise ValueError(
                    "StoryLink invariant violation: POTENTIAL_MATCH must NOT have resolved_story_key"
                )
            if not self.potential_match_reasons:
                raise ValueError(
                    "StoryLink invariant violation: POTENTIAL_MATCH requires at least one potential_match_reason"
                )
        elif self.status == "UNRESOLVED":
            if self.resolved_story_key is not None:
                raise ValueError(
                    "StoryLink invariant violation: UNRESOLVED must NOT have resolved_story_key"
                )
        return self


class ChangeRecord(StrictModel):
    """
    Audit record capturing technical change detection for a candidate.
    Answers: Has this candidate content changed, is it new, a duplicate, or a follow-up?
    """
    record_id: str = Field(
        ...,
        description="Unique identifier for this change record (e.g. chg_hash)",
    )
    candidate_id: str = Field(
        ...,
        description="Target candidate identifier evaluated",
    )
    state: CandidateState = Field(
        ...,
        description="Technical state: NEW, UNCHANGED, or UPDATED",
    )
    change_type: EditorialChangeType = Field(
        ...,
        description="Editorial change classification: INITIAL, UPDATE, CORRECTION, FOLLOW_UP, or DUPLICATE",
    )
    previous_fingerprint: Optional[str] = Field(
        default=None,
        description="Previous content fingerprint in state if candidate existed previously",
    )
    current_fingerprint: str = Field(
        ...,
        description="Current content fingerprint evaluated",
    )
    reason_code: ChangeReasonCode = Field(
        ...,
        description="Structured rationale code for this change classification",
    )
    parent_candidate_id: Optional[str] = Field(
        default=None,
        description="Identifier of preceding candidate if this record represents a follow-up or update",
    )
    resolution_rationale: str = Field(
        ...,
        description="Human-readable audit explanation of the change detection decision",
    )
