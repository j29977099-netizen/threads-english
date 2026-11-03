import json
import os
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import publish  # noqa: E402
from publish import ApiError, Log, Publisher, ThreadsApi, ZernioApi, ZernioPublisher, threads_target  # noqa: E402
from qc import check_post, check_queue, load_queue, parse_time  # noqa: E402


def post(pid, at, text=None, **extra):
    return dict({"id": pid, "publish_at": at, "kind": "lesson", "text": text or "text of " + pid}, **extra)


QUIZ = post("d1-quiz", "2026-11-09T06:00:00Z", kind="quiz", poll=["to see", "to seeing"], answer="to seeing")
REVEAL = post("d2-reveal", "2026-11-10T06:15:00Z", "✅ Разбор: to seeing", kind="reveal", reply_to="d1-quiz")
LESSON = post("d1-lesson", "2026-11-09T16:00:00Z")


class FakeApi:
    def __init__(self):
        self.containers = {}
        self.posts = {}
        self.create_errors = []
        self.publish_errors = []

    def me(self):
        return {"id": "u1"}

    def create_container(self, user_id, post, image_url=None, reply_to_id=None):
        if self.create_errors:
            raise self.create_errors.pop(0)
        cid = "c%d" % (len(self.containers) + 1)
        self.containers[cid] = {"status": "FINISHED", "text": post["text"], "reply_to": reply_to_id}
        return cid

    def container_status(self, cid):
        return self.containers[cid]["status"], None

    def publish(self, user_id, cid):
        if self.publish_errors:
            raise self.publish_errors.pop(0)
        mid = "m%d" % (len(self.posts) + 1)
        self.posts[mid] = dict(self.containers[cid])
        self.containers[cid]["status"] = "PUBLISHED"
        return mid

    def permalink(self, mid):
        return "https://www.threads.com/@teacher/post/" + mid

    def recent_texts(self, user_id):
        return [(mid, p["text"]) for mid, p in self.posts.items()]


class Harness(unittest.TestCase):
    publisher = Publisher

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.tmp.name, "log.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def run_at(self, when, posts, api=None, **kwargs):
        pub = self.publisher(api or self.api, Log(self.log_path), sleep=lambda s: None,
                             clock=lambda: parse_time(when))
        return pub.run(posts, parse_time(when), **kwargs)

    def events(self):
        with open(self.log_path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh]

    def outcomes(self, report):
        return {pid: outcome for pid, outcome, _ in report}


