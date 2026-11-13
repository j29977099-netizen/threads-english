"""How the text looks: the queue check refuses posts that read as generated (STRATEGY.md §2)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from qc import STYLE_FROM, check_queue, style_problems  # noqa: E402

TYPED = """🗽 Идиома дня: hit the sack

Дословно получается ударить мешок
А значит это пойти спать

I'm exhausted. I'm going to hit the sack
Сил больше нет, пойду спать

Во сколько ты обычно hit the sack?"""

GENERATED = """🗽 Идиома дня: hit the sack

Дословно — «ударить мешок».
На самом деле — пойти спать, завалиться спать.

✔️ I'm exhausted. I'm going to hit the sack.
— Сил больше нет. Пойду спать.

Обе фразы разговорные: с друзьями — да; в рабочем письме — нет.

Во сколько ты обычно ложишься? Напиши: «я ложусь в…»."""


def lesson(text, when):
    return {"id": "2026-11-20-p2-sample", "kind": "lesson", "publish_at": when, "text": text,
            "topic_tag": "Английский язык"}


class StyleTest(unittest.TestCase):
    def test_a_post_typed_like_a_person_passes(self):
        self.assertEqual(style_problems(TYPED), [])

    def test_each_generated_habit_is_named(self):
        problems = " | ".join(style_problems(GENERATED))
        for expected in ("quotation marks", "long dashes", "colons", "semicolon", "last line ends with a period"):
            self.assertIn(expected, problems)

    def test_a_period_on_most_lines_is_refused_but_one_is_fine(self):
        self.assertEqual(style_problems("Одна мысль.\nВторая без точки\nТретья\nЧетвёртая"), [])
        self.assertTrue(any("lines end with a period" in p
                            for p in style_problems("Одна мысль.\nВторая.\nТретья.\nЧетвёртая")))

    def test_english_punctuation_and_times_are_not_counted(self):
        self.assertEqual(style_problems("I can't pick you up at 3:00, it's a five-minute walk\nА ты что скажешь?"), [])
        self.assertEqual(style_problems("Бывает раз в 2–3 года"), [])

    def test_replies_are_held_tighter_than_posts(self):
        one_dash = "Так говорят в Штатах — и только так"
        self.assertEqual(style_problems(one_dash), [])
        self.assertTrue(style_problems(one_dash, kind="reply"))
        self.assertTrue(style_problems("Здравствуйте, это верно", kind="reply"))
        self.assertEqual(style_problems("Здравствуйте, это верно", kind="dm"), [])
        self.assertTrue(style_problems("верно 🙌🔥👏", kind="dm"))
        self.assertEqual(style_problems("да, так и говорят)", kind="reply"), [])

    def test_the_queue_check_applies_it_only_from_the_day_the_rule_began(self):
        self.assertEqual(check_queue([lesson(GENERATED, "2026-11-13T16:00:00Z")]), [])
        errors = check_queue([lesson(GENERATED, STYLE_FROM)])
        self.assertTrue(errors and all(e.startswith("2026-11-20-p2-sample: ") for e in errors))
        self.assertEqual(check_queue([lesson(TYPED, STYLE_FROM)]), [])


if __name__ == "__main__":
    unittest.main()
