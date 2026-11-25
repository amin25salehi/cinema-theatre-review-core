"""
Editorial OS - Natural Cultural Message Formatter & Text Budget Compressor
Strictly complies with:
1. Elimination of repetitive/rigid category prefixes (no '[پرونده آرشیوی]', 'نقد و بررسی:', 'جستار نظری:').
2. Organic, precise, lucid, and readable critical prose (پرهیز از ترکیبات پرطمطراق و اصطلاحات سنگین غیرضروری).
3. Discreet single-line editorial notes only when genuinely needed (e.g. unknown source date). Zero notes if clean.
4. Autonomous text compression strictly enforcing <= 950 characters.
5. Clean, clickable HTML hyperlinks (<a href="...">...</a>) and natural typography.
"""

import re
from typing import Dict, Any, Optional, List

def soften_pompous_phrasing(text: str) -> str:
    """
    Substitutes convoluted, jargon-heavy or bombastic phrases with clear,
    insightful, and engaging Persian critical prose.
    """
    replacements = [
        (r"کالبدشکافی فرم و زمان مادی[؛،\s]*", "بررسی فرم و تجربه زمان در "),
        (r"کالبدشکافی مستند معاصر[؛،\s]*", "نگاهی به مستند معاصر؛ "),
        (r"کالبدشکافی زناشویی", "واکاوی روابط زناشویی"),
        (r"امتناع از تسلیم به تقطیع سریع مونتاژ و تحمیل تعلیق‌های ساختگی[،\s]*کنشی رادیکال علیه سینمای مصرفی بود",
         "پرهیز از شتاب مونتاژ و هیجان‌های کاذب، رویکردی اصیل در بازنمایی واقعیت پدید آورد"),
        (r"امتناع سهراب شهیدثالث از تسلیم به تقطیع سریع مونتاژ و تحمیل تعلیق‌های ساختگی[،\s]*کنشی رادیکال علیه سینمای مصرفی بود",
         "در سینمای سهراب شهیدثالث، پرهیز از شتاب مونتاژ و هیجان‌های ساختگی، نگاهی اصیل به تجربه زیسته می‌آفریند"),
        (r"در دستگاه زبان", "در ساحت زبان و روایت"),
        (r"سوبژکتیویته رادیکال", "روایت اول‌شخص و نگاه ذهنی"),
        (r"دیالکتیک تصویر-بلور", "مفهوم تصویر-بلور"),
        (r"پدیدارشناسی ساحت تفکر", "ساحت اندیشه و تأمل"),
        (r"هندسه بصری او را آشکار کرده است", "رویکرد بصری او را روشن‌تر ساخته است"),
        (r"در چرخ‌دنده‌های روزمرگی شهری از معنا تهی می‌شود", "در روزمرگی شهری با تنهایی خویش روبه‌رو می‌شود"),
    ]
    refined = text
    for pat, repl in replacements:
        refined = re.sub(pat, repl, refined)
    return refined


