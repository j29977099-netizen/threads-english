import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import comments  # noqa: E402
from publish import ZernioApi  # noqa: E402
from qc import parse_time  # noqa: E402
from test_publish import FakeResponse, FakeSession  # noqa: E402

QUIZ = {"id": "d1-quiz", "publish_at": "2026-11-09T06:00:00Z", "kind": "quiz", "text": "Quiz text", "answer": "B"}
REVEAL = {"id": "d2-reveal", "publish_at": "2026-11-10T06:15:00Z", "kind": "reveal", "reply_to": "d1-quiz",
          "text": "Reveal text"}
NOW = parse_time("2026-11-09T12:00:00Z")


def comment(cid, text, username="reader", owner=False, created="2026-11-09T10:00:00+0000", replies=()):
    return {"id": cid, "message": text, "createdTime": created, "url": "https://www.threads.com/c/" + cid,
            "from": {"username": username, "isOwner": owner}, "replies": list(replies), "canReply": True}


class FakeInboxApi:
    def __init__(self, posts, threads, instagram_posts=None):
        self.posts = posts
        self.threads = threads
        self.instagram_posts = instagram_posts

    def account(self, platform):
        if platform == "instagram" and self.instagram_posts is None:
            raise comments.ApiError("no active Instagram account is connected in Zernio", code="auth_expired")
        return {"_id": "acc-" + platform}

    def commented_posts(self, account_id, since, platform="threads"):
        self.since = since
        return self.posts if platform == "threads" else self.instagram_posts

    def post_comments(self, post_id, account_id):
        return self.threads.get(post_id, [])


class InboxTest(unittest.TestCase):
    def published(self, *ids):
        events = {"d1-quiz": {"id": "d1-quiz", "media_id": "T1", "permalink": "https://www.threads.com/p/T1"},
                  "d2-reveal": {"id": "d2-reveal", "media_id": "T2"}}
        return {i: events[i] for i in ids}

    def test_new_comments_come_with_quiz_context(self):
        api = FakeInboxApi([{"id": "T1", "commentCount": 3, "content": "Quiz text"}], {"T1": [
            comment("c1", "B!"),
            comment("c2", "mine", owner=True),
            comment("c3", "A?", replies=[comment("c4", "thanks", owner=True)]),
        ]})
        result = comments.inbox(api, [("threads", [QUIZ, REVEAL], self.published("d1-quiz"))], {}, NOW)
        self.assertEqual([c["comment_id"] for c in result["comments"]], ["c1"])
        first = result["comments"][0]
        self.assertEqual((first["queue_id"], first["answer"], first["answer_published"]), ("d1-quiz", "B", False))
        self.assertEqual(api.since, "2026-11-02")

    def test_answer_counts_as_public_once_the_reveal_is_out(self):
        api = FakeInboxApi([{"id": "T1", "commentCount": 1}], {"T1": [comment("c1", "B")]})
        result = comments.inbox(api, [("threads", [QUIZ, REVEAL], self.published("d1-quiz", "d2-reveal"))], {}, NOW)
        self.assertTrue(result["comments"][0]["answer_published"])

    def test_decided_and_old_comments_are_left_out(self):
        api = FakeInboxApi([{"id": "T1", "commentCount": 2}], {"T1": [
            comment("c1", "done already"),
            comment("c2", "old", created="2026-10-30T10:00:00+0000"),
        ]})
        result = comments.inbox(api, [("threads", [QUIZ], self.published("d1-quiz"))], {"c1": {"event": "replied"}}, NOW)
        self.assertEqual(result["comments"], [])


