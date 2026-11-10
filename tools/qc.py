"""Mechanical quality checks for the post queue.

Run before content is committed (and in CI on every push). The publisher calls
check_post() again right before publishing, so a broken post fails alone
instead of blocking the whole queue.

Limits come from the Threads API docs (checked 2026-11-02): text <= 500 chars,
poll 2-4 options of 1-25 chars on text-only posts, <= 5 links, images JPEG/PNG
<= 8 MB and >= 320 px wide, topic tag without '.' or '&'.

What a post may use depends on the publishing backend (PUBLISH_BACKEND, see
tools/publish.py): only the direct Threads API can post polls and replies.
"""
import argparse
import glob
import json
import os
import re
import struct
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_GLOB = os.path.join(ROOT, "content", "queue", "*.json")
LOG_PATH = os.path.join(ROOT, "log", "publications.jsonl")
# Each platform has its own queue and its own publication log.
QUEUES = {"threads": QUEUE_GLOB, "instagram": os.path.join(ROOT, "content", "instagram", "*.json")}
LOGS = {"threads": LOG_PATH, "instagram": os.path.join(ROOT, "log", "instagram.jsonl")}
# Instagram (via Zernio): JPEG only, 1-10 slides here (Instagram allows 20), 4:5 up to 1.91:1,
# caption <= 2,200 characters, <= 30 hashtags.
IG_MAX_CAPTION = 2200
IG_MAX_HASHTAGS = 30
IG_MAX_SLIDES = 10
IG_KINDS = {"quiz", "lesson", "tip", "promo", "intro"}

MAX_TEXT = 500
MAX_POLL_OPTION = 25
MAX_LINKS = 5
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIN_IMAGE_WIDTH = 320
KINDS = {"intro", "quiz", "challenge", "lesson", "tip", "promo", "reveal", "reply"}
NEEDS_REVEAL = {"quiz", "challenge"}
POLL_OPEN = timedelta(hours=24)
BACKEND = os.environ.get("PUBLISH_BACKEND", "zernio")
CAN = {"threads": {"polls", "replies"}, "zernio": set()}

LINK_RE = re.compile(r"https?://|www\.", re.I)


def parse_time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("publish_at must be an ISO UTC time ending in Z, got %r" % (value,))
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def load_queue(pattern=QUEUE_GLOB):
    posts = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as fh:
            for post in json.load(fh):
                post["_file"] = os.path.relpath(path, ROOT)
                posts.append(post)
    return posts


def png_or_jpeg_width(path):
    with open(path, "rb") as fh:
        head = fh.read(32)
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return struct.unpack(">I", head[16:20])[0]
        if head[:2] == b"\xff\xd8":
            fh.seek(2)
            while True:
                marker = fh.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                size = struct.unpack(">H", fh.read(2))[0]
                if marker[1] in (0xC0, 0xC1, 0xC2):
                    fh.read(1)
                    _, width = struct.unpack(">HH", fh.read(4))
                    return width
                fh.seek(size - 2, 1)
    return None


def check_instagram_post(post, root=ROOT):
    """Problems that make an Instagram post unpublishable."""
    from PIL import Image

    errors = []
    pid = post.get("id") or ""
    if not re.fullmatch(r"ig-[a-z0-9][a-z0-9-]*", pid):
        errors.append("id must start with ig- and use lowercase letters, digits and dashes")
    if post.get("kind") not in IG_KINDS:
        errors.append("kind must be one of %s (answers go on a later slide, not in a reveal post)" % sorted(IG_KINDS))
    try:
        parse_time(post.get("publish_at"))
    except ValueError as exc:
        errors.append(str(exc))
    text = post.get("text") or ""
    if not text.strip():
        errors.append("caption is empty")
    if len(text) > IG_MAX_CAPTION:
        errors.append("caption is %d characters (max %d)" % (len(text), IG_MAX_CAPTION))
    if len(re.findall(r"#\w", text)) > IG_MAX_HASHTAGS:
        errors.append("more than %d hashtags" % IG_MAX_HASHTAGS)
    for field in ("poll", "reply_to", "topic_tag", "image"):
        if post.get(field) is not None:
            errors.append("%s is a Threads field; Instagram posts use images and alt_text lists" % field)

    images, alts = post.get("images") or [], post.get("alt_text") or []
    if not 1 <= len(images) <= IG_MAX_SLIDES:
        errors.append("needs 1-%d images" % IG_MAX_SLIDES)
    if not isinstance(alts, list) or len(alts) != len(images) or not all(a.strip() for a in alts):
        errors.append("alt_text must be a list with one description per image")
    sizes = set()
    for image in images:
        path = os.path.join(root, image)
        if not os.path.isfile(path):
            errors.append("image %s not found" % image)
            continue
        with Image.open(path) as im:
            if im.format != "JPEG":
                errors.append("%s must be JPEG (Instagram takes only JPEG)" % image)
            width, height = im.size
        sizes.add((width, height))
        if os.path.getsize(path) > MAX_IMAGE_BYTES:
            errors.append("%s is larger than 8 MB" % image)
        if not 0.8 <= width / height <= 1.91:
            errors.append("%s is %dx%d; Instagram feed needs 4:5 up to 1.91:1" % (image, width, height))
    if len(sizes) > 1:
        errors.append("all slides of a carousel must be the same size")
    return errors


