"""
Acquisition Contract Schemas - Cinema & Theatre Review Editorial OS v1.0.1
Defines strict Pydantic v2 data contracts for technical source acquisition,
verification records, rate limiting policies, and dynamic source health.
"""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AcquisitionMethod(str, Enum):
    WEBSITE = "website"
    RSS = "rss"
    API = "api"
    SITEMAP = "sitemap"
    PRESS_AREA = "press_area"
    SOCIAL_MEDIA = "social_media"
    EMAIL_ALERT = "email_alert"


class AccessMode(str, Enum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    API_KEY = "api_key"
    SUBSCRIPTION = "subscription"
    PRESS_CREDENTIAL = "press_credential"
    UNKNOWN = "unknown"


class AuthenticationRequirement(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    OAUTH = "oauth"
    LOGIN = "login"
    PRESS_LOGIN = "press_login"
    SUBSCRIPTION = "subscription"
    UNKNOWN = "unknown"


class AcquisitionStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    REQUIRES_AUTH = "requires_auth"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"


class RateLimitType(str, Enum):
    SOURCE_DEFINED = "source_defined"
    DYNAMIC = "dynamic"
    UNKNOWN = "unknown"
    NONE_DOCUMENTED = "none_documented"


class RateLimitPolicy(StrictModel):
    rate_limit_type: RateLimitType = Field(
        default=RateLimitType.UNKNOWN,
        description="Policy category describing source rate limiting behavior",
    )
    requests_per_window: int | None = Field(
        default=None,
        ge=1,
        description="Maximum requests permitted in a time window",
    )
    window_seconds: int | None = Field(
        default=None,
        ge=1,
        description="Duration of the rate limit window in seconds",
    )
    concurrency_limit: int | None = Field(
        default=None,
        ge=1,
        description="Maximum concurrent HTTP connections allowed",
    )
    backoff_required: bool = Field(
        default=False,
        description="Whether client must apply exponential backoff on retry",
    )
    notes: str | None = Field(
        default=None,
        description="Official documentation references or dynamic behavior notes",
    )


class VerificationCheckType(str, Enum):
    HOMEPAGE = "homepage"
    RSS = "rss"
    API = "api"
    SITEMAP = "sitemap"
    PRESS_AREA = "press_area"
    NEWS_INDEX = "news_index"


class VerificationStatus(str, Enum):
    OK = "ok"
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    REDIRECT = "redirect"
    UNAUTHORIZED = "unauthorized"
    REQUIRES_AUTH = "requires_auth"
    FORBIDDEN = "forbidden"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    PARSE_ERROR = "parse_error"
    UNVERIFIED = "unverified"
    UNCONFIGURED = "unconfigured"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    UNKNOWN = "unknown"


class ContentAccessState(str, Enum):
    PUBLIC_CONTENT = "public_content"
    AUTHENTICATED_CONTENT = "authenticated_content"
    REACHABLE_BUT_LOCKED = "reachable_but_locked"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class FailureCategory(str, Enum):
    DNS_FAILURE = "dns_failure"
    TLS_FAILURE = "tls_failure"
    TIMEOUT = "timeout"
    FORBIDDEN_403 = "403_forbidden"
    RATE_LIMITED_429 = "429_rate_limited"
    NOT_FOUND_404 = "404_not_found"
    SERVER_ERROR_5XX = "5xx_server_error"
    REDIRECT_LOOP = "redirect_loop"
    NETWORK_FAILURE = "network_failure"
    CONTENT_UNUSABLE = "content_unusable"
    UNKNOWN = "unknown"


class ContentMode(str, Enum):
    STANDARD_HTML = "standard_html"
    JAVASCRIPT_REQUIRED = "javascript_required"
    JSON = "json"
    XML = "xml"
    UNKNOWN = "unknown"


HTTP_URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def validate_http_url(url: str, field_name: str = "url") -> str:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"{field_name} '{url}' must start with http:// or https://")
    if not HTTP_URL_PATTERN.match(url):
        raise ValueError(f"{field_name} '{url}' is a malformed HTTP/HTTPS URL")
    return url


class VerificationRecord(StrictModel):
    check_type: VerificationCheckType = Field(..., description="Target capability checked")
    target_url: str = Field(..., description="Exact URL probed during check")
    status: VerificationStatus = Field(..., description="Observed verification status")
    reachable: bool = Field(
        default=False,
        description="Whether endpoint was reached over the network (HTTP response obtained)",
    )
    accessible: bool = Field(
        default=False,
        description="Whether content is accessible without login barriers, credentials, or blocking",
    )
    authenticated: bool = Field(
        default=False,
        description="Whether accessing content requires authentication, token, or media accreditation",
    )
    verified: bool = Field(
        default=False,
        description="Whether endpoint and content structure were verified as valid and usable",
    )
    content_access: str | None = Field(
        default=None,
        description="Detailed content accessibility: public_content, authenticated_content, reachable_but_locked, forbidden, not_found, unknown",
    )
    content_mode: str | None = Field(
        default="standard_html",
        description="Detected rendering mode required: standard_html, javascript_required, json, xml",
    )
    http_status: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="Observed HTTP status code",
    )
    content_type: str | None = Field(
        default=None,
        description="Observed Content-Type header from endpoint",
    )
    final_url: str | None = Field(
        default=None,
        description="Final destination URL after redirects",
    )
    latency_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Probe round-trip latency in milliseconds",
    )
    parseable: bool | None = Field(
        default=None,
        description="Whether response payload could be parsed as expected schema/format",
    )
    item_count_sample: int | None = Field(
        default=None,
        ge=0,
        description="Sample count of feed/catalog items observed",
    )
    retry_after: str | None = Field(
        default=None,
        description="Retry-After header value if rate limited",
    )
    error_category: str | None = Field(
        default=None,
        description="Normalized category of failure (e.g. dns_failure, timeout, auth_error)",
    )
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the check",
    )
    verification_method: str = Field(
        default="http_head_get",
        description="Transport technique used (e.g., http_head_get, api_ping)",
    )
    notes: str | None = Field(
        default=None,
        description="Observations, headers, or error diagnostic notes",
    )

    @field_validator("target_url")
    @classmethod
    def check_target_url(cls, v: str) -> str:
        return validate_http_url(v, "target_url")

    @model_validator(mode="after")
    def _backfill_semantics(self) -> "VerificationRecord":
        if not self.reachable and (
            (self.http_status and self.http_status > 0)
            or self.status in (VerificationStatus.OK, VerificationStatus.REDIRECT)
        ):
            self.reachable = True
        if self.content_access is None or self.content_access == ContentAccessState.UNKNOWN.value:
            if self.status in (VerificationStatus.OK, VerificationStatus.REDIRECT) and not self.authenticated:
                self.content_access = ContentAccessState.PUBLIC_CONTENT.value
                self.accessible = True
                self.verified = True
            elif self.status in (VerificationStatus.UNAUTHORIZED, VerificationStatus.REQUIRES_AUTH) or self.authenticated:
                self.content_access = ContentAccessState.AUTHENTICATED_CONTENT.value
            elif self.status == VerificationStatus.FORBIDDEN:
                self.content_access = ContentAccessState.FORBIDDEN.value
            elif self.status == VerificationStatus.NOT_FOUND:
                self.content_access = ContentAccessState.NOT_FOUND.value
        return self


