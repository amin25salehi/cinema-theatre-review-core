"""
Authority Evaluator - Cinema & Theatre Review Editorial OS v1.0.1
Evaluates evidence against Authority Map rules, enforcing minimum confirmation thresholds,
source class authority, independent organization/domain counts, and conflict policies.
"""

from schemas.authority_map import AuthorityMap, AuthorityRule, ConflictPolicy
from schemas.evidence_card import (
    AuthorityResolutionItem,
    AuthorityStatus,
    Claim,
    EvidenceItem,
    EvidenceRelation,
)
from schemas.source_registry import SourceClass, SourceProfile, SourceRole


def classify_source(source: SourceProfile, rule: AuthorityRule, claim_type: str) -> str:
    """
    Classifies a source relative to an authority rule and claim predicate:
    Returns 'primary', 'secondary', 'discovery', or 'none'.
    """
    # If the source explicitly disclaims authority for this claim type
    if claim_type in source.not_authoritative_for:
        return "none"

    # If source explicitly lists authoritative claims, and this claim is not one of them
    if source.authoritative_claims and claim_type not in source.authoritative_claims:
        # Cannot be primary or secondary if explicitly restricted
        return "none"

    # Check if primary class
    if source.source_class in rule.primary_authority_classes:
        return "primary"

    # Check if secondary class
    if source.source_class in rule.secondary_authority_classes:
        return "secondary"

    # Check if discovery only
    if (
        source.source_class in rule.discovery_only_classes
        or source.roles == [SourceRole.DISCOVERY]
    ):
        return "discovery"

    return "none"


def count_unique_domains(sources: list[SourceProfile]) -> int:
    """
    Counts unique organizations/domains among the provided sources.
    """
    domains = {s.domain.strip().lower() for s in sources if s.domain}
    return len(domains)


def count_independent_confirmations(
    evidence_items: list[EvidenceItem],
    sources: dict[str, SourceProfile],
) -> int:
    """
    Counts independent source confirmations enforcing:
    1. Unique SourceProfile.domain (same domain counts as 1).
    2. Cryptographic de-syndication (identical content_hash across different domains
       counts as exactly ONE independent confirmation).
    """
    seen_domains: set[str] = set()
    seen_content_hashes: set[str] = set()
    count = 0

    for ev in evidence_items:
        src = sources.get(ev.source_id)
        if not src or not src.domain:
            continue
        dom = src.domain.strip().lower()
        chash = ev.content_hash.strip().lower() if ev.content_hash else None

        if dom in seen_domains:
            continue

        if chash and chash in seen_content_hashes:
            continue

        seen_domains.add(dom)
        if chash:
            seen_content_hashes.add(chash)
        count += 1

    return count