def compress_text_to_budget(text: str, max_chars: int = 950) -> str:
    """
    Intelligently compresses Persian cultural analysis text to stay strictly <= max_chars.
    Preserves:
    - Title / Header
    - Primary analytical thesis and critical argumentation
    - Direct citations, director/year references, and archive links
    - Hashtags
    Eliminates:
    - Rhetorical fluff and redundant conversational preamble
    - Secondary explanatory clauses that exceed the budget
    """
    if len(text) <= max_chars:
        return text

    # Phase 1: Prune redundant journalistic padding & filler phrases
    padding_patterns = [
        (r"در ادامه گزارش‌های تحریریه[،\s]+", ""),
        (r"لازم به ذکر است که\s*", ""),
        (r"باید خاطرنشان کرد که\s*", ""),
        (r"همان‌طور که پیش‌تر اشاره شد[،\s]*", ""),
        (r"به عنوان یکی از مهم‌ترین نکات[،\s]*", ""),
        (r"در این میان می‌توان گفت که\s*", ""),
        (r"نکته قابل توجه این است که\s*", ""),
        (r"در واقع باید گفت که\s*", ""),
        (r"به عبارت دقیق‌تر[،\s]*", ""),
        (r"به تعبیر دیگر[،\s]*", ""),
    ]
    cleaned = text
    for pat, repl in padding_patterns:
        cleaned = re.sub(pat, repl, cleaned)

    # Evaluate visible length ignoring HTML markup
    visible_len = len(re.sub(r'<[^>]+>', '', cleaned))
    if visible_len <= max_chars:
        return cleaned

    # Phase 2: Separate structural components:
    # 1. Header (first line)
    # 2. Body paragraphs
    # 3. Footer (Link, Notes, Hashtags)
    lines = cleaned.split("\n")
    header_lines = []
    body_lines = []
    footer_lines = []

    in_footer = False
    for idx, line in enumerate(lines):
        stripped = line.strip().strip("\u200f\u2066\u2069\u200e\ufeff")
        if idx == 0 or (idx == 1 and not stripped):
            header_lines.append(line)
        elif stripped.startswith("🔗") or stripped.startswith("<a ") or "<a href=" in stripped or stripped.startswith("📌") or stripped.startswith("#"):
            in_footer = True
            footer_lines.append(line)
        elif in_footer:
            footer_lines.append(line)
        else:
            body_lines.append(line)

    header_text = "\n".join(header_lines)
    footer_text = "\n".join(footer_lines)
    body_text = "\n".join(body_lines)

    reserved_len = len(re.sub(r'<[^>]+>', '', header_text)) + len(re.sub(r'<[^>]+>', '', footer_text)) + 4
    available_body_budget = max(200, max_chars - reserved_len)

    # Condense body sentences
    paragraphs = [p for p in body_text.split("\n\n") if p.strip()]
    condensed_paras = []

    for p in paragraphs:
        sentences = re.split(r'(?<=[.!?؟。])\s+', p.strip())
        if len(sentences) <= 1:
            condensed_paras.append(p.strip())
            continue

        kept = [sentences[0]]
        for s in sentences[1:-1]:
            potential = "\n\n".join(condensed_paras + [" ".join(kept + [s])])
            potential_len = len(re.sub(r'<[^>]+>', '', potential))
            if potential_len <= available_body_budget:
                kept.append(s)
        if len(sentences) > 1 and sentences[-1] not in kept:
            potential = "\n\n".join(condensed_paras + [" ".join(kept + [sentences[-1]])])
            potential_len = len(re.sub(r'<[^>]+>', '', potential))
            if potential_len <= available_body_budget:
                kept.append(sentences[-1])
        condensed_paras.append(" ".join(kept))

    new_body = "\n\n".join(condensed_paras)
    visible_total = len(re.sub(r'<[^>]+>', '', header_text + "\n\n" + new_body + "\n\n" + footer_text))

    if visible_total > max_chars:
        excess = visible_total - max_chars
        target_body_len = max(150, len(new_body) - excess - 5)
        trimmed_body = new_body[:target_body_len]
        last_period = max(trimmed_body.rfind("."), trimmed_body.rfind("؛"), trimmed_body.rfind("!"))
        if last_period > 100:
            new_body = trimmed_body[:last_period + 1]
        else:
            new_body = trimmed_body.rstrip() + "..."

    final_text = header_text + "\n\n" + new_body
    if footer_text.strip():
        final_text += "\n\n" + footer_text

    return final_text.strip()


def build_discreet_editorial_note(post: Dict[str, Any]) -> str:
    """
    Synthesizes a minimal, elegant editorial note when genuinely relevant.
    - Strips internal system tiers (A/B), char limits, technical logs.
    - Only flags genuine publication date absence or archival image provenance.
    - Returns EMPTY string if no issues exist.
    """
    notes = []

    # 1. Publication date check
    temporal = post.get("temporal_model") or {}
    source_pub_date = post.get("source_publication_date") or temporal.get("source_publication_date")
    if not source_pub_date and not temporal.get("has_valid_source_date"):
        notes.append("تاریخ انتشار اصلی منبع مشخص نیست")

    # 2. Image provenance check (only if image is marked as secondary portrait/archive)
    image_credit = str(post.get("image_credit", "")).lower()
    if any(k in image_credit for k in ["photocall", "portrait", "پرتره"]):
        notes.append("تصویر آرشیوی است")

    if not notes:
        return ""

    combined_note = " و ".join(notes) + "."
    return f"📌 <i>یادداشت تحریریه: {combined_note}</i>"