class AvailabilityState(str, Enum):
    AVAILABLE = "available"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    UNAVAILABLE = "unavailable"
    REQUIRES_AUTH = "requires_auth"
    UNKNOWN = "unknown"


class SourceHealth(StrictModel):
    source_id: str = Field(..., description="Canonical source ID")
    availability_state: AvailabilityState = Field(
        default=AvailabilityState.UNKNOWN,
        description="Overall technical availability state",
    )
    last_success: datetime | None = Field(
        default=None,
        description="Timestamp of most recent successful check",
    )
    consecutive_failures: int = Field(
        default=0,
        ge=0,
        description="Counter of consecutive failed checks",
    )
    last_http_status: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="HTTP status from last check attempt",
    )
    last_error: str | None = Field(
        default=None,
        description="Error message from last failure",
    )
    last_checked_at: datetime | None = Field(
        default=None,
        description="Timestamp of last check attempt",
    )


class SourceAcquisitionStatus(StrictModel):
    source_id: str = Field(..., description="Canonical source identifier")
    status: AcquisitionStatus = Field(
        default=AcquisitionStatus.UNVERIFIED,
        description="Technical capability verification status",
    )
    verified_at: datetime | None = Field(
        default=None,
        description="Timestamp when status was verified",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Cache expiration timestamp for verification result",
    )
    content_hash: str | None = Field(
        default=None,
        description="Cryptographic hash of verified endpoint content/headers",
    )
    health: SourceHealth = Field(..., description="Observed dynamic health state")
    records: list[VerificationRecord] = Field(
        default_factory=list,
        description="History of verification probe records",
    )

    @field_validator("records")
    @classmethod
    def deduplicate_records(cls, records: list[VerificationRecord]) -> list[VerificationRecord]:
        """Ensures records do not contain exact duplicates of check_type and target_url within same timestamp."""
        seen = set()
        deduped = []
        for r in records:
            # Key by check_type, target_url, and rounded timestamp to second
            ts_sec = int(r.checked_at.timestamp())
            key = (r.check_type, r.target_url, ts_sec)
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped


