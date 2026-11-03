"""Publish due posts from content/queue/ to Threads.

Two backends, chosen with PUBLISH_BACKEND:
  zernio  (default) Zernio's API, which posts through its own Meta-approved app,
          so no Meta developer account is needed. No polls, and a reveal goes
          out as its own post instead of a reply under the quiz.
  threads Meta's Threads API directly, with your own app and token. Supports
          polls and replies.

Every run (GitHub Actions, every 15 minutes):
  1. replays log/publications.jsonl to know what is already out,
  2. picks posts whose publish_at has passed,
  3. publishes each one (threads: container -> FINISHED -> publish;
     zernio: one publish-now request with an idempotency key),
  4. appends every step to the log (flushed immediately).

Safety rails:
  - a post is never created twice: a started publish is resumed from the log,
    and before starting a new one the account is checked for the same text
    (covers a run that died before its log was committed);
  - reveals wait for their quiz and are skipped if the quiz never went out;
  - transient API errors are retried on later runs, up to MAX_ATTEMPTS;
  - posts more than MAX_LATENESS late are skipped, not dumped in a burst;
  - any failure or skip makes the run exit 1 so the workflow opens an issue.

    python tools/publish.py --dry-run --now 2026-11-09T06:05:00Z
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qc import BACKEND, LOG_PATH, check_post, load_queue, normalize, parse_time  # noqa: E402

API_BASE = os.environ.get("THREADS_API_BASE", "https://graph.threads.com/v1.0")
ZERNIO_API_BASE = os.environ.get("ZERNIO_API_BASE", "https://zernio.com/api/v1")
ZERNIO_IN_FLIGHT = {"pending", "processing", "uploading"}
# Zernio errorCategory values worth another try on a later run.
ZERNIO_TRANSIENT = {"platform_error", "platform_rate_limit", "quota_exhausted", "system_error", "unknown"}
MAX_ATTEMPTS = 3
MAX_LATENESS = timedelta(hours=6)
MAX_PER_RUN = 4
STATUS_CHECKS = 12
STATUS_INTERVAL = 5
TERMINAL = {"published", "failed", "skipped"}


class ApiError(Exception):
    def __init__(self, message, status=None, code=None, transient=False):
        super().__init__(message)
        self.status = status
        self.code = code
        self.transient = transient

    @property
    def auth(self):
        return self.code in (190, "auth_expired") or self.status == 401


class StillPublishing(Exception):
    """The backend accepted the post but has not finished; check again next run."""


class ThreadsApi:
    def __init__(self, token, base=API_BASE, session=None):
        self.token = token
        self.base = base.rstrip("/")
        self.session = session or requests.Session()

    def _call(self, method, path, **params):
        if not self.token:
            raise ApiError("THREADS_ACCESS_TOKEN is not set", status=401)
        params["access_token"] = self.token
        url = "%s/%s" % (self.base, path.lstrip("/"))
        try:
            if method == "GET":
                resp = self.session.get(url, params=params, timeout=30)
            else:
                resp = self.session.post(url, data=params, timeout=60)
        except requests.RequestException as exc:
            raise ApiError("network error: %s" % exc.__class__.__name__, transient=True)
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code >= 400 or "error" in body:
            err = body.get("error") or {}
            raise ApiError(
                err.get("error_user_msg") or err.get("message") or "HTTP %d" % resp.status_code,
                status=resp.status_code,
                code=err.get("code"),
                transient=bool(err.get("is_transient")) or resp.status_code == 429 or resp.status_code >= 500,
            )
        return body

    def me(self):
        return self._call("GET", "me", fields="id,username")

    def create_container(self, user_id, post, image_url=None, reply_to_id=None):
        params = {"media_type": "IMAGE" if image_url else "TEXT", "text": post["text"]}
        if image_url:
            params["image_url"] = image_url
            params["alt_text"] = post["alt_text"]
        if post.get("topic_tag"):
            params["topic_tag"] = post["topic_tag"]
        if post.get("poll"):
            params["poll_attachment"] = json.dumps(
                {"option_" + "abcd"[i]: option for i, option in enumerate(post["poll"])}, ensure_ascii=False)
        if reply_to_id:
            params["reply_to_id"] = reply_to_id
        return self._call("POST", "%s/threads" % user_id, **params)["id"]

    def container_status(self, container_id):
        body = self._call("GET", container_id, fields="status,error_message")
        return body.get("status"), body.get("error_message")

    def publish(self, user_id, container_id):
        return self._call("POST", "%s/threads_publish" % user_id, creation_id=container_id)["id"]

    def permalink(self, media_id):
        return self._call("GET", media_id, fields="permalink").get("permalink")

    def recent_texts(self, user_id):
        """(media_id, text) for the account's latest posts and replies."""
        found = []
        for edge in ("threads", "replies"):
            body = self._call("GET", "%s/%s" % (user_id, edge), fields="id,text,timestamp", limit=25)
            found.extend((item["id"], item.get("text") or "") for item in body.get("data", []))
        return found


