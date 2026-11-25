"""
Evidence Corroborator & In-Memory Index - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.21: In-Memory Indexing & 8-Step Corroboration Pipeline.

Strict Invariants:
- 0 network requests, 0 LLM calls, 0 external APIs.
- Operates over transient in-memory AcquisitionHandoff.items_by_id pool.
- Full 8-step matching pipeline enforcing claim identity, domain independence,
  de-syndication, claim-specific temporal windows, and lifecycle relations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Mapping, Optional, Sequence

from evidence.predicate_resolver import ClaimPredicateResolver, PredicateResolutionResult
from pipeline.entity_resolver import CanonicalEntityResolver, EntityMatch
from schemas.entity_registry import EntityProfile
from schemas.evidence_card import Claim, EvidenceItem, EvidenceRelation
from schemas.normalized_item import NormalizedItem
from schemas.source_registry import SourceProfile

# Exact claim-specific temporal windows (in days) from Stage 8.21 Contract 9
CLAIM_TEMPORAL_WINDOWS: dict[str, int] = {
    "festival_selection": 30,
    "award_conferral": 30,
    "premiere_date": 30,
    "documentary_selection": 30,
    "festival_programme": 30,
    "jury_selection": 30,
    "official_festival_report": 30,
    "theatre_premiere": 45,
    "performance_dates": 45,
    "distribution_deal": 60,
    "institutional_appointment": 60,
    "production_commencement": 90,
    "book_publication_date": 90,
    "play_publication": 90,
    "bibliographic_record": 180,
    "archival_restoration": 180,
    "critical_assessment": 365,
    "theatre_criticism": 365,
    "scholarly_analysis": 365,
}

# Relation Classification Triggers
DIRECT_NEGATION_TRIGGERS: tuple[str, ...] = (
    "not selected",
    "rejected from",
    "passed over",
    "did not win",
    "denied selection",
    "denies selection",
    "refutes selection",
    "selection denied",
    "failed to qualify",
    "not in competition",
    "rumor denied",
    "was not awarded",
    "did not premiere",
    "انتخاب نشد",
    "رد شد",
    "پذیرفته نشد",
    "جایزه نگرفت",
    "تکذیب شد",
    "به نمایش درنیامد",
)

LATER_LIFECYCLE_TRIGGERS: tuple[str, ...] = (
    "withdrawn",
    "withdraws",
    "pulled from",
    "cancelled",
    "postponed",
    "rescheduled",
    "removed from competition",
    "removed from lineup",
    "dropped from",
    "انصراف داد",
    "خارج شد",
    "لغو شد",
    "به تعویق افتاد",
    "حذف شد",
)

AFFIRMATIVE_TRIGGERS: tuple[str, ...] = (
    "selected",
    "in competition",
    "competes",
    "competing",
    "lineup",
    "won",
    "awarded",
    "premieres",
    "opening",
    "restored",
    "published",
    "stages",
    "festival debrief",
    "debrief report",
    "livre le bilan",
    "bilan de la",
    "bilan de l'édition",
    "rapport officiel",
    "debrief",
    "bilan",
    "delivers",
    "انتخاب شد",
    "برنده شد",
    "به نمایش درمی‌آید",
    "افتتاح می‌شود",
    "منتشر شد",
    "گزارش جشنواره",
    "بیلان جشنواره",
)

SAFE_SLUG_PATTERN = re.compile(r"^[a-z0-9_]+$")


def _sanitize_slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", text).strip("_").lower()
    return cleaned or "ev"


@dataclass(frozen=True)
class _CorpusIndexingAdapter:
    """Private lightweight adapter supplying story_hint to CanonicalEntityResolver."""
    story_hint: Optional[str] = None


class CorroborationIndex:
    """
    Transient in-memory index built over AcquisitionHandoff.items_by_id.
    Maps canonical entity_id -> list of (NormalizedItem, list[EntityMatch]).
    """

    def __init__(
        self,
        entity_resolver: CanonicalEntityResolver,
        items_by_id: Mapping[str, NormalizedItem],
    ):
        self.entity_resolver = entity_resolver
        self._entity_to_items: dict[str, list[tuple[NormalizedItem, list[EntityMatch]]]] = {}
        self._item_matches: dict[str, list[EntityMatch]] = {}
        self._build_index(items_by_id)

    def _build_index(self, items_by_id: Mapping[str, NormalizedItem]) -> None:
        """Indexes every NormalizedItem by its matched canonical entities."""
        adapter = _CorpusIndexingAdapter(story_hint=None)
        for item in items_by_id.values():
            matches = self.entity_resolver.resolve_matches(adapter, item)  # type: ignore[arg-type]
            if not matches:
                continue

            self._item_matches[item.item_id] = matches
            subject_id = self.entity_resolver.select_subject_entity(matches)
            if subject_id not in self._entity_to_items:
                self._entity_to_items[subject_id] = []
            self._entity_to_items[subject_id].append((item, matches))

    def get_items_for_entity(self, entity_id: str) -> list[tuple[NormalizedItem, list[EntityMatch]]]:
        """Returns all items whose resolved subject anchor matches entity_id."""
        return self._entity_to_items.get(entity_id, [])

    def get_matches_for_item(self, item_id: str) -> list[EntityMatch]:
        """Returns precomputed entity matches for a given item_id."""
        return self._item_matches.get(item_id, [])


class EvidenceCorroborator:
    """
    Executes the 8-step deterministic corroboration pipeline for a target claim.
    """

    def __init__(
        self,
        index: CorroborationIndex,
        predicate_resolver: ClaimPredicateResolver,
        sources: Mapping[str, SourceProfile],
    ):
        self.index = index
        self.predicate_resolver = predicate_resolver
        self.sources = dict(sources)

    def corroborate_claim(
        self,
        target_claim: Claim,
        primary_item: NormalizedItem,
    ) -> list[EvidenceItem]:
        """
        Evaluates all candidate items sharing target_claim.subject_entity_id
        through the 8-step corroboration sequence.
        """
        if not target_claim.subject_entity_id:
            return []

        harvested: list[EvidenceItem] = []
        candidate_items = self.index.get_items_for_entity(target_claim.subject_entity_id)

        # Primary source domain and content hash for de-syndication
        primary_src = self.sources.get(primary_item.source_id)
        primary_domain = primary_src.domain.strip().lower() if primary_src and primary_src.domain else ""
        primary_hash = (
            primary_item.fingerprints.get("text_sha256")
            or hashlib.sha256(primary_item.content_text.encode("utf-8")).hexdigest()
        )
        primary_title_hash = (
            primary_item.fingerprints.get("title_sha256")
            or hashlib.sha256(primary_item.title.strip().lower().encode("utf-8")).hexdigest()
        )

        seen_domains: set[str] = {primary_domain} if primary_domain else set()
        seen_content_hashes: set[str] = {primary_hash}

        for item, matches in candidate_items:
            # Skip the primary item itself
            if item.item_id == primary_item.item_id:
                continue

            # Step 1: Subject Entity Match (already satisfied by index lookup)

            # Step 2: Predicate Match
            pred_res = self.predicate_resolver.resolve(
                normalized_item=item,
                subject_entity_id=target_claim.subject_entity_id,
                entity_matches=matches,
            )
            if pred_res.claim_type != target_claim.claim_type or pred_res.is_ambiguous:
                continue

            # Step 3: Object Entity + object_value Match
            if pred_res.object_entity_id != target_claim.object_entity_id:
                continue
            if pred_res.object_value != target_claim.object_value:
                continue

            # Step 4: Domain Independence Check
            item_src = self.sources.get(item.source_id)
            if not item_src or not item_src.domain:
                continue
            item_domain = item_src.domain.strip().lower()
            if item_domain in seen_domains:
                # Same-domain duplicate -> discard
                continue

            # Step 5: Cryptographic De-Syndication Check
            item_hash = (
                item.fingerprints.get("text_sha256")
                or hashlib.sha256(item.content_text.encode("utf-8")).hexdigest()
            )
            item_title_hash = (
                item.fingerprints.get("title_sha256")
                or hashlib.sha256(item.title.strip().lower().encode("utf-8")).hexdigest()
            )
            if item_hash in seen_content_hashes or item_title_hash == primary_title_hash:
                # Syndicated wire / mirrored release -> discard
                continue

            # Step 6: Claim-Specific Temporal Window Check
            allowed_window_days = CLAIM_TEMPORAL_WINDOWS.get(target_claim.claim_type, 30)
            if not self._check_temporal_window(primary_item, item, allowed_window_days):
                continue

            # Step 7: Factual Relation Classification
            relation = self._classify_relation(item)

            # Step 8: Harvest EvidenceItem
            seen_domains.add(item_domain)
            seen_content_hashes.add(item_hash)

            evidence_item = self._build_evidence_item(
                item=item,
                claim_id=target_claim.claim_id,
                relation=relation,
                content_hash=item_hash,
            )
            harvested.append(evidence_item)

        return harvested

    def _check_temporal_window(
        self,
        item1: NormalizedItem,
        item2: NormalizedItem,
        allowed_days: int,
    ) -> bool:
        """Validates temporal proximity within allowed claim-specific window."""
        dt1 = item1.published_at or item1.retrieved_at
        dt2 = item2.published_at or item2.retrieved_at

        # If either item lacks published_at and relies on retrieved_at, cap window at 7 days
        if not item1.published_at or not item2.published_at:
            allowed_days = min(allowed_days, 7)

        # Normalize timezones
        if dt1.tzinfo is None:
            dt1 = dt1.replace(tzinfo=timezone.utc)
        if dt2.tzinfo is None:
            dt2 = dt2.replace(tzinfo=timezone.utc)

        delta_seconds = abs((dt1 - dt2).total_seconds())
        return delta_seconds <= (allowed_days * 86400)

    def _classify_relation(self, item: NormalizedItem) -> EvidenceRelation:
        """
        Deterministically classifies evidence relation:
        - Direct factual negation -> CONTRADICTS
        - Later lifecycle state -> QUALIFIES (non-confirming)
        - Affirmative -> SUPPORTS
        - Ambiguous -> CONTEXT
        """
        text = f"{item.title} {item.summary or ''}".lower()

        # Check direct factual negation first
        if any(neg in text for neg in DIRECT_NEGATION_TRIGGERS):
            return EvidenceRelation.CONTRADICTS

        # Check later lifecycle state (withdrawn / cancelled / postponed)
        if any(lc in text for lc in LATER_LIFECYCLE_TRIGGERS):
            return EvidenceRelation.QUALIFIES

        # Check affirmative pattern
        if any(aff in text for aff in AFFIRMATIVE_TRIGGERS):
            return EvidenceRelation.SUPPORTS

        return EvidenceRelation.CONTEXT

    def _build_evidence_item(
        self,
        item: NormalizedItem,
        claim_id: str,
        relation: EvidenceRelation,
        content_hash: str,
    ) -> EvidenceItem:
        """Constructs an immutable EvidenceItem adhering to schemas/evidence_card.py."""
        slug_src = _sanitize_slug(item.source_id)[:16]
        slug_item = _sanitize_slug(item.item_id)[:16]
        evidence_id = f"ev_corrob_{slug_src}_{slug_item}"

        excerpt = item.summary or item.content_text[:300]
        if not excerpt.strip():
            excerpt = f"Corroborating report: {item.title}"

        published_str = item.published_at.isoformat() if item.published_at else None
        retrieved_str = item.retrieved_at.isoformat()

        return EvidenceItem(
            evidence_id=evidence_id,
            source_id=item.source_id,
            source_url=item.canonical_url,
            evidence_type="corroborating_source",
            relation=relation,
            claim_refs=[claim_id],
            excerpt=excerpt.strip(),
            locator=None,
            published_at=published_str,
            retrieved_at=retrieved_str,
            content_hash=content_hash,
        )
