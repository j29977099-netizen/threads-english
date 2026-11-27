"""Render an Instagram Reel (1080x1920 MP4 and its cover) from slide specs.

From 2026-11-27 Instagram gets one Reel a day instead of a carousel. Instagram mostly shows a new
account to strangers through Reels, and its ranking page says it shows less of reels that have
borders, are muted, are mostly text or were already posted. So the slides of a Reel are the same
cards tools/render_cards.py draws, in their 1080x1350 layout, but:

- the background (photo or the theme's gradient) fills the whole 9:16 frame, with no borders;
- the layout box sits at y=230, inside the feed's 4:5 crop and clear of the Reels buttons;
- the background zooms in slowly under still text, and the slides change with a short fade;
- a first slide that leads to more slides counts down on its prompt line (Ответ через 7 ... 1);
- the sound is made here: a tick each second of the countdown, a chime when the answer comes, a
  whoosh between slides and a very quiet room sound throughout. No music.

Each slide is drawn twice, over black and over white, which gives its text layer with exact
transparency, so the text can sit still over the moving background.

A spec in content/cards/*.json:

    {"template": "reel", "out": "media/ig/<date>-<slug>.mp4",
     "countdown": "Ответ через", "cover_prompt": "Ответ в конце ролика",
     "slides": [<card spec>, <card spec>]}

countdown and cover_prompt are optional (those are the defaults). The cover is the first slide with
cover_prompt on its prompt line, saved next to the video as <date>-<slug>-cover.jpg. A Reel refuses
swipe words (a video has no slides to swipe) and photos marked ai_generated in brand/photos/index.json
(Meta wants AI-made video labelled). It needs ffmpeg (see find_ffmpeg).

    python tools/render_cards.py content/cards/ig-<date>.json    # renders cards and reels alike
"""
import json
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
import wave
from array import array

from PIL import Image, ImageChops

import render_cards as rc
from qc import REEL_SWIPE_RE

W, H = 1080, 1920
BOX_TOP = 230        # where the card's 1080x1350 layout sits: label at 286, text ends by ~1430, handle by ~1520
FPS = 30
ZOOM = 0.06          # the background grows 6% over the whole video
FADE = 0.4           # seconds between two slides: the old text fades out, then the new one in
FADE_OUT = 0.16
MIN_READ, MAX_READ = 4.0, 12.0
MAX_SLIDES = 4
RATE = 48000
COUNTDOWN = "Ответ через"
COVER_PROMPT = "Ответ в конце ролика"
PROMPT_FIELD = {"quiz": "prompt", "chat": "prompt", "list": "cta"}  # the line a countdown takes
PHOTO_INDEX = os.path.join(rc.ROOT, "brand", "photos", "index.json")


def cover_path(out):
    return re.sub(r"\.mp4$", "", out) + "-cover.jpg"


def drawn_text(spec):
    """The words a template puts on the card (a photo quiz shows situation, bubble and question)."""
    t = spec["template"]
    if t == "quiz" and spec.get("photo"):
        return [spec.get("situation"), spec.get("bubble") or spec.get("title"), spec.get("question"),
                spec.get("options")]
    if t == "chat":
        return [spec.get("title"), [m.get("text") for m in spec.get("messages", [])], spec.get("question")]
    fields = {"quiz": ("title", "sentence", "options"), "answer": ("title", "answer", "why", "examples"),
              "list": ("title", "items"), "phrase": ("phrase", "meaning", "examples", "note"),
              "versus": ("title", "textbook", "real_question", "real_answers", "note"),
              "mistakes": ("title", "items")}[t]
    return [spec.get(k) for k in fields]


def words(spec):
    return sum(len(s.split()) for s in rc.strings_in(drawn_text(spec)) if s)


def read_time(spec):
    """Seconds to read a slide: a second to find your way, then about 0.27 s a word, 4-12 s."""
    return min(MAX_READ, max(MIN_READ, 1.0 + 0.27 * words(spec)))


