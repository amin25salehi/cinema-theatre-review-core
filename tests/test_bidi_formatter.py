"""
Unit Tests for BiDi (Bidirectional Text) Isolation in Editorial Message Formatter.
Tests:
1. RTL base paragraph anchoring with Unicode RLM (U+200F).
2. LTR isolate wrapping (U+2066 ... U+2069) for English film titles, names, publications, and acronyms.
3. Natural positioning of Persian quotation marks « » outside isolates.
4. Protection of source names in hyperlinks, including parenthetical descriptions (e.g. 'POV Magazine (Point of View Documentary)').
5. Protection of Latin hashtags (e.g. '#POV_Magazine') from rightward '#' sign flipping.
6. Preservation of numbers, dates, and Persian punctuation without character reversal.
7. Strict idempotency: formatting already formatted text does not produce nested or duplicate isolates.
"""

import unittest
from editorial.message_formatter import apply_bidi_isolation, format_editorial_caption, RLM, LRI, PDI


class TestBiDiFormatter(unittest.TestCase):

    def test_persian_paragraph_anchored_with_rlm(self):
        text = "سینمای سهراب شهیدثالث در دوران تبعید آلمان شکل گرفت."
        isolated = apply_bidi_isolation(text)
        self.assertTrue(isolated.startswith(RLM))

    def test_english_title_isolated_inside_persian_quotes(self):
        text = "فیلم «Il Paese: The Village Review – The Tomatoes Are Always Redder» در جشنواره به نمایش درآمد."
        isolated = apply_bidi_isolation(text)
        expected_chunk = f"«{LRI}Il Paese: The Village Review – The Tomatoes Are Always Redder{PDI}»"
        self.assertIn(expected_chunk, isolated)
        # Quotes must be outside the isolate
        self.assertNotIn(f"{LRI}«", isolated)
        self.assertNotIn(f"»{PDI}", isolated)

    def test_hyperlink_source_with_parentheses_isolated(self):
        link_line = "🔗 <a href='https://povmagazine.com'>مشاهده نقد کامل در پایگاه رسمی POV Magazine (Point of View Documentary)</a>"
        isolated = apply_bidi_isolation(link_line)
        expected_source = f"{LRI}POV Magazine (Point of View Documentary){PDI}"
        self.assertIn(expected_source, isolated)
        # HTML tag integrity preserved
        self.assertIn("<a href='https://povmagazine.com'>", isolated)
        self.assertIn("</a>", isolated)

    def test_mixed_hashtags_isolated(self):
        hashtags = "#سینما_مستند #POV_Magazine #سینمای_ایران #Four_Daughters"
        isolated = apply_bidi_isolation(hashtags)
        self.assertIn(f"{LRI}#POV_Magazine{PDI}", isolated)
        self.assertIn(f"{LRI}#Four_Daughters{PDI}", isolated)
        self.assertIn("#سینما_مستند", isolated)
        self.assertIn("#سینمای_ایران", isolated)

    def test_english_acronyms_and_resolutions(self):
        text = "نسخه ۴K و اسکن 4K با نظارت DFF و Arsenal برلین آماده شد."
        isolated = apply_bidi_isolation(text)
        self.assertIn(f"{LRI}4K{PDI}", isolated)
        self.assertIn(f"{LRI}DFF{PDI}", isolated)
        self.assertIn(f"{LRI}Arsenal{PDI}", isolated)

    def test_strict_idempotency(self):
        sample = (
            "<b>مرمت ۴K آثار سهراب شهیدثالث در DFF فرانکفورت و آرسنال</b>\n\n"
            "تحلیل جامع فیلم «Il Paese: The Village Review – The Tomatoes Are Always Redder» منتشر شد.\n\n"
            "🔗 <a href='https://povmagazine.com'>مشاهده در پایگاه رسمی POV Magazine (Point of View Documentary)</a>\n\n"
            "#سینما_مستند #POV_Magazine"
        )
        first_pass = apply_bidi_isolation(sample)
        second_pass = apply_bidi_isolation(first_pass)
        third_pass = apply_bidi_isolation(second_pass)
        self.assertEqual(first_pass, second_pass)
        self.assertEqual(second_pass, third_pass)
        # Ensure no nested LRI marks
        self.assertNotIn(f"{LRI}{LRI}", third_pass)
        self.assertNotIn(f"{PDI}{PDI}", third_pass)


if __name__ == "__main__":
    unittest.main()