class PublisherTest(Harness):
    def setUp(self):
        super().setUp()
        self.api = FakeApi()

    def test_publishes_due_posts_only(self):
        report = self.run_at("2026-11-09T06:05:00Z", [QUIZ, LESSON])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "published"})
        self.assertEqual(len(self.api.posts), 1)

    def test_reveal_replies_to_its_quiz(self):
        self.run_at("2026-11-09T06:05:00Z", [QUIZ, REVEAL])
        report = self.run_at("2026-11-10T06:20:00Z", [QUIZ, REVEAL])
        self.assertEqual(self.outcomes(report), {"d2-reveal": "published"})
        reveal = [p for p in self.api.posts.values() if p["text"] == REVEAL["text"]][0]
        self.assertEqual(reveal["reply_to"], "m1")

    def test_second_run_does_not_post_again(self):
        self.run_at("2026-11-09T06:05:00Z", [QUIZ])
        report = self.run_at("2026-11-09T06:20:00Z", [QUIZ])
        self.assertEqual(report, [])
        self.assertEqual(len(self.api.posts), 1)

    def test_lost_log_does_not_cause_duplicate(self):
        self.run_at("2026-11-09T06:05:00Z", [QUIZ])
        os.remove(self.log_path)  # the run died before its log was committed
        report = self.run_at("2026-11-09T06:20:00Z", [QUIZ])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "published"})
        self.assertEqual(len(self.api.posts), 1)
        self.assertEqual(self.events()[-1]["media_id"], "m1")

    def test_existing_container_is_reused(self):
        self.api.publish_errors.append(ApiError("timeout", status=500, transient=True))
        self.run_at("2026-11-09T06:05:00Z", [QUIZ])
        self.run_at("2026-11-09T06:20:00Z", [QUIZ])
        self.assertEqual(len(self.api.containers), 1)
        self.assertEqual(len(self.api.posts), 1)

    def test_transient_errors_retry_then_fail(self):
        for _ in range(3):
            self.api.create_errors.append(ApiError("busy", status=503, transient=True))
        outcomes = [self.outcomes(self.run_at(t, [QUIZ]))["d1-quiz"]
                    for t in ("2026-11-09T06:05:00Z", "2026-11-09T06:20:00Z", "2026-11-09T06:35:00Z")]
        self.assertEqual(outcomes, ["retry later", "retry later", "failed"])
        self.assertEqual(self.run_at("2026-11-09T06:50:00Z", [QUIZ]), [])

    def test_permanent_error_fails_at_once(self):
        self.api.create_errors.append(ApiError("Param text is too long", status=400, code=100))
        report = self.run_at("2026-11-09T06:05:00Z", [QUIZ])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "failed"})

    def test_stale_quiz_and_its_reveal_are_skipped(self):
        report = self.run_at("2026-11-10T06:20:00Z", [QUIZ, REVEAL])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "skipped", "d2-reveal": "skipped"})
        self.assertEqual(self.api.posts, {})

    def test_auth_error_stops_the_run(self):
        self.api.create_errors.append(ApiError("Error validating access token", status=400, code=190))
        with self.assertRaises(ApiError):
            self.run_at("2026-11-09T06:05:00Z", [QUIZ])
        self.assertNotIn("failed", [e["event"] for e in self.events()] if os.path.exists(self.log_path) else [])

    def test_invalid_post_fails_without_api_call(self):
        bad = post("too-long", "2026-11-09T06:00:00Z", "x" * 501)
        report = self.run_at("2026-11-09T06:05:00Z", [bad])
        self.assertEqual(self.outcomes(report), {"too-long": "failed"})
        self.assertEqual(self.api.containers, {})

    def test_per_run_limit(self):
        posts = [post("p%d" % i, "2026-11-09T06:00:00Z") for i in range(6)]
        report = self.run_at("2026-11-09T06:05:00Z", posts, max_posts=4)
        self.assertEqual(sum(1 for _, o, _ in report if o == "published"), 4)
        self.assertEqual(sum(1 for _, o, _ in report if o == "deferred"), 2)

    def test_dry_run_touches_nothing(self):
        report = self.run_at("2026-11-10T06:20:00Z", [QUIZ, REVEAL, LESSON], dry_run=True)
        self.assertFalse(os.path.exists(self.log_path))
        self.assertEqual(self.api.containers, {})
        self.assertIn("skipped", self.outcomes(report).values())


ZQUIZ = post("d1-quiz", "2026-11-09T06:00:00Z", kind="quiz", answer="B")
ZREVEAL = post("d2-reveal", "2026-11-10T06:15:00Z", "✅ Разбор вчерашнего квиза: B", kind="reveal", reply_to="d1-quiz")


class FakeZernioApi:
    """Answers like Zernio: same Idempotency-Key replays the first response."""

    def __init__(self):
        self.posts = {}
        self.replies = {}
        self.outcomes = []  # per new post: "published", "pending", a failure category, or an ApiError
        self.keys = []

    def threads_account(self):
        return {"_id": "acc1", "username": "esl_teacher_bro"}

    def create_post(self, account_id, post, image_url=None, idempotency_key=None):
        self.keys.append(idempotency_key)
        if idempotency_key in self.replies:
            return self.replies[idempotency_key]
        outcome = self.outcomes.pop(0) if self.outcomes else "published"
        if isinstance(outcome, ApiError):
            raise outcome
        zid = "z%d" % (len(self.posts) + 1)
        target = {"platform": "threads", "status": outcome}
        if outcome == "published":
            target.update(platformPostId="t" + zid, platformPostUrl="https://www.threads.com/@esl_teacher_bro/post/" + zid)
        elif outcome != "pending":
            target.update(status="failed", errorCategory=outcome, errorMessage="it broke")
        self.posts[zid] = {"_id": zid, "content": post["text"], "image_url": image_url, "platforms": [target]}
        self.replies[idempotency_key] = {"post": self.posts[zid]}
        return self.replies[idempotency_key]

    def get_post(self, zid):
        return self.posts.get(zid, {})

    def find_published(self, account_id, text):
        for zpost in self.posts.values():
            if zpost["content"] == text and threads_target(zpost)["status"] == "published":
                return zpost
        return None

    def published(self):
        return [p for p in self.posts.values() if threads_target(p)["status"] == "published"]