def check_post(post, root=ROOT, backend=None, platform="threads"):
    """Problems that make a single post unpublishable."""
    if platform == "instagram":
        return check_instagram_post(post, root)
    backend = backend or BACKEND
    if backend not in CAN:
        return ["unknown PUBLISH_BACKEND %r (use one of %s)" % (backend, sorted(CAN))]
    errors = []
    pid = post.get("id")
    if not pid or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", pid):
        errors.append("id must be lowercase letters, digits and dashes")
    if post.get("kind") not in KINDS:
        errors.append("kind must be one of %s" % sorted(KINDS))
    try:
        parse_time(post.get("publish_at"))
    except ValueError as exc:
        errors.append(str(exc))

    text = post.get("text") or ""
    if not text.strip():
        errors.append("text is empty")
    if len(text) > MAX_TEXT:
        errors.append("text is %d characters (max %d)" % (len(text), MAX_TEXT))
    # Emoji outside the BMP count double in UTF-16; stay safe if Meta counts that way.
    utf16 = len(text.encode("utf-16-le")) // 2
    if utf16 > MAX_TEXT:
        errors.append("text is %d UTF-16 units (max %d)" % (utf16, MAX_TEXT))
    if len(LINK_RE.findall(text)) > MAX_LINKS:
        errors.append("more than %d links" % MAX_LINKS)

    tag = post.get("topic_tag")
    if tag is not None and (not tag.strip() or len(tag) > 50 or "." in tag or "&" in tag):
        errors.append("topic_tag must be 1-50 characters without '.' or '&'")

    poll = post.get("poll")
    image = post.get("image")
    if poll is not None:
        if "polls" not in CAN[backend]:
            errors.append("the %s backend cannot post polls; ask for answers in the comments" % backend)
        if image:
            errors.append("polls only work on text-only posts")
        if not isinstance(poll, list) or not 2 <= len(poll) <= 4:
            errors.append("poll needs 2-4 options")
        else:
            for option in poll:
                if not isinstance(option, str) or not 1 <= len(option) <= MAX_POLL_OPTION:
                    errors.append("poll option %r must be 1-%d characters" % (option, MAX_POLL_OPTION))
            if len(set(poll)) != len(poll):
                errors.append("poll options must be distinct")
        if post.get("answer") is not None and post.get("answer") not in (poll or []):
            errors.append("answer %r is not one of the poll options" % post.get("answer"))

    if image:
        path = os.path.join(root, image)
        if not os.path.isfile(path):
            errors.append("image %s not found" % image)
        else:
            if os.path.getsize(path) > MAX_IMAGE_BYTES:
                errors.append("image is larger than 8 MB")
            width = png_or_jpeg_width(path)
            if width is None:
                errors.append("image must be PNG or JPEG")
            elif width < MIN_IMAGE_WIDTH:
                errors.append("image is %d px wide (min %d)" % (width, MIN_IMAGE_WIDTH))
        if not (post.get("alt_text") or "").strip():
            errors.append("image posts need alt_text")
        elif len(post["alt_text"]) > 1000:
            errors.append("alt_text is longer than 1000 characters")

    if post.get("kind") == "reveal" and not post.get("reply_to"):
        errors.append("a reveal needs reply_to")
    if post.get("kind") == "reply":
        if "replies" not in CAN[backend]:
            errors.append("the %s backend cannot reply to comments" % backend)
        elif not post.get("reply_to_media_id"):
            errors.append("a reply to a comment needs reply_to_media_id")
    return errors


def check_queue(posts, published=None, backend=None, platform="threads"):
    """Cross-post problems: duplicates, reveal linkage, spoilers.

    published maps post id -> text for everything already in the log.
    """
    errors = []
    by_id = {}
    for post in posts:
        pid = post.get("id")
        for problem in check_post(post, backend=backend, platform=platform):
            errors.append("%s: %s" % (pid, problem))
        if pid in by_id:
            errors.append("%s: duplicate id" % pid)
        by_id[pid] = post

    seen = {normalize(text): "published post %s" % pid
            for pid, text in (published or {}).items() if pid not in by_id}
    for post in posts:
        key = normalize(post.get("text"))
        if key in seen:
            errors.append("%s: same text as %s" % (post["id"], seen[key]))
        seen.setdefault(key, post["id"])

    revealed = set()
    for post in posts:
        parent_id = post.get("reply_to")
        if not parent_id:
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            errors.append("%s: reply_to %s is not in the queue" % (post["id"], parent_id))
            continue
        revealed.add(parent_id)
        try:
            gap = parse_time(post["publish_at"]) - parse_time(parent["publish_at"])
        except (KeyError, ValueError):
            continue
        min_gap = POLL_OPEN if parent.get("poll") else timedelta(hours=1)
        if gap < min_gap:
            errors.append("%s: published %s after its quiz; needs at least %s" % (post["id"], gap, min_gap))
        answer = parent.get("answer")
        if post.get("kind") == "reveal" and answer and answer not in post.get("text", ""):
            errors.append("%s: reveal does not mention the answer %r" % (post["id"], answer))

    for post in posts:
        if platform == "threads" and post.get("kind") in NEEDS_REVEAL and post["id"] not in revealed:
            errors.append("%s: quiz has no reveal" % post["id"])
    return errors


def published_from_log(path=LOG_PATH):
    published = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    event = json.loads(line)
                    if event.get("event") == "published" and event.get("text"):
                        published[event["id"]] = event["text"]
    return published


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--platform", choices=sorted(QUEUES), help="check one platform (default: all)")
    args = parser.parse_args(argv)

    failed = False
    for platform in [args.platform] if args.platform else sorted(QUEUES, reverse=True):
        posts = load_queue(QUEUES[platform])
        errors = check_queue(posts, published_from_log(LOGS[platform]), platform=platform)
        for line in errors:
            print("ERROR", platform, line)
        print("%s: %d posts checked, %d problems" % (platform, len(posts), len(errors)))
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