class ZernioApi:
    """Zernio (zernio.com) REST API; field names checked against its OpenAPI spec 1.444.0."""

    def __init__(self, key, base=ZERNIO_API_BASE, session=None):
        self.key = key
        self.base = base.rstrip("/")
        self.session = session or requests.Session()

    def _call(self, method, path, body=None, params=None, idempotency_key=None):
        if not self.key:
            raise ApiError("ZERNIO_API_KEY is not set", status=401)
        headers = {"Authorization": "Bearer " + self.key}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        url = "%s/%s" % (self.base, path.lstrip("/"))
        try:
            resp = self.session.request(method, url, json=body, params=params, headers=headers, timeout=120)
        except requests.RequestException as exc:
            raise ApiError("network error: %s" % exc.__class__.__name__, transient=True)
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code >= 400:
            raise ApiError(
                data.get("error") or data.get("message") or "HTTP %d" % resp.status_code,
                status=resp.status_code,
                code=data.get("code"),
                # 409: an idempotency key still in progress, or duplicate content (handled by the caller)
                transient=resp.status_code in (409, 429) or resp.status_code >= 500,
            )
        return data

    def threads_account(self):
        accounts = [a for a in self._call("GET", "accounts", params={"platform": "threads"}).get("accounts", [])
                    if a.get("platform") == "threads" and a.get("isActive", True) and a.get("enabled", True)]
        if not accounts:
            raise ApiError("no active Threads account is connected in Zernio", code="auth_expired")
        if accounts[0].get("needsReconnection"):
            raise ApiError("Threads @%s needs reconnecting in Zernio" % accounts[0].get("username"),
                           code="auth_expired")
        return accounts[0]

    def create_post(self, account_id, post, image_url=None, idempotency_key=None):
        target = {"platform": "threads", "accountId": account_id}
        if post.get("topic_tag"):
            target["platformSpecificData"] = {"topic_tag": post["topic_tag"]}
        body = {"content": post["text"], "publishNow": True, "platforms": [target]}
        if image_url:
            body["mediaItems"] = [{"type": "image", "url": image_url, "altText": post["alt_text"]}]
        return self._call("POST", "posts", body=body, idempotency_key=idempotency_key)

    def get_post(self, zernio_id):
        return self._call("GET", "posts/%s" % zernio_id).get("post") or {}

    def find_published(self, account_id, text):
        """The published Zernio post with exactly this text, if any."""
        params = {"accountId": account_id, "platform": "threads", "status": "published",
                  "search": text[:80], "limit": 20}
        for item in self._call("GET", "posts", params=params).get("posts", []):
            if normalize(item.get("content")) == normalize(text):
                return item
        return None

    def analytics(self, zernio_id):
        return self._call("GET", "analytics", params={"postId": zernio_id})

    def follower_stats(self, account_id, since, until):
        return self._call("GET", "accounts/follower-stats",
                          params={"accountIds": account_id, "fromDate": since, "toDate": until})


def threads_target(zpost):
    for target in zpost.get("platforms") or []:
        if target.get("platform") == "threads":
            return target
    return {}


