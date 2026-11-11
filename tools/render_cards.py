"""Render educational cards (1080x1350) from JSON specs in content/cards/.

Templates: quiz, versus, mistakes, answer, phrase, list, chat, avatar.

The look lives in brand/brand.json: one colour theme per template (a gradient, soft glows and
fine grain), Unbounded for titles, Onest for text and Caveat for handwritten notes. A spec can
borrow another template's colours with "theme": "<name>". A character a font lacks is drawn
with the fallback font, and a card with a character no font can draw is refused, so a card
never ships with missing-glyph boxes. A card whose text doesn't fit is refused too.

    python tools/render_cards.py content/cards/2026-11-09_week1.json
"""
import argparse
import json
import math
import os
import random
import sys

from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLANK = "___"
BLANK_EM = 2.6  # width of a blank, in font sizes
SCALE = 2  # cards are drawn at twice their size and scaled down: smooth curves and crisp small text
FALLBACK = "fallback"  # the font that draws what another font lacks (arrows, IPA)
FALLBACK_SCALE = {"hand": 0.72}  # the handwriting is small for its size; shrink borrowed glyphs to match
CAP_HALF = 0.36  # half the height of a capital letter, in font sizes
BADGES = ("pink", "orange", "mint", "blue")
_CMAPS = {}


def load_brand():
    with open(os.path.join(ROOT, "brand", "brand.json"), encoding="utf-8") as fh:
        return json.load(fh)


def rgb(value, alpha=None):
    """'#RRGGBB' as a tuple, with an alpha (0-255) when given."""
    value = value.lstrip("#")
    color = tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    return color + (alpha,) if alpha is not None else color


def font_file(entry):
    return entry if isinstance(entry, str) else entry["file"]


def cmap_of(path):
    if path not in _CMAPS:
        _CMAPS[path] = set(TTFont(os.path.join(ROOT, path)).getBestCmap())
    return _CMAPS[path]


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in ("out", "template", "theme"):
                yield from strings_in(item)


def missing_glyphs(spec, brand):
    """Characters no font can draw: each must be in the fallback font or in every other font."""
    fonts = brand["fonts"]
    fallback = cmap_of(font_file(fonts[FALLBACK]))
    others = [cmap_of(font_file(entry)) for kind, entry in fonts.items() if kind != FALLBACK]
    missing = set()
    for text in strings_in(spec):
        for ch in text:
            if not ch.isspace() and ord(ch) not in fallback and not all(ord(ch) in cmap for cmap in others):
                missing.add(ch)
    return sorted(missing)


