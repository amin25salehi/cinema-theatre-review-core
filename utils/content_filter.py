"""
Content Filter & Editorial News Qualifier - Cinema & Theatre Review Editorial OS v1.0.1

Distinguishes legitimate cinema, theatre, festival, archive, and book news/events
from uninformative generic, promotional, service, and privacy/legal utility pages.

Strict Invariants:
1. Retains all cinema, theatre, festival, archive, and book news and events.
2. Filters out generic institutional, promotional, service, and privacy/legal pages
   lacking specific editorial news content.
3. Purely deterministic evaluation (0 LLM, 0 external network requests).
"""

from __future__ import annotations

import re
from typing import Optional, Sequence
from urllib.parse import urlparse


# =============================================================================
# Substantive Editorial News & Cultural Event Indicators (Strong Positive Signals)
# =============================================================================

EDITORIAL_NEWS_INDICATOR_PATTERNS: list[re.Pattern] = [
    # Cinema & Film events, selections, restorations, critical assessment
    re.compile(r"\b(?:restoration|restored|remastered|4k|photochemical|digitised|digitized)\b", re.IGNORECASE),
    re.compile(r"\b(?:premiere|premieres|premiered|screening|screenings|retrospective)\b", re.IGNORECASE),
    re.compile(r"\b(?:official\s+selection|competition\s+lineup|lineup|line-up|in\s+competition)\b", re.IGNORECASE),
    re.compile(r"\b(?:palme\s+d['’]or|golden\s+lion|golden\s+bear|silver\s+bear|prix|award|awards|awarded|winner|winners|wins|won)\b", re.IGNORECASE),
    re.compile(r"\b(?:jury|filmmaker|director|documentary|short\s+film|feature\s+film|feature)\b", re.IGNORECASE),
    re.compile(r"\b(?:review|reviews|critique|critical\s+assessment|interview|interviews|profile)\b", re.IGNORECASE),
    re.compile(r"\b(?:announces|announced|unveils|reveals|unveiled|revealed|curated\s+season|preservation)\b", re.IGNORECASE),
    re.compile(r"\b(?:greatest\s+films|sight\s+and\s+sound\s+poll|decennial\s+poll)\b", re.IGNORECASE),

    # Theatre & Performing Arts
    re.compile(r"\b(?:theatre|theater|stage|playwright|theatre\s+production|theater\s+production|stage\s+production)\b", re.IGNORECASE),
    re.compile(r"\b(?:opening\s+night|rehearsal|revival|dramaturgy|theatre\s+premiere|theater\s+premiere|staged|stages)\b", re.IGNORECASE),
    re.compile(r"\b(?:performance\s+dates|festival\s+programme|festival\s+program)\b", re.IGNORECASE),

    # Books, Monographs & Dramatic texts
    re.compile(r"\b(?:book\s+publication|monograph|monographs|published\s+by|publishes|dramatic\s+text|anthology)\b", re.IGNORECASE),

    # Festivals, Archives & Cinematheques
    re.compile(r"\b(?:film\s+festival|theatre\s+festival|theater\s+festival|national\s+archive|cinematheque|cinémathèque|cinemateca)\b", re.IGNORECASE),

    # Persian editorial indicators
    re.compile(r"(?:مرمت|نسخه\s*۴k|اکران|افتتاحیه|جشنواره|برنده|جایزه|هیئت\s*داوران|کارگردان|مستند|فیلم\s*کوتاه|نقد|گفت‌وگو|مرور\s*آثار|تئاتر|نمایشنامه|اجرا|روی\s*صحنه|کتاب|انتشار|آرشیو|فیلمخانه)", re.IGNORECASE),

    # French editorial indicators
    re.compile(r"\b(?:restauration|palmarès|sélection\s+officielle|compétition|prix|critique|entretien|avant-première|cinémathèque|hommage)\b", re.IGNORECASE),
]


