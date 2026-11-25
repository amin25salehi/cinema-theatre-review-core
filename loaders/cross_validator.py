"""
Cross-Registry Validator - Cinema & Theatre Review Editorial OS v1.0.1
Fails fast by checking foreign-key references, unique IDs, source classes,
and authority maps across all registry fragments and typed configs.

Usage:
    python -m loaders.cross_validator
"""

import json
import sys
from pathlib import Path

from loaders.config_loader import ConfigLoader
from loaders.entity_loader import EntityLoader
from loaders.source_loader import SourceLoader
from schemas.acquisition import (
    AccessMode,
    AcquisitionMethod,
    AcquisitionProfile,
    AcquisitionReadinessState,
    AcquisitionStatus,
    AuthenticationRequirement,
    CollectorFamily,
    SourceAcquisitionMatrix,
    TechnicalBlockReason,
)
from schemas.authority_map import AuthorityMap
from schemas.editorial_rules import EditorialRules
from schemas.entity_registry import EntityProfile
from schemas.iran_exceptions import IranExceptionsPolicy
from schemas.source_registry import SourceProfile
from schemas.taxonomy import ContentTaxonomy


class CrossRegistryValidator:
    def __init__(self, base_dir: Path | str = "."):
        self.base_dir = Path(base_dir)
        self.config_dir = self.base_dir / "config"
        self.sources_dir = self.config_dir / "sources"
        self.entities_dir = self.config_dir / "entities"

    def validate_all(self) -> tuple[bool, list[str], dict]:
        errors: list[str] = []
        stats = {
            "sources_count": 0,
            "entities_count": 0,
            "authority_rules_count": 0,
            "iran_exception_categories_count": 0,
            "taxonomy_claim_types_count": 0,
        }

        # 1. Load and validate sources
        source_loader = SourceLoader(self.sources_dir)
        try:
            sources: dict[str, SourceProfile] = source_loader.load_all_sources()
            stats["sources_count"] = len(sources)
        except Exception as e:
            errors.append(f"[Source Registry Error]: {e}")
            sources = {}

        # 2. Load and validate entities
        entity_loader = EntityLoader(self.entities_dir)
        try:
            entities: dict[str, EntityProfile] = entity_loader.load_all_entities()
            stats["entities_count"] = len(entities)
        except Exception as e:
            errors.append(f"[Entity Registry Error]: {e}")
            entities = {}

        # 3. Load configurations (Authority Map, Content Taxonomy, Editorial Rules, Iran Exceptions)
        config_loader = ConfigLoader(self.config_dir)
        try:
            authority_map: AuthorityMap = config_loader.load_authority_map()
            stats["authority_rules_count"] = len(authority_map.rules)
        except Exception as e:
            errors.append(f"[Authority Map Error]: {e}")
            authority_map = None

        try:
            taxonomy: ContentTaxonomy = config_loader.load_content_taxonomy()
            valid_claim_types = {ct.code for ct in taxonomy.claim_types}
            stats["taxonomy_claim_types_count"] = len(valid_claim_types)
        except Exception as e:
            errors.append(f"[Taxonomy Error]: {e}")
            valid_claim_types = set()

        try:
            editorial_rules: EditorialRules = config_loader.load_editorial_rules()
        except Exception as e:
            errors.append(f"[Editorial Rules Error]: {e}")
            editorial_rules = None

        try:
            iran_exceptions: IranExceptionsPolicy = config_loader.load_iran_exceptions()
            stats["iran_exception_categories_count"] = len(
                iran_exceptions.allowed_exception_categories
            )
        except Exception as e:
            errors.append(f"[Iran Exceptions Error]: {e}")
            iran_exceptions = None

        # Compute domain, class, and tier statistics for sources
        sources_by_domain: dict[str, int] = {}
        sources_by_class: dict[str, int] = {}
        sources_by_tier: dict[int, int] = {}
        for s in sources.values():
            sources_by_domain[s.domain] = sources_by_domain.get(s.domain, 0) + 1
            cls_val = s.source_class.value if hasattr(s.source_class, "value") else str(s.source_class)
            sources_by_class[cls_val] = sources_by_class.get(cls_val, 0) + 1
            sources_by_tier[s.tier] = sources_by_tier.get(s.tier, 0) + 1

        stats["sources_by_domain"] = sources_by_domain
        stats["sources_by_class"] = sources_by_class
        stats["sources_by_tier"] = sources_by_tier
        stats["invalid_references_count"] = 0
        stats["unresolved_claim_references_count"] = 0

        # 4. Cross-Reference Validation: Entity Provenance -> Source Registry
        for entity_id, entity in entities.items():
            for prov in entity.provenance:
                if prov.source_id not in sources:
                    stats["invalid_references_count"] += 1
                    errors.append(
                        f"[Foreign Key Violation]: Entity '{entity_id}' references source_id "
                        f"'{prov.source_id}' in provenance which does not exist in Source Registry."
                    )

        # 5. Authority Registry Validation: Source authoritative_claims & not_authoritative_for -> Taxonomy
        # Explicit non-claim domain/capability exclusions allowed in not_authoritative_for
        SPECIAL_NON_CLAIM_CAPABILITIES = {
            "box_office",
            "commercial_box_office",
            "breaking_news",
            "production_schedules",
            "commercial_distribution_deals",
            "commercial_theatre",
            "film_reviews",
            "theatre_reviews",
            "cinema",
            "academic_peer_review",
            "factual_release_dates",
            "filmography",
            "restoration_history",
            "scholarly_reception",
            "film_history",
            "academic_filmography",
            "restoration_provenance",
            "unreleased_film_details",
            "commercial_availability",
            "film_production_dates",
            "editorial_evaluations",
            "unverified_claims",
            "performance_reviews",
            "international_avant_garde",
            "fringe_theatre",
            "contractual_rights",
            "scholarly_biographies",
        }

        if valid_claim_types:
            for source_id, source in sources.items():
                for claim_code in source.authoritative_claims:
                    if claim_code not in valid_claim_types:
                        stats["unresolved_claim_references_count"] += 1
                        errors.append(
                            f"[Undefined Claim Type]: Source '{source_id}' claims authoritative status for "
                            f"'{claim_code}', which is not defined in content_taxonomy.json."
                        )
                for claim_code in source.not_authoritative_for:
                    if (
                        claim_code not in valid_claim_types
                        and claim_code not in SPECIAL_NON_CLAIM_CAPABILITIES
                    ):
                        stats["unresolved_claim_references_count"] += 1
                        errors.append(
                            f"[Undefined Claim Type]: Source '{source_id}' disclaims authority for "
                            f"'{claim_code}', which is neither a known claim type in content_taxonomy.json "
                            f"nor a documented special non-claim capability."
                        )

        # 6. Cross-Reference Validation: Authority Map -> Source Registry & Taxonomy
        if authority_map:
            for rule_code, rule in authority_map.rules.items():
                if valid_claim_types and rule_code not in valid_claim_types:
                    stats["unresolved_claim_references_count"] += 1
                    errors.append(
                        f"[Taxonomy Mismatch]: Authority Map rule '{rule_code}' is not defined "
                        f"in content_taxonomy.json claim_types."
                    )
                for pref_id in rule.preferred_source_ids:
                    if pref_id not in sources:
                        stats["invalid_references_count"] += 1
                        errors.append(
                            f"[Foreign Key Violation]: Authority rule '{rule_code}' lists preferred_source_id "
                            f"'{pref_id}' which does not exist in Source Registry."
                        )
                    else:
                        source = sources[pref_id]
                        allowed_classes = set(rule.primary_authority_classes) | set(
                            rule.secondary_authority_classes
                        )
                        if source.source_class not in allowed_classes:
                            errors.append(
                                f"[Class Authority Conflict]: Authority rule '{rule_code}' lists "
                                f"preferred_source_id '{pref_id}' with class '{source.source_class.value}', "
                                f"which is not among allowed primary/secondary classes for this rule."
                            )
                        if rule_code in source.not_authoritative_for:
                            errors.append(
                                f"[Disclaimed Authority Conflict]: Authority rule '{rule_code}' lists "
                                f"preferred_source_id '{pref_id}', but source '{pref_id}' explicitly "
                                f"disclaims authority for this claim type in not_authoritative_for."
                            )
                        if source.authoritative_claims and rule_code not in source.authoritative_claims:
                            errors.append(
                                f"[Unlisted Authority Conflict]: Authority rule '{rule_code}' lists "
                                f"preferred_source_id '{pref_id}', but source '{pref_id}' defines an explicit "
                                f"authoritative_claims list that omits '{rule_code}'."
                            )

        # 7. Acquisition Profile Validation: Verify technical acquisition contracts
        acquisition_profiles_count = 0
        acquisition_methods_checked = 0
        sources_with_api = 0
        sources_with_rss = 0
        sources_with_press = 0

        for source_id, source in sources.items():
            # Validate source acquisition methods
            for method in source.acquisition_method:
                acquisition_methods_checked += 1
                if not isinstance(method, AcquisitionMethod):
                    try:
                        AcquisitionMethod(method)
                    except ValueError:
                        errors.append(
                            f"[Invalid Acquisition Method]: Source '{source_id}' references unknown "
                            f"acquisition_method '{method}'."
                        )

            # Validate acquisition contract profile
            profile = source.get_acquisition_profile()
            acquisition_profiles_count += 1

            if AcquisitionMethod.API in profile.methods or profile.api_base_url:
                sources_with_api += 1
                if profile.preferred_method == AcquisitionMethod.API and not profile.api_base_url:
                    errors.append(
                        f"[Acquisition Contract Error]: Source '{source_id}' has preferred_method 'api' "
                        f"but lacks required api_base_url."
                    )

            if AcquisitionMethod.RSS in profile.methods or profile.feed_urls:
                sources_with_rss += 1

            if AcquisitionMethod.PRESS_AREA in profile.methods:
                sources_with_press += 1

            # Semantic constraint: Technical verification status must never override negative authority
            if profile.status == AcquisitionStatus.VERIFIED:
                # Disclaimed claims must remain disclaimed regardless of acquisition verification
                for disclaimed in source.not_authoritative_for:
                    if disclaimed in source.authoritative_claims:
                        errors.append(
                            f"[Semantic Authority Violation]: Source '{source_id}' has verified acquisition "
                            f"status but conflates authority by listing disclaimed claim '{disclaimed}' "
                            f"as authoritative."
                        )

        stats["acquisition_profiles_count"] = acquisition_profiles_count
        stats["acquisition_methods_checked"] = acquisition_methods_checked
        stats["sources_with_api"] = sources_with_api
        stats["sources_with_rss"] = sources_with_rss
        stats["sources_with_press"] = sources_with_press

        # 6. Validate Verified Acquisition Matrix (Stage 7B.3 Section 24)
        matrix_path = self.base_dir / "data" / "source_acquisition_matrix.json"
        if matrix_path.exists():
            try:
                with open(matrix_path, "r", encoding="utf-8") as f:
                    matrix_data = json.load(f)
                matrix = SourceAcquisitionMatrix(**matrix_data)
                valid_collector_types = {cf.value for cf in CollectorFamily} | {None}
                valid_methods = {"rss", "api", "sitemap", "press_area", "website", "static_page"}

                stats["matrix_sources_count"] = len(matrix.sources)
                stats["matrix_production_ready_count"] = sum(
                    1 for s in matrix.sources.values() if s.production_ready
                )

                # 1. Every matrix source exists in registry
                for sid, entry in matrix.sources.items():
                    if sid not in sources:
                        errors.append(
                            f"[Matrix Unknown Source]: Source '{sid}' in matrix does not exist in registry."
                        )

                    # 2. Every collector type is known
                    if entry.collector_type not in valid_collector_types:
                        errors.append(
                            f"[Matrix Collector Error]: Source '{sid}' has unknown collector type '{entry.collector_type}'."
                        )

                    # 3. Every fallback method is valid
                    for fb in entry.fallback_methods:
                        if fb not in valid_methods:
                            errors.append(
                                f"[Matrix Fallback Error]: Source '{sid}' has invalid fallback method '{fb}'."
                            )

                    # 4. Best method is among verified methods
                    if entry.best_available_method is not None:
                        if entry.best_available_method not in entry.verified_methods:
                            errors.append(
                                f"[Matrix Best Method Error]: Source '{sid}' best method '{entry.best_available_method}' is not among verified methods {entry.verified_methods}."
                            )
                    elif len(entry.verified_methods) > 0:
                        errors.append(
                            f"[Matrix Best Method Error]: Source '{sid}' has verified methods {entry.verified_methods} but best_available_method is None."
                        )

                    # 5. No authenticated method is falsely marked public
                    if entry.authentication_required or entry.content_access == "authenticated_content":
                        if entry.access_mode == "public" and entry.authentication == "none":
                            errors.append(
                                f"[Matrix Auth Conflation Error]: Source '{sid}' requires authentication but is marked public with authentication='none'."
                            )

                    # 6. No unconfigured method is marked verified
                    for vm in entry.verified_methods:
                        if vm in entry.unconfigured_methods:
                            errors.append(
                                f"[Matrix Unconfigured Error]: Source '{sid}' has method '{vm}' marked as both verified and unconfigured."
                            )

                    # 7. Acquisition state remains separate from editorial authority
                    if entry.production_ready and sid in sources:
                        src_obj = sources[sid]
                        for disclaimed in src_obj.not_authoritative_for:
                            if disclaimed in src_obj.authoritative_claims:
                                errors.append(
                                    f"[Matrix Authority Conflation]: Source '{sid}' production readiness cannot override editorial disclaim of '{disclaimed}'."
                                )

                # 8. Canonical readiness states and partition invariant (Stage 7B.3 Patch Section 2 & 5)
                valid_readiness_states = {s.value for s in AcquisitionReadinessState}
                valid_block_reasons = {b.value for b in TechnicalBlockReason}

                for sid, entry in matrix.sources.items():
                    if entry.readiness_state not in valid_readiness_states:
                        errors.append(
                            f"[Matrix Readiness State Error]: Source '{sid}' has invalid readiness state '{entry.readiness_state}'."
                        )
                    if entry.technical_block_reason is not None and entry.technical_block_reason not in valid_block_reasons:
                        errors.append(
                            f"[Matrix Technical Block Error]: Source '{sid}' has invalid technical_block_reason '{entry.technical_block_reason}'."
                        )
                    if entry.website_only and (entry.has_api or entry.has_structured_feed or entry.has_sitemap):
                        errors.append(
                            f"[Matrix Website-Only Error]: Source '{sid}' marked website_only=True but has structured capabilities verified."
                        )

                # Ensure all registered sources are present in the matrix
                for sid in sources:
                    if sid not in matrix.sources:
                        errors.append(
                            f"[Matrix Missing Source]: Source '{sid}' in registry is missing from acquisition matrix."
                        )

                # Partition invariant: sum of readiness states equals total sources
                readiness_sum = sum(1 for s in matrix.sources.values() if s.readiness_state in valid_readiness_states)
                if readiness_sum != len(matrix.sources):
                    errors.append(
                        f"[Matrix Partition Error]: Readiness states sum ({readiness_sum}) does not equal total sources ({len(matrix.sources)})."
                    )

            except Exception as e:
                errors.append(f"[Matrix Load Error]: Failed to validate acquisition matrix: {e}")

        is_valid = len(errors) == 0
        return is_valid, errors, stats