class AuthorityEvaluator:
    def __init__(self, authority_map: AuthorityMap, sources: dict[str, SourceProfile]):
        self.authority_map = authority_map
        self.sources = sources

    def get_rule_for_claim(self, claim_type: str) -> AuthorityRule | None:
        return self.authority_map.rules.get(claim_type)

    def evaluate_claim(
        self, claim: Claim, evidence_items: list[EvidenceItem]
    ) -> AuthorityResolutionItem:
        rule = self.get_rule_for_claim(claim.claim_type)

        if not rule:
            # Fallback when no specific authority rule is registered for claim type
            return AuthorityResolutionItem(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                preferred_authority_classes=[],
                preferred_source_id=None,
                status=AuthorityStatus.INSUFFICIENT,
                rule_applied="no_registered_authority_rule",
            )

        # 1. Collect evidence items for this claim
        relevant_evidence = [ev for ev in evidence_items if claim.claim_id in ev.claim_refs]
        supporting_evidence = [
            ev for ev in relevant_evidence if ev.relation == EvidenceRelation.SUPPORTS
        ]
        contradicting_evidence = [
            ev for ev in relevant_evidence if ev.relation == EvidenceRelation.CONTRADICTS
        ]

        # 2. Map supporting evidence and classify by authority class
        primary_evidence = [
            ev for ev in supporting_evidence
            if ev.source_id in self.sources
            and classify_source(self.sources[ev.source_id], rule, claim.claim_type) == "primary"
        ]
        secondary_evidence = [
            ev for ev in supporting_evidence
            if ev.source_id in self.sources
            and classify_source(self.sources[ev.source_id], rule, claim.claim_type) == "secondary"
        ]

        supporting_sources: list[SourceProfile] = [
            self.sources[ev.source_id] for ev in supporting_evidence if ev.source_id in self.sources
        ]
        primary_sources = [
            s for s in supporting_sources
            if classify_source(s, rule, claim.claim_type) == "primary"
        ]

        # 3. Apply independence requirements to count confirmations
        req_independent = rule.minimum_confirmation.require_independent_sources
        if req_independent:
            primary_confirmations = count_independent_confirmations(primary_evidence, self.sources)
            secondary_confirmations = count_independent_confirmations(secondary_evidence, self.sources)
        else:
            primary_confirmations = len({ev.source_id for ev in primary_evidence})
            secondary_confirmations = len({ev.source_id for ev in secondary_evidence})

        # 4. Check if confirmation threshold is satisfied
        min_conf = rule.minimum_confirmation
        primary_satisfied = (
            min_conf.primary_count > 0
            and primary_confirmations >= min_conf.primary_count
        )
        secondary_satisfied = (
            min_conf.secondary_count > 0
            and secondary_confirmations >= min_conf.secondary_count
        )

        # 5. Evaluate contradictions according to ConflictPolicy
        if contradicting_evidence:
            contradicting_sources: list[SourceProfile] = []
            for ev in contradicting_evidence:
                src = self.sources.get(ev.source_id)
                if src:
                    contradicting_sources.append(src)

            contra_primary = [
                s for s in contradicting_sources
                if classify_source(s, rule, claim.claim_type) == "primary"
            ]

            if rule.conflict_policy == ConflictPolicy.PREFER_PRIMARY:
                # Primary wins ONLY if primary confirmation is satisfied AND no primary contradicts
                if primary_satisfied and not contra_primary:
                    preliminary_status = AuthorityStatus.CONFIRMED
                else:
                    preliminary_status = AuthorityStatus.CONFLICTED
            elif rule.conflict_policy == ConflictPolicy.ALLOW_QUALIFIED_DISCOURSE:
                # Differing discourse allowed (e.g. critical assessment)
                if primary_satisfied:
                    preliminary_status = AuthorityStatus.CONFIRMED
                elif secondary_satisfied:
                    preliminary_status = AuthorityStatus.SECONDARY_CONFIRMED
                else:
                    preliminary_status = AuthorityStatus.INSUFFICIENT
            else:
                # HOLD_ON_UNRESOLVED or PROHIBIT_PUBLICATION
                preliminary_status = AuthorityStatus.CONFLICTED
        else:
            # No contradicting evidence
            if primary_satisfied:
                preliminary_status = AuthorityStatus.CONFIRMED
            elif secondary_satisfied:
                preliminary_status = AuthorityStatus.SECONDARY_CONFIRMED
            else:
                preliminary_status = AuthorityStatus.INSUFFICIENT

        # Determine preferred source if matched
        matched_preferred: str | None = None
        for ev in supporting_evidence:
            if ev.source_id in rule.preferred_source_ids:
                matched_preferred = ev.source_id
                break
        if not matched_preferred:
            for s in primary_sources:
                if s.source_id in rule.preferred_source_ids:
                    matched_preferred = s.source_id
                    break
                for alias in s.aliases:
                    if alias in rule.preferred_source_ids:
                        matched_preferred = alias
                        break
                if matched_preferred:
                    break

        preferred_classes = [c.value for c in rule.primary_authority_classes]

        return AuthorityResolutionItem(
            claim_id=claim.claim_id,
            claim_type=claim.claim_type,
            preferred_authority_classes=preferred_classes,
            preferred_source_id=matched_preferred,
            status=preliminary_status,
            rule_applied=f"{rule.claim_type}_v{self.authority_map.version}",
        )