class AcquisitionStatusRegistry(StrictModel):
    version: str = Field(default="1.0.0", description="Status document format version")
    last_run_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when verifier last ran",
    )
    sources: dict[str, SourceAcquisitionStatus] = Field(
        default_factory=dict,
        description="Map of source_id -> observed runtime acquisition status",
    )


class AcquisitionProfile(StrictModel):
    methods: list[AcquisitionMethod] = Field(
        ...,
        min_length=1,
        description="Permitted ingestion methods for this source",
    )
    preferred_method: AcquisitionMethod = Field(
        ...,
        description="Primary recommended ingestion method",
    )
    feed_urls: list[str] = Field(
        default_factory=list,
        description="Explicit RSS/Atom feed endpoints",
    )
    api_base_url: str | None = Field(
        default=None,
        description="Base URL for REST/GraphQL API queries",
    )
    sitemap_url: str | None = Field(
        default=None,
        description="Explicit sitemap endpoint URL if declared or verified",
    )
    press_area_url: str | None = Field(
        default=None,
        description="Explicit press area endpoint URL if declared or verified",
    )
    access_mode: AccessMode = Field(
        default=AccessMode.PUBLIC,
        description="Access requirements to acquire data",
    )
    authentication: AuthenticationRequirement = Field(
        default=AuthenticationRequirement.NONE,
        description="Authentication mechanism required (metadata only, no secrets)",
    )
    rate_limit_policy: RateLimitPolicy = Field(
        default_factory=RateLimitPolicy,
        description="Rate limiting and concurrency policy",
    )
    recommended_poll_interval_minutes: int | None = Field(
        default=None,
        ge=1,
        description="Recommended polling cadence in minutes",
    )
    parser_type: str | None = Field(
        default=None,
        description="Assigned downstream parser type (e.g., json_api, rss, html_index)",
    )
    status: AcquisitionStatus = Field(
        default=AcquisitionStatus.UNVERIFIED,
        description="Current technical verification status",
    )
    last_verified_at: datetime | None = Field(
        default=None,
        description="UTC timestamp of last technical verification",
    )
    verification_source: str | None = Field(
        default=None,
        description="Source of verification (e.g., manual_audit, automated_verifier)",
    )
    verification_notes: str | None = Field(
        default=None,
        description="Technical verification notes or diagnostic commentary",
    )

    @field_validator("methods", mode="before")
    @classmethod
    def normalize_methods(cls, v: Any) -> list[Any]:
        if isinstance(v, (str, AcquisitionMethod)):
            return [v]
        return v

    @field_validator("feed_urls")
    @classmethod
    def validate_feed_urls(cls, v: list[str]) -> list[str]:
        return [validate_http_url(url, "feed_url") for url in v]

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_http_url(v, "api_base_url")
        return None

    @field_validator("rate_limit_policy", mode="before")
    @classmethod
    def normalize_rate_limit_policy(cls, v: Any) -> Any:
        if isinstance(v, (str, RateLimitType)):
            return RateLimitPolicy(rate_limit_type=RateLimitType(v))
        if isinstance(v, dict):
            return RateLimitPolicy(**v)
        return v

    @model_validator(mode="after")
    def validate_acquisition_contract(self) -> "AcquisitionProfile":
        # 1. Preferred method must be in declared methods
        if self.preferred_method not in self.methods:
            raise ValueError(
                f"preferred_method '{self.preferred_method.value}' must be present in declared methods: "
                f"{[m.value for m in self.methods]}"
            )

        # 2. When API is preferred or required, api_base_url must be provided
        if self.preferred_method == AcquisitionMethod.API and not self.api_base_url:
            raise ValueError("api_base_url is required when preferred_method is 'api'")

        # 3. Secret prevention check: No raw credentials in notes or URLs
        secret_patterns = [r"bearer\s+[a-z0-9_\-\.]{10,}", r"api[_\-]?key\s*=\s*[a-z0-9_\-\.]{10,}", r"password\s*="]
        for pattern in secret_patterns:
            if self.verification_notes and re.search(pattern, self.verification_notes, re.IGNORECASE):
                raise ValueError("Verification notes must not contain embedded secrets or API keys")
            if self.api_base_url and re.search(pattern, self.api_base_url, re.IGNORECASE):
                raise ValueError("api_base_url must not contain embedded secrets or API keys")

        return self


