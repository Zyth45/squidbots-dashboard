import unittest

from mind import filters, prompt


class TypographyTests(unittest.TestCase):
    def test_em_and_en_dashes_become_commas(self):
        self.assertEqual(filters.clean("wait \u2014 what? no\u2013way"), "wait, what? no, way")

    def test_curly_quotes_and_ellipsis_are_typed_plain(self):
        self.assertEqual(filters.clean("it\u2019s \u201Cfine\u201D\u2026"), 'it\'s "fine"...')

    def test_a_dash_before_punctuation_does_not_leave_a_stray_comma(self):
        self.assertEqual(filters.clean("ok \u2014."), "ok.")

    def test_plain_hyphens_are_left_alone(self):
        self.assertEqual(filters.clean("half-price, 5-10 gold"), "half-price, 5-10 gold")

    def test_every_persona_prompt_forbids_dashes(self):
        self.assertIn("em dashes", prompt.persona_block({"name": "Brick"}, ""))
        self.assertIn("em dashes", prompt.persona_block({"name": "Brick"}, "", actions=False))


if __name__ == "__main__":
    unittest.main()
