"""The Reel renderer: what each frame says, what it refuses, and a real video that QC accepts."""
import glob
import json
import os
import sys
import tempfile
import unittest

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import render_cards  # noqa: E402
import render_reel  # noqa: E402
from qc import QUEUES, load_queue, reel_problems  # noqa: E402

QUIZ = {"template": "quiz", "label": "ПРОВЕРЬ СЕБЯ", "title": "Say или tell?",
        "sentence": "He ___ me that he was tired.", "options": ["told", "said"],
        "prompt": "Листай → ответ на следующем слайде"}
ANSWER = {"template": "answer", "label": "ОТВЕТ", "title": "Ответ A", "answer": "He told me",
          "why": ["tell всегда с человеком"], "examples": ["He told me that he was tired."]}


def reel(*slides, **extra):
    return dict({"template": "reel", "out": "media/ig/test-reel.mp4", "slides": list(slides)}, **extra)


def photos():
    with open(os.path.join(ROOT, "brand", "photos", "index.json"), encoding="utf-8") as fh:
        return json.load(fh)


def real_photo():
    return next(p["file"] for p in photos() if not p.get("ai_generated"))


class Plan(unittest.TestCase):
    def test_the_first_slide_counts_down_to_the_answer(self):
        shown, cover, countdown = render_reel.plan(reel(QUIZ, ANSWER))
        (first, seconds, field), (last, last_seconds, none) = shown
        self.assertEqual((field, none, countdown), ("prompt", None, "Ответ через"))
        self.assertEqual(first["out"], "media/ig/test-reel.mp4, slide 1")  # where a "too long" error points
        self.assertEqual(seconds, round(render_reel.read_time(QUIZ)))
        self.assertEqual(first["prompt"], "Ответ через %d" % seconds)
        self.assertEqual(cover["prompt"], "Ответ в конце ролика")
        self.assertTrue(render_reel.MIN_READ <= last_seconds <= render_reel.MAX_READ)
        self.assertEqual(dict(last, out=None), dict(ANSWER, out=None))

    def test_a_list_counts_down_on_its_cta_and_the_words_can_change(self):
        lst = {"template": "list", "label": "МОИ УЧЕНИКИ", "title": "Уровень высокий", "items": ["Занимаются"],
               "cta": "Листай → как это по-английски"}
        phrase = {"template": "phrase", "label": "ФРАЗА", "phrase": "Use it or lose it", "meaning": "не используешь, теряешь",
                  "examples": [{"en": "Use it or lose it.", "ru": "Не используешь, теряешь."}]}
        shown, cover, _ = render_reel.plan(reel(lst, phrase, countdown="По-английски через",
                                                cover_prompt="Как это по-английски, в конце"))
        self.assertTrue(shown[0][0]["cta"].startswith("По-английски через "))
        self.assertEqual(cover["cta"], "Как это по-английски, в конце")

    def test_reading_time_follows_the_words_actually_drawn(self):
        photo_quiz = dict(QUIZ, photo=real_photo(), situation="Коллега пишет", bubble="Can you cover?",
                          question="Что ответить?", sentence="слова " * 40)
        self.assertEqual(render_reel.words(photo_quiz), 2 + 3 + 2 + 2)  # the sentence isn't on a photo quiz
        self.assertEqual(render_reel.read_time({"template": "answer", "title": "x " * 200}), render_reel.MAX_READ)
        self.assertEqual(render_reel.read_time({"template": "answer", "title": "x"}), render_reel.MIN_READ)

    def test_what_cannot_go_out_as_a_reel_is_refused(self):
        ai = next(p["file"] for p in photos() if p.get("ai_generated"))
        cases = {
            "no slides to swipe": reel(QUIZ, dict(ANSWER, why=["Листай дальше"])),
            "AI-made": reel(dict(QUIZ, photo=ai), ANSWER),
            "not in brand/photos/index.json": reel(dict(QUIZ, photo="brand/photos/nowhere.jpg"), ANSWER),
            "1-4 slides": reel(*[ANSWER] * 5),
            "an .mp4 path": dict(reel(QUIZ, ANSWER), out="media/ig/test.jpg"),
            "no card template": reel({"template": "avatar", "text": "Hi"}),
        }
        for expected, spec in cases.items():
            with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, expected):
                render_reel.plan(spec)

    def test_every_reel_in_the_repo_plans_and_its_files_exist(self):
        specs = []
        for path in sorted(glob.glob(os.path.join(ROOT, "content", "cards", "*.json"))):
            with open(path, encoding="utf-8") as fh:
                specs.extend(s for s in json.load(fh) if s["template"] == "reel")
        posts = {p.get("video"): p for p in load_queue(QUEUES["instagram"]) if p.get("video")}
        for spec in specs:
            with self.subTest(out=spec["out"]):
                render_reel.plan(spec)
                self.assertEqual(render_cards.missing_glyphs(spec, render_cards.load_brand()), [])
                self.assertTrue(os.path.exists(os.path.join(ROOT, spec["out"])))
                self.assertTrue(os.path.exists(os.path.join(ROOT, render_reel.cover_path(spec["out"]))))
        for video, post in posts.items():
            self.assertIn(video, [s["out"] for s in specs], "%s has no reel spec in content/cards" % post["id"])
            self.assertEqual(post["cover"], render_reel.cover_path(video))


