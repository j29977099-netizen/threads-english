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
                specs.extend(s for s in json.load(fh) if s["template"] != "reel")  # tests/test_render_reel.py
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

    def test_a_chat_card_draws_messages_and_a_typing_bubble_and_refuses_too_much(self):
        chat = {"template": "chat", "label": "А ДАЛЬШЕ ЧТО?", "question": "Что ответить?",
                "prompt": "Листай → три способа на следующем слайде",  # shrinks to fit the card's width
                "messages": [{"from": "them", "name": "Коллега", "text": "Can you cover my shift on Saturday?"},
                             {"from": "me", "typing": True}]}
        self.render(chat)
        with self.assertRaisesRegex(ValueError, "too long"):
            self.render(dict(chat, messages=[{"from": "them", "text": "Can you cover my shift on Saturday? " * 4}] * 6))
        with self.assertRaisesRegex(ValueError, "too long for one line"):
            self.render(dict(chat, prompt="Листай → три способа на следующем слайде, их там правда три"))

    def test_the_same_spec_renders_the_same_file(self):
        with open(self.render(QUIZ, "a.jpg"), "rb") as a, open(self.render(QUIZ, "b.jpg"), "rb") as b:
            self.assertEqual(a.read(), b.read())

    # ----- photo cards (2026-11-17) -----

    def photos(self):
        with open(os.path.join(ROOT, "brand", "photos", "index.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_the_photo_index_lists_files_that_exist_and_every_photo_a_spec_uses(self):
        index = self.photos()
        self.assertTrue(index)
        listed = {entry["file"] for entry in index}
        for entry in index:
            self.assertTrue(os.path.exists(os.path.join(ROOT, entry["file"])), entry["file"])
            self.assertTrue(entry.get("scene") and entry.get("tags"), entry["file"])
        for path in sorted(glob.glob(os.path.join(ROOT, "content", "cards", "*.json"))):
            with open(path, encoding="utf-8") as fh:
                for spec in json.load(fh):
                    for card in spec.get("slides") or [spec]:  # a reel's slides are cards too
                        if card.get("photo"):
                            self.assertIn(card["photo"], listed, spec["out"])

    def test_every_template_draws_on_a_photo(self):
        photo = self.photos()[0]["file"]
        specs = [
            dict(QUIZ, situation="Друг зовёт на ужин, а ты отвечаешь", bubble="Can I take\na rain check?"),
            {"template": "answer", "label": "ОТВЕТ", "title": "Ответ A", "answer": "Давай перенесём на другой раз",
             "why": ["rain check это вежливый отказ"], "examples": ["I'll take a rain check", "! I take rain check"]},
            {"template": "chat", "label": "А ДАЛЬШЕ ЧТО?", "question": "Что ответить?",
             "messages": [{"from": "them", "text": "How was your weekend?"}, {"from": "me", "typing": True}]},
            {"template": "list", "label": "СОВЕТ", "title": "Два способа", "items": ["Pretty good!", "Relaxing."]},
            {"template": "phrase", "label": "ФРАЗА", "phrase": "I'm good", "meaning": "нет, спасибо",
             "examples": [{"en": "I'm good, thanks.", "ru": "Нет, спасибо."}]},
        ]
        for spec in specs:
            with self.subTest(template=spec["template"]):
                plain = Image.open(self.render(spec, "plain.jpg")).convert("RGB")
                shot = Image.open(self.render(dict(spec, photo=photo), "photo.jpg")).convert("RGB")
                self.assertEqual(shot.size, tuple(self.brand["size"]))
                # the middle of the card shows the photo, not the theme's gradient
                self.assertNotEqual(plain.getpixel((540, 1250)), shot.getpixel((540, 1250)))

    def test_a_photo_that_does_not_exist_is_refused(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.render(dict(QUIZ, photo="brand/photos/nowhere.jpg"))

    def test_a_photo_quiz_with_a_phrase_too_long_for_its_bubble_is_refused(self):
        photo = self.photos()[0]["file"]
        with self.assertRaisesRegex(ValueError, "too long"):
            self.render(dict(QUIZ, photo=photo, bubble="Can I take a rain check on that dinner invitation? " * 6))


if __name__ == "__main__":
    unittest.main()