# =============================================================================
# Generic, Promotional, Service, and Privacy/Legal Patterns (Negative Signals)
# =============================================================================

# Title patterns indicating non-news utility pages
GENERIC_OR_UTILITY_TITLE_PATTERNS: list[re.Pattern] = [
    # Privacy & Legal Policy
    re.compile(
        r"\b(?:privacy\s+policy|privacy\s+notice|cookie\s+policy|cookie\s+preferences|manage\s+cookies|"
        r"terms\s+(?:and|&)\s+conditions|terms\s+of\s+use|terms\s+of\s+service|conditions\s+of\s+sale|"
        r"legal\s+notice|legal\s+information|disclaimer|copyright\s+notice|accessibility\s+statement)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:حریم\s*خصوصی|شرایط\s*استفاده|قوانین\s*و\s*مقررات|سیاست\s*کوکی|سلب\s*مسئولیت|حقوق\s*نشر)", re.IGNORECASE),
    re.compile(r"\b(?:politique\s+de\s+confidentialité|mentions\s+légales|conditions\s+d['’]utilisation|gestion\s+des\s+cookies)\b", re.IGNORECASE),

    # Generic & Institutional Pages (e.g. "About the BFI", "About us", "Contact us", "FAQ")
    re.compile(r"^\s*about\s+(?:the\s+)?[a-z0-9\s_-]+$", re.IGNORECASE),
    re.compile(
        r"\b(?:who\s+we\s+are|what\s+we\s+do|our\s+mission|our\s+team|board\s+of\s+governors|"
        r"annual\s+report|visitor\s+information|getting\s+here|how\s+to\s+find\s+us|careers|work\s+for\s+us|jobs\s+at)\b",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*(?:contact|contact\s+us|faq|frequently\s+asked\s+questions|help|sitemap)\s*$", re.IGNORECASE),
    re.compile(r"(?:درباره\s*ما|معرفی\s*ما|ارتباط\s*با\s*ما|تماس\s*با\s*ما|پرسش‌های\s*متداول|راهنما|فرصت‌های\s*شغلی)", re.IGNORECASE),
    re.compile(r"\b(?:à\s+propos|qui\s+sommes-nous|notre\s+équipe|nous\s+contacter)\b", re.IGNORECASE),

    # Promotional, Commercial & Membership (e.g. "Become a BFI member", "Donate", "Support us")
    re.compile(
        r"\b(?:become\s+a\s+(?:[a-z0-9_-]+\s+)?member|become\s+a\s+member|membership|join\s+us|join\s+the|"
        r"donate|donate\s+to|make\s+a\s+donation|support\s+us|support\s+the|corporate\s+support|"
        r"sponsorship|our\s+sponsors|our\s+partners|advertise\s+with\s+us|advertising|"
        r"newsletter\s+sign[\s-]?up|subscribe\s+to\s+newsletter|email\s+updates)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:عضویت|حمایت\s*مالی|تبلیغات|خبرنامه)", re.IGNORECASE),
    re.compile(r"\b(?:devenir\s+membre|adhésion|faire\s+un\s+don|soutenez-nous|partenaires|newsletter)\b", re.IGNORECASE),

    # Service Platforms, Ticketing & Accounts (e.g. "BFI Player", "Tickets", "My account", "Shop")
    re.compile(r"^\s*(?:[a-z0-9_-]+\s+)?player\s*$", re.IGNORECASE),
    re.compile(r"^\s*watch\s+on\s+(?:[a-z0-9_-]+\s+)?player\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:streaming\s+service|video\s+on\s+demand|vod\s+platform)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:book\s+tickets|buy\s+tickets|tickets\s+and\s+booking|box\s+office(?:\s+info)?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:my\s+account|sign\s+in|log\s+in|login|register|shopping\s+cart|basket|checkout)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:[a-z0-9_-]+\s+)?shop(?:\s+online)?\s*$", re.IGNORECASE),
    re.compile(r"(?:پخش\s*آنلاین|خرید\s*بلیت|بلیت‌فروشی|ورود\s*به\s*حساب|سبد\s*خرید|فروشگاه)", re.IGNORECASE),
    re.compile(r"\b(?:billetterie|réserver|mon\s+compte|se\s+connecter|boutique)\b", re.IGNORECASE),
]

# URL path and domain patterns indicating utility pages
GENERIC_OR_UTILITY_URL_PATTERNS: list[re.Pattern] = [
    re.compile(r"/(?:privacy|privacy-policy|privacy-notice)(?:/|\.[a-z]+)?$", re.IGNORECASE),
    re.compile(r"/(?:cookie|cookies|cookie-policy|cookie-preferences)(?:/|\.[a-z]+)?$", re.IGNORECASE),
    re.compile(r"/(?:terms|terms-and-conditions|terms-of-use|terms-of-service)(?:/|\.[a-z]+)?$", re.IGNORECASE),
    re.compile(r"/(?:legal|legal-notice|disclaimer|accessibility)(?:/|\.[a-z]+)?$", re.IGNORECASE),
    re.compile(r"/(?:about|about-us|about-bfi|who-we-are)(?:/|\.[a-z]+)?$", re.IGNORECASE),
    re.compile(r"/(?:contact|contact-us|help|faq|sitemap|careers|jobs)(?:/|\.[a-z]+)?$", re.IGNORECASE),
    re.compile(r"/(?:membership|become-a-member|become-a-bfi-member|join|donate|support-us|sponsorship|advertising)(?:/|\.[a-z]+)?$", re.IGNORECASE),
    re.compile(r"/(?:bfi-player|player|watch-online)(?:/|\.[a-z]+)?$", re.IGNORECASE),
    re.compile(r"/(?:tickets|booking|box-office|login|signin|register|account|shop|cart|basket|checkout)(?:/|\.[a-z]+)?$", re.IGNORECASE),
]


def has_specific_news_content(text: str) -> bool:
    """
    Checks whether the given text contains unambiguous editorial news or event indicators
    in cinema, theatre, festivals, archives, or books.
    """
    if not text or not text.strip():
        return False
    return any(p.search(text) for p in EDITORIAL_NEWS_INDICATOR_PATTERNS)


def is_generic_or_utility_item(
    url: Optional[str] = None,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    content_text: Optional[str] = None,
    story_hint: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
) -> bool:
    """
    Determines whether an item represents an uninformative generic, promotional,
    service, or privacy/legal utility page lacking specific editorial news content.

    Returns True if:
    - The title or URL matches generic/promotional/service/privacy patterns.
    - AND the item lacks specific editorial news/event indicators.

    Returns False if:
    - The item does not match any generic patterns.
    - OR the item contains specific editorial news/event indicators.
    """
    url_str = (url or "").strip()
    title_str = (title or "").strip()
    summary_str = (summary or "").strip()
    content_str = (content_text or "").strip()
    hint_str = (story_hint or "").strip()
    tags_str = " ".join(t.strip() for t in (tags or []) if t and t.strip())

    combined_text = f"{title_str} {summary_str} {content_str} {hint_str} {tags_str}".strip()

    # If the item has substantive editorial news or cultural event indicators,
    # it is NOT a generic utility page (preserve it!)
    if has_specific_news_content(combined_text):
        return False

    # Check URL patterns
    if url_str:
        parsed = urlparse(url_str)
        # Dedicated utility subdomains (e.g. player.bfi.org.uk)
        if parsed.netloc.lower().startswith("player."):
            return True
        path = parsed.path.rstrip("/")
        if any(p.search(path) for p in GENERIC_OR_UTILITY_URL_PATTERNS):
            return True

    # Check title and story hint patterns
    for candidate_str in (title_str, hint_str):
        if candidate_str:
            if any(p.search(candidate_str) for p in GENERIC_OR_UTILITY_TITLE_PATTERNS):
                return True

    return False