class Frames(unittest.TestCase):
    def test_a_text_layer_over_any_background_is_the_card_drawn_on_it(self):
        brand = render_cards.load_brand()
        photo = real_photo()
        for spec in (dict(QUIZ, out="quiz"), dict(ANSWER, photo=photo, out="answer")):
            with self.subTest(template=spec["template"], photo=bool(spec.get("photo"))):
                card = render_reel.FlatCard(brand, None, spec["template"], spec.get("photo"))
                card.flat = (90, 140, 60)
                render_cards.TEMPLATES[spec["template"]](card, spec)
                direct = card.img.reduce(render_cards.SCALE)
                layer = render_reel.text_layer(spec, brand)
                base = Image.new("RGB", (render_reel.W, render_reel.H), (90, 140, 60))
                box = (0, render_reel.BOX_TOP, 1080, render_reel.BOX_TOP + 1350)
                lifted = layer.over(base).crop(box)
                worst = max(hi for _, hi in ImageChops.difference(direct, lifted).getextrema())
                self.assertLessEqual(worst, 3)
                # nothing of the card spills outside its box
                self.assertEqual(layer.matte.crop((0, 0, 1080, render_reel.BOX_TOP)).getextrema(), (0, 0))

    def test_the_background_fills_the_frame_and_darkens_under_the_apps_buttons(self):
        brand = render_cards.load_brand()
        photo = dict(ANSWER, photo=real_photo())
        still = render_reel.Backdrop(photo, brand).still.convert("L")
        self.assertEqual(still.size, (render_reel.W, render_reel.H))

        def light(y):
            return sum(still.crop((0, y, render_reel.W, y + 40)).getdata()) / (render_reel.W * 40)
        self.assertLess(light(render_reel.H - 60), light(render_reel.BOX_TOP + 600))
        self.assertLess(light(10), light(render_reel.BOX_TOP + 600))
        gradient = render_reel.Backdrop(QUIZ, brand)
        self.assertIs(gradient.at(1.05), gradient.still)  # a gradient doesn't move


@unittest.skipUnless(render_reel.find_ffmpeg(), "needs ffmpeg")
class Video(unittest.TestCase):
    def test_a_reel_renders_to_a_video_qc_accepts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "reel.mp4")
            render_cards.render(dict(reel(QUIZ, ANSWER), out=out))
            post = {"video": "reel.mp4", "cover": "reel-cover.jpg", "alt_text": ["question", "answer"]}
            self.assertEqual(reel_problems(post, root=tmp), [])
            shown, _, _ = render_reel.plan(reel(QUIZ, ANSWER))
            planned = sum(s for _, s, _ in shown) + render_reel.FADE
            from qc import mp4_info
            self.assertAlmostEqual(mp4_info(out)["seconds"], planned, delta=0.2)


if __name__ == "__main__":
    unittest.main()