def zernio_error(target, body):
    category = target.get("errorCategory")
    message = target.get("errorMessage")
    for result in body.get("platformResults") or []:
        if result.get("platform") == "threads" and result.get("error"):
            message = message or result["error"]
    message = message or body.get("error") or body.get("message") or "Zernio did not publish the post"
    return ApiError("%s (%s)" % (message, category) if category else message,
                    code=category, transient=category in ZERNIO_TRANSIENT)


def utcnow():
    return datetime.now(timezone.utc)


def stamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class Log:
    """Append-only JSONL log; state is rebuilt by replaying events."""

    def __init__(self, path=LOG_PATH, clock=utcnow):
        self.path = path
        self.clock = clock
        self.state = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        self._apply(json.loads(line))

    def _apply(self, event):
        st = self.state.setdefault(event["id"], {"status": "pending", "attempts": 0})
        kind = event["event"]
        if kind == "container_created":
            st["container_id"] = event["container_id"]
        elif kind == "container_discarded":
            st.pop("container_id", None)
        elif kind == "zernio_created":
            st["zernio_id"] = event["zernio_id"]
        elif kind == "zernio_discarded":
            st.pop("zernio_id", None)
        elif kind == "attempt_failed":
            st["attempts"] += 1
        elif kind in TERMINAL:
            st["status"] = kind
            if kind == "published":
                st["media_id"] = event["media_id"]

    def write(self, post_id, event, **fields):
        record = dict({"ts": stamp(self.clock()), "id": post_id, "event": event}, **fields)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self._apply(record)
        return record

    def get(self, post_id):
        return self.state.get(post_id, {"status": "pending", "attempts": 0})