def main():
    validator = CrossRegistryValidator()
    is_valid, errors, stats = validator.validate_all()

    print("================================================================================")
    print("Cinema & Theatre Review - Editorial OS / Data & Editorial Core v1.0.1")
    print("Cross-Registry Validation Runner")
    print("================================================================================")
    print(f"Total Sources Loaded:     {stats['sources_count']}")
    print(f"Entities Loaded:          {stats['entities_count']}")
    print(f"Taxonomy Claim Types:     {stats['taxonomy_claim_types_count']}")
    print(f"Authority Rules Loaded:   {stats['authority_rules_count']}")
    print(f"Iran Exception Types:     {stats['iran_exception_categories_count']}")
    print(f"Invalid References:       {stats['invalid_references_count']}")
    print(f"Unresolved Claims:        {stats['unresolved_claim_references_count']}")
    print(f"Acquisition Profiles:     {stats['acquisition_profiles_count']}")
    print(f"Acquisition Methods:      {stats['acquisition_methods_checked']}")
    print(f"  API Channels:           {stats['sources_with_api']}")
    print(f"  RSS Channels:           {stats['sources_with_rss']}")
    print(f"  Press Area Channels:    {stats['sources_with_press']}")
    if "matrix_sources_count" in stats:
        print(f"Acquisition Matrix:       {stats['matrix_sources_count']} sources verified & planned")
        print(f"  Production Ready:       {stats['matrix_production_ready_count']}")
    print("--------------------------------------------------------------------------------")
    print("Sources by Tier:")
    for tier in sorted(stats.get("sources_by_tier", {}).keys()):
        print(f"  Tier {tier}: {stats['sources_by_tier'][tier]}")
    print("--------------------------------------------------------------------------------")
    print("Sources by Class:")
    for cls_name, count in sorted(stats.get("sources_by_class", {}).items()):
        print(f"  {cls_name}: {count}")
    print("--------------------------------------------------------------------------------")
    print(f"Sources by Domain ({len(stats.get('sources_by_domain', {}))} unique domains):")
    for dom, count in sorted(stats.get("sources_by_domain", {}).items())[:10]:
        print(f"  {dom}: {count}")
    if len(stats.get("sources_by_domain", {})) > 10:
        print(f"  ... and {len(stats['sources_by_domain']) - 10} more domains")
    print("--------------------------------------------------------------------------------")

    if is_valid:
        print("[SUCCESS] All registry fragments, schemas, and foreign-key references are VALID.")
        print("================================================================================")
        sys.exit(0)
    else:
        print(f"[FAILED] Found {len(errors)} cross-registry errors:")
        for idx, err in enumerate(errors, 1):
            print(f"  {idx}. {err}")
        print("================================================================================")
        sys.exit(1)


if __name__ == "__main__":
    main()
