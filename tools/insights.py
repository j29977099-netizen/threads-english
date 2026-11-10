"""Collect metrics for recently published posts into reports/insights-<date>.json.

Per post: views, likes, replies and shares (plus reposts, quotes and poll
results on the threads backend). Per account: followers (and totals on the
threads backend). The weekly report is written from this file, so it reflects
real numbers, not guesses.

    ZERNIO_API_KEY=... python tools/insights.py --days 7
    PUBLISH_BACKEND=threads THREADS_ACCESS_TOKEN=... python tools/insights.py --days 7
"""
import argparse
import json
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from publish import ApiError, Log, ThreadsApi, ZernioApi, stamp, utcnow  # noqa: E402
from qc import BACKEND, LOG_PATH, ROOT, load_queue, parse_time  # noqa: E402

POST_METRICS = "views,likes,replies,reposts,quotes,shares"
ACCOUNT_METRICS = "views,likes,replies,reposts,quotes,followers_count"
POLL_FIELDS = "poll_attachment{option_a,option_b,option_c,option_d,option_a_votes_percentage," \
              "option_b_votes_percentage,option_c_votes_percentage,option_d_votes_percentage,total_votes}"


def metric_values(body):
    """Insights responses carry either total_value or a list of values."""
    out = {}
    for item in body.get("data", []):
        if "total_value" in item:
            out[item["name"]] = item["total_value"].get("value")
        else:
            out[item["name"]] = sum(v.get("value", 0) for v in item.get("values", []))
    return out


def published_since(cutoff, path=LOG_PATH):
    events = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    event = json.loads(line)
                    if event["event"] == "published" and parse_time(event["ts"]) >= cutoff:
                        events.append(event)
    return events


def threads_metrics(api, event, meta, row):
    row["metrics"] = metric_values(api._call("GET", "%s/insights" % event["media_id"], metric=POST_METRICS))
    if meta.get("poll"):
        row["poll"] = api._call("GET", event["media_id"], fields=POLL_FIELDS).get("poll_attachment")
        row["answer"] = meta.get("answer")


def threads_account(api, cutoff, now):
    return metric_values(api._call("GET", "%s/threads_insights" % api.me()["id"], metric=ACCOUNT_METRICS,
                                   since=int(cutoff.timestamp()), until=int(now.timestamp())))


def zernio_metrics(api, event, meta, row):
    if not event.get("zernio_id"):
        # A reveal replied under its quiz through the inbox is not a Zernio post, so Zernio has no metrics for it.
        row["note"] = "reply under its quiz: no Zernio metrics"
        return
    body = api.analytics(event["zernio_id"])
    row["metrics"] = body.get("analytics") or {}
    if body.get("syncStatus") not in (None, "synced"):
        row["note"] = body.get("message") or "metrics still syncing"


def zernio_account(api, cutoff, now):
    account = api.threads_account()
    body = api.follower_stats(account["_id"], stamp(cutoff), stamp(now))
    stats = (body.get("accounts") or [{}])[0]
    return {"followers": stats.get("currentFollowers", account.get("followersCount")),
            "follower_growth": stats.get("growth")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv)

    if BACKEND == "zernio":
        api, post_metrics, account_metrics = ZernioApi(os.environ.get("ZERNIO_API_KEY", "")), \
            zernio_metrics, zernio_account
    else:
        api, post_metrics, account_metrics = ThreadsApi(os.environ.get("THREADS_ACCESS_TOKEN", "")), \
            threads_metrics, threads_account
    now = utcnow().replace(microsecond=0)
    cutoff = now - timedelta(days=args.days)
    queue = {p["id"]: p for p in load_queue()}
    Log()  # fails loudly on a corrupt log before any API call

    posts = []
    for event in published_since(cutoff):
        meta = queue.get(event["id"], {})
        row = {"id": event["id"], "published": event["ts"], "kind": meta.get("kind"),
               "topic": meta.get("topic"), "permalink": event.get("permalink")}
        try:
            post_metrics(api, event, meta, row)
        except ApiError as exc:
            if exc.auth:
                raise
            row["error"] = str(exc)
        posts.append(row)

    try:
        account = account_metrics(api, cutoff, now)
    except ApiError as exc:
        if exc.auth:
            raise
        account = {"error": str(exc)}
    report = {"generated": stamp(now), "since": stamp(cutoff), "backend": BACKEND,
              "account": account, "posts": posts}
    path = os.path.join(ROOT, "reports", "insights-%s.json" % now.strftime("%Y-%m-%d"))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print("wrote %s (%d posts)" % (os.path.relpath(path, ROOT), len(posts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