class InstagramInboxTest(unittest.TestCase):
    IG_POST = {"id": "ig-2026-11-12-quiz", "publish_at": "2026-11-12T15:00:00Z", "kind": "quiz", "text": "Caption",
               "images": ["a.jpg", "b.jpg"], "alt_text": ["question", "answer B"]}

    def test_instagram_comments_join_and_answers_count_as_public(self):
        api = FakeInboxApi([], {"IG1": [comment("i1", "B?")]}, instagram_posts=[{"id": "IG1", "commentCount": 1}])
        sources = [("threads", [QUIZ], {}),
                   ("instagram", [self.IG_POST], {"ig-2026-11-12-quiz": {"id": "ig-2026-11-12-quiz", "media_id": "IG1"}})]
        result = comments.inbox(api, sources, {}, NOW)
        item = result["comments"][0]
        self.assertEqual((item["platform"], item["queue_id"], item["answer_published"]), ("instagram", "ig-2026-11-12-quiz", True))
        self.assertEqual(item["slides"], ["question", "answer B"])

    def test_instagram_not_connected_is_left_out(self):
        api = FakeInboxApi([], {})
        result = comments.inbox(api, [("threads", [QUIZ], {}), ("instagram", [], {})], {}, NOW)
        self.assertEqual(result, {"accounts": {"threads": "acc-threads"}, "comments": []})


class ReplyCheckTest(unittest.TestCase):
    def test_rules(self):
        for good in ("спасибо, разбор будет завтра утром 🙌", "Верно! После to здесь идёт working, потому что это предлог",
                     "Почти) В американском скажут I'm good, а не I'm fine thanks"):
            self.assertEqual(comments.check_reply(good), [], good)
        for bad in ("", "x" * 221, "смотри https://example.com", "Урок стоит 2000 ₽", "Johnathan тут"):
            self.assertTrue(comments.check_reply(bad), bad)

    def test_a_reply_that_reads_as_generated_is_not_sent(self):
        for bad, why in (("Спасибо! Разбор — завтра утром", "long dash"),
                         ("Верно! Так и говорят.", "ends with a period"),
                         ("Здравствуйте! Спасибо за ответ", "form letter"),
                         ("Говорят «I'm beat», а не «I'm very tired»", "quotation marks"),
                         ("Смотри: правило такое: после to идёт -ing", "colons"),
                         ("Верно 🙌🔥👏", "emoji")):
            self.assertTrue(comments.check_reply(bad), why)


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, "comments.jsonl")
        patcher = mock.patch.object(comments, "COMMENTS_LOG", self.log)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def run_cli(self, *argv, api=None):
        with mock.patch.object(comments, "ZernioApi", lambda key: api):
            return comments.main(list(argv))

    def events(self):
        with open(self.log, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh]

    def test_reply_is_sent_once_with_an_idempotency_key(self):
        session = FakeSession([FakeResponse(200, {"accounts": [{"_id": "acc1", "platform": "threads"}]}),
                               FakeResponse(200, {"success": True, "data": {"commentId": "r1"}})])
        api = ZernioApi("proxy", session=session)
        self.assertEqual(self.run_cli("reply", "--post", "T1", "--comment", "c1", "--text", "Спасибо!", api=api), 0)
        method, url, body, params, headers = session.calls[1]
        self.assertEqual((method, url), ("POST", "https://zernio.com/api/v1/inbox/comments/T1"))
        self.assertEqual(body, {"accountId": "acc1", "message": "Спасибо!", "commentId": "c1"})
        self.assertEqual(headers, {"Idempotency-Key": "reply-c1"})  # the proxy adds Authorization
        self.assertEqual(self.events()[0]["reply_id"], "r1")
        self.assertEqual(self.run_cli("reply", "--post", "T1", "--comment", "c1", "--text", "Ещё раз", api=api), 1)

    def test_bad_reply_is_not_sent(self):
        session = FakeSession([])
        self.assertEqual(self.run_cli("reply", "--post", "T1", "--comment", "c1", "--text", "2000 руб",
                                      api=ZernioApi("proxy", session=session)), 1)
        self.assertEqual(session.calls, [])
        self.assertFalse(os.path.exists(self.log))

    def test_escalation_records_no_comment_text(self):
        self.assertEqual(self.run_cli("escalate", "--post", "T1", "--comment", "c9", "--reason", "pricing",
                                      "--url", "https://www.threads.com/c/c9", api=None), 0)
        event = self.events()[0]
        self.assertEqual((event["event"], event["reason"]), ("escalated", "pricing"))
        self.assertNotIn("text", event)


if __name__ == "__main__":
    unittest.main()
