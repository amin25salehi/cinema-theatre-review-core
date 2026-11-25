"""
Tests for Authority Evaluator
Verifies minimum confirmation counts, source independence, and conflict policies.
"""

from evidence.authority_evaluator import AuthorityEvaluator, classify_source
from evidence.claim_builder import ClaimBuilder
from evidence.evidence_builder import EvidenceBuilder
from schemas.authority_map import AuthorityMap, AuthorityRule, ConflictPolicy, MinimumConfirmation
from schemas.evidence_card import AuthorityStatus, EvidenceRelation
from schemas.source_registry import SourceClass, SourceProfile, SourceRole


def test_classify_source_respects_not_authoritative_for():
    source = SourceProfile(
        source_id="src_test_archive",
        name="Test Archive",
        source_class=SourceClass.ARCHIVE_PRIMARY,
        tier=1,
        region="international",
        domain="archive.org",
        canonical_url="https://archive.org",
        language="en",
        acquisition_method="manual_audit",
        roles=[SourceRole.AUTHORITY],
        authoritative_claims=["archival_restoration"],
        not_authoritative_for=["commercial_box_office", "festival_selection"],
    )
    rule = AuthorityRule(
        claim_type="festival_selection",
        description="Festival selection",
        primary_authority_classes=[SourceClass.ARCHIVE_PRIMARY],
        secondary_authority_classes=[],
        discovery_only_classes=[],
        preferred_source_ids=[],
        minimum_confirmation=MinimumConfirmation(primary_count=1, secondary_count=2, require_independent_sources=True),
        conflict_policy=ConflictPolicy.HOLD_ON_UNRESOLVED,
    )

    # Even though source_class is in primary_authority_classes, festival_selection is disclaimed
    res = classify_source(source, rule, "festival_selection")
    assert res == "none"


def test_authority_evaluator_two_primaries_required_one_provided():
    # Setup rule requiring 2 primary confirmations
    rule = AuthorityRule(
        claim_type="high_stakes_claim",
        description="High stakes claim requiring 2 independent primary confirmations",
        primary_authority_classes=[SourceClass.FESTIVAL_PRIMARY],
        secondary_authority_classes=[SourceClass.CRITICAL_JOURNAL],
        discovery_only_classes=[],
        preferred_source_ids=[],
        minimum_confirmation=MinimumConfirmation(primary_count=2, secondary_count=3, require_independent_sources=True),
        conflict_policy=ConflictPolicy.HOLD_ON_UNRESOLVED,
    )
    auth_map = AuthorityMap(version="1.0.0", updated_at="2026-09-17T00:00:00Z", rules={"high_stakes_claim": rule})

    sources = {
        "src_cannes": SourceProfile(
            source_id="src_cannes",
            name="Cannes",
            source_class=SourceClass.FESTIVAL_PRIMARY,
            tier=1,
            region="international",
            domain="festival-cannes.com",
            canonical_url="https://festival-cannes.com",
            language="fr",
            acquisition_method="manual_audit",
            roles=[SourceRole.AUTHORITY],
            authoritative_claims=[],
            not_authoritative_for=[],
        )
    }

    evaluator = AuthorityEvaluator(auth_map, sources)

    claim = ClaimBuilder.create_claim(
        claim_id="clm_hs_01",
        claim_type="high_stakes_claim",
        subject_entity_id="film_taste_of_cherry",
        claim_text="High stakes event.",
        material=True,
    )
    ev1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_01",
        source_id="src_cannes",
        source_url="https://festival-cannes.com",
        evidence_type="official_release",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_hs_01"],
        excerpt="Only one primary confirmation provided.",
    )

    result = evaluator.evaluate_claim(claim, [ev1])
    # Must be INSUFFICIENT because primary_count is 1, but rule requires 2
    assert result.status == AuthorityStatus.INSUFFICIENT


