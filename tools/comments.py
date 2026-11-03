"""Handle comments on the account's Threads posts through Zernio.

The comment routine (strategy/COMMENTS.md) uses it three times a day:

    python tools/comments.py inbox
        New comments that still need a decision, as JSON, each with what is
        needed to answer it: the post, its quiz answer, and whether that
        answer has been revealed yet.
    python tools/comments.py reply --post P --comment C --text "..."
    python tools/comments.py escalate --post P --comment C --reason pricing --url URL
    python tools/comments.py skip --post P --comment C --reason "emoji only"

Every comment gets exactly one decision. log/comments.jsonl records ids,
decisions and our own reply text, never what other people wrote, because the
repository is public. Escalations open a GitHub issue (comments.yml).

In a Claude cloud session the Zernio key is a network secret, so run with
ZERNIO_API_KEY=proxy.
"""
import argparse
import json
import os
import re
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from publish import ApiError, ZernioApi, stamp, utcnow  # noqa: E402
from qc import LINK_RE, LOG_PATH, ROOT, load_queue, normalize, parse_time  # noqa: E402

COMMENTS_LOG = os.path.join(ROOT, "log", "comments.jsonl")
MAX_AGE = timedelta(days=7)
MAX_REPLY = 300
MAX_REPLIES_PER_DAY = 60
REASONS = {"pricing", "booking", "personal", "complaint", "harassment", "sensitive", "partnership", "unsure", "other"}
PRICE_RE = re.compile(r"\d\s*(₽|руб|\$|€|usd|eur|долл)", re.I)
DECISIONS = {"replied", "escalated", "skipped"}


def handled(path=None):
    """comment id -> the decision recorded for it."""
    path = path or COMMENTS_LOG
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    event = json.loads(line)
                    done[event["comment_id"]] = event
    return done


def record(event, path=None, clock=utcnow):
    path = path or COMMENTS_LOG
    event = dict({"ts": stamp(clock())}, **event)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return event


def check_reply(text):
    """Problems that make a reply unsendable."""
    errors = []
    if not text.strip():
        errors.append("reply is empty")
    if len(text) > MAX_REPLY:
        errors.append("reply is %d characters (max %d)" % (len(text), MAX_REPLY))
    if LINK_RE.search(text):
        errors.append("replies carry no links")
    if PRICE_RE.search(text):
        errors.append("replies never mention prices; escalate instead")
    if re.search(r"johnathan|джонатан", text, re.I):
        errors.append("posts and replies never name the teacher")
    return errors


def post_context(queue, published):
    """Map Threads post ids, links and texts to what the queue knows about each post."""
    by_id = {p["id"]: p for p in queue}
    reveal_of = {p["reply_to"]: p["id"] for p in queue if p.get("kind") == "reveal" and p.get("reply_to")}
    index = {}
    for post in queue:
        pid = post["id"]
        quiz = by_id.get(post.get("reply_to")) if post.get("kind") == "reveal" else post
        answer = (quiz or {}).get("answer")
        reveal_id = reveal_of.get(pid)
        info = {
            "queue_id": pid,
            "kind": post.get("kind"),
            "topic": post.get("topic"),
            "answer": answer,
            # A reveal post is the answer; for a quiz, the answer is public once its reveal went out.
            "answer_published": post.get("kind") == "reveal" or bool(reveal_id and reveal_id in published),
        }
        event = published.get(pid, {})
        for key in (event.get("media_id"), event.get("zernio_id"), event.get("permalink"), normalize(post.get("text"))):
            if key:
                index[key] = info
    return index


def flatten(comments):
    for comment in comments:
        yield comment
        for reply in comment.get("replies") or []:
            yield reply


def owner_replied(comment):
    return any((r.get("from") or {}).get("isOwner") for r in comment.get("replies") or [])


def inbox(api, queue, published, done, now):
    account_id = api.threads_account()["_id"]
    index = post_context(queue, published)
    since = (now - MAX_AGE).strftime("%Y-%m-%d")
    found = []
    for post in api.commented_posts(account_id, since):
        if not post.get("commentCount"):
            continue
        context = (index.get(post.get("id")) or index.get(post.get("permalink"))
                   or index.get(normalize(post.get("content"))) or {"queue_id": None})
        for comment in flatten(api.post_comments(post["id"], account_id)):
            author = comment.get("from") or {}
            if author.get("isOwner") or comment.get("id") in done or owner_replied(comment):
                continue
            created = comment.get("createdTime")
            try:
                if created and now - parse_time(created[:19] + "Z") > MAX_AGE:
                    continue
            except ValueError:
                pass  # an unexpected date format shouldn't hide a comment
            found.append(dict(context, post_id=post["id"], post_text=(post.get("content") or "")[:280],
                              post_url=post.get("permalink"), comment_id=comment["id"],
                              author=author.get("username"), text=comment.get("message"),
                              created=created, comment_url=comment.get("url"),
                              can_reply=comment.get("canReply", True)))
    return {"account_id": account_id, "comments": found}


def published_events(path=LOG_PATH):
    """The publish log's 'published' events, with media ids and links."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    event = json.loads(line)
                    if event.get("event") == "published":
                        yield event


def replies_today(done, now):
    day = now.strftime("%Y-%m-%d")
    return sum(1 for e in done.values() if e.get("event") == "replied" and e.get("ts", "").startswith(day))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inbox")
    for name in ("reply", "escalate", "skip"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--post", required=True, help="post id from the inbox output")
        cmd.add_argument("--comment", required=True, help="comment id from the inbox output")
    sub.choices["reply"].add_argument("--text", required=True)
    sub.choices["escalate"].add_argument("--reason", required=True, choices=sorted(REASONS))
    sub.choices["escalate"].add_argument("--url", default=None, help="comment_url from the inbox output")
    sub.choices["skip"].add_argument("--reason", required=True)
    args = parser.parse_args(argv)

    now = utcnow().replace(microsecond=0)
    done = handled()
    api = ZernioApi(os.environ.get("ZERNIO_API_KEY", ""))
    try:
        if args.command == "inbox":
            published = {event["id"]: event for event in published_events()}
            print(json.dumps(inbox(api, load_queue(), published, done, now), ensure_ascii=False, indent=2))
            return 0

        if args.comment in done:
            print("comment %s already has a decision: %s" % (args.comment, done[args.comment]["event"]),
                  file=sys.stderr)
            return 1
        if args.command == "reply":
            problems = check_reply(args.text)
            if replies_today(done, now) >= MAX_REPLIES_PER_DAY:
                problems.append("daily limit of %d replies reached" % MAX_REPLIES_PER_DAY)
            if problems:
                print("not sent: " + "; ".join(problems), file=sys.stderr)
                return 1
            account_id = api.threads_account()["_id"]
            data = api.reply_to_comment(args.post, account_id, args.comment, args.text,
                                        idempotency_key="reply-%s" % args.comment)
            record({"event": "replied", "comment_id": args.comment, "post_id": args.post,
                    "reply_id": data.get("commentId"), "text": args.text})
        elif args.command == "escalate":
            record({"event": "escalated", "comment_id": args.comment, "post_id": args.post,
                    "reason": args.reason, "url": args.url})
        else:
            record({"event": "skipped", "comment_id": args.comment, "post_id": args.post, "reason": args.reason})
        print("%s %s" % (args.command, args.comment))
        return 0
    except ApiError as exc:
        print("Zernio error: %s" % exc, file=sys.stderr)
        return 2 if exc.auth else 1


if __name__ == "__main__":
    sys.exit(main())