def plan(spec):
    """The slides as shown, in order: [(card spec, seconds, countdown or None)], and the cover spec.

    Refuses what can't go out as a Reel."""
    slides = spec.get("slides") or []
    out = spec.get("out") or ""
    if not out.endswith(".mp4"):
        raise ValueError("%s: a reel's out must be an .mp4 path" % out)
    if not 1 <= len(slides) <= MAX_SLIDES:
        raise ValueError("%s: a reel needs 1-%d slides" % (out, MAX_SLIDES))
    with open(PHOTO_INDEX, encoding="utf-8") as fh:
        photos = {entry["file"]: entry for entry in json.load(fh)}
    countdown = spec.get("countdown") or COUNTDOWN
    field = PROMPT_FIELD.get(slides[0].get("template")) if len(slides) > 1 else None
    shown = []
    for i, slide in enumerate(slides):
        if slide.get("template") not in rc.TEMPLATES or slide["template"] == "avatar":
            raise ValueError("%s: slide %d has no card template" % (out, i + 1))
        if slide.get("size"):
            raise ValueError("%s: slide %d sets its own size; a reel's slides use the card size" % (out, i + 1))
        photo = slide.get("photo")
        if photo and photo not in photos:
            raise ValueError("%s: photo %s is not in brand/photos/index.json" % (out, photo))
        if photo and photos[photo].get("ai_generated"):
            raise ValueError("%s: %s is AI-made, and Meta wants AI-made video labelled; use a real photo "
                             "or the gradient" % (out, photo))
        seconds = read_time(slide)
        slide = dict(slide, out="%s, slide %d" % (out, i + 1))  # where a template's "too long" points
        if i == 0 and field:
            seconds = max(int(MIN_READ), round(seconds))
            slide[field] = "%s %d" % (countdown, seconds)
        for text in rc.strings_in(slide):
            if REEL_SWIPE_RE.search(text):
                raise ValueError("%s: slide %d says «%s», but a video has no slides to swipe" % (out, i + 1, text))
        shown.append((slide, seconds, field if i == 0 and field else None))
    cover = dict(shown[0][0])
    if shown[0][2]:
        cover[shown[0][2]] = spec.get("cover_prompt") or COVER_PROMPT
    if REEL_SWIPE_RE.search(" ".join(rc.strings_in(cover))):
        raise ValueError("%s: the cover prompt mentions swiping" % out)
    return shown, cover, countdown


# ----- pictures -----

class FlatCard(rc.Card):
    """A card on one flat colour instead of its photo or gradient, so its text layer can be lifted off."""

    flat = (0, 0, 0)

    def background(self):
        self.img.paste(Image.new("RGB", self.img.size, self.flat), (0, 0))


class Layer:
    """A slide's text layer on the 9:16 frame: premultiplied colour and its coverage."""

    def __init__(self, colour, matte):
        self.colour, self.matte = colour, matte
        self.clear = Image.merge("RGB", [ImageChops.invert(matte)] * 3)

    def over(self, base):
        return ImageChops.add(self.colour, ImageChops.multiply(base, self.clear))

    def faded(self, k):
        return Layer(self.colour.point(lambda v: round(v * k)), self.matte.point(lambda v: round(v * k)))


def text_layer(slide, brand):
    shots = []
    for flat in ((0, 0, 0), (255, 255, 255)):
        card = FlatCard(brand, None, slide.get("theme") or slide["template"], slide.get("photo"), slide.get("focus"),
                        slide.get("shade", 1.0))
        card.flat = flat
        rc.TEMPLATES[slide["template"]](card, slide)
        shots.append(card.img)
    # over black a pixel is a*colour, over white a*colour + (1-a)*255: the difference gives a.
    # Both halve by averaging (reduce), which keeps colour and coverage exact; a sharpening filter
    # (LANCZOS) would clip its overshoot differently in each and leave fringes at sharp edges.
    coverage = ImageChops.invert(ImageChops.subtract(shots[1], shots[0]).convert("L"))
    colour = Image.new("RGB", (W, H))
    colour.paste(shots[0].reduce(rc.SCALE), (0, BOX_TOP))
    matte = Image.new("L", (W, H))
    matte.paste(coverage.reduce(rc.SCALE), (0, BOX_TOP))
    return Layer(colour, matte)