class Card:
    """A canvas in card units (1080x1350); every drawing call takes card units."""

    def __init__(self, brand, size=None, theme=None):
        self.brand = brand
        self.w, self.h = size or brand["size"]
        self.m = brand["margin"]
        self.c = brand["colors"]
        themes = brand.get("themes", {})
        self.theme = themes.get(theme) or themes.get("default") or {}
        self.s = SCALE
        self.img = Image.new("RGB", (self.w * self.s, self.h * self.s), rgb(self.c["paper"]))
        self.draw = ImageDraw.Draw(self.img, "RGBA")
        self._fonts = {}

    # ----- text -----

    def font(self, kind, size):
        key = (kind, round(size * self.s))
        if key not in self._fonts:
            entry = self.brand["fonts"][kind]
            font = ImageFont.truetype(os.path.join(ROOT, font_file(entry)), key[1])
            if not isinstance(entry, str) and entry.get("wght"):
                font.set_variation_by_axes([entry["wght"]])
            self._fonts[key] = font
        return self._fonts[key]

    def runs(self, text, kind, size):
        """The text as (piece, font) runs: a character the font lacks goes to the fallback font."""
        own = cmap_of(font_file(self.brand["fonts"][kind]))
        pieces = []
        for ch in text:
            k = kind if ch.isspace() or ord(ch) in own else FALLBACK
            if pieces and pieces[-1][1] == k:
                pieces[-1][0] += ch
            else:
                pieces.append([ch, k])
        borrowed = size * FALLBACK_SCALE.get(kind, 1)
        return [(piece, self.font(k, size if k == kind else borrowed)) for piece, k in pieces]

    def tw(self, text, kind, size):
        return sum(self.draw.textlength(piece, font=font) for piece, font in self.runs(text, kind, size)) / self.s

    def ascent(self, kind, size):
        return self.font(kind, size).getmetrics()[0] / self.s

    def text(self, x, y, text, kind, size, fill, anchor="la", draw=None):
        """One line. anchor: l, m or r across; then a (y is the top), c (y is the middle of the capitals)."""
        draw = draw or self.draw
        runs = self.runs(text, kind, size)
        width = sum(draw.textlength(piece, font=font) for piece, font in runs)
        px = x * self.s - {"l": 0, "m": width / 2, "r": width}[anchor[0]]
        base = y * self.s + (self.font(kind, size).getmetrics()[0] if anchor[1] == "a" else size * self.s * CAP_HALF)
        for piece, font in runs:
            draw.text((px, base), piece, font=font, fill=fill, anchor="ls")
            px += draw.textlength(piece, font=font)
        return width / self.s

    def wrap(self, text, kind, size, width, balance=False):
        """Word-wrap to width; an explicit '\\n' forces a break. balance evens out the lines (no one-word last line)."""
        lines = self._wrap(text, kind, size, width)
        if balance and len(lines) > 1 and "\n" not in text:
            low, high = width * 0.45, width
            for _ in range(10):  # the narrowest width that needs no extra line
                mid = (low + high) / 2
                if len(self._wrap(text, kind, size, mid)) <= len(lines):
                    high = mid
                else:
                    low = mid
            lines = self._wrap(text, kind, size, high)
        return lines

    def _wrap(self, text, kind, size, width):
        lines = []
        space = self.tw(" ", kind, size)
        for segment in text.split("\n"):
            line, used = [], 0
            for word in segment.split():
                ww = size * BLANK_EM if word == BLANK else self.tw(word, kind, size)
                if line and used + space + ww > width:
                    lines.append(line)
                    line, used = [word], ww
                else:
                    used += (space if line else 0) + ww
                    line.append(word)
            if line:
                lines.append(line)
        return lines

    def line_width(self, line, kind, size):
        """The width of one line from wrap()."""
        widths = [size * BLANK_EM if word == BLANK else self.tw(word, kind, size) for word in line]
        return sum(widths) + self.tw(" ", kind, size) * (len(line) - 1)

    def paragraph(self, x, y, text, kind, size, fill, width, leading, blank_fill=None, balance=True):
        """Draw wrapped text; '___' tokens become highlighted blanks. Returns new y."""
        space = self.tw(" ", kind, size)
        base = self.ascent(kind, size)
        for line in self.wrap(text, kind, size, width, balance):
            cx = x
            for token in line:
                if token == BLANK:
                    bw = size * BLANK_EM
                    self.rrect([cx, y + base - size * 0.82, cx + bw, y + base + size * 0.18], size * 0.22,
                               fill=blank_fill or self.c["sun"])
                    cx += bw + space
                else:
                    cx += self.text(cx, y, token, kind, size, fill) + space
            y += leading
        return y

    def text_height(self, text, kind, size, width, leading):
        return len(self.wrap(text, kind, size, width)) * leading

    def fit(self, text, kind, sizes, width, max_lines=None):
        """The largest of sizes at which the text takes no more lines than max_lines (default: its own breaks)."""
        max_lines = max_lines or text.count("\n") + 1
        for size in sizes:
            lines = self.wrap(text, kind, size, width)
            widest = max(self.tw(word, kind, size) for line in lines for word in line if word != BLANK)
            if len(lines) <= max_lines and widest <= width:
                return size
        return sizes[-1]

    def fit_line(self, text, kind, sizes, width, out="card"):
        """The largest of sizes at which the text fits on one line of this width; refuses a line that never fits."""
        for size in sizes:
            if self.tw(text, kind, size) <= width:
                return size
        raise ValueError("%s: «%s» is too long for one line; shorten it" % (out, text))

    # ----- shapes -----

    def _px(self, values):
        return [v * self.s for v in values]

    def rrect(self, box, radius, fill=None, outline=None, width=0):
        self.draw.rounded_rectangle(self._px(box), radius=radius * self.s, fill=fill, outline=outline,
                                    width=round(width * self.s))

    def ellipse(self, box, fill=None, outline=None, width=0):
        self.draw.ellipse(self._px(box), fill=fill, outline=outline, width=round(width * self.s))

    def stroke(self, points, fill, width):
        """A line with round ends and joints."""
        pts = [(x * self.s, y * self.s) for x, y in points]
        self.draw.line(pts, fill=fill, width=round(width * self.s), joint="curve")
        r = width * self.s / 2
        for x, y in pts:
            self.draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def shadow(self, box, radius, blur=30, dy=18, alpha=95):
        """A soft drop shadow under a rounded box, tinted with the theme's shadow colour."""
        x0, y0, x1, y1 = box
        pad = blur * 2.5
        k = self.s / 2  # drawn at half the canvas resolution: it is all blur anyway
        size = (round((x1 - x0 + 2 * pad) * k), round((y1 - y0 + 2 * pad) * k))
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([pad * k, pad * k, size[0] - pad * k, size[1] - pad * k],
                                               radius=radius * k, fill=alpha)
        mask = mask.filter(ImageFilter.GaussianBlur(blur * k * 0.6)).resize((size[0] * 2, size[1] * 2), Image.BILINEAR)
        tint = Image.new("RGB", mask.size, rgb(self.theme.get("shadow", self.c["ink"])))
        self.img.paste(tint, (round((x0 - pad) * self.s), round((y0 - pad + dy) * self.s)), mask)

    def panel(self, box, radius, fill, shadow="soft"):
        """A rounded box: on a soft shadow, or "hard" (outlined, on a solid offset block), or None."""
        if shadow == "hard":
            x0, y0, x1, y1 = box
            self.rrect([x0 + 9, y0 + 9, x1 + 9, y1 + 9], radius, fill=self.c["ink"])
            self.rrect(box, radius, fill=fill, outline=self.c["ink"], width=3.5)
            return
        if shadow:
            self.shadow(box, radius)
        self.rrect(box, radius, fill=fill)

    def pill(self, x, y, text, kind, size, fill, ink, pad=(24, 13), anchor="l"):
        """Text in a pill; anchor "r" puts its right edge at x. Returns (width, height)."""
        w = self.tw(text, kind, size) + 2 * pad[0]
        h = size * 1.2 + 2 * pad[1]
        if anchor == "r":
            x -= w
        self.rrect([x, y, x + w, y + h], h / 2, fill=fill)
        self.text(x + pad[0], y + h / 2, text, kind, size, ink, anchor="lc")
        return w, h

    def sticker(self, x, y, text, kind="display", size=23, fill=None, ink=None, angle=3, pad=(26, 16)):
        """A tilted, outlined label on a solid offset block. Returns its height."""
        s = self.s
        fill, ink = fill or self.c["sun"], ink or self.c["ink"]
        w = self.tw(text, kind, size) + 2 * pad[0]
        h = size * 1.2 + 2 * pad[1]
        off = 6
        layer = Image.new("RGBA", (round((w + off + 4) * s), round((h + off + 4) * s)), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle([off * s, off * s, (w + off) * s, (h + off) * s], radius=h / 2 * s, fill=ink)
        d.rounded_rectangle([0, 0, w * s, h * s], radius=h / 2 * s, fill=fill, outline=ink, width=round(3 * s))
        self.text(pad[0], h / 2, text, kind, size, ink, anchor="lc", draw=d)
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
        self.img.paste(layer, (round(x * s), round(y * s)), layer)
        return layer.size[1] / s

    def sparkle(self, cx, cy, r, fill):
        """A four-point star."""
        points = []
        for i in range(8):
            angle = math.pi / 4 * i - math.pi / 2
            reach = r if i % 2 == 0 else r * 0.3
            points.append(((cx + reach * math.cos(angle)) * self.s, (cy + reach * math.sin(angle)) * self.s))
        self.draw.polygon(points, fill=fill)

    def badge(self, cx, cy, r, text, fill, ink=None):
        """A filled circle with a letter or number in it."""
        self.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
        self.text(cx, cy, text, "display", r * 0.92, ink or self.c["white"], anchor="mc")

    def check_mark(self, cx, cy, r, ok=True):
        c = self.c
        self.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c["mint"] if ok else c["red"])
        width = max(3, r * 0.26)
        if ok:
            self.stroke([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.48, cy - r * 0.32)],
                        c["white"], width)
        else:
            d = r * 0.38
            self.stroke([(cx - d, cy - d), (cx + d, cy + d)], c["white"], width)
            self.stroke([(cx - d, cy + d), (cx + d, cy - d)], c["white"], width)

    # ----- the shared look -----

    def background(self):
        """The theme's gradient, with soft glows and a fine grain so it doesn't look flat."""
        size = (self.w * self.s, self.h * self.s)
        grid = self.theme.get("bg") or [[self.c["paper"]]]
        small = Image.new("RGB", (len(grid[0]), len(grid)))
        small.putdata([rgb(color) for row in grid for color in row])
        bg = small.resize(size, Image.BICUBIC)

        q = 8  # glows are drawn small and scaled up
        glow = Image.new("RGBA", (self.w // q, self.h // q), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for spot in self.theme.get("glow", []):
            x, y, r = spot["at"]
            gd.ellipse([(x - r) / q, (y - r) / q, (x + r) / q, (y + r) / q], fill=rgb(spot["color"], spot.get("alpha", 150)))
        glow = glow.filter(ImageFilter.GaussianBlur(self.theme.get("blur", 120) / q)).resize(size, Image.BICUBIC)
        bg.paste(glow, (0, 0), glow)

        rng = random.Random(7)  # seeded: the same spec always renders the same file
        tile = 256
        noise = Image.frombytes("L", (tile, tile), bytes(min(255, max(0, round(rng.gauss(128, 26)))) for _ in range(tile * tile)))
        grain = Image.new("L", (self.w, self.h))
        for gx in range(0, self.w, tile):
            for gy in range(0, self.h, tile):
                grain.paste(noise, (gx, gy))
        grain = grain.resize(size, Image.NEAREST)
        bg = ImageChops.soft_light(bg, Image.merge("RGB", (grain, grain, grain)))
        self.img.paste(bg, (0, 0))

    def frame(self, label):
        """Background, corner decoration, the label sticker and the footer. Returns the y where content starts."""
        m, c = self.m, self.c
        self.background()
        self.ellipse([self.w - 260, -180, self.w + 180, 260], outline=rgb(c["white"], 52), width=3)
        self.ellipse([self.w - 170, -90, self.w + 90, 170], outline=rgb(c["white"], 36), width=3)
        self.sparkle(self.w - m - 30, m + 36, 32, c["sun"])
        self.sparkle(self.w - m - 104, m + 92, 14, c["white"])
        top = m - 8 + self.sticker(m - 2, m - 8, label) + 30
        y = self.h - m - 50
        self.pill(m, y, self.brand["wordmark"], "bold", 25, fill=c["ink"], ink=c["white"])
        if self.brand.get("handle"):
            self.pill(self.w - m, y, self.brand["handle"], "bold", 25, fill=rgb(c["white"], 240), ink=c["ink"], anchor="r")
        return top

    def note(self, y, text, fill=None):
        """A handwritten line across the card, as large as fits on one line."""
        size = self.fit_line(text, "hand", (62, 58, 54, 50, 46, 42), self.w - 2 * self.m - 8)
        self.text(self.m + 4, y, text, "hand", size, fill or self.c["sun"])

    def content_bottom(self):
        """Lowest y body content may reach without touching the footer."""
        return self.h - self.m - 50 - 28

    def spare(self, bottom, gaps, most):
        """Extra space for each of `gaps` gaps when the content ends at `bottom`: the room left, capped at `most`."""
        return max(0, min((self.content_bottom() - bottom) / gaps, most))

    def title(self, y, text, sizes, max_lines=None, gap=34):
        """The card's headline in the display font, as large as fits. Returns the y below it."""
        inner = self.w - 2 * self.m
        size = self.fit(text, "display", sizes, inner, max_lines)
        return self.paragraph(self.m, y, text, "display", size, self.c["white"], inner, size * 1.2) + gap

    def save(self, out):
        """PNG for Threads; .jpg for Instagram, which accepts only JPEG."""
        path = os.path.join(ROOT, out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        final = self.img.resize((self.w, self.h), Image.LANCZOS)
        if out.lower().endswith((".jpg", ".jpeg")):
            final.save(path, "JPEG", quality=92, optimize=True)
        else:
            final.save(path, "PNG", optimize=True)
        return path


def too_long(spec, what):
    return ValueError("%s: %s is too long for one card; shorten %s" % (spec["out"], spec["template"], what))


def render_quiz(card, spec):
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.title(card.frame(spec["label"]), spec["title"], (62, 58, 54, 50, 46, 42), max_lines=2)

    # Shrink the sentence and option rows until everything clears the footer.
    pad = 46
    options = spec["options"]
    for sent_size, leading, row, gap in ((54, 76, 112, 22), (50, 70, 104, 20), (46, 64, 96, 16), (42, 58, 88, 12)):
        sent_h = card.text_height(spec["sentence"], "semibold", sent_size, inner - 2 * pad, leading)
        bottom = y + sent_h + 2 * pad + 30 + len(options) * (row + gap) + 76
        if bottom <= card.content_bottom():
            break
    else:
        raise too_long(spec, "the sentence or the options")
    air = card.spare(bottom, len(options) + 2, 22)  # room left over opens up the gaps

    y += air
    box_h = sent_h + 2 * pad - (leading - sent_size) * 0.5
    card.panel([m, y, card.w - m, y + box_h], 40, c["white"])
    card.paragraph(m + pad, y + pad - 6, spec["sentence"], "semibold", sent_size, c["ink"], inner - 2 * pad, leading)
    y += box_h + 30 + air

    text_x = m + row + 6
    opt_size = min(card.fit_line(option, "semibold", (44, 42, 40, 38, 36, 34, 32), card.w - m - 34 - text_x, spec["out"])
                   for option in options)
    for i, option in enumerate(options):
        card.panel([m, y, card.w - m, y + row], row / 2, c["white"])
        card.badge(m + row / 2, y + row / 2, row / 2 - 14, "ABCD"[i], c[BADGES[i % len(BADGES)]])
        card.text(text_x, y + row / 2, option, "semibold", opt_size, c["ink"], anchor="lc")
        y += row + gap + air

    card.note(y + 2, spec["prompt"])


def render_versus(card, spec):
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.title(card.frame(spec["label"]), spec["title"], (88, 80, 72, 64, 56), gap=30)

    pad = 44
    lines_h = sum(card.text_height(t, "semibold", 40, inner - 2 * pad, 56) for t in spec["textbook"])
    box_h = pad + 50 + lines_h + pad - 14
    card.panel([m, y, card.w - m, y + box_h], 40, rgb(c["white"], 238))
    card.text(m + pad, y + pad - 4, spec.get("top_tag", "В УЧЕБНИКЕ"), "display", 20, c["muted"])
    ty = y + pad + 46
    for text in spec["textbook"]:
        ty = card.paragraph(m + pad, ty, text, "semibold", 40, c["muted"], inner - 2 * pad, 56)
    y += box_h + 28

    box_h = pad + 50 + 62 + 16 + 80 * len(spec["real_answers"]) + pad - 18
    card.panel([m, y, card.w - m, y + box_h], 40, c["ink"])
    card.text(m + pad, y + pad - 4, spec.get("bottom_tag", "В ЖИЗНИ"), "display", 20, c["sun"])
    ty = y + pad + 46
    q_size = card.fit_line(spec["real_question"], "semibold", (40, 38, 36, 34, 32), inner - 2 * pad, spec["out"])
    card.text(m + pad, ty, spec["real_question"], "semibold", q_size, c["white"])
    ty += 62 + 16
    a_size = min(card.fit_line(answer, "bold", (46, 44, 42, 40, 38, 36, 34), inner - 2 * pad - 68, spec["out"])
                 for answer in spec["real_answers"])
    for answer in spec["real_answers"]:
        card.check_mark(m + pad + 24, ty + 30, 24)
        card.text(m + pad + 68, ty + 30, answer, "bold", a_size, c["white"], anchor="lc")
        ty += 80
    y += box_h + 34

    if y + card.text_height(spec["note"], "semibold", 34, inner, 48) > card.content_bottom():
        raise too_long(spec, "the lines or the note")
    card.paragraph(m, y, spec["note"], "semibold", 34, c["white"], inner, 48)


def render_mistakes(card, spec):
    c, m = card.c, card.m
    y = card.title(card.frame(spec["label"]), spec["title"], (56, 52, 48, 44, 40), max_lines=2, gap=28)

    items = spec["items"]
    bottom = card.content_bottom()
    pad = 30
    row_h = (bottom - y - 2 * pad) / len(items)
    if row_h < 134:
        raise too_long(spec, "the title or use fewer items")
    card.panel([m, y, card.w - m, bottom], 44, c["white"])
    k = min(1.2, row_h / 134)  # fewer items leave taller rows: the text grows into them
    text_x = m + pad + 78
    text_w = card.w - m - pad - text_x
    for i, item in enumerate(items, 1):
        top = y + pad + (i - 1) * row_h + (row_h - 134 * k) / 2
        card.badge(m + pad + 30, top + 56 * k, 30, str(i), c[BADGES[(i - 1) % len(BADGES)]])

        wrong_size = card.fit_line(item["wrong"], "semibold", [round(s * k) for s in (34, 32, 30, 28)], text_w, spec["out"])
        ww = card.text(text_x, top, item["wrong"], "semibold", wrong_size, c["red"])
        strike = top + card.ascent("semibold", wrong_size) - wrong_size * 0.26
        card.stroke([(text_x - 4, strike), (text_x + ww + 4, strike)], c["red"], 3.5)

        full = round(46 * k)
        right_size = card.fit_line(item["right"], "bold", [round(s * k) for s in (46, 44, 42, 40, 38, 36, 34)], text_w,
                                   spec["out"])
        card.text(text_x, top + 40 * k + (full - right_size) * 0.5, item["right"], "bold", right_size, c["teal"])
        note_size = card.fit_line(item["note"], "medium", [round(s * k) for s in (27, 26, 25, 24, 23)], text_w, spec["out"])
        card.text(text_x, top + 100 * k, item["note"], "medium", note_size, c["muted"])
        if i < len(items):
            line_y = y + pad + i * row_h
            card.stroke([(text_x, line_y), (card.w - m - pad, line_y)], c["mist"], 2.5)


def render_answer(card, spec):
    """Carousel answer slide: the right option, why, and examples marked ok / wrong."""
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.title(card.frame(spec["label"]), spec["title"], (66, 60, 54, 48), gap=30)

    pad = 44
    why, examples = spec.get("why", []), spec.get("examples", [])
    tiers = ((56, 42, 44), (52, 39, 41), (48, 36, 38), (44, 34, 36), (40, 32, 34))
    # The answer reads best on one or two lines: a size that needs more is passed over when a smaller one doesn't.
    most_lines = max(2, len(card.wrap(spec["answer"], "bold", tiers[-1][0], inner - 2 * pad - 9)))
    for ans_size, why_size, ex_size in tiers:
        ans_lead, why_lead, ex_lead = ans_size * 1.32, why_size * 1.38, ex_size * 1.4
        row = why_size * 0.5  # space under each reason and example
        ans_h = card.text_height(spec["answer"], "bold", ans_size, inner - 2 * pad - 9, ans_lead)
        if ans_h > most_lines * ans_lead:
            continue
        why_h = sum(card.text_height(line, "medium", why_size, inner - 2 * pad - 38, why_lead) + row for line in why)
        ex_h = sum(card.text_height(e.lstrip("!").strip(), "semibold", ex_size, inner - 2 * pad - 66, ex_lead) + row
                   for e in examples)
        divider = 40 if why and examples else 0
        sheet_h = why_h + divider + ex_h + 2 * pad - row
        bottom = y + ans_h + 2 * pad + 43 + sheet_h
        if bottom <= card.content_bottom():
            break
    else:
        raise too_long(spec, "the answer, the reasons or the examples")
    air = card.spare(bottom, 2, 26)

    y += air
    box_h = ans_h + 2 * pad - (ans_lead - ans_size) * 0.5
    card.panel([m, y, card.w - m - 9, y + box_h], 36, c["sun"], shadow="hard")
    card.paragraph(m + pad, y + pad - 6, spec["answer"], "bold", ans_size, c["ink"], inner - 2 * pad - 9, ans_lead)
    y += box_h + 9 + 34 + air

    if not (why or examples):
        return
    card.panel([m, y, card.w - m, y + sheet_h], 40, c["white"])
    ty = y + pad
    for i, line in enumerate(why):
        dot = ty + card.ascent("medium", why_size) - why_size * CAP_HALF
        card.ellipse([m + pad, dot - 9, m + pad + 18, dot + 9], fill=c[BADGES[i % len(BADGES)]])
        ty = card.paragraph(m + pad + 38, ty, line, "medium", why_size, c["ink"], inner - 2 * pad - 38, why_lead) + row
    if divider:
        card.stroke([(m + pad, ty + 8), (card.w - m - pad, ty + 8)], c["mist"], 3)
        ty += divider
    for example in examples:
        ok = not example.startswith("!")
        mid = ty + card.ascent("semibold", ex_size) - ex_size * CAP_HALF
        card.check_mark(m + pad + 24, mid, 24, ok)
        ty = card.paragraph(m + pad + 66, ty, example.lstrip("!").strip(), "semibold", ex_size,
                            c["ink"] if ok else c["red"], inner - 2 * pad - 66, ex_lead) + row


def render_phrase(card, spec):
    """Phrase of the day: the phrase, how to say it, what it means, two examples."""
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.title(card.frame(spec["label"]) + 4, spec["phrase"], (120, 108, 100, 92, 84, 76, 68, 60), gap=2)
    ipa, note, examples = spec.get("ipa"), spec.get("note"), spec["examples"]
    in_pill = card.tw(spec["meaning"], "bold", 42) + 64 <= inner
    meaning_h = 42 * 1.2 + 36 if in_pill else card.text_height(spec["meaning"], "bold", 42, inner, 56)

    for en_size, ru_size, pad in ((50, 38, 50), (46, 35, 46), (42, 33, 42), (38, 30, 38), (34, 27, 34)):
        en_lead, ru_lead = en_size * 1.34, ru_size * 1.38
        heights = [card.text_height(ex["en"], "semibold", en_size, inner - 2 * pad, en_lead)
                   + card.text_height(ex["ru"], "medium", ru_size, inner - 2 * pad, ru_lead) + 2 * pad - 8
                   for ex in examples]
        note_h = card.text_height(note, "semibold", ru_size, inner, ru_lead) + 12 if note else 0
        bottom = y + (64 if ipa else 0) + 8 + meaning_h + 38 + sum(heights) + 24 * len(heights) + note_h
        if bottom <= card.content_bottom():
            break
    else:
        raise too_long(spec, "the examples or the note")
    air = card.spare(bottom, len(examples) + 2, 34)

    if ipa:
        card.text(m + 2, y, ipa, FALLBACK, 40, rgb(c["white"], 235))
        y += 64
    y += 8 + air
    if in_pill:
        card.pill(m, y, spec["meaning"], "bold", 42, fill=c["sun"], ink=c["ink"], pad=(32, 18))
    else:
        card.paragraph(m, y, spec["meaning"], "bold", 42, c["sun"], inner, 56)
    y += meaning_h + 38 + air
    for ex, h in zip(examples, heights):
        card.panel([m, y, card.w - m, y + h], 38, c["white"])
        ty = card.paragraph(m + pad, y + pad - 6, ex["en"], "semibold", en_size, c["ink"], inner - 2 * pad, en_lead)
        card.paragraph(m + pad, ty + 2, ex["ru"], "medium", ru_size, c["muted"], inner - 2 * pad, ru_lead)
        y += h + 24 + air
    if note:
        card.paragraph(m, y + 12 - air / 2, note, "semibold", ru_size, c["white"], inner, ru_lead)


def render_list(card, spec):
    """Title and numbered points: tips, word lists, a short promo."""
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.title(card.frame(spec["label"]), spec["title"], (60, 56, 52, 48, 44, 40), max_lines=2)

    items = [(item, None) if isinstance(item, str) else (item["text"], item.get("sub")) for item in spec["items"]]
    cta_h = 96 if spec.get("cta") else 0
    for head_size, sub_size, r, gap, pad in ((52, 39, 36, 52, 48), (48, 36, 34, 46, 44), (44, 34, 32, 40, 42),
                                             (42, 32, 30, 34, 40), (38, 30, 28, 28, 36)):
        head_lead, sub_lead = head_size * 1.28, sub_size * 1.38
        text_x = m + pad + 2 * r + 24
        text_w = card.w - m - pad - text_x
        rows = [(head, sub, card.text_height(head, "bold", head_size, text_w, head_lead),
                 card.text_height(sub, "medium", sub_size, text_w, sub_lead) if sub else 0) for head, sub in items]
        bottom = y + sum(head_h + sub_h for _, _, head_h, sub_h in rows) + gap * (len(rows) - 1) + 2 * pad - 6 + cta_h
        if bottom <= card.content_bottom():
            break
    else:
        raise too_long(spec, "the points")
    air = card.spare(bottom, len(rows) + 1, 30)
    gap += air
    y += air
    sheet_h = sum(head_h + sub_h for _, _, head_h, sub_h in rows) + gap * (len(rows) - 1) + 2 * pad - 6

    card.panel([m, y, card.w - m, y + sheet_h], 40, c["white"])
    ty = y + pad
    for i, (head, sub, head_h, sub_h) in enumerate(rows, 1):
        card.badge(m + pad + r, ty + card.ascent("bold", head_size) - head_size * CAP_HALF, r, str(i),
                   c[BADGES[(i - 1) % len(BADGES)]])
        card.paragraph(text_x, ty, head, "bold", head_size, c["ink"], text_w, head_lead)
        if sub:
            card.paragraph(text_x, ty + head_h, sub, "medium", sub_size, c["muted"], text_w, sub_lead)
        ty += head_h + sub_h + gap
        if i < len(rows):
            card.stroke([(text_x, ty - gap / 2 - 2), (card.w - m - pad, ty - gap / 2 - 2)], c["mist"], 2.5)
    if spec.get("cta"):
        card.note(y + sheet_h + 26, spec["cta"])


def render_chat(card, spec):
    """A message exchange as chat bubbles, then the question it raises. A message is
    {"from": "them" or "me", "text": ...}, with an optional "name" above it, or
    {"from": "me", "typing": true} for three dots where the reader has to answer."""
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.frame(spec["label"])
    if spec.get("title"):
        y = card.title(y, spec["title"], (58, 54, 50, 46, 42), max_lines=2, gap=30)
    messages, question, prompt = spec["messages"], spec.get("question"), spec.get("prompt")

    widest = inner * 0.84
    for size, pad, gap in ((56, 40, 30), (50, 36, 26), (46, 32, 24), (42, 30, 22), (38, 26, 18), (34, 24, 16),
                           (30, 20, 14)):
        lead = size * 1.3
        bubbles = []
        for msg in messages:
            if msg.get("typing"):
                bubbles.append((msg, None, size * 2.5 + 2 * pad, size * 0.7 + 2 * pad))
                continue
            lines = card.wrap(msg["text"], "semibold", size, widest - 2 * pad, balance=True)
            if max(card.line_width(line, "semibold", size) for line in lines) > widest - 2 * pad:
                break  # a single word wider than a bubble: try a smaller size
            width = max(card.line_width(line, "semibold", size) for line in lines) + 2 * pad
            bubbles.append((msg, lines, width, len(lines) * lead + 2 * pad - (lead - size) * 0.7))
        if len(bubbles) < len(messages):
            continue
        names_h = sum(36 for msg in messages if msg.get("name"))
        q_size = card.fit(question, "display", (58, 54, 50, 46, 42, 38), inner, 3) if question else 0
        q_h = card.text_height(question, "display", q_size, inner, q_size * 1.22) + 46 if question else 0
        bottom = y + sum(b[3] for b in bubbles) + gap * (len(bubbles) - 1) + names_h + q_h + (84 if prompt else 0)
        if bottom <= card.content_bottom():
            break
    else:
        raise too_long(spec, "the messages or the question")
    air = card.spare(bottom, len(bubbles) + 2, 60)

    y += air
    for msg, lines, width, height in bubbles:
        mine = msg.get("from") == "me"
        x0 = card.w - m - width if mine else m
        if msg.get("name"):
            card.text(card.w - m - 8 if mine else m + 8, y, msg["name"], "bold", 25, rgb(c["white"], 230),
                      anchor="ra" if mine else "la")
            y += 36
        fill = c["sun"] if mine else c["white"]
        radius = min(40, height / 2)
        card.shadow([x0, y, x0 + width, y + height], radius)
        # the tail: a small wedge at the bottom corner on the speaker's side
        tip = x0 + width + 14 if mine else x0 - 14
        root = x0 + width - 34 if mine else x0 + 34
        card.draw.polygon(card._px([root, y + height - 40, tip, y + height + 4, root, y + height - 4]), fill=fill)
        card.rrect([x0, y, x0 + width, y + height], radius, fill=fill)
        if lines is None:
            for i in range(3):
                cx = x0 + width / 2 + (i - 1) * size * 0.62
                r = size * 0.17
                card.ellipse([cx - r, y + height / 2 - r, cx + r, y + height / 2 + r], fill=rgb(c["ink"], 150 + i * 40))
        else:
            ty = y + pad - size * 0.14
            for line in lines:
                card.paragraph(x0 + pad, ty, " ".join(line), "semibold", size, c["ink"], width, lead, balance=False)
                ty += lead
        y += height + gap + air
    y += air
    if question:
        y = card.paragraph(m, y + 46 - gap, question, "display", q_size, c["white"], inner, q_size * 1.22)
    if prompt:
        card.note(y + 18, prompt)


def render_avatar(card, spec):
    """Profile picture: a speech bubble on ink, kept inside the circle crop."""
    c = card.c
    card.rrect([0, 0, card.w, card.h], 0, fill=c["ink"])
    bw, bh = card.w * 0.62, card.h * 0.44
    x0, y0 = (card.w - bw) / 2, (card.h - bh * 1.25) / 2
    card.rrect([x0, y0, x0 + bw, y0 + bh], bh / 3, fill=c["white"])
    tail_x = x0 + bw / 4
    card.draw.polygon(card._px([tail_x, y0 + bh - 2, tail_x + bh / 3, y0 + bh - 2, tail_x - bh / 12, y0 + bh + bh / 4]),
                      fill=c["white"])
    card.text(card.w / 2, y0 + bh / 2, spec["text"], "display", bh * 0.5, c["ink"], anchor="mc")


TEMPLATES = {"quiz": render_quiz, "versus": render_versus, "mistakes": render_mistakes, "answer": render_answer,
             "phrase": render_phrase, "list": render_list, "chat": render_chat, "avatar": render_avatar}


def render(spec, brand=None):
    brand = brand or load_brand()
    missing = missing_glyphs(spec, brand)
    if missing:
        raise ValueError("%s: no font has a glyph for %s" % (spec["out"], " ".join(missing)))
    card = Card(brand, spec.get("size"), spec.get("theme") or spec["template"])
    TEMPLATES[spec["template"]](card, spec)
    return card.save(spec["out"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("specs", nargs="+", help="card spec JSON files")
    args = parser.parse_args(argv)
    brand = load_brand()
    for path in args.specs:
        with open(path, encoding="utf-8") as fh:
            for spec in json.load(fh):
                print("rendered", os.path.relpath(render(spec, brand), ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
