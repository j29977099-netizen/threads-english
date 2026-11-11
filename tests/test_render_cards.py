"""The card renderer: every spec in the repo still renders, and unusable cards are refused."""
import glob
import json
import os
import sys
import tempfile
import unittest

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import render_cards  # noqa: E402

QUIZ = {"template": "quiz", "label": "ПРОВЕРЬ СЕБЯ", "title": "Present Perfect\nили Past Simple?",
        "sentence": "I ___ to New York three times.", "options": ["have been", "was", "am"],
        "prompt": "Листай → ответ на следующем слайде"}


class RenderCards(unittest.TestCase):
    def setUp(self):
        self.brand = render_cards.load_brand()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def render(self, spec, name="card.jpg"):
        return render_cards.render(dict(spec, out=os.path.join(self.tmp.name, name)), self.brand)

    def test_every_spec_in_the_repo_renders_at_card_size(self):
        specs = []
        for path in sorted(glob.glob(os.path.join(ROOT, "content", "cards", "*.json"))):
            with open(path, encoding="utf-8") as fh:
                specs.extend(json.load(fh))
        self.assertTrue(specs)
        for spec in specs:
            with self.subTest(out=spec["out"]):
                path = self.render(spec, os.path.basename(spec["out"]))
                with Image.open(path) as img:
                    self.assertEqual(img.size, tuple(spec.get("size") or self.brand["size"]))
                    self.assertEqual(img.format, "JPEG" if path.endswith(".jpg") else "PNG")

    def test_every_template_has_a_colour_theme_and_every_font_file_exists(self):
        for name in render_cards.TEMPLATES:
            if name != "avatar":
                self.assertIn(name, self.brand["themes"])
        for entry in self.brand["fonts"].values():
            self.assertTrue(os.path.exists(os.path.join(ROOT, render_cards.font_file(entry))))

    def test_a_character_only_the_fallback_font_has_is_drawn_not_refused(self):
        self.assertEqual(render_cards.missing_glyphs({"ipa": "[ˈjuːst tə] →"}, self.brand), [])
        self.render(dict(QUIZ, sentence="[ˈjuːst tə] ___ →"))

    def test_a_character_no_font_has_is_refused(self):
        with self.assertRaisesRegex(ValueError, "no font has a glyph"):
            self.render(dict(QUIZ, title="Квиз 🧩"))

    def test_a_quiz_too_long_for_one_card_is_refused(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            self.render(dict(QUIZ, sentence="I have been to New York three times. " * 12))
        with self.assertRaisesRegex(ValueError, "too long for one line"):
            self.render(dict(QUIZ, options=["have been living here for a very long time already, you know"] * 3))

    def test_the_same_spec_renders_the_same_file(self):
        with open(self.render(QUIZ, "a.jpg"), "rb") as a, open(self.render(QUIZ, "b.jpg"), "rb") as b:
            self.assertEqual(a.read(), b.read())


if __name__ == "__main__":
    unittest.main()