class DiscoveredFeed(StrictModel):
    discovery_method: str = Field(default="html_alternate_link", description="Technique used to discover feed")
    discovered_url: str = Field(..., description="Discovered feed endpoint URL")
    content_type: str | None = Field(default=None, description="Reported or declared Content-Type header")
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Verification state of the discovered feed",
    )
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of discovery",
    )

    @field_validator("discovered_url")
    @classmethod
    def validate_discovered_url(cls, v: str) -> str:
        return validate_http_url(v, "discovered_url")


class DiscoveredSitemap(StrictModel):
    sitemap_url: str = Field(..., description="Explicitly discovered sitemap URL")
    discovery_source: str = Field(default="robots_txt", description="Authority source (robots_txt, explicit_html_link)")
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of discovery",
    )

    @field_validator("sitemap_url")
    @classmethod
    def validate_sitemap_url(cls, v: str) -> str:
        return validate_http_url(v, "sitemap_url")


class DiscoveredApiDoc(StrictModel):
    api_documentation_url: str = Field(..., description="URL to official API documentation")
    api_base_url_if_explicitly_documented: str | None = Field(
        default=None,
        description="API base endpoint if explicitly stated in official docs",
    )
    authentication_model: str | None = Field(
        default=None,
        description="Documented auth model (e.g. api_key, oauth, none, unknown)",
    )
    documentation_source_url: str = Field(..., description="Page where API documentation was linked")
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of discovery",
    )


class DiscoveredIndex(StrictModel):
    index_url: str = Field(..., description="Discovered index URL")
    index_type: str = Field(default="press_index", description="Type of index (press_index, news_index)")
    accessibility: str = Field(default="unknown", description="Accessibility status of index content")
    discovery_source: str = Field(..., description="Page where index link was found")
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of discovery",
    )


class SourceDiscoveryReport(StrictModel):
    source_id: str = Field(..., description="Canonical source ID")
    canonical_url: str = Field(..., description="Canonical homepage URL inspected")
    discovered_feeds: list[DiscoveredFeed] = Field(default_factory=list)
    discovered_sitemaps: list[DiscoveredSitemap] = Field(default_factory=list)
    discovered_api_docs: list[DiscoveredApiDoc] = Field(default_factory=list)
    discovered_indexes: list[DiscoveredIndex] = Field(default_factory=list)
    content_mode: str = Field(default="standard_html", description="standard_html or javascript_required")
    robots_txt_inspected: bool = Field(default=False)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CollectorFamily(str, Enum):
    """Reusable collector family classifications (Stage 7B.3 Section 7)."""
    RSS_COLLECTOR = "RSSCollector"
    API_COLLECTOR = "APICollector"
    SITEMAP_COLLECTOR = "SitemapCollector"
    WEB_INDEX_COLLECTOR = "WebIndexCollector"
    PRESS_AREA_COLLECTOR = "PressAreaCollector"
    STATIC_PAGE_COLLECTOR = "StaticPageCollector"


class AcquisitionReadinessState(str, Enum):
    """Canonical primary acquisition readiness states (Stage 7B.3 Patch).
    These states are mutually exclusive and form an exact partition of all active sources.
    """
    READY = "ready"
    PARTIALLY_READY = "partially_ready"
    NEEDS_AUTH = "needs_auth"
    NEEDS_DISCOVERY = "needs_discovery"
    BLOCKED = "blocked"
    NOT_READY = "not_ready"