class Backdrop:
    """The slide's photo or gradient filling the frame. A photo zooms in slowly; a gradient stays still,
    because its fine grain on the move would make every pixel of every frame new (a 3x larger file)."""

    def __init__(self, slide, brand):
        card = rc.Card(brand, (W, H), slide.get("theme") or slide["template"], slide.get("photo"), slide.get("focus"),
                       slide.get("shade", 1.0), box=(BOX_TOP, brand["size"][1]))
        card.background()
        self.moving = bool(slide.get("photo"))
        if self.moving:
            self.big = card.img.resize((round(W * (1 + ZOOM)), round(H * (1 + ZOOM))), Image.LANCZOS)
        self.still = self.at(1.0) if self.moving else card.img.resize((W, H), Image.LANCZOS)

    def at(self, z):
        """The background zoomed in by z (1 to 1 + ZOOM) around the centre."""
        if not self.moving:
            return self.still
        cw, ch = self.big.width / z, self.big.height / z
        x0, y0 = (self.big.width - cw) / 2, (self.big.height - ch) / 2
        return self.big.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def smooth(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


# ----- sound -----

def _tone(buf, at, freq, amp, decay, length, partials=((1.0, 1.0),), pan=0.0):
    start = int(at * RATE)
    for i in range(int(length * RATE)):
        j = start + i
        if j >= len(buf[0]):
            break
        t = i / RATE
        v = sum(a * math.sin(2 * math.pi * freq * m * t) * math.exp(-t / (decay / m ** 0.5)) for m, a in partials)
        v *= amp * min(1.0, t / 0.002)
        buf[0][j] += v * (1 - max(0.0, pan))
        buf[1][j] += v * (1 + min(0.0, pan))


def tick(buf, at, amp):
    """A soft wooden tick."""
    _tone(buf, at, 1180, amp, 0.018, 0.09, partials=((1.0, 1.0), (2.41, 0.35)))


def chime(buf, at):
    """Two bell notes: the answer is here."""
    bell = ((1.0, 1.0), (2.76, 0.32), (5.40, 0.12))
    _tone(buf, at, 1046.5, 0.30, 0.9, 1.6, bell, pan=-0.15)
    _tone(buf, at + 0.11, 1318.5, 0.30, 0.9, 1.6, bell, pan=0.15)


def whoosh(buf, at, length=0.35, amp=0.10):
    """Air rising into the moment at."""
    rng = random.Random(3)
    start = int((at - length) * RATE)
    low = 0.0
    for i in range(int((length + 0.12) * RATE)):
        t = i / RATE
        env = (t / length) ** 2 if t < length else math.exp(-(t - length) / 0.04)
        low += (0.02 + 0.25 * min(1.0, t / length)) * (rng.uniform(-1, 1) - low)
        j = start + i
        if 0 <= j < len(buf[0]):
            buf[0][j] += amp * env * low
            buf[1][j] += amp * env * low


def room(buf, amp=0.012):
    """A very quiet low room sound, so the video is never silent."""
    rng = random.Random(5)
    for ch in buf:
        brown = 0.0
        for j in range(len(ch)):
            brown = 0.995 * brown + 0.05 * rng.uniform(-1, 1)
            ch[j] += amp * brown * 4


def soundtrack(path, total, shown):
    n = int(round(total * RATE))
    buf = [[0.0] * n, [0.0] * n]
    room(buf)
    at = 0.0
    for i, (_, seconds, counting) in enumerate(shown):
        if counting:
            for s in range(int(seconds)):
                tick(buf, at + s + 0.02, 0.20 if seconds - s <= 3 else 0.10)
        at += seconds
        if i + 1 < len(shown):
            whoosh(buf, at)
            if counting:
                chime(buf, at + FADE_OUT)  # as the answer starts to show
            at += FADE
    peak = max(1e-9, max(abs(v) for ch in buf for v in ch))
    k = min(1.0, 0.5 / peak)  # never louder than -6 dBFS
    pcm = array("h")
    for left, right in zip(*buf):
        pcm.append(int(max(-1.0, min(1.0, left * k)) * 32767))
        pcm.append(int(max(-1.0, min(1.0, right * k)) * 32767))
    with wave.open(path, "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(RATE)
        fh.writeframes(pcm.tobytes())


# ----- the video -----

def find_ffmpeg():
    """Where ffmpeg is: $FFMPEG, else on the PATH, else the copy the imageio-ffmpeg package ships
    (python -m pip install imageio-ffmpeg, as the cloud routine does). None if nowhere."""
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    return imageio_ffmpeg.get_ffmpeg_exe()


def ffmpeg():
    exe = find_ffmpeg()
    if not exe:
        raise RuntimeError("ffmpeg not found: install it, set FFMPEG to its path, or "
                           "python -m pip install imageio-ffmpeg (see strategy/ROUTINE.md)")
    return exe


def encode_command(audio, out):
    """H.264 and AAC as Meta's Reels spec asks: 4:2:0, closed GOP, 30 fps, 48 kHz, index first, no edit lists."""
    return [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
            "-i", audio, "-map", "0:v", "-map", "1:a",
            "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
            "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-profile:v", "high", "-level", "4.2",
            "-g", str(FPS * 10), "-x264-params", "open-gop=0:colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-c:a", "aac", "-b:a", "128k", "-ar", str(RATE), "-ac", "2",
            "-movflags", "+faststart", "-use_editlist", "0", "-map_metadata", "-1", "-shortest", out]


def render(spec, brand=None):
    """Write the reel and its cover; returns the video's path."""
    brand = brand or rc.load_brand()
    shown, cover, countdown = plan(spec)
    out = os.path.join(rc.ROOT, spec["out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)

    backgrounds, layers, timeline = {}, [], []
    for slide, seconds, counting in shown:  # a background is drawn once, however many slides share it
        key = json.dumps([slide.get("theme") or slide["template"], slide.get("photo"), slide.get("focus"),
                          slide.get("shade", 1.0)])
        if key not in backgrounds:
            backgrounds[key] = Backdrop(slide, brand)
        if counting:
            texts = [text_layer(dict(slide, **{counting: "%s %d" % (countdown, n)}), brand)
                     for n in range(int(seconds), 0, -1)]
        else:
            texts = [text_layer(slide, brand)]
        layers.append(texts)
        timeline.append((backgrounds[key], seconds))
    total = sum(seconds for _, seconds in timeline) + FADE * (len(timeline) - 1)

    text_layer(cover, brand).over(timeline[0][0].still).save(cover_path(out), "JPEG", quality=92, optimize=True)

    def frame_at(t):
        z = 1 + ZOOM * t / total
        at = 0.0
        for i, ((bg, seconds), texts) in enumerate(zip(timeline, layers)):
            if t < at + seconds or i == len(timeline) - 1:
                second = min(len(texts) - 1, int(t - at)) if len(texts) > 1 else 0
                return texts[second].over(bg.at(z))
            if t < at + seconds + FADE:
                k = (t - at - seconds) / FADE
                nxt_bg = timeline[i + 1][0]
                base = bg.at(z) if nxt_bg is bg else Image.blend(bg.at(z), nxt_bg.at(z), smooth(k))
                if t < at + seconds + FADE_OUT:
                    return texts[-1].faded(smooth(1 - (t - at - seconds) / FADE_OUT)).over(base)
                return layers[i + 1][0].faded(smooth((t - at - seconds - FADE_OUT) / (FADE - FADE_OUT))).over(base)
            at += seconds + FADE
        raise AssertionError("time %.2f is past the end" % t)

    frames = int(round(total * FPS))
    preview, marks, at = [], [], 0.0
    for _, seconds in timeline:
        marks.append(int((at + seconds - 0.5) * FPS))
        at += seconds + FADE
    with tempfile.TemporaryDirectory() as tmp:
        audio = os.path.join(tmp, "sound.wav")
        soundtrack(audio, frames / FPS, shown)
        enc = subprocess.Popen(encode_command(audio, out), stdin=subprocess.PIPE)
        try:
            for f in range(frames):
                frame = frame_at(f / FPS)
                enc.stdin.write(frame.tobytes())
                if f in marks:
                    preview.append(frame.resize((W // 2, H // 2), Image.LANCZOS))
        finally:
            enc.stdin.close()
            if enc.wait():
                raise RuntimeError("ffmpeg could not encode %s" % spec["out"])

    sheet = Image.new("RGB", ((W // 2 + 20) * (len(preview) + 1) - 20, H // 2), rc.rgb(brand["colors"]["ink"]))
    with Image.open(cover_path(out)) as img:
        preview.insert(0, img.resize((W // 2, H // 2), Image.LANCZOS))
    for i, img in enumerate(preview):
        sheet.paste(img, (i * (W // 2 + 20), 0))
    sheet_path = os.path.join(tempfile.gettempdir(), os.path.basename(out).replace(".mp4", "-preview.jpg"))
    sheet.save(sheet_path, "JPEG", quality=88)
    print("preview %s (cover, then the end of each slide): open it and check every word" % sheet_path)
    print("cover", os.path.relpath(cover_path(out), rc.ROOT))
    return out
