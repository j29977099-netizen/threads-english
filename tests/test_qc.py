"""What the queue check refuses besides broken fields: posts that read as generated (STRATEGY.md §2)
and posts that say more about the teacher's students than the teacher has told (strategy/students.json)."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from qc import (STYLE_FROM, STUDENTS_PATH, check_post, check_queue, load_students,  # noqa: E402
                student_problems, style_problems)

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


GROUPS = {
    "usa": {"facts": ["A few students relocated to the USA.", "They need English to live there and for their business."]},
    "dubai": {"facts": ["A few students relocated to Dubai.", "Together with the teacher for about 5 years."]},
}

DUBAI = """🎓 Учить язык just for the fun of it

С несколькими учениками мы занимаемся уже около пяти лет
Они переехали в Дубай
Учат не потому, что надо, а потому что нравится

А ты что делаешь just for fun?"""


def student_post(text, topic="students: dubai", **extra):
    post = {"id": "2026-12-09-p2-students-sample", "kind": "lesson", "publish_at": "2026-12-09T16:00:00Z",
            "topic": topic, "topic_tag": "Английский язык", "text": text}
    post.update(extra)
    return post


class StudentPostTest(unittest.TestCase):
    """A post about the teacher's students may say only what the teacher has told."""

    def problems(self, text, topic="students: dubai"):
        return " | ".join(student_problems(student_post(text, topic), GROUPS))

    def test_a_post_inside_the_facts_passes(self):
        self.assertEqual(student_problems(student_post(DUBAI), GROUPS), [])
        self.assertEqual(student_problems(student_post(DUBAI.replace("пяти", "5")), GROUPS), [])

    def test_a_post_that_is_not_about_students_is_left_alone(self):
        plain = student_post("📌 Выражение дня: run late\n\nI've lived here for 3 years", topic="run late")
        self.assertEqual(student_problems(plain, GROUPS), [])
        # ... and needs no facts file at all
        self.assertEqual(student_problems(plain, path=os.path.join(ROOT, "no-such-file.json")), [])
        school = student_post("pupil - ученик в школе\nstudent - студент в колледже", topic="pupil vs student")
        self.assertEqual(student_problems(school, GROUPS), [])

    def test_speaking_of_my_students_needs_the_students_topic(self):
        for text in ("Мои ученики часто путают say и tell", "У моих учеников причины разные", DUBAI):
            self.assertIn("students: <group>", self.problems(text, topic="why people learn"))

    def test_the_group_has_to_be_one_the_teacher_told_us_about(self):
        self.assertIn("unknown group", self.problems(DUBAI, topic="students: germany"))
        self.assertIn("dubai", self.problems(DUBAI, topic="students: germany"))
        self.assertEqual(self.problems(DUBAI, topic="students: all"), "")

    def test_a_number_the_facts_do_not_give_is_refused(self):
        self.assertIn("number 3", self.problems(DUBAI + "\nЗа 3 месяца заговорили"))
        self.assertIn("number 5", self.problems(DUBAI.replace("пяти", "5"), topic="students: usa"))
        self.assertIn("number 2", self.problems(DUBAI + "\nУровень уже B2", topic="students: all"))

    def test_a_quote_is_refused(self):
        self.assertIn("quotation marks", self.problems(DUBAI + "\nГоворят: «это мой отдых»"))
        self.assertIn("quotation marks", self.problems(DUBAI + '\nГоворят "это мой отдых"'))

    def test_one_persons_story_is_refused(self):
        for line in ("Одна моя ученица открыла в Дубае кафе", "У меня есть ученик из Дубая",
                     "С этим студентом мы занимаемся давно"):
            self.assertIn("one student", self.problems(DUBAI + "\n" + line), line)
        self.assertEqual(self.problems(DUBAI + "\nУ кого-то из учеников это хобби, а ученицы шутят про это"), "")

    def test_a_missing_or_broken_facts_file_fails_the_post_not_the_run(self):
        self.assertIn("students.json", " ".join(
            student_problems(student_post(DUBAI), path=os.path.join(ROOT, "no-such-file.json"))))

    def test_the_publisher_check_refuses_it_on_both_platforms(self):
        made_up = student_post("🎓 Одна моя ученица за 3 месяца дошла до C1")
        self.assertTrue(any("one student" in p for p in check_post(made_up)))
        instagram = dict(made_up, id="ig-2026-12-09-students-sample", images=[], alt_text=[])
        del instagram["topic_tag"]
        self.assertTrue(any("one student" in p for p in check_post(instagram, platform="instagram")))
        self.assertTrue(any("one student" in e for e in check_queue([made_up])))

    def test_the_facts_file_is_well_formed(self):
        groups = load_students()
        self.assertTrue(groups)
        for key, group in groups.items():
            self.assertRegex(key, r"^[a-z][a-z-]*$")
            self.assertNotEqual(key, "all")
            self.assertTrue(group["facts"] and all(isinstance(f, str) and f.strip() for f in group["facts"]), key)
        with open(STUDENTS_PATH, encoding="utf-8") as fh:
            self.assertIn("note", json.load(fh))


if __name__ == "__main__":
    unittest.main()