class TechnicalBlockReason(str, Enum):
    """Controlled values for technical blocking reasons (Stage 7B.3 Patch Section 7)."""
    FORBIDDEN = "forbidden"
    AUTHENTICATION = "authentication"
    ANTI_BOT = "anti_bot"
    NETWORK_RESTRICTION = "network_restriction"
    DEAD_ENDPOINT = "dead_endpoint"
    TEMPORARY_FAILURE = "temporary_failure"
    UNSUPPORTED_METHOD = "unsupported_method"
    UNKNOWN = "unknown"


class CollectorPriority(str, Enum):
    """Collector implementation priority levels (Stage 7B.3 Section 11)."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DISCOVERY_ONLY = "discovery_only"


class FailureRiskLevel(str, Enum):
    """Failure risk levels based on technical observation (Stage 7B.3 Section 12)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class DeduplicationKeyStrategy(str, Enum):
    """Deduplication key identity strategies (Stage 7B.3 Section 9)."""
    CANONICAL_URL = "canonical_url"
    SOURCE_GUID = "source_guid"
    EXTERNAL_ID = "external_id"
    DOI = "doi"
    ISBN = "isbn"
    NORMALIZED_TITLE_DATE = "normalized_title + date"


class PollIntervalCategory(str, Enum):
    """Recommended polling interval categories (Stage 7B.3 Section 10)."""
    M15 = "15m"
    M30 = "30m"
    M60 = "60m"
    M180 = "180m"
    M360 = "360m"
    DAILY = "daily"
    MANUAL = "manual"


class AuthenticationMode(str, Enum):
    """Explicit authentication requirements (Stage 7B.3 Section 14)."""
    NONE = "none"
    API_KEY = "api_key"
    OAUTH = "oauth"
    LOGIN = "login"
    PRESS_LOGIN = "press_login"
    SUBSCRIPTION = "subscription"
    UNKNOWN = "unknown"


class AcquisitionEvidenceItem(StrictModel):
    """Traceable evidence supporting verified acquisition capabilities (Stage 7B.3 Section 6 & 20)."""
    discovery_method: str = Field(default="declared_contract", description="Technique or rule that discovered/verified method")
    source_url: str = Field(..., description="Canonical source URL")
    endpoint_url: str = Field(..., description="Endpoint URL checked or declared")
    verification_status: str = Field(default="ok", description="Status code or state string (ok, verified, redirected, etc.)")
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of verification")
    verification_source: str = Field(default="live_probe", description="official_documentation or live_probe")
    notes: str | None = Field(default=None, description="Diagnostic notes or evidence notes")


class CollectorConfigPlan(StrictModel):
    """Future collector configuration representation contract (Stage 7B.3 Section 8)."""
    collector_type: str = Field(..., description="Assigned collector family")
    entrypoint: str = Field(..., description="Primary entrypoint URL for collector")
    endpoint: str | None = Field(default=None, description="Specific target endpoint URL if distinct from entrypoint")
    parser: str = Field(default="html_index", description="Parser identifier (html_index, json_api, rss_xml, press_html)")
    selectors_or_mapping: dict[str, str] | None = Field(default=None, description="Optional selectors or payload field mappings")
    pagination_mode: str = Field(default="none", description="Pagination mode: none, page_number, cursor, offset_limit")
    deduplication_key: str = Field(default="canonical_url", description="Deduplication key strategy")
    rate_limit_policy: str = Field(default="unknown", description="Rate limit policy rule or classification")
    poll_interval: str = Field(default="180m", description="Poll interval category: 15m, 30m, 60m, 180m, 360m, daily, manual")
    authentication_mode: str = Field(default="none", description="Authentication mode requirement")
    fallback_collector: str | None = Field(default=None, description="Fallback collector family if primary fails")