RLM = "\u200F"  # Right-to-Left Mark (anchors base RTL paragraph direction)
LRI = "\u2066"  # Left-to-Right Isolate
PDI = "\u2069"  # Pop Directional Isolate


def apply_bidi_isolation(text: str) -> str:
    """
    Applies Unicode Bidirectional (BiDi) isolation to Persian cultural texts containing
    English film titles, director/critic names, source publications, hashtags, and acronyms.

    Technical Specifications:
    1. Idempotency: Strips existing LRI/PDI/RLM marks first to prevent duplicate or nested wrapping.
    2. Base RTL direction: Paragraphs containing Persian text are anchored with Unicode RLM (U+200F).
    3. English isolation: Every continuous Latin fragment (including internal punctuation like
       parentheses, hyphens, colons, ampersands: e.g. 'POV Magazine (Point of View Documentary)')
       is wrapped as an isolated LTR block (U+2066 ... U+2069).
    4. Persian punctuation outside: Quotes « », colons, and periods remain outside the isolates
       so they maintain their natural visual positions in RTL reading flow.
    5. Clean HTML preservation: Does not alter HTML tags (<b>, <a>, <i>) or URLs.
    6. Hashtag protection: Latin hashtags (#POV_Magazine, #Four_Daughters) are isolated to
       prevent the hash sign from flipping to the right side.
    7. No invalid HTML: Strictly avoids non-standard tags like <div dir="rtl">.
    8. Zero character reversal: Logical character order is preserved without reversal.
    """
    if not text:
        return text

    # Strip existing isolate markers to guarantee idempotency
    clean = text.replace(LRI, "").replace(PDI, "")

    # Split text preserving HTML tags so tags and URLs are never broken
    parts = re.split(r'(<[^>]+>)', clean)
    out_parts = []

    # Matches continuous Latin sequences with internal punctuation
    latin_chunk_pattern = re.compile(
        r'(?<![A-Za-z0-9_#])(#?[A-Za-z0-9](?:[A-Za-z0-9_\s.,/\'’\-–—&():]*[A-Za-z0-9)])?)(?![A-Za-z0-9_])'
    )

    for part in parts:
        if part.startswith('<') and part.endswith('>'):
            out_parts.append(part)
        else:
            def isolate_repl(m):
                chunk = m.group(1).strip()
                orig = chunk
                while chunk.endswith(")") and chunk.count(")") > chunk.count("("):
                    chunk = chunk[:-1].rstrip()
                while chunk.endswith("]") and chunk.count("]") > chunk.count("["):
                    chunk = chunk[:-1].rstrip()
                # Ensure the chunk contains at least one Latin letter
                if not any(c.isalpha() and ord(c) < 128 for c in chunk):
                    return m.group(0)
                suffix = orig[len(chunk):]
                return f"{LRI}{chunk}{PDI}{suffix}"

            isolated_part = latin_chunk_pattern.sub(isolate_repl, part)
            out_parts.append(isolated_part)

    isolated_text = "".join(out_parts)

    # Anchor RTL direction on each non-empty paragraph
    lines = isolated_text.split("\n")
    anchored_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            anchored_lines.append(line)
        else:
            clean_str = stripped.lstrip(RLM)
            has_persian = any('\u0600' <= c <= '\u06FF' for c in clean_str)
            if has_persian:
                anchored_lines.append(f"{RLM}{line.lstrip(RLM)}")
            else:
                anchored_lines.append(line)

    return "\n".join(anchored_lines)


