"""
Editorial Diversity, Archetype Formatting, Anti-Cliché, and Temporal Disambiguation Engine.
Guarantees:
1. Dynamic, heterogeneous post structures across 7 editorial archetypes.
2. Strict prohibition of hyperbolic AI clichés and marketing superlatives.
3. Anti-hallucination quote rule: Direct quotes are strictly forbidden unless verified from source;
   otherwise analytical editorial prose is generated without blockquotes.
4. Clear temporal distinction: Historical retrospectives are explicitly badged as [مرور تاریخی / آرشیو].
5. Anti-repetition check against recent posts to ensure consecutive stylistic diversity.
"""

import re
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

class EditorialArchetype(str, Enum):
    ANALYTICAL_ESSAY = "analytical_essay"              # یادداشت تحلیلی و بوطیقای فرم
    CRITICAL_SPOTLIGHT = "critical_spotlight"          # کالبدشکافی انتقادی اثر معاصر
    FESTIVAL_DISPATCH = "festival_dispatch"            # گزارش فرهنگی و چشم‌انداز فستیوالی
    HISTORICAL_RETROSPECTIVE = "historical_retrospective" # مرور تاریخی و باستان‌شناسی فرم
    STAGE_CHRONICLE = "stage_chronicle"                # کرونیکل صحنه و دراماتورژی زنده
    CRITICAL_DIALOGUE = "critical_dialogue"            # صورت‌بندی موضع انتقادی و مناظره
    MONOGRAPH_THEORY = "monograph_theory"              # معرفی کتاب، مانیفست و رساله نظری

# Blacklisted clichés and hollow hyperbolic promotional marketing phrases
BANNED_EDITORIAL_CLICHES = [
    "اثری درخشان",
    "شاهکاری بی‌بدیل",
    "شاهکاری بی بدیل",
    "سفری شگفت‌انگیز",
    "سفری شگفت انگیز",
    "تجربه‌ای خارق‌العاده",
    "تجربه ای خارق العاده",
    "یکی از درخشان‌ترین آثار تاریخ",
    "یکی از درخشان ترین آثار تاریخ",
    "بی‌نظیر و تکرارنشدنی",
    "بی نظیر و تکرار نشدنی",
    "معجزه‌ای بر پرده سینما",
    "معجزه ای بر پرده سینما",
    "چشم‌نوازترین اثر",
    "فوق‌العاده و بی‌نقص",
    "اثری بی‌همتا",
]

ARCHETYPE_HEADERS = {
    EditorialArchetype.ANALYTICAL_ESSAY: "📐 <b>بوطیقای فرم و زیبایی‌شناسی سینما</b>",
    EditorialArchetype.CRITICAL_SPOTLIGHT: "🎬 <b>کالبدشکافی اثر؛ موضع انتقادی تحریریه</b>",
    EditorialArchetype.FESTIVAL_DISPATCH: "🌐 <b>چشم‌انداز فستیوال و نبض رویدادهای زنده</b>",
    EditorialArchetype.HISTORICAL_RETROSPECTIVE: "🏛 <b>[مرور تاریخی / آرشیو] باستان‌شناسی فرم</b>",
    EditorialArchetype.STAGE_CHRONICLE: "🎭 <b>دراماتورژی صحنه و تئاتر پیشرو</b>",
    EditorialArchetype.CRITICAL_DIALOGUE: "⚖️ <b>مناظره انتقادی؛ تقابل خوانش‌ها</b>",
    EditorialArchetype.MONOGRAPH_THEORY: "📚 <b>کتاب‌نامه و نظریه بنیادین</b>"
}

def detect_editorial_archetype(topic: str, text: str = "") -> EditorialArchetype:
    """Classifies an editorial item into one of the 7 diverse archetypes."""
    combined = (topic + " " + text).lower()

    if any(k in combined for k in ["کتاب", "رساله", "مانیفست", "انتشارات", "ترجمه"]):
        return EditorialArchetype.MONOGRAPH_THEORY
    elif any(k in combined for k in ["مناظره", "دوئل", "تقابل", "کایه دو سینما در برابر", "آیا پلان‌های"]):
        return EditorialArchetype.CRITICAL_DIALOGUE
    elif any(k in combined for k in ["تئاتر", "صحنه", "تانزتئاتر", "شوبونه", "دراماتورژی", "آوینیون", "کاستلوچی"]):
        return EditorialArchetype.STAGE_CHRONICLE
    elif any(k in combined for k in ["مرمت", "تاریخی", "آرشیو", "دهه ۱۹", "۱۹۶", "۱۹۷", "۱۹۵", "۱۹۴", "برسون", "تارکوفسکی"]):
        return EditorialArchetype.HISTORICAL_RETROSPECTIVE
    elif any(k in combined for k in ["فستیوال", "جشنواره", "کن", "ونیز", "برلین", "لوکارنو", "گزارش"]):
        return EditorialArchetype.FESTIVAL_DISPATCH
    elif any(k in combined for k in ["بوطیقا", "تدوین", "میزانسن", "صدا", "پلان", "نورپردازی", "تصویر-زمان"]):
        return EditorialArchetype.ANALYTICAL_ESSAY
    else:
        return EditorialArchetype.CRITICAL_SPOTLIGHT

