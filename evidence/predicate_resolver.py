"""
Claim Predicate & Object Resolver - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.21: Deterministic Predicate Resolution & Object Entity Extraction.

Strict Invariants:
- 0 LLM calls, 0 embeddings, 0 semantic guessing.
- Purely deterministic string containment and rule precedence.
- Valid predicates strictly restricted to the 18 registered AuthorityMap rules.
- Discovery topics NEVER directly become claim predicates.
- Object resolution enforces required EntityType; positional fallback strictly rejected.
- object_value encodes sorted deterministic key-value qualifications.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Optional, Sequence

from pipeline.entity_resolver import EntityMatch
from schemas.entity_registry import EntityProfile, EntityType
from schemas.normalized_item import NormalizedItem

SAFE_SLUG_PATTERN = re.compile(r"^[a-z0-9_]+$")

# The 19 Canonical Claim Types registered in config/authority_map.json
CANONICAL_CLAIM_TYPES: frozenset[str] = frozenset({
    "festival_selection",
    "award_conferral",
    "theatre_premiere",
    "book_publication_date",
    "archival_restoration",
    "critical_assessment",
    "distribution_deal",
    "institutional_appointment",
    "production_commencement",
    "premiere_date",
    "documentary_selection",
    "festival_programme",
    "official_festival_report",
    "performance_dates",
    "jury_selection",
    "play_publication",
    "bibliographic_record",
    "scholarly_analysis",
    "theatre_criticism",
})

# Contested / dispute patterns that force unresolved ambiguous status
DISPUTE_PATTERNS: tuple[str, ...] = (
    "disputed",
    "disputes",
    "denied",
    "denies",
    "rumored",
    "rumour",
    "rumors",
    "alleged",
    "controversy",
    "unconfirmed",
    "تکذیب",
    "شایعه",
    "ادعا",
    "اختلاف",
)

# Trigger patterns per predicate (case-folded exact substrings)
PREDICATE_TRIGGERS: dict[str, tuple[str, ...]] = {
    "award_conferral": (
        "palme d'or",
        "golden bear",
        "silver bear",
        "golden lion",
        "best director",
        "best actor",
        "best actress",
        "best screenplay",
        "jury prize",
        "grand prix",
        "awarded",
        "wins award",
        "won award",
        "winner",
        "wins prize",
        "won prize",
        "wins the",
        "نخل طلا",
        "خرس طلا",
        "شیر طلا",
        "برنده جایزه",
        "جایزه بهترین",
        "برنده شد",
    ),
    "jury_selection": (
        "jury president",
        "head of jury",
        "jury member",
        "on the jury",
        "presides jury",
        "presided by",
        "رئیس هیئت داوران",
        "داور جشنواره",
        "عضو هیئت داوران",
    ),
    "premiere_date": (
        "world premiere",
        "international premiere",
        "opening night",
        "premiere date",
        "premieres on",
        "نخستین نمایش جهانی",
        "افتتاحیه",
        "تاریخ افتتاحیه",
        "نخستین اکران",
    ),
    "festival_selection": (
        "official selection",
        "in competition",
        "from competition",
        "un certain regard",
        "selected for",
        "selected in",
        "festival lineup",
        "main competition",
        "competition lineup",
        "competes at",
        "competing at",
        "screen in competition",
        "حضور در جشنواره",
        "بخش مسابقه",
        "مسابقه اصلی",
        "انتخاب شد",
        "حضور دارد",
    ),
    "theatre_premiere": (
        "stage premiere",
        "opening at",
        "theatrical staging",
        "stages new production",
        "new play opens",
        "premieres at theatre",
        "world premiere of play",
        "اجرای تئاتر",
        "روی صحنه می‌رود",
        "افتتاح نمایش",
        "اجرای جدید",
    ),
    "documentary_selection": (
        "documentary competition",
        "doc competition",
        "documentary lineup",
        "مسابقه مستند",
        "بخش مستند",
    ),
    "performance_dates": (
        "performance dates",
        "ticket sales",
        "runs through",
        "performance run",
        "limited run",
        "تاریخ اجرا",
        "تمدید اجرا",
        "زمان‌بندی اجرا",
    ),
    "festival_programme": (
        "festival programme",
        "announces programme",
        "full schedule",
        "programme announcement",
        "برنامه جشنواره",
        "جدول نمایش‌ها",
    ),
    "official_festival_report": (
        "livre le bilan",
        "bilan de l'édition",
        "bilan de la",
        "festival debrief",
        "rapport officiel",
        "گزارش جشنواره",
        "بیلان جشنواره",
    ),
    "archival_restoration": (
        "photochemical restoration",
        "4k restoration",
        "restored print",
        "restoration premiere",
        "preservation",
        "digitally restored",
        "restored version",
        "مرمت فیلم",
        "نسخه مرمت‌شده",
        "ترمیم فیلم",
        "مرمت ۴k",
    ),
    "book_publication_date": (
        "published by",
        "critical edition",
        "new monograph",
        "book release",
        "book publication",
        "monograph on",
        "منتشر شد",
        "کتاب جدید",
        "چاپ کتاب",
        "انتشار کتاب",
    ),
    "play_publication": (
        "play text published",
        "script publication",
        "play script released",
        "نمایشنامه منتشر شد",
        "متن نمایشنامه",
    ),
    "distribution_deal": (
        "distribution rights",
        "acquired by",
        "theatrical distribution",
        "distribution deal",
        "worldwide rights",
        "حق پخش",
        "اکران سراسری",
        "پخش‌کننده",
    ),
    "institutional_appointment": (
        "appointed artistic director",
        "appointed director",
        "named curator",
        "new director of",
        "انتصاب مدیر",
        "مدیر هنری جدید",
    ),
    "production_commencement": (
        "principal photography",
        "starts filming",
        "begins filming",
        "rehearsals begin",
        "starts shooting",
        "begins production",
        "کلید خورد",
        "آغاز فیلمبرداری",
        "تمرینات آغاز شد",
    ),
    "critical_assessment": (
        "critical essay",
        "film review",
        "retrospective review",
        "review:",
        "critical roundtable",
        "نقد فیلم",
        "یادداشت تحلیلی",
        "بررسی تحلیلی",
    ),
    "theatre_criticism": (
        "theatre review",
        "stage review",
        "review of staging",
        "نقد تئاتر",
        "یادداشت تئاتر",
    ),
    "scholarly_analysis": (
        "scholarly analysis",
        "aesthetic analysis",
        "film theory",
        "academic study",
        "مقاله پژوهشی",
        "رویکرد نظری",
    ),
    "bibliographic_record": (
        "isbn:",
        "catalogue entry",
        "bibliographic record",
        "شناسه کتابشناسی",
    ),
}

# Strict specificity rank (lower integer = higher priority)
PREDICATE_RANK: dict[str, int] = {
    "award_conferral": 1,
    "jury_selection": 2,
    "premiere_date": 3,
    "festival_selection": 4,
    "theatre_premiere": 5,
    "documentary_selection": 6,
    "performance_dates": 7,
    "festival_programme": 8,
    "official_festival_report": 9,
    "archival_restoration": 10,
    "book_publication_date": 11,
    "play_publication": 12,
    "distribution_deal": 13,
    "institutional_appointment": 14,
    "production_commencement": 15,
    "critical_assessment": 16,
    "theatre_criticism": 17,
    "scholarly_analysis": 18,
    "bibliographic_record": 19,
}

# Required EntityType for object entity per predicate
REQUIRED_OBJECT_ENTITY_TYPE: dict[str, tuple[EntityType, ...]] = {
    "festival_selection": (EntityType.FESTIVAL,),
    "award_conferral": (EntityType.AWARD, EntityType.FESTIVAL),
    "theatre_premiere": (EntityType.THEATRE, EntityType.FESTIVAL),
    "premiere_date": (EntityType.FESTIVAL, EntityType.THEATRE),
    "documentary_selection": (EntityType.FESTIVAL,),
    "jury_selection": (EntityType.FESTIVAL,),
    "festival_programme": (EntityType.FESTIVAL,),
    "official_festival_report": (EntityType.FESTIVAL, EntityType.INSTITUTION),
    "performance_dates": (EntityType.THEATRE,),
    "archival_restoration": (EntityType.ARCHIVE, EntityType.INSTITUTION),
    "book_publication_date": (EntityType.PUBLISHER,),
    "play_publication": (EntityType.PUBLISHER,),
    "distribution_deal": (EntityType.INSTITUTION,),
    "institutional_appointment": (EntityType.INSTITUTION,),
    "production_commencement": (EntityType.INSTITUTION,),
    "critical_assessment": (EntityType.INSTITUTION,),
    "theatre_criticism": (EntityType.INSTITUTION,),
    "scholarly_analysis": (EntityType.INSTITUTION,),
    "bibliographic_record": (EntityType.PUBLISHER,),
}


@dataclass(frozen=True)
class PredicateResolutionResult:
    """Deterministic result envelope of claim predicate and object resolution."""
    claim_type: Optional[str]
    object_entity_id: Optional[str]
    object_value: Optional[str]
    is_ambiguous: bool = False
    resolution_note: str = ""


class ClaimPredicateResolver:
    """
    Deterministic resolution engine for atomic claim predicates, object entities,
    and composite qualification values.
    """

    def __init__(self, entities: Mapping[str, EntityProfile]):
        self.entities = dict(entities)

    def resolve(
        self,
        normalized_item: NormalizedItem,
        subject_entity_id: str,
        entity_matches: Sequence[EntityMatch],
        target_topic: Optional[str] = None,
        story_hint: Optional[str] = None,
    ) -> PredicateResolutionResult:
        """
        Deterministically resolves the canonical claim predicate, object entity,
        and composite object_value.
        """
        title_text = (normalized_item.title or "").strip()
        summary_text = (normalized_item.summary or "").strip()
        hint_text = (story_hint or "").strip()

        # Step 1: Check for contested/disputed phrases in title or hint
        combined_header = f"{title_text} {hint_text}".lower()
        if any(d in combined_header for d in DISPUTE_PATTERNS):
            return PredicateResolutionResult(
                claim_type=None,
                object_entity_id=None,
                object_value=None,
                is_ambiguous=True,
                resolution_note="Contested or disputed phrasing detected in header text.",
            )

        # Step 2: Scan for matching predicates in Title (priority 1) and Summary (priority 2)
        title_matches = self._find_matching_predicates(title_text)
        if not title_matches and hint_text:
            title_matches = self._find_matching_predicates(hint_text)

        summary_matches = self._find_matching_predicates(summary_text)

        selected_predicate: Optional[str] = None

        if title_matches:
            # Title matches take absolute precedence over summary
            sorted_by_rank = sorted(title_matches, key=lambda p: PREDICATE_RANK.get(p, 999))
            selected_predicate = sorted_by_rank[0]
        elif summary_matches:
            # Fallback to summary matches if title had zero trigger matches
            sorted_by_rank = sorted(summary_matches, key=lambda p: PREDICATE_RANK.get(p, 999))
            selected_predicate = sorted_by_rank[0]

        if not selected_predicate or selected_predicate not in CANONICAL_CLAIM_TYPES:
            return PredicateResolutionResult(
                claim_type=None,
                object_entity_id=None,
                object_value=None,
                is_ambiguous=False,
                resolution_note="No registered atomic claim predicate matched trigger vocabulary.",
            )

        # Step 3: Resolve Object Entity (Typed Role Matching)
        object_entity_id = self._resolve_object_entity(
            predicate=selected_predicate,
            subject_entity_id=subject_entity_id,
            matches=entity_matches,
        )

        # Step 4: Resolve Composite object_value (Deterministic Key-Value Encoding)
        object_value = self._extract_composite_object_value(
            item=normalized_item,
            predicate=selected_predicate,
            object_entity_id=object_entity_id,
        )

        return PredicateResolutionResult(
            claim_type=selected_predicate,
            object_entity_id=object_entity_id,
            object_value=object_value,
            is_ambiguous=False,
            resolution_note=f"Resolved predicate '{selected_predicate}' with rank {PREDICATE_RANK.get(selected_predicate)}.",
        )

    def _find_matching_predicates(self, text: str) -> list[str]:
        """Finds all canonical predicates whose trigger phrases appear in text."""
        if not text:
            return []
        text_lower = text.lower()
        matched: list[str] = []
        for predicate, triggers in PREDICATE_TRIGGERS.items():
            if any(trigger in text_lower for trigger in triggers):
                matched.append(predicate)
        return matched

    def _resolve_object_entity(
        self,
        predicate: str,
        subject_entity_id: str,
        matches: Sequence[EntityMatch],
    ) -> Optional[str]:
        """
        Resolves object_entity_id strictly matching REQUIRED_OBJECT_ENTITY_TYPE.
        Explicitly rejects arbitrary positional selection.
        """
        allowed_types = REQUIRED_OBJECT_ENTITY_TYPE.get(predicate, ())
        if not allowed_types:
            return None

        # Filter out subject entity
        candidate_matches = [m for m in matches if m.entity_id != subject_entity_id]

        # Filter for required EntityType
        typed_matches: list[EntityMatch] = []
        for m in candidate_matches:
            prof = self.entities.get(m.entity_id)
            if prof and prof.entity_type in allowed_types:
                typed_matches.append(m)

        if not typed_matches:
            return None

        # Sort by section priority (title > summary), character offset, and entity_id
        sec_priority = {"title": 1, "summary": 2, "content_text": 3, "story_hint": 4, "tags": 5}

        def _sort_key(m: EntityMatch) -> tuple[int, int, str]:
            sec_p = sec_priority.get(m.section, 99)
            return (sec_p, m.start_char_index, m.entity_id)

        sorted_matches = sorted(typed_matches, key=_sort_key)
        return sorted_matches[0].entity_id

    def _extract_composite_object_value(
        self,
        item: NormalizedItem,
        predicate: str,
        object_entity_id: Optional[str],
    ) -> Optional[str]:
        """
        Extracts deterministic sorted key-value pairs for object_value.
        Example: 'edition=2026;section=competition'
        """
        full_text = f"{item.title} {item.summary or ''}".lower()
        kvs: list[tuple[str, str]] = []

        # 1. Edition / Year extraction (e.g. 2024, 2025, 2026, 2027 or 79e, 79th)
        edition_match = re.search(
            r"\b(\d{1,3})(?:e|ème|th|st|nd|rd)?\s+(?:[a-z0-9_\-]+\s+)*(?:édition|edition|festival|debrief|report)\b",
            full_text,
        )
        if edition_match:
            kvs.append(("edition", edition_match.group(1)))
        else:
            year_match = re.search(r"\b(202[0-9]|2030)\b", full_text)
            if year_match:
                kvs.append(("edition", year_match.group(1)))

        # 2. Section extraction for festival selection
        if predicate in ("festival_selection", "documentary_selection"):
            if "un certain regard" in full_text:
                kvs.append(("section", "un_certain_regard"))
            elif "directors' fortnight" in full_text or "quinzaine" in full_text:
                kvs.append(("section", "directors_fortnight"))
            elif "competition" in full_text or "مسابقه" in full_text:
                kvs.append(("section", "competition"))

        # 3. Category extraction for awards
        if predicate == "award_conferral":
            if "palme d'or" in full_text or "نخل طلا" in full_text:
                kvs.append(("category", "palme_dor"))
            elif "best director" in full_text or "بهترین کارگردانی" in full_text:
                kvs.append(("category", "best_director"))
            elif "golden bear" in full_text or "خرس طلا" in full_text:
                kvs.append(("category", "golden_bear"))
            elif "grand prix" in full_text:
                kvs.append(("category", "grand_prix"))

        if not kvs:
            return None

        # Canonical sort: key ascending, value ascending
        sorted_kvs = sorted(kvs, key=lambda kv: (kv[0], kv[1]))
        # Deduplicate keys
        seen_keys: set[str] = set()
        deduped: list[str] = []
        for k, v in sorted_kvs:
            if k not in seen_keys:
                seen_keys.add(k)
                clean_k = re.sub(r"[^a-z0-9_]+", "", k)
                clean_v = re.sub(r"[^a-z0-9_]+", "", v)
                deduped.append(f"{clean_k}={clean_v}")

        return ";".join(deduped) if deduped else None