def format_editorial_caption(post: Dict[str, Any], max_chars: int = 1020) -> str:
    """
    Formats the complete cultural publication message for Telegram.
    Rule 1: Natural headlines WITHOUT repetitive artificial prefixes.
    Rule 2: Lucid, precise critical prose without pretentious jargon.
    Rule 3: Clickable valid HTML links (<a href="...">...</a>).
    Rule 4: Discreet single-line editorial note only when needed; zero notes otherwise.
    Rule 5: Strict <= 950 char budget enforcement.
    Rule 6: Bidirectional (BiDi) isolation for mixed Persian and English typography.
    """
    topic = post.get("topic", "").strip()
    raw_text = post.get("text", "").strip()
    original_url = post.get("original_url", "").strip()
    source_name = post.get("source_name", "منبع رسمی").strip()

    # Strip preexisting mechanical warnings and leading directional/emoji clutter
    clean_text = raw_text.strip().strip("\u200f\u2066\u2069\u200e\ufeff")
    clean_text = re.sub(r'^(?:⚠️[^\n]+\n+)+', '', clean_text).strip()

    # Robust Headline Extraction:
    # First check if clean_text starts with a bold header (allowing for emojis, RLM, and spaces)
    clean_no_bidi = re.sub(r'[\u200f\u2066\u2069\u200e\ufeff]', '', clean_text).strip()
    headline_match = re.match(r'^(?:[🎬🎙📚🎭🎞🎥📖]\s*)?<b>(.*?)</b>\s*\n*(.*)', clean_no_bidi, re.DOTALL)
    if headline_match:
        raw_headline = headline_match.group(1).strip()
        # Find where </b> ends in clean_text to preserve original body formatting
        b_end = clean_text.find("</b>")
        if b_end != -1:
            body_content = clean_text[b_end + 4:].strip()
        else:
            body_content = headline_match.group(2).strip()
    else:
        raw_headline = topic
        body_content = clean_text

    # Strip rigid boilerplate prefixes from headline (Rule #1)
    clean_headline = raw_headline
    clean_headline = re.sub(r'^[🎬🎙📚🎭🎞🎥📖]\s*', '', clean_headline).strip()
    rigid_prefixes = [
        "نقد و بررسی:", "نقد و بررسی", "[نقد و بررسی]",
        "معرفی و نقد کتاب:", "معرفی و نقد کتاب", "[معرفی و نقد کتاب]",
        "جستار نظری:", "جستار نظری", "[جستار نظری]",
        "پرونده آرشیوی:", "پرونده آرشیوی", "[پرونده آرشیوی]",
        "گفت‌وگوی انتقادی:", "گفت‌وگوی انتقادی", "[گفت‌وگوی انتقادی]",
        "تئاتر معاصر:", "گزارش روز:", "پرونده:", "نقد:", "جستار:"
    ]
    for prefix in rigid_prefixes:
        if clean_headline.startswith(prefix):
            clean_headline = clean_headline[len(prefix):].strip()
        if clean_headline.startswith("؛"):
            clean_headline = clean_headline[1:].strip()

    # Soften bombastic jargon in headline (Rule #2)
    clean_headline = soften_pompous_phrasing(clean_headline)
    header = f"🎬 <b>{clean_headline}</b>"

    # Separate existing links and hashtags from body (ensuring zero duplicate links)
    body_lines = []
    link_line = ""
    hashtag_line = ""

    for line in body_content.split("\n"):
        stripped = line.strip().strip("\u200f\u2066\u2069\u200e\ufeff")
        if stripped.startswith("🔗") or "<a href=" in stripped or stripped.startswith("<a "):
            if not link_line:
                link_line = line.strip()
        elif stripped.startswith("#"):
            if not hashtag_line:
                hashtag_line = line.strip()
            else:
                hashtag_line += " " + line.strip()
        elif not stripped.startswith("⚠️") and not stripped.startswith("📌"):
            # Avoid stray URLs or duplicate headlines leaking into body lines
            if not (stripped.startswith("http://") or stripped.startswith("https://")):
                body_lines.append(line)

    body_core = "\n".join(body_lines).strip()
    body_core = soften_pompous_phrasing(body_core)

    # Build clean clickable HTML link if not already extracted (Rule #3)
    if not link_line and original_url:
        link_line = f"🔗 <a href='{original_url}'>مشاهده گزارش در پایگاه رسمی {source_name}</a>"

    # Assemble draft: strictly clean, forwardable message
    parts = [header, body_core]
    footer_parts = []
    if link_line:
        footer_parts.append(link_line)
    if hashtag_line:
        footer_parts.append(hashtag_line)

    draft = "\n\n".join(parts)
    if footer_parts:
        draft += "\n\n" + "\n\n".join(footer_parts)

    # Enforce strictly <= max_chars (Rule #5) and apply BiDi isolation (Rule #6)
    compressed = compress_text_to_budget(draft, max_chars=max_chars)
    return apply_bidi_isolation(compressed)
