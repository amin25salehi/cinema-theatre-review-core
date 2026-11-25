"""
Entity Registry Schema - Cinema & Theatre Review Editorial OS v1.0
Strict Pydantic v2 data contract for cultural entities.
Entity identity is strictly independent from editorial eligibility.
"""

import re
from enum import Enum

from pydantic import Field, field_validator, model_validator

from schemas.source_registry import StrictModel

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class EntityType(str, Enum):
    FILMMAKER = "filmmaker"
    ACTOR = "actor"
    FILM = "film"
    PLAYWRIGHT = "playwright"
    THEATRE_DIRECTOR = "theatre_director"
    PLAY = "play"
    FESTIVAL = "festival"
    AWARD = "award"
    THEATRE = "theatre"
    ARCHIVE = "archive"
    PUBLISHER = "publisher"
    INSTITUTION = "institution"


class EntityStatus(str, Enum):
    REFERENCE = "reference"
    RECOGNIZED = "recognized"
    EMERGING = "emerging"
    LOCAL = "local"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"


class IdentityStatus(str, Enum):
    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    DEPRECATED = "deprecated"


class ProvenanceReasonCode(str, Enum):
    MAJOR_AWARD = "major_award"
    MAJOR_FESTIVAL_SELECTION = "major_festival_selection"
    HISTORICAL_CANON = "historical_canon"
    MAJOR_RETROSPECTIVE = "major_retrospective"
    ARCHIVE_RECOGNITION = "archive_recognition"
    ACADEMIC_RECOGNITION = "academic_recognition"
    MAJOR_PRODUCTION = "major_production"
    MAJOR_PUBLICATION = "major_publication"


class ExternalIds(StrictModel):
    wikidata: str | None = None
    imdb: str | None = None
    isni: str | None = None
    orcid: str | None = None
    openalex: str | None = None
    viaf: str | None = None
    ibdb: str | None = None


class EntityProvenance(StrictModel):
    source_id: str = Field(..., description="Foreign key reference to source_registry source_id")
    reason_code: ProvenanceReasonCode = Field(..., description="Standardized objective justification")
    added_at: str = Field(..., description="ISO datetime when provenance record was created")
    notes: str | None = Field(default=None, description="Additional context or citation")

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"source_id '{v}' in provenance must match ^[a-z0-9_]+$")
        return v


class EntityProfile(StrictModel):
    entity_id: str = Field(..., description="Unique entity identifier matching ^[a-z0-9_]+$")
    name: str = Field(..., description="Canonical standard primary name")
    name_persian: str | None = Field(default=None, description="Persian translation/transliteration")
    aliases: list[str] = Field(default_factory=list, description="Alternative international names/spellings")
    aliases_persian: list[str] = Field(default_factory=list, description="Alternative Persian spellings")
    entity_type: EntityType = Field(..., description="Semantic entity type")
    status: EntityStatus = Field(..., description="Registry status (reference, recognized, emerging, local, unknown, blocked)")
    identity_status: IdentityStatus = Field(default=IdentityStatus.CONFIRMED, description="Identity resolution status")
    external_ids: ExternalIds = Field(default_factory=ExternalIds, description="External global identifiers (optional)")
    provenance: list[EntityProvenance] = Field(default_factory=list, description="Audit chain of why entity is in the registry")
    biography_summary: str | None = Field(default=None, description="Brief neutral background summary")
    active: bool = Field(default=True, description="Whether entity is active in the registry")

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"entity_id '{v}' does not match required format ^[a-z0-9_]+$")
        return v

    @model_validator(mode="after")
    def validate_provenance_for_status(self) -> "EntityProfile":
        # Rule: Every reference/recognized/emerging entity must have provenance
        if self.status in (EntityStatus.REFERENCE, EntityStatus.RECOGNIZED, EntityStatus.EMERGING):
            if not self.provenance:
                raise ValueError(
                    f"Entity '{self.entity_id}' with status '{self.status.value}' must have at least one provenance record"
                )
        return self


class EntityRegistry(StrictModel):
    version: str = Field(..., description="Version of the entity registry format")
    entities: list[EntityProfile] = Field(default_factory=list)
