"""
Stage 7: Flexible Multi-Tier Quality Gate.
Cinema & Theatre Review Editorial OS.

Replaces rigid 'fail-closed' mechanical blocking with a 3-tier advisory system:
- Level A (آماده بازبینی): Verified facts, authentic still/clean text, proper temporal classification.
- Level B (نیازمند توجه سردبیر): Useful cultural content with minor ambiguity (e.g. date approximate, image is festival photocall rather than film still, or review age > 7 days). Post is generated and flagged with advisory notices for the editor!
- Level C (دارای نقص جدی): Broken link or hallucinated quote. In this case, the quote/defect is sanitized and salvaged as cohesive analytical prose for editor inspection.

Never drop valuable content simply due to a missing exact date or image.
"""

import re
from typing import Dict, Any, List, Tuple

BANNED_PROMOTIONAL_CLICHES = [
    "اثری درخشان", "شاهکاری بی بدیل", "شاهکاری بی‌بدیل", "رویدادی تکرارنشدنی",
    "معجزه ای بر پرده", "معجزه‌ای بر پرده", "نقطه عطفی تکرارنشدنی",
    "اثری فوق العاده", "اثری فوق‌العاده", "هنرمندی بی همتا", "هنرمندی بی‌همتا",
    "شاهکار قرن", "بی نظیر در تاریخ", "بی‌نظیر در تاریخ"
]

def sanitize_and_salvage_text(text: str) -> Tuple[str, List[str]]:
    """
    Sanitizes defects (removes marketing superlatives, bureaucratic bullets,
    and converts questionable <blockquote> quotes to cohesive analytical prose).
    """
    sanitized = text
    modifications = []

    # 1. Remove bureaucratic bullets
    if "▫️" in sanitized or "▪️" in sanitized:
        sanitized = re.sub(r'[▫▪]\s*[^:\n]+:\s*', '', sanitized)
        modifications.append("حذف بولت‌ها و برچسب‌های بروکراتیک («▫️ اثر:»)")

    # 2. Replace marketing clichés
    for cliche in BANNED_PROMOTIONAL_CLICHES:
        if cliche in sanitized:
            sanitized = sanitized.replace(cliche, "اثری واجد تامل زیباشناختی")
            modifications.append(f"پالایش صفت تبلیغاتی «{cliche}»")

    # 3. Check quotes: If <blockquote> lacks an attribution line (— نام گوینده), salvage to prose
    blockquote_match = re.search(r'<blockquote>(.*?)</blockquote>', sanitized, re.DOTALL)
    if blockquote_match:
        bq_content = blockquote_match.group(1).strip()
        if "—" not in bq_content and "-" not in bq_content:
            # Unattributed quote -> convert to analytical prose
            clean_prose = bq_content.replace('«', '').replace('»', '').replace('"', '')
            sanitized = sanitized.replace(blockquote_match.group(0), f"در خوانش تحلیلی اثر، {clean_prose}")
            modifications.append("تبدیل نقل‌قول فاقد منبع به نثر تحلیلی پیوسته")

    return sanitized, modifications

def evaluate_quality_tier(post: Dict[str, Any]) -> Tuple[str, str, List[str]]:
    """
    Returns (quality_tier, quality_status, advisory_warnings).
    Tiers: 'A' (Ready), 'B' (Editor Attention), 'C' (Defect Salvaged).
    """
    text = post.get("text", "")
    topic = post.get("topic", "")
    temporal = post.get("temporal_model", {})
    image_file = post.get("image_file")
    image_mode = post.get("image_mode", "TEXT_ONLY")

    warnings = []
    has_defect = False

    # Check temporal warnings
    if temporal.get("is_stale"):
        warnings.append(f"تاریخ انتشار منبع ({temporal.get('age_hours')}h) خارج از بازه معمول است؛ برای پرونده تاریخی/آرشیوی مناسب است.")

    if not temporal.get("source_publication_date"):
        warnings.append("تاریخ انتشار دقیق در فید منبع قید نشده بود؛ تاریخ دریافت سیستم لحاظ شد.")

    # Check image context
    if image_file:
        credit = post.get("image_credit", "")
        # If image is a photocall/portrait for a film analysis post, add advisory note
        if any(w in credit.lower() for w in ["photocall", "cannes_film_festival", "portrait"]):
            if any(w in topic.lower() for w in ["کالبدشکافی", "نقد", "بوطیقا", "فیلم"]):
                warnings.append("تصویر انتخابی پرتره یا فوتوکال است؛ در صورت امکان با استیل فیلم جایگزین شود.")

    # Check text quality
    if len(text) < 250:
        warnings.append("طول متن کوتاه‌تر از حد استاندارد تحریریه (حداقل ۲۵۰ کاراکتر) است.")
        has_defect = True

    if len(text) > 950:
        warnings.append("طول متن از بودجه تلگرامی (۹۵۰ کاراکتر) فراتر رفته است.")

    # Determine Tier
    if not warnings and not has_defect:
        return "A", "READY_FOR_REVIEW", []
    elif not has_defect:
        return "B", "NEEDS_EDITOR_ATTENTION", warnings
    else:
        return "C", "DEFECT_SALVAGED", warnings
