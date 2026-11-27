"""Mechanical quality checks for the post queue.

Run before content is committed (and in CI on every push). The publisher calls
check_post() again right before publishing, so a broken post fails alone
instead of blocking the whole queue.

Limits come from the Threads API docs (checked 2026-11-02): text <= 500 chars,
poll 2-4 options of 1-25 chars on text-only posts, <= 5 links, images JPEG/PNG
<= 8 MB and >= 320 px wide, topic tag without '.' or '&'.

What a post may use depends on the publishing backend (PUBLISH_BACKEND, see
tools/publish.py): only the direct Threads API can post polls and replies to
comments (kind "reply"). On both backends a reveal is a reply under its quiz.

style_problems() counts the marks that make a text read as generated (quotation
marks, long dashes, colons, a period on every line). The queue check applies it
to posts from STYLE_FROM on; tools/comments.py applies it to every reply.

student_problems() keeps a post about the teacher's students inside what the
teacher has told (strategy/students.json). It is part of check_post(), so the
publisher holds such a post back too: nothing made up about real people goes out.
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
# A Reel (from 2026-11-27, tools/render_reel.py): Meta's Reels spec, read 2026-11-24, asks for MP4 with
# its index (moov) first and no edit lists, H.264 or HEVC, 23-60 fps, AAC at <= 48 kHz in 1-2 channels,
# 3 s to 15 min, <= 300 MB, and a JPEG cover <= 8 MB, 9:16 recommended. Ours are 1080x1920 and short,
# with sound (Instagram shows muted reels less), and a file under GitHub's 50 MB warning.
IG_REEL_SIZE = (1080, 1920)
IG_REEL_SECONDS = (3, 90)
IG_REEL_FPS = (23, 60)
IG_REEL_MAX_BYTES = 50 * 1024 * 1024
REEL_SWIPE_RE = re.compile(r"листа(й|йте|ть)\b|слайд|свайп", re.I)  # a video has no slides to swipe

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

# How the text looks (STRATEGY.md §2). Measured on 248 real Russian posts and replies about learning
# English, read on Threads on 2026-11-13: 13% end with a period and 18% of their lines do, about one
# in ten has a quotation mark or a long dash, one in six a colon, none a semicolon. Ours had all of
# them in nearly every post. Posts dated before STYLE_FROM were written under the old rule and stay.
STYLE_FROM = "2026-11-14T00:00:00Z"
MAX_QUOTE_PAIRS = 1
MAX_LONG_DASHES = 1
MAX_COLONS = 2
MAX_PERIOD_LINES = 0.25     # share of a post's lines that may end with a period
MAX_REPLY_EMOJI = 2
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⭐⭕]")
FORM_LETTER_RE = re.compile(r"\s*(здравствуйте|добрый\s+(день|вечер)|доброе\s+утро|приветствую)", re.I)

# Posts about the teacher's own students (STRATEGY.md §1 and §3, 🎓 Мои ученики). The facts and the
# group keys live in strategy/students.json and nowhere else. A post is about them when its topic
# says so, it carries the series marker, or it speaks of «мои ученики» in any case form.
STUDENTS_PATH = os.path.join(ROOT, "strategy", "students.json")
STUDENTS_ALL = "all"        # topic "students: all" (several groups at once), and the file's key for
#                             what the teacher said about their students as a whole
STUDENT_TOPIC_RE = re.compile(r"\s*students:\s*(.*?)\s*$", re.I)
MY_STUDENTS_RE = re.compile(r"🎓|\bмо(?:и|их|им|ими|й|его|ему|ём|ем|я|ей|ю)\s+учени[кц]", re.I)
# Singular forms only: «учеников», «учениками» and «ученицы» don't match.
ONE_STUDENT_RE = re.compile(r"\bученик(?:а|у|ом|е)?\b|\bучениц(?:а|е|у|ей|ой)\b"
                            r"|\bстудент(?:а|у|ом|е|ка|ке|ку|кой)?\b", re.I)


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
    if post.get("video") is not None:
        errors.extend(reel_problems(post, root))
        errors.extend(student_problems(post))
        return errors

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
    errors.extend(student_problems(post))
    return errors


def mp4_boxes(data, start=0, end=None):
    """(type, payload start, payload end) of each MP4 box between start and end."""
    end = len(data) if end is None else end
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        head = 8
        if size == 1:
            size, head = struct.unpack(">Q", data[pos + 8:pos + 16])[0], 16
        elif size == 0:
            size = end - pos
        if size < head or pos + size > end:
            raise ValueError("broken %r box at byte %d" % (kind, pos))
        yield kind.decode("latin-1"), pos + head, pos + size
        pos += size


def _box(data, start, end, path):
    """The payload (start, end) of the first box down a path such as "mdia/minf/stbl", or None."""
    for name in path.split("/"):
        found = next(((s, e) for kind, s, e in mp4_boxes(data, start, end) if kind == name), None)
        if found is None:
            return None
        start, end = found
    return start, end


def mp4_info(path):
    """What QC needs from an MP4, read from its boxes: their order, edit lists, the duration, and per
    track its handler (vide, soun), codec, frame size, frames per second or sample rate and channels."""
    with open(path, "rb") as fh:
        data = fh.read()
    top = [(kind, s, e) for kind, s, e in mp4_boxes(data)]
    info = {"order": [kind for kind, _, _ in top], "edit_lists": False, "tracks": []}
    moov = next(((s, e) for kind, s, e in top if kind == "moov"), None)
    if moov is None:
        return info
    mvhd = _box(data, moov[0], moov[1], "mvhd")
    if mvhd:
        version = data[mvhd[0]]
        timescale, duration = (struct.unpack(">IQ", data[mvhd[0] + 20:mvhd[0] + 32]) if version == 1
                               else struct.unpack(">II", data[mvhd[0] + 12:mvhd[0] + 20]))
        info["seconds"] = duration / timescale if timescale else 0
    for kind, s, e in mp4_boxes(data, *moov):
        if kind != "trak":
            continue
        if _box(data, s, e, "edts/elst"):
            info["edit_lists"] = True
        track = {}
        tkhd = _box(data, s, e, "tkhd")
        if tkhd:
            width, height = struct.unpack(">II", data[tkhd[1] - 8:tkhd[1]])
            track["size"] = (width >> 16, height >> 16)
        hdlr = _box(data, s, e, "mdia/hdlr")
        track["handler"] = data[hdlr[0] + 8:hdlr[0] + 12].decode("latin-1") if hdlr else None
        mdhd = _box(data, s, e, "mdia/mdhd")
        stsd = _box(data, s, e, "mdia/minf/stbl/stsd")
        stts = _box(data, s, e, "mdia/minf/stbl/stts")
        if stsd:
            entry = stsd[0] + 8
            track["codec"] = data[entry + 4:entry + 8].decode("latin-1")
            if track["handler"] == "soun":
                track["channels"] = struct.unpack(">H", data[entry + 24:entry + 26])[0]
                track["rate"] = struct.unpack(">I", data[entry + 32:entry + 36])[0] >> 16
        if mdhd and stts and track["handler"] == "vide":
            version = data[mdhd[0]]
            timescale, duration = (struct.unpack(">IQ", data[mdhd[0] + 20:mdhd[0] + 32]) if version == 1
                                   else struct.unpack(">II", data[mdhd[0] + 12:mdhd[0] + 20]))
            count = struct.unpack(">I", data[stts[0] + 4:stts[0] + 8])[0]
            frames = sum(struct.unpack(">I", data[stts[0] + 8 + 8 * i:stts[0] + 12 + 8 * i])[0] for i in range(count))
            track["fps"] = frames * timescale / duration if duration else 0
        info["tracks"].append(track)
    return info


def reel_problems(post, root=ROOT):
    """Problems that make an Instagram Reel unpublishable: the video, its cover and the fields."""
    from PIL import Image

    errors = []
    if post.get("images"):
        errors.append("a post is a carousel (images) or a Reel (video), not both")
    alts = post.get("alt_text")
    if not isinstance(alts, list) or not alts or not all(isinstance(a, str) and a.strip() for a in alts):
        errors.append("alt_text must be a list describing each slide of the Reel (QC reads it; "
                      "Instagram has no alt text for Reels)")
    video = post.get("video") or ""
    path = os.path.join(root, video)
    if not video.endswith(".mp4"):
        errors.append("video must be an .mp4 made by tools/render_reel.py")
    elif not os.path.isfile(path):
        errors.append("video %s not found" % video)
    elif os.path.getsize(path) > IG_REEL_MAX_BYTES:
        errors.append("%s is larger than %d MB" % (video, IG_REEL_MAX_BYTES // 2 ** 20))
    else:
        try:
            info = mp4_info(path)
        except (ValueError, struct.error) as exc:
            info = None
            errors.append("%s is not a readable MP4 (%s)" % (video, exc))
        if info:
            order = info["order"]
            if not order or order[0] != "ftyp" or "moov" not in order or "mdat" not in order:
                errors.append("%s is not an MP4 with ftyp, moov and mdat boxes" % video)
            elif order.index("moov") > order.index("mdat"):
                errors.append("%s has its index (moov) after the media; Meta wants it first (faststart)" % video)
            if info["edit_lists"]:
                errors.append("%s has edit lists, which Meta's Reels spec rules out" % video)
            low, high = IG_REEL_SECONDS
            if not low <= info.get("seconds", 0) <= high:
                errors.append("%s lasts %.1f s; a Reel here is %d-%d s" % (video, info.get("seconds", 0), low, high))
            videos = [t for t in info["tracks"] if t.get("handler") == "vide"]
            sounds = [t for t in info["tracks"] if t.get("handler") == "soun"]
            if len(videos) != 1 or videos[0].get("codec") not in ("avc1", "hvc1", "hev1"):
                errors.append("%s needs one H.264 or HEVC video track" % video)
            else:
                if videos[0].get("size") != IG_REEL_SIZE:
                    errors.append("%s is %dx%d; a Reel here is 1080x1920" % ((video,) + tuple(videos[0].get("size") or (0, 0))))
                fps = videos[0].get("fps", 0)
                if not IG_REEL_FPS[0] <= fps <= IG_REEL_FPS[1]:
                    errors.append("%s runs at %.1f fps; Meta takes 23-60" % (video, fps))
            if len(sounds) != 1 or sounds[0].get("codec") != "mp4a":
                errors.append("%s needs one AAC sound track (Instagram shows muted reels less)" % video)
            elif sounds[0].get("rate", 0) > 48000 or sounds[0].get("channels") not in (1, 2):
                errors.append("%s sound must be at most 48 kHz, mono or stereo" % video)
    cover = post.get("cover") or ""
    cover_path = os.path.join(root, cover)
    if not cover:
        errors.append("a Reel needs a cover (the JPEG tools/render_reel.py writes next to the video)")
    elif not os.path.isfile(cover_path):
        errors.append("cover %s not found" % cover)
    else:
        with Image.open(cover_path) as im:
            if im.format != "JPEG" or im.size != IG_REEL_SIZE:
                errors.append("cover %s must be a 1080x1920 JPEG" % cover)
        if os.path.getsize(cover_path) > MAX_IMAGE_BYTES:
            errors.append("cover %s is larger than 8 MB" % cover)
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
    errors.extend(student_problems(post))
    return errors


def load_students(path=STUDENTS_PATH):
    """All that the teacher has told about their students.

    {"groups": {key: {"facts": [...]}}, "all": {"facts": [...]}}: `groups` is what holds for each
    group, and `all` (it may be missing) is what holds for the students as a whole.
    """
    with open(path, encoding="utf-8") as fh:
        students = json.load(fh)
    students["groups"]          # a file without groups is broken: the caller reports the KeyError
    return students


def student_problems(post, students=None, path=STUDENTS_PATH):
    """Where a post about the teacher's students goes beyond what the teacher has told.

    The countable part only: the post names its group in `topic`, carries no number that the
    facts don't give (the group's own, and those about the students as a whole), no quotation
    marks (a quote would be invented speech) and speaks of several students, never of one.
    Whether the words add a detail still takes a reader (STRATEGY.md §8). A post that doesn't
    speak of the students is left alone.
    """
    alt = post.get("alt_text") or ""
    text = post.get("text") or ""
    blob = "\n".join([text] + (alt if isinstance(alt, list) else [alt]))
    tagged = STUDENT_TOPIC_RE.match(post.get("topic") or "")
    if not tagged and not MY_STUDENTS_RE.search(blob):
        return []
    if students is None:
        try:
            students = load_students(path)
        except (OSError, ValueError, KeyError) as exc:
            return ["strategy/students.json could not be read (%s), and it is the only source for a post "
                    "about the teacher's students" % exc.__class__.__name__]

    groups = students["groups"]
    shared = (students.get(STUDENTS_ALL) or {}).get("facts", [])
    problems = []
    known = sorted(groups)
    key = tagged.group(1).lower() if tagged else None
    facts = None
    if key is None:
        problems.append('speaks of the teacher\'s students, so `topic` must be "students: <group>", with a '
                        'group from strategy/students.json (%s) or "%s"' % (", ".join(known), STUDENTS_ALL))
    elif key == STUDENTS_ALL:
        facts = shared + [fact for name in known for fact in groups[name]["facts"]]
    elif key in groups:
        facts = shared + groups[key]["facts"]
    else:
        problems.append('unknown group %r in `topic`: strategy/students.json has %s (or "%s")'
                        % (key, ", ".join(known), STUDENTS_ALL))
    if facts is not None:
        told = set(re.findall(r"\d+", " ".join(facts)))
        for number in sorted(set(re.findall(r"\d+", blob)) - told):
            problems.append("the number %s is not among the teacher's facts for %s (strategy/students.json)"
                            % (number, key))
    if re.search('[«“„"]', text):
        problems.append("quotation marks in a post about students: a quote would be invented speech")
    one = ONE_STUDENT_RE.search(blob)
    if one:
        problems.append("tells about one student («%s»): the teacher told us about groups, so write about "
                        "several students, never one person's story" % one.group(0))
    return problems


def style_problems(text, kind="post"):
    """Marks that make a text read as generated rather than typed by a person.

    kind "reply" (a public reply) and "dm" are held tighter than "post": no long dash, one colon and
    two emoji at most. Only a public reply may not open like a form letter.
    """
    text = (text or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    short = kind != "post"
    problems = []

    quotes = text.count("«") + text.count("“") + text.count("„") + text.count('"') // 2
    if quotes > MAX_QUOTE_PAIRS:
        problems.append("%d pairs of quotation marks (max %d): English needs none, and a Russian phrase "
                        "can stand on its own line" % (quotes, MAX_QUOTE_PAIRS))
    dashes = text.count("—") + len(re.findall(r"\s–\s", text))
    max_dashes = 0 if short else MAX_LONG_DASHES
    if dashes > max_dashes:
        problems.append("%d long dashes (max %d): start a new line or sentence, or put a hyphen between "
                        "a word and its translation" % (dashes, max_dashes))
    colons = len(re.findall(r":(?=\s|$)", text))
    max_colons = 1 if short else MAX_COLONS
    if colons > max_colons:
        problems.append("%d colons (max %d)" % (colons, max_colons))
    if ";" in text:
        problems.append("a semicolon: nobody types those here")

    period_lines = [line for line in lines if re.search(r"(?<!\.)\.$", line)]
    if lines[-1] in period_lines:
        problems.append("the last line ends with a period")
    elif not short and len(period_lines) > max(1, int(len(lines) * MAX_PERIOD_LINES)):
        problems.append("%d of %d lines end with a period (at most a quarter): the line break already "
                        "ends the thought" % (len(period_lines), len(lines)))

    if short and len(EMOJI_RE.findall(text)) > MAX_REPLY_EMOJI:
        problems.append("more than %d emoji in a reply" % MAX_REPLY_EMOJI)
    if kind == "reply" and FORM_LETTER_RE.match(text):
        problems.append("opens like a form letter: answer what the person said, without a greeting")
    return problems


def check_queue(posts, published=None, backend=None, platform="threads"):
    """Cross-post problems: duplicates, reveal linkage, spoilers, and how the text looks.

    published maps post id -> text for everything already in the log. The style check lives here
    and not in check_post, so the publisher never holds a post back over a comma.
    """
    errors = []
    by_id = {}
    for post in posts:
        pid = post.get("id")
        for problem in check_post(post, backend=backend, platform=platform):
            errors.append("%s: %s" % (pid, problem))
        when = post.get("publish_at")
        if isinstance(when, str) and when >= STYLE_FROM:
            for problem in style_problems(post.get("text")):
                errors.append("%s: %s" % (pid, problem))
        if post.get("video") is not None and REEL_SWIPE_RE.search(post.get("text") or ""):
            errors.append("%s: the caption of a Reel talks about slides or swiping; say the answer comes at "
                          "the end of the video" % pid)
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