class SourceCapabilityEntry(StrictModel):
    source_id: str = Field(..., description="Canonical source ID")
    best_available_method: str | None = Field(
        default=None,
        description="Highest ranked available acquisition method",
    )
    fallback_methods: list[str] = Field(
        default_factory=list,
        description="Ordered list of secondary acquisition methods",
    )
    verified_methods: list[str] = Field(
        default_factory=list,
        description="Acquisition methods verified as available and usable",
    )
    unconfigured_methods: list[str] = Field(
        default_factory=list,
        description="Acquisition methods that are not declared or configured for this source",
    )
    unavailable_methods: list[str] = Field(
        default_factory=list,
        description="Acquisition methods configured or attempted but failing, blocked, or unavailable",
    )
    failed_methods: list[str] = Field(
        default_factory=list,
        description="Acquisition methods tested but currently failing or unavailable (compatibility alias)",
    )
    access_mode: str = Field(
        default="public",
        description="Observed access mode (public, api_key, subscription, authenticated, press_credential)",
    )
    access_requirements: str = Field(
        default="public",
        description="Observed access and authentication requirements (compatibility alias)",
    )
    authentication: str = Field(
        default="none",
        description="Authentication mechanism required: none, api_key, oauth, login, press_login, subscription, unknown",
    )
    parser_type: str | None = Field(
        default=None,
        description="Assigned parser type for best available method",
    )
    rate_limit_policy: str = Field(
        default="unknown",
        description="Rate limiting and concurrency policy specification",
    )
    backoff_required: bool = Field(
        default=False,
        description="Whether backoff is required on 429/rate limits",
    )
    recommended_poll_interval_minutes: int | None = Field(
        default=180,
        description="Recommended polling cadence in minutes",
    )
    poll_interval_category: str = Field(
        default="180m",
        description="Poll interval category: 15m, 30m, 60m, 180m, 360m, daily, manual",
    )
    production_ready: bool = Field(
        default=False,
        description="Whether endpoint is production usable",
    )
    readiness_state: str = Field(
        default="not_ready",
        description="Canonical primary readiness state: ready, partially_ready, needs_auth, needs_discovery, blocked, not_ready",
    )
    website_only: bool = Field(
        default=False,
        description="Whether only website scraping is verified (no structured feed, API, sitemap)",
    )
    has_structured_feed: bool = Field(
        default=False,
        description="Whether an RSS or Atom feed is verified",
    )
    has_api: bool = Field(
        default=False,
        description="Whether an official API is verified",
    )
    has_sitemap: bool = Field(
        default=False,
        description="Whether an XML sitemap is verified",
    )
    has_press_area: bool = Field(
        default=False,
        description="Whether an accredited or public press area is verified",
    )
    technical_block_reason: str | None = Field(
        default=None,
        description="Controlled technical block reason (forbidden, authentication, anti_bot, network_restriction, dead_endpoint, temporary_failure, unsupported_method, unknown)",
    )
    collector_type: str | None = Field(
        default=None,
        description="Assigned collector family: RSSCollector, APICollector, SitemapCollector, WebIndexCollector, PressAreaCollector, StaticPageCollector",
    )
    collector_priority: str = Field(
        default="medium",
        description="Collector implementation priority: critical, high, medium, low, discovery_only",
    )
    failure_category: str | None = Field(
        default=None,
        description="Specific homepage/endpoint failure classification",
    )
    risk_level: str = Field(
        default="low",
        description="Failure risk level: low, medium, high, unknown",
    )
    evidence_refs: list[AcquisitionEvidenceItem] = Field(
        default_factory=list,
        description="Traceable verification evidence items",
    )
    collector_config: CollectorConfigPlan | None = Field(
        default=None,
        description="Future collector configuration contract",
    )
    deduplication_key: str = Field(
        default="canonical_url",
        description="Deduplication key strategy for this source",
    )
    availability_state: str = Field(
        default="unknown",
        description="Dynamic health classification (healthy, degraded, unavailable, requires_auth)",
    )
    endpoint_reachable: bool = Field(
        default=False,
        description="Whether endpoint was reached over the network",
    )
    content_access: str | None = Field(
        default=None,
        description="Content access state (public_content, authenticated_content, reachable_but_locked, forbidden, not_found, unknown)",
    )
    authentication_required: bool = Field(
        default=False,
        description="Whether authentication is required for full access",
    )
    discovery_method: str | None = Field(
        default=None,
        description="How acquisition capability was discovered",
    )
    discovered_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when capability was discovered",
    )
    content_mode: str | None = Field(
        default="standard_html",
        description="Rendering mode required: standard_html, javascript_required, json, xml",
    )
    last_verified_at: datetime | None = Field(
        default=None,
        description="UTC timestamp of capability evaluation",
    )


class SourceAcquisitionMatrix(StrictModel):
    version: str = Field(default="1.0.0", description="Matrix document version")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of matrix generation",
    )
    total_sources: int = Field(default=0, description="Total sources evaluated")
    sources: dict[str, SourceCapabilityEntry] = Field(
        default_factory=dict,
        description="Map of source_id -> capability matrix entry",
    )
