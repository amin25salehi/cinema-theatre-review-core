"""
Automated Unit Tests for Editorial Diversity, Archetypes, Anti-Cliché, and Temporal Disambiguation.
Validates:
1. Classification into all 7 editorial archetypes.
2. Complete detection and rejection of hyperbolic marketing clichés.
3. Temporal disambiguation of vintage works (<2015) with [مرور تاریخی / آرشیو].
4. Sentence starter Jaccard structural similarity computation.
"""

import pytest
from editorial.editorial_diversity_engine import (
    EditorialArchetype,
    detect_editorial_archetype,
    validate_editorial_quality,
    sanitize_and_disambiguate_temporality,
    compute_structural_similarity,
    BANNED_EDITORIAL_CLICHES,
    ARCHETYPE_HEADERS
)

def test_seven_archetypes_exist():
    assert len(EditorialArchetype) == 7
    assert EditorialArchetype.ANALYTICAL_ESSAY == "analytical_essay"
    assert EditorialArchetype.CRITICAL_SPOTLIGHT == "critical_spotlight"
    assert EditorialArchetype.FESTIVAL_DISPATCH == "festival_dispatch"
    assert EditorialArchetype.HISTORICAL_RETROSPECTIVE == "historical_retrospective"
    assert EditorialArchetype.STAGE_CHRONICLE == "stage_chronicle"
    assert EditorialArchetype.CRITICAL_DIALOGUE == "critical_dialogue"
    assert EditorialArchetype.MONOGRAPH_THEORY == "monograph_theory"

def test_archetype_detection():
    # Monograph theory
    assert detect_editorial_archetype("معرفی کتاب جدید در نظریه فیلم و رساله سینماتوگراف") == EditorialArchetype.MONOGRAPH_THEORY
    # Stage chronicle
    assert detect_editorial_archetype("دراماتورژی صحنه و تئاتر آوینیون در آثار کاستلوچی") == EditorialArchetype.STAGE_CHRONICLE
    # Critical dialogue
    assert detect_editorial_archetype("مناظره انتقادی؛ تقابل خوانش‌ها و دوئل فرم") == EditorialArchetype.CRITICAL_DIALOGUE
    # Festival dispatch
    assert detect_editorial_archetype("گزارش زنده از جشنواره کن و نخل طلای فیلمسازان") == EditorialArchetype.FESTIVAL_DISPATCH
    # Historical retrospective
    assert detect_editorial_archetype("مرمت نگاتیوهای دهه ۱۹۶۰ و آرشیو سینمای کلاسیک") == EditorialArchetype.HISTORICAL_RETROSPECTIVE
    # Analytical essay
    assert detect_editorial_archetype("بوطیقا و زیباشناسی پلان و تدوین در سینمای مدرن") == EditorialArchetype.ANALYTICAL_ESSAY

def test_hyperbolic_cliche_rejection():
    # Clean text (sufficient length and valid link)
    clean_text = (
        "کالبدشکافی ساختار روایی در سینمای اصغر فرهادی. "
        "دوربین با ثبت جزئیات رفتاری طبقه متوسط، تنش‌های اخلاقی را بدون قضاوت به نمایش می‌گذارد و بحران اعتماد را کالبدشکافی می‌کند. "
        "روابط انسانی در بستر یک جامعه در حال گذار، پیچیدگی‌های قضاوت اخلاقی را نمایان می‌سازد. "
        "🔗 <a href='https://example.com'>منبع استناد و تحلیل</a>"
    )
    is_valid, violations = validate_editorial_quality(clean_text)
    assert is_valid, f"Violations: {violations}"
    assert len(violations) == 0

    # Text containing banned marketing clichés
    dirty_text = (
        "این اثر یک شاهکاری بی‌بدیل و اثری درخشان است که سفری شگفت‌انگیز را برای مخاطب رقم می‌زند. "
        "🔗 <a href='https://example.com'>لینک</a>"
    )
    is_valid, violations = validate_editorial_quality(dirty_text)
    assert not is_valid
    assert any("شاهکاری بی‌بدیل" in v for v in violations)
    assert any("اثری درخشان" in v for v in violations)

def test_temporal_disambiguation():
    # Contemporary film (2024 festival winner)
    c_topic, c_text = sanitize_and_disambiguate_temporality(
        topic="«دانه انجیر معابد» و بوطیقای مقاومت",
        text="تحلیل فیلم محمد رسول‌اف در فستیوال کن ۲۰۲۴"
    )
    assert "[مرور تاریخی" not in c_topic
    assert "#مرور_تاریخی" not in c_text

    # Classic film with active 4K restoration hook (Active Cultural News)
    r_topic, r_text = sanitize_and_disambiguate_temporality(
        topic="مرمت ۴K «شطرنج باد» محمدرضا اصلانی در کن کلاسیک",
        text="رستاخیز نگاتیوهای اصلانی با همکاری بنیاد فیلم اسکورسیزی"
    )
    assert "[مرور تاریخی" not in r_topic  # Active cultural event hook protects it

    # Pure historical retrospective with NO active event hook
    h_topic, h_text = sanitize_and_disambiguate_temporality(
        topic="بازخوانی سینمای دهه ۱۹۵۰ روبر برسون و بوطیقای مدل",
        text="پرونده تاریخی پیرامون یادداشت‌های سینماتوگراف"
    )
    assert "[مرور تاریخی / آرشیو]" in h_topic
    assert "#مرور_تاریخی" in h_text

def test_structural_similarity():
    text_a = (
        "🎬 کالبدشکافی اثر اول\n"
        "این فیلم در سال ۲۰۲۳ ساخته شده است.\n"
        "کارگردان با بهره‌گیری از پلان‌های ثابت حقیقت را بازنمایی می‌کند."
    )
    # Identical structure
    text_b = (
        "🎬 کالبدشکافی اثر اول\n"
        "این فیلم در سال ۲۰۲۳ ساخته شده است.\n"
        "کارگردان با بهره‌گیری از پلان‌های متحرک تنش را بازنمایی می‌کند."
    )
    sim = compute_structural_similarity(text_a, text_b)
    assert sim > 0.4  # High structural similarity

    # Diverse structure
    text_c = (
        "🎭 دراماتورژی صحنه معاصر\n"
        "بر صحنه سالن تئاتر شوبونه، بازیگران از هرگونه اغراق حسی پرهیز می‌کنند.\n"
        "صداهای زنده محیطی فضای دراماتیک را شکل می‌دهند."
    )
    sim_diverse = compute_structural_similarity(text_a, text_c)
    assert sim_diverse < 0.2
