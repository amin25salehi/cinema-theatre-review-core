"""
Source Registry Schema - Cinema & Theatre Review Editorial OS v1.0
Strict Pydantic v2 data contract for Source Profiles.
"""

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceClass(str, Enum):
    FESTIVAL_PRIMARY = "festival_primary"
    ARCHIVE_PRIMARY = "archive_primary"
    VENUE_PRIMARY = "venue_primary"
    AWARD_PRIMARY = "award_primary"
    CINEMATHEQUE = "cinematheque"
    MUSEUM = "museum"
    UNIVERSITY = "university"
    NATIONAL_THEATRE = "national_theatre"
    CULTURAL_INSTITUTION = "cultural_institution"
    CRITICAL_JOURNAL = "critical_journal"
    ACADEMIC_JOURNAL = "academic_journal"
    TRADE_PUBLICATION = "trade_publication"
    PUBLISHER = "publisher"
    DATABASE = "database"
    RESEARCH_NETWORK = "research_network"


class SourceRole(str, Enum):
    # Core roles
    AUTHORITY = "authority"
    DISCOVERY = "discovery"
    ARCHIVE = "archive"
    INGESTION = "ingestion"
    # Festival & institution roles
    OFFICIAL_NEWS = "official_news"
    SELECTION = "selection"
    AWARDS = "awards"
    PROGRAMME = "programme"
    VERIFICATION = "verification"
    IMAGE_SOURCE = "image_source"
    # Archive & preservation roles
    PRESERVATION = "preservation"
    RESTORATION = "restoration"
    HISTORICAL_CONTEXT = "historical_context"
    ARCHIVE_NETWORK = "archive_network"
    # Editorial & critical roles
    CRITICISM = "criticism"
    CONTEXT = "context"
    FESTIVAL_COVERAGE = "festival_coverage"
    INTERVIEWS = "interviews"
    HISTORY = "history"
    THEATRE_NEWS = "theatre_news"
    RESEARCH = "research"
    PERFORMANCE_STUDIES = "performance_studies"
    # Reception & discovery roles
    RECEPTION = "reception"
    TREND_DETECTION = "trend_detection"
    AGGREGATED_RECEPTION = "aggregated_reception"
    CRITICAL_RECEPTION = "critical_reception"
    AUDIENCE_RECEPTION = "audience_reception"
    # Bibliographic & database roles
    METADATA = "metadata"
    IDENTITY_ENRICHMENT = "identity_enrichment"
    IMAGES = "images"
    FILMOGRAPHY = "filmography"
    BIBLIOGRAPHIC_METADATA = "bibliographic_metadata"
    LIBRARY_PRESENCE = "library_presence"
    BOOK_DISCOVERY = "book_discovery"
    SCHOLARLY_METADATA = "scholarly_metadata"
    DOI_METADATA = "doi_metadata"
    RESEARCH_DISCOVERY = "research_discovery"
    AUTHOR_INSTITUTION_LINKING = "author_institution_linking"
    ENTITY_RESOLUTION = "entity_resolution"
    EXTERNAL_IDENTIFIER_MAPPING = "external_identifier_mapping"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    AUTHORITY_CONTROL = "authority_control"
    NAME_DISAMBIGUATION = "name_disambiguation"
    BIBLIOGRAPHIC_IDENTITY = "bibliographic_identity"
    BROADWAY_HISTORY = "broadway_history"
    PRODUCTION_METADATA = "production_metadata"
    THEATRE_HISTORY = "theatre_history"
    PLAY_DISCOVERY = "play_discovery"
    PLAYWRIGHT_DISCOVERY = "playwright_discovery"


from schemas.acquisition import (
    AccessMode,
    AcquisitionMethod,
    AcquisitionProfile,
    AcquisitionStatus,
    AuthenticationRequirement,
    RateLimitPolicy,
)

LEGACY_METHOD_MAP = {
    "manual_audit": AcquisitionMethod.WEBSITE,
    "crawler": AcquisitionMethod.WEBSITE,
    "curated_scrape": AcquisitionMethod.WEBSITE,
}

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


class SourceProfile(StrictModel):
    source_id: str = Field(..., description="Stable unique identifier matching ^[a-z0-9_]+$")
    name: str = Field(..., description="Human-readable name of the source")
    domain: str = Field(..., description="Primary web domain (e.g. festival-cannes.com)")
    source_class: SourceClass = Field(..., description="Classification category of the source")
    tier: int = Field(..., ge=1, le=5, description="Institutional trust tier (1=primary/premier, 2=major, 3=specialized)")
    region: str = Field(..., description="Geographic or institutional region (e.g. international, europe, north_america)")
    language: str = Field(..., description="Primary language code (e.g. en, fr, de, fa, it)")
    roles: list[SourceRole] = Field(..., min_length=1, description="Separated roles (trust/authority/discovery/ingestion)")
    authoritative_claims: list[str] = Field(default_factory=list, description="Claim types for which this source can be authoritative")
    not_authoritative_for: list[str] = Field(default_factory=list, description="Claim types explicitly excluded from this source authority")
    acquisition_method: list[AcquisitionMethod] = Field(..., min_length=1, description="Ingestion/acquisition mechanism(s)")
    canonical_url: str = Field(..., description="Canonical root or profile URL")
    active: bool = Field(default=True, description="Whether this source is currently active in the registry")
    aliases: list[str] = Field(default_factory=list, description="Alternative or legacy source identifiers")
    notes: str | None = Field(default=None, description="Editorial notes on source usage")
    acquisition: AcquisitionProfile | None = Field(default=None, description="Technical acquisition contract and profile")

    @field_validator("acquisition_method", mode="before")
    @classmethod
    def normalize_acquisition_method(cls, v):
        if isinstance(v, (str, AcquisitionMethod)):
            v = [v]
        normalized = []
        for item in v:
            if isinstance(item, str) and item in LEGACY_METHOD_MAP:
                normalized.append(LEGACY_METHOD_MAP[item])
            else:
                normalized.append(item)
        return normalized

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(f"source_id '{v}' does not match required format ^[a-z0-9_]+$")
        return v

    @field_validator("canonical_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"canonical_url '{v}' must be a valid HTTP/HTTPS URL")
        return v

    def get_acquisition_profile(self) -> AcquisitionProfile:
        """Returns explicitly configured acquisition profile or derives an unverified default."""
        if self.acquisition is not None:
            return self.acquisition
        preferred = self.acquisition_method[0]
        api_url = self.canonical_url if preferred == AcquisitionMethod.API else None
        return AcquisitionProfile(
            methods=self.acquisition_method,
            preferred_method=preferred,
            feed_urls=[],
            api_base_url=api_url,
            access_mode=AccessMode.PUBLIC,
            authentication=AuthenticationRequirement.NONE,
            rate_limit_policy=RateLimitPolicy(),
            status=AcquisitionStatus.UNVERIFIED,
        )


class SourceRegistry(StrictModel):
    version: str = Field(..., description="Version of the source registry format")
    sources: list[SourceProfile] = Field(default_factory=list)