class Publisher:
    """Publishes through Meta's Threads API (backend "threads")."""

    backend = "threads"
    replies = True  # a reveal is posted as a reply under its quiz

    def __init__(self, api, log, media_base_url="", sleep=time.sleep, clock=utcnow):
        self.api = api
        self.log = log
        self.media_base_url = media_base_url
        self.sleep = sleep
        self.clock = clock
        self._user_id = None
        self._recent = None
        self._simulated = {}  # dry-run outcomes, so dependent posts see them
        self.report = []

    @property
    def user_id(self):
        if self._user_id is None:
            self._user_id = self.api.me()["id"]
        return self._user_id

    def recent(self):
        if self._recent is None:
            self._recent = {normalize(text): media_id for media_id, text in self.api.recent_texts(self.user_id)}
        return self._recent

    def note(self, post_id, outcome, detail=""):
        self.report.append((post_id, outcome, detail))

    def status(self, post_id):
        return self._simulated.get(post_id) or self.log.get(post_id)["status"]

    def run(self, posts, now, dry_run=False, max_posts=MAX_PER_RUN):
        by_id = {p["id"]: p for p in posts}
        due = [p for p in posts
               if self.log.get(p["id"])["status"] not in TERMINAL and parse_time(p["publish_at"]) <= now]
        due.sort(key=lambda p: p["publish_at"])
        done = 0
        for post in due:
            if done >= max_posts:
                self.note(post["id"], "deferred", "per-run limit reached")
                continue
            pid = post["id"]
            state = self.log.get(pid)
            started = state.get("container_id") or state.get("zernio_id")
            late = now - parse_time(post["publish_at"])
            if late > MAX_LATENESS and not started:
                self._finish(pid, "skipped", "stale: %d h late" % (late.total_seconds() // 3600), dry_run)
                continue

            reply_to_id = post.get("reply_to_media_id")
            parent_id = post.get("reply_to")
            if parent_id:
                parent_status = self.status(parent_id)
                if parent_status == "published":
                    if self.replies:
                        reply_to_id = self.log.get(parent_id).get("media_id") or "<media id of %s>" % parent_id
                elif parent_status in TERMINAL or parent_id not in by_id:
                    self._finish(pid, "skipped", "its quiz %s was not published" % parent_id, dry_run)
                    continue
                else:
                    self.note(pid, "waiting", "for %s" % parent_id)
                    continue

            problems = check_post(post, backend=self.backend)
            if problems:
                self._finish(pid, "failed", "; ".join(problems), dry_run)
                continue
            if dry_run:
                self._simulated[pid] = "published"
                detail = "reply to %s" % reply_to_id if reply_to_id else ("after %s" % parent_id if parent_id else "")
                self.note(pid, "would publish", detail)
                done += 1
                continue

            try:
                self._publish_one(post, reply_to_id)
                done += 1
            except StillPublishing as exc:
                self.note(pid, "publishing", str(exc))
                done += 1
            except ApiError as exc:
                if exc.auth:
                    raise
                attempts = self.log.get(pid)["attempts"] + 1
                if exc.transient and attempts < MAX_ATTEMPTS:
                    self.log.write(pid, "attempt_failed", error=str(exc))
                    self.note(pid, "retry later", "attempt %d/%d: %s" % (attempts, MAX_ATTEMPTS, exc))
                else:
                    self.log.write(pid, "failed", error=str(exc))
                    self.note(pid, "failed", str(exc))
        return self.report

    def _finish(self, pid, outcome, reason, dry_run):
        if dry_run:
            self._simulated[pid] = outcome
        else:
            self.log.write(pid, outcome, error=reason)
        self.note(pid, outcome, reason)

    def _publish_one(self, post, reply_to_id):
        pid = post["id"]
        container_id = self.log.get(pid).get("container_id")
        if container_id:
            status, error = self.api.container_status(container_id)
            if status == "PUBLISHED":
                media_id = self.recent().get(normalize(post["text"]))
                if not media_id:
                    raise ApiError("container %s is published but the post was not found" % container_id)
                self._published(post, media_id, "recovered after an interrupted run",
                                self._permalink(media_id), container_id=container_id)
                return
            if status not in ("FINISHED", "IN_PROGRESS"):
                self.log.write(pid, "container_discarded", container_id=container_id,
                               error="%s %s" % (status, error or ""))
                container_id = None

        if not container_id:
            existing = self.recent().get(normalize(post["text"]))
            if existing:
                self._published(post, existing, "already on Threads, not posted again", self._permalink(existing))
                return
            image_url = self.media_base_url + post["image"] if post.get("image") else None
            container_id = self.api.create_container(self.user_id, post, image_url, reply_to_id)
            self.log.write(pid, "container_created", container_id=container_id)

        self._wait_until_finished(container_id)
        media_id = self.api.publish(self.user_id, container_id)
        self._published(post, media_id, "", self._permalink(media_id), container_id=container_id)

    def _wait_until_finished(self, container_id):
        for _ in range(STATUS_CHECKS):
            self.sleep(STATUS_INTERVAL)
            status, error = self.api.container_status(container_id)
            if status == "FINISHED":
                return
            if status != "IN_PROGRESS":
                raise ApiError("container %s is %s: %s" % (container_id, status, error or "no details"))
        raise ApiError("container %s still processing" % container_id, transient=True)

    def _permalink(self, media_id):
        try:
            return self.api.permalink(media_id)
        except ApiError:
            return None

    def _published(self, post, media_id, detail, link=None, **fields):
        self.log.write(post["id"], "published", media_id=media_id, permalink=link, text=post["text"], **fields)
        self.note(post["id"], "published", link or detail)


class ZernioPublisher(Publisher):
    """Publishes through Zernio (backend "zernio").

    Zernio cannot reply to an existing post, so a reveal goes out as its own
    post once its quiz is published. Each publish request carries an
    Idempotency-Key, so a retried request replays the first answer.
    """

    backend = "zernio"
    replies = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._account_id = None

    @property
    def account_id(self):
        if self._account_id is None:
            self._account_id = self.api.threads_account()["_id"]
        return self._account_id

    def _publish_one(self, post, reply_to_id):
        pid = post["id"]
        state = self.log.get(pid)
        zernio_id = state.get("zernio_id")
        if zernio_id:
            target = threads_target(self.api.get_post(zernio_id))
            if target.get("status") == "published":
                self._published_target(post, zernio_id, target, "recovered after an interrupted run")
                return
            if target.get("status") in ZERNIO_IN_FLIGHT:
                self._still_publishing(post, zernio_id)
            self.log.write(pid, "zernio_discarded", zernio_id=zernio_id,
                           error=target.get("errorMessage") or target.get("status") or "not found")

        image_url = self.media_base_url + post["image"] if post.get("image") else None
        key = "%s.%d" % (pid, state["attempts"])
        try:
            body = self.api.create_post(self.account_id, post, image_url, key)
        except ApiError as exc:
            if exc.status != 409:
                raise
            found = self.api.find_published(self.account_id, post["text"])
            if not found:
                raise
            self._published_target(post, found["_id"], threads_target(found), "already on Threads, not posted again")
            return

        zpost = body.get("post") or {}
        if zpost.get("_id"):
            self.log.write(pid, "zernio_created", zernio_id=zpost["_id"])
        target = threads_target(zpost)
        if target.get("status") == "published":
            self._published_target(post, zpost["_id"], target, "")
        elif target.get("status") in ZERNIO_IN_FLIGHT and zpost.get("_id"):
            self._still_publishing(post, zpost["_id"])
        else:
            raise zernio_error(target, body)

    def _still_publishing(self, post, zernio_id):
        if self.clock() - parse_time(post["publish_at"]) > MAX_LATENESS:
            raise ApiError("Zernio post %s has not published after %s" % (zernio_id, MAX_LATENESS))
        raise StillPublishing("Zernio post %s is still publishing" % zernio_id)

    def _published_target(self, post, zernio_id, target, detail):
        self._published(post, target.get("platformPostId"), detail, target.get("platformPostUrl"),
                        zernio_id=zernio_id)


def summarize(report, now, dry_run, check=False):
    title = "Connection check" if check else "Dry run" if dry_run else "Publish run"
    lines = ["## %s at %s UTC" % (title, stamp(now)), ""]
    if not report:
        lines.append("Nothing was due.")
    for pid, outcome, detail in report:
        lines.append("- **%s** `%s`%s" % (outcome, pid, (" — " + detail) if detail else ""))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="validate and show what is due; no API calls")
    parser.add_argument("--now", help="pretend the current UTC time is this (ISO, ends in Z)")
    parser.add_argument("--max-posts", type=int, default=MAX_PER_RUN)
    parser.add_argument("--summary-file", help="also write the markdown summary here")
    parser.add_argument("--check", action="store_true",
                        help="only confirm the key works and which Threads account it reaches; publish nothing")
    args = parser.parse_args(argv)

    now = parse_time(args.now) if args.now else utcnow().replace(microsecond=0)
    # A missing key only matters once something is due: the first API call then
    # fails as an auth error, which stops the run with exit code 2.
    secret = "ZERNIO_API_KEY" if BACKEND == "zernio" else "THREADS_ACCESS_TOKEN"
    key = os.environ.get(secret, "")
    media_base_url = os.environ.get("MEDIA_BASE_URL", "")
    if BACKEND == "zernio":
        publisher = ZernioPublisher(ZernioApi(key), Log(), media_base_url)
    else:
        publisher = Publisher(ThreadsApi(key), Log(), media_base_url)
    code = 0
    try:
        if args.check:
            if BACKEND == "zernio":
                account = publisher.api.threads_account()
                detail = "@%s via Zernio, %s followers" % (account.get("username"), account.get("followersCount", "?"))
            else:
                detail = "@%s via the Threads API" % publisher.api.me().get("username")
            report = [("(connection)", "ok", detail)]
        else:
            report = publisher.run(load_queue(), now, dry_run=args.dry_run, max_posts=args.max_posts)
        if any(outcome in ("failed", "skipped") for _, outcome, _ in report):
            code = 1
    except ApiError as exc:
        report = publisher.report + [("(run)", "stopped", "%s (check the %s secret and the account connection)"
                                      % (exc, secret))]
        code = 2

    summary = summarize(report, now, args.dry_run, args.check)
    print(summary)
    for path in filter(None, [args.summary_file, os.environ.get("GITHUB_STEP_SUMMARY")]):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(summary)
    return code


if __name__ == "__main__":
    sys.exit(main())