def test_authority_evaluator_independent_domains_enforcement():
    # Secondary confirmation requires 2 independent sources
    rule = AuthorityRule(
        claim_type="theatre_premiere",
        description="Theatre premiere",
        primary_authority_classes=[SourceClass.VENUE_PRIMARY],
        secondary_authority_classes=[SourceClass.CRITICAL_JOURNAL],
        discovery_only_classes=[],
        preferred_source_ids=[],
        minimum_confirmation=MinimumConfirmation(primary_count=1, secondary_count=2, require_independent_sources=True),
        conflict_policy=ConflictPolicy.HOLD_ON_UNRESOLVED,
    )
    auth_map = AuthorityMap(version="1.0.0", updated_at="2026-09-17T00:00:00Z", rules={"theatre_premiere": rule})

    # Two sources from the SAME domain
    sources = {
        "src_journal_main": SourceProfile(
            source_id="src_journal_main",
            name="Theatre Journal Main",
            source_class=SourceClass.CRITICAL_JOURNAL,
            tier=2,
            region="international",
            domain="theatrejournal.org",
            canonical_url="https://theatrejournal.org",
            language="en",
            acquisition_method="manual_audit",
            roles=[SourceRole.AUTHORITY],
            authoritative_claims=[],
            not_authoritative_for=[],
        ),
        "src_journal_blog": SourceProfile(
            source_id="src_journal_blog",
            name="Theatre Journal Blog",
            source_class=SourceClass.CRITICAL_JOURNAL,
            tier=2,
            region="international",
            domain="theatrejournal.org",  # Same domain!
            canonical_url="https://theatrejournal.org/blog",
            language="en",
            acquisition_method="manual_audit",
            roles=[SourceRole.AUTHORITY],
            authoritative_claims=[],
            not_authoritative_for=[],
        ),
        "src_independent_review": SourceProfile(
            source_id="src_independent_review",
            name="Independent Stage Review",
            source_class=SourceClass.CRITICAL_JOURNAL,
            tier=2,
            region="international",
            domain="independentstage.co.uk",  # Distinct domain!
            canonical_url="https://independentstage.co.uk",
            language="en",
            acquisition_method="manual_audit",
            roles=[SourceRole.AUTHORITY],
            authoritative_claims=[],
            not_authoritative_for=[],
        ),
    }

    evaluator = AuthorityEvaluator(auth_map, sources)

    claim = ClaimBuilder.create_claim(
        claim_id="clm_th_01",
        claim_type="theatre_premiere",
        subject_entity_id="play_waiting_for_godot",
        claim_text="Premiere staged in Berlin.",
        material=True,
    )

    ev_same_1 = EvidenceBuilder.create_evidence(
        evidence_id="ev_s1",
        source_id="src_journal_main",
        source_url="https://theatrejournal.org/main",
        evidence_type="review",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_th_01"],
        excerpt="Review of premiere.",
    )
    ev_same_2 = EvidenceBuilder.create_evidence(
        evidence_id="ev_s2",
        source_id="src_journal_blog",
        source_url="https://theatrejournal.org/blog",
        evidence_type="review",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_th_01"],
        excerpt="Blog notice of premiere.",
    )

    # When both are from theatrejournal.org, independent count is 1 -> INSUFFICIENT
    res_same = evaluator.evaluate_claim(claim, [ev_same_1, ev_same_2])
    assert res_same.status == AuthorityStatus.INSUFFICIENT

    # When replaced with a source from a distinct domain -> SECONDARY_CONFIRMED
    ev_indep = EvidenceBuilder.create_evidence(
        evidence_id="ev_ind",
        source_id="src_independent_review",
        source_url="https://independentstage.co.uk/review",
        evidence_type="review",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_th_01"],
        excerpt="Independent review of premiere.",
    )
    res_indep = evaluator.evaluate_claim(claim, [ev_same_1, ev_indep])
    assert res_indep.status == AuthorityStatus.SECONDARY_CONFIRMED


def test_conflict_policy_prefer_primary():
    rule = AuthorityRule(
        claim_type="award_conferral",
        description="Award conferral",
        primary_authority_classes=[SourceClass.FESTIVAL_PRIMARY],
        secondary_authority_classes=[SourceClass.CRITICAL_JOURNAL],
        discovery_only_classes=[],
        preferred_source_ids=[],
        minimum_confirmation=MinimumConfirmation(primary_count=1, secondary_count=2, require_independent_sources=True),
        conflict_policy=ConflictPolicy.PREFER_PRIMARY,
    )
    auth_map = AuthorityMap(version="1.0.0", updated_at="2026-09-17T00:00:00Z", rules={"award_conferral": rule})

    sources = {
        "src_cannes": SourceProfile(
            source_id="src_cannes",
            name="Cannes",
            source_class=SourceClass.FESTIVAL_PRIMARY,
            tier=1,
            region="international",
            domain="festival-cannes.com",
            canonical_url="https://festival-cannes.com",
            language="fr",
            acquisition_method="manual_audit",
            roles=[SourceRole.AUTHORITY],
            authoritative_claims=[],
            not_authoritative_for=[],
        ),
        "src_rumor_journal": SourceProfile(
            source_id="src_rumor_journal",
            name="Rumor Journal",
            source_class=SourceClass.CRITICAL_JOURNAL,
            tier=2,
            region="international",
            domain="rumorjournal.com",
            canonical_url="https://rumorjournal.com",
            language="en",
            acquisition_method="manual_audit",
            roles=[SourceRole.AUTHORITY],
            authoritative_claims=[],
            not_authoritative_for=[],
        ),
    }

    evaluator = AuthorityEvaluator(auth_map, sources)

    claim = ClaimBuilder.create_claim(
        claim_id="clm_awd_01",
        claim_type="award_conferral",
        subject_entity_id="film_taste_of_cherry",
        claim_text="Won Palme d'Or.",
        material=True,
    )

    ev_supp_primary = EvidenceBuilder.create_evidence(
        evidence_id="ev_p1",
        source_id="src_cannes",
        source_url="https://festival-cannes.com/palme",
        evidence_type="official_communique",
        relation=EvidenceRelation.SUPPORTS,
        claim_refs=["clm_awd_01"],
        excerpt="Palme d'Or awarded to Taste of Cherry.",
    )
    ev_contra_secondary = EvidenceBuilder.create_evidence(
        evidence_id="ev_c1",
        source_id="src_rumor_journal",
        source_url="https://rumorjournal.com/doubt",
        evidence_type="commentary",
        relation=EvidenceRelation.CONTRADICTS,
        claim_refs=["clm_awd_01"],
        excerpt="Doubt cast on the jury award outcome.",
    )

    # Because PREFER_PRIMARY policy applies, and primary confirms while only secondary contradicts,
    # it is CONFIRMED in favor of primary.
    res = evaluator.evaluate_claim(claim, [ev_supp_primary, ev_contra_secondary])
    assert res.status == AuthorityStatus.CONFIRMED