class ZernioPublisherTest(Harness):
    publisher = ZernioPublisher

    def setUp(self):
        super().setUp()
        self.api = FakeZernioApi()

    def test_publishes_and_logs_the_threads_link(self):
        report = self.run_at("2026-11-09T06:05:00Z", [ZQUIZ, LESSON])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "published"})
        last = self.events()[-1]
        self.assertEqual((last["event"], last["zernio_id"], last["media_id"]), ("published", "z1", "tz1"))
        self.assertTrue(last["permalink"].endswith("/post/z1"))
        self.assertEqual(self.run_at("2026-11-09T06:20:00Z", [ZQUIZ, LESSON]), [])

    def test_reveal_is_its_own_post_after_the_quiz(self):
        self.assertEqual(self.outcomes(self.run_at("2026-11-10T06:20:00Z", [ZQUIZ, ZREVEAL])),
                         {"d1-quiz": "skipped", "d2-reveal": "skipped"})
        os.remove(self.log_path)
        self.run_at("2026-11-09T06:05:00Z", [ZQUIZ, ZREVEAL])
        report = self.run_at("2026-11-10T06:20:00Z", [ZQUIZ, ZREVEAL])
        self.assertEqual(self.outcomes(report), {"d2-reveal": "published"})
        self.assertEqual([p["content"] for p in self.api.published()], [ZQUIZ["text"], ZREVEAL["text"]])

    def test_lost_log_replays_instead_of_reposting(self):
        self.run_at("2026-11-09T06:05:00Z", [ZQUIZ])
        os.remove(self.log_path)
        report = self.run_at("2026-11-09T06:20:00Z", [ZQUIZ])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "published"})
        self.assertEqual(len(self.api.posts), 1)
        self.assertEqual(self.api.keys, ["d1-quiz.0", "d1-quiz.0"])

    def test_duplicate_conflict_is_recorded_not_reposted(self):
        self.run_at("2026-11-09T06:05:00Z", [ZQUIZ])
        os.remove(self.log_path)
        self.api.replies.clear()  # the idempotency key has expired
        self.api.outcomes.append(ApiError("Duplicate content detected", status=409, transient=True))
        report = self.run_at("2026-11-09T06:20:00Z", [ZQUIZ])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "published"})
        self.assertEqual(len(self.api.posts), 1)

    def test_platform_error_retries_with_a_new_key(self):
        self.api.outcomes.append("platform_error")
        first = self.run_at("2026-11-09T06:05:00Z", [ZQUIZ])
        second = self.run_at("2026-11-09T06:20:00Z", [ZQUIZ])
        self.assertEqual((self.outcomes(first), self.outcomes(second)),
                         ({"d1-quiz": "retry later"}, {"d1-quiz": "published"}))
        self.assertEqual(self.api.keys, ["d1-quiz.0", "d1-quiz.1"])

    def test_content_error_fails_at_once(self):
        self.api.outcomes.append("user_content")
        report = self.run_at("2026-11-09T06:05:00Z", [ZQUIZ])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "failed"})

    def test_still_publishing_is_checked_next_run(self):
        self.api.outcomes.append("pending")
        report = self.run_at("2026-11-09T06:05:00Z", [ZQUIZ])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "publishing"})
        threads_target(self.api.posts["z1"]).update(status="published", platformPostId="tz1")
        report = self.run_at("2026-11-09T13:00:00Z", [ZQUIZ])  # past MAX_LATENESS, but already started
        self.assertEqual(self.outcomes(report), {"d1-quiz": "published"})
        self.assertEqual(len(self.api.posts), 1)

    def test_disconnected_account_stops_the_run(self):
        self.api.outcomes.append("auth_expired")
        with self.assertRaises(ApiError):
            self.run_at("2026-11-09T06:05:00Z", [ZQUIZ])

    def test_polls_are_rejected_before_any_request(self):
        report = self.run_at("2026-11-09T06:05:00Z", [QUIZ])
        self.assertEqual(self.outcomes(report), {"d1-quiz": "failed"})
        self.assertEqual(self.api.keys, [])
        self.assertTrue(any("cannot post polls" in p for p in check_post(QUIZ, backend="zernio")))
        self.assertEqual(check_post(QUIZ, backend="threads"), [])


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, data=None, timeout=None):
        self.calls.append(("POST", url, data))
        return self.responses.pop(0)

    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, params))
        return self.responses.pop(0)

    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        self.calls.append((method, url, json, params, headers))
        return self.responses.pop(0)