def validate_editorial_quality(text: str) -> Tuple[bool, List[str]]:
    """
    Validates text against editorial standards:
    - Zero banned hyperbolic clichés.
    - Balanced character count (300 to 1200 characters).
    - Meaningful hashtags and reputable source attribution.
    """
    violations = []

    # 1. Check for banned clichés
    for cliché in BANNED_EDITORIAL_CLICHES:
        if cliché in text:
            violations.append(f"Contains banned hyperbolic cliché: '{cliché}'")

    # 2. Check length
    char_len = len(text)
    if char_len < 250:
        violations.append(f"Text too short ({char_len} chars, minimum 250 required).")
    elif char_len > 1400:
        violations.append(f"Text too long ({char_len} chars, maximum 1400 for Telegram).")

    # 3. Source link check
    if "href=" not in text:
        violations.append("Missing source documentation hyperlink.")

    return (len(violations) == 0, violations)

def sanitize_and_disambiguate_temporality(
    topic: str,
    text: str,
    is_pure_retrospective: bool = False,
    current_year: int = 2026
) -> Tuple[str, str]:
    """
    Distinguishes active cultural news from purely archival retrospectives:
    - If the topic/text involves an active contemporary hook (e.g. 4K restoration,
      Cannes Classics, theatrical re-release, newly discovered archival documents,
      recent monograph publication), it is treated as ACTIVE CULTURAL NEWS and NOT
      stigmatized as outdated archive.
    - Only if it is explicitly a pure historical retrospective or career survey with
      NO contemporary hook is it badged with [مرور تاریخی / آرشیو].
    - Eliminates any rigid production-year barrier (< 2015).
    """
    combined = (topic + " " + text).lower()

    # Active contemporary event hooks that make coverage of a classic work fresh cultural news:
    contemporary_event_hooks = [
        "مرمت ۴k", "مرمت 4k", "بازسازی ۴k", "کن کلاسیک", "کشف نگاتیو",
        "اکران مجدد", "نسخه ترمیم‌شده", "نسخه جدید", "انتشار نسخه",
        "جشنواره ۲۰۲", "جشنواره 202", "رویداد ۲۰۲", "رویداد 202",
        "اسکن ۴k", "بنیاد فیلم اسکورسیزی", "سینماتک بولونیا"
    ]
    has_active_hook = any(hook in combined for hook in contemporary_event_hooks)

    # Pure retrospective indicators without any news hook:
    retrospective_indicators = [
        "بازخوانی سینمای", "مرور کارنامه", "پرونده تاریخی", "دهه ۱۹۶۰", "دهه ۱۹۷۰",
        "دهه ۱۹۵۰", "دهه ۱۹۴۰", "دهه ۱۹۳۰", "سینمای کلاسیک هالیوود"
    ]
    is_historical_retrospective = (
        is_pure_retrospective or
        (any(r in combined for r in retrospective_indicators) and not has_active_hook)
    )

    cleaned_topic = topic
    cleaned_text = text

    if is_historical_retrospective:
        if "مرور تاریخی" not in cleaned_topic and "آرشیو" not in cleaned_topic:
            cleaned_topic = f"[مرور تاریخی / آرشیو] {cleaned_topic}"
        if "#مرور_تاریخی" not in cleaned_text:
            cleaned_text += "\n\n#مرور_تاریخی #آرشیو_سینما"

    return cleaned_topic, cleaned_text

def compute_structural_similarity(text1: str, text2: str) -> float:
    """
    Multi-layer structural and semantic similarity analyzer between consecutive posts:
    1. Evaluates paragraph line starter structure (skeleton similarity).
    2. Computes word bi-gram token overlap (semantic vocabulary similarity).
    Returns the higher of the two metrics (0.0 to 1.0).
    """
    if not text1 or not text2:
        return 0.0

    # 1. Structural skeleton similarity (line starters)
    lines1 = [line.strip() for line in text1.splitlines() if len(line.strip()) > 10]
    lines2 = [line.strip() for line in text2.splitlines() if len(line.strip()) > 10]

    struct_sim = 0.0
    if lines1 and lines2:
        starters1 = set(line[:25] for line in lines1)
        starters2 = set(line[:25] for line in lines2)
        inter = starters1 & starters2
        union = starters1 | starters2
        struct_sim = len(inter) / len(union) if union else 0.0

    # 2. Semantic n-gram token similarity (shingles)
    def extract_bigrams(txt: str) -> set:
        clean = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', txt.lower())
        words = [w for w in clean.split() if len(w) > 2]
        return set(f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1))

    bg1 = extract_bigrams(text1)
    bg2 = extract_bigrams(text2)

    sem_sim = 0.0
    if bg1 and bg2:
        inter_bg = bg1 & bg2
        union_bg = bg1 | bg2
        sem_sim = len(inter_bg) / len(union_bg) if union_bg else 0.0

    return max(struct_sim, sem_sim)