class ZernioApiTest(unittest.TestCase):
    def test_publish_request(self):
        session = FakeSession([FakeResponse(201, {"post": {"_id": "z1"}})])
        api = ZernioApi("sk_test", session=session)
        image_post = post("img", "2026-11-09T06:00:00Z", image="media/a.png", alt_text="alt",
                          topic_tag="Английский язык")
        api.create_post("acc1", image_post, "https://example.org/media/a.png", "img.0")
        method, url, body, params, headers = session.calls[0]
        self.assertEqual((method, url), ("POST", "https://zernio.com/api/v1/posts"))
        self.assertEqual(headers, {"Authorization": "Bearer sk_test", "Idempotency-Key": "img.0"})
        self.assertEqual(body["platforms"], [{"platform": "threads", "accountId": "acc1",
                                              "platformSpecificData": {"topic_tag": "Английский язык"}}])
        self.assertTrue(body["publishNow"])
        self.assertEqual(body["mediaItems"], [{"type": "image", "url": "https://example.org/media/a.png",
                                               "altText": "alt"}])

    def test_error_classification(self):
        cases = [(500, True, False), (429, True, False), (409, True, False), (400, False, False), (401, False, True)]
        for status, transient, auth in cases:
            api = ZernioApi("sk_test", session=FakeSession([FakeResponse(status, {"error": "x"})]))
            with self.assertRaises(ApiError) as ctx:
                api.get_post("z1")
            self.assertEqual((ctx.exception.transient, ctx.exception.auth), (transient, auth), status)

    def test_disconnected_account_is_an_auth_error(self):
        body = {"accounts": [{"_id": "a1", "platform": "threads", "username": "u", "needsReconnection": True}]}
        api = ZernioApi("sk_test", session=FakeSession([FakeResponse(200, body)]))
        with self.assertRaises(ApiError) as ctx:
            api.threads_account()
        self.assertTrue(ctx.exception.auth)


class ThreadsApiTest(unittest.TestCase):
    def test_poll_and_reply_parameters(self):
        session = FakeSession([FakeResponse(200, {"id": "c1"})])
        api = ThreadsApi("TOKEN", session=session)
        api.create_container("u1", dict(QUIZ, topic_tag="Английский язык"), reply_to_id="m9")
        method, url, data = session.calls[0]
        self.assertEqual(url, "https://graph.threads.com/v1.0/u1/threads")
        self.assertEqual(data["media_type"], "TEXT")
        self.assertEqual(json.loads(data["poll_attachment"]), {"option_a": "to see", "option_b": "to seeing"})
        self.assertEqual(data["reply_to_id"], "m9")
        self.assertEqual(data["topic_tag"], "Английский язык")

    def test_image_parameters(self):
        session = FakeSession([FakeResponse(200, {"id": "c1"})])
        api = ThreadsApi("TOKEN", session=session)
        api.create_container("u1", post("img", "2026-11-09T06:00:00Z", image="media/a.png", alt_text="alt"),
                             image_url="https://example.org/media/a.png")
        data = session.calls[0][2]
        self.assertEqual((data["media_type"], data["image_url"], data["alt_text"]),
                         ("IMAGE", "https://example.org/media/a.png", "alt"))

    def test_error_classification(self):
        cases = [
            (FakeResponse(500, {"error": {"message": "boom"}}), True, False),
            (FakeResponse(429, {"error": {"message": "slow down"}}), True, False),
            (FakeResponse(400, {"error": {"message": "bad param", "code": 100}}), False, False),
            (FakeResponse(400, {"error": {"message": "expired", "code": 190}}), False, True),
            (FakeResponse(400, {"error": {"message": "hiccup", "code": 2, "is_transient": True}}), True, False),
        ]
        for response, transient, auth in cases:
            api = ThreadsApi("TOKEN", session=FakeSession([response]))
            with self.assertRaises(ApiError) as ctx:
                api.me()
            self.assertEqual((ctx.exception.transient, ctx.exception.auth), (transient, auth), response._body)


class QueueTest(unittest.TestCase):
    def test_committed_queue_passes_qc(self):
        self.assertEqual(check_queue(load_queue()), [])


if __name__ == "__main__":
    unittest.main()
