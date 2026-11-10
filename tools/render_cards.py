"""Render educational cards (1080x1350 PNG) from JSON specs in content/cards/.

Templates: quiz, versus, mistakes, answer, phrase, list, avatar. Every string is checked against the font's
character map first, so a card can never ship with missing-glyph boxes.

    python tools/render_cards.py content/cards/2026-11-09_week1.json
"""
import argparse
import json
import os
import sys

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLANK = "___"


def load_brand():
    with open(os.path.join(ROOT, "brand", "brand.json"), encoding="utf-8") as fh:
        return json.load(fh)


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in ("out", "template"):
                yield from strings_in(item)


def missing_glyphs(spec, brand):
    missing = set()
    for path in brand["fonts"].values():
        cmap = TTFont(os.path.join(ROOT, path)).getBestCmap()
        for text in strings_in(spec):
            missing.update(ch for ch in text if not ch.isspace() and ord(ch) not in cmap)
    return sorted(missing)


class Card:
    def __init__(self, brand, size=None):
        self.brand = brand
        self.w, self.h = size or brand["size"]
        self.m = brand["margin"]
        self.c = brand["colors"]
        self.img = Image.new("RGB", (self.w, self.h), self.c["paper"])
        self.draw = ImageDraw.Draw(self.img)
        self._fonts = {}

    def font(self, kind, size):
        key = (kind, size)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(os.path.join(ROOT, self.brand["fonts"][kind]), size)
        return self._fonts[key]

    def width_of(self, token, font):
        if token == BLANK:
            return int(font.size * 2.6)
        return self.draw.textlength(token, font=font)

    def wrap(self, text, font, width):
        """Word-wrap to width; an explicit '\\n' forces a break."""
        lines = []
        space = self.draw.textlength(" ", font=font)
        for segment in text.split("\n"):
            line = []
            for word in segment.split():
                trial = sum(self.width_of(t, font) for t in line + [word]) + space * len(line)
                if line and trial > width:
                    lines.append(line)
                    line = [word]
                else:
                    line.append(word)
            if line:
                lines.append(line)
        return lines

    def paragraph(self, x, y, text, font, fill, width, leading, blank_fill=None):
        """Draw wrapped text; '___' tokens become highlighted blanks. Returns new y."""
        space = self.draw.textlength(" ", font=font)
        for line in self.wrap(text, font, width):
            cx = x
            for token in line:
                if token == BLANK:
                    bw = self.width_of(token, font)
                    top = y + font.size * 0.18
                    self.draw.rounded_rectangle([cx, top, cx + bw, top + font.size * 0.95],
                                                radius=10, fill=blank_fill or self.c["sun"])
                    cx += bw + space
                else:
                    self.draw.text((cx, y), token, font=font, fill=fill)
                    cx += self.draw.textlength(token, font=font) + space
            y += leading
        return y

    def text_height(self, text, font, width, leading):
        return len(self.wrap(text, font, width)) * leading

    def frame(self, label):
        m, c = self.m, self.c
        f = self.font("bold", 26)
        tw = self.draw.textlength(label, font=f)
        self.draw.rounded_rectangle([m, m, m + tw + 44, m + 52], radius=26, fill=c["sun"])
        self.draw.text((m + 22, m + 11), label, font=f, fill=c["ink"])

        foot = self.font("semibold", 30)
        self.draw.text((m, self.h - m - 40), self.brand["wordmark"], font=foot, fill=c["ink"])
        handle = self.brand.get("handle")
        if handle:
            hw = self.draw.textlength(handle, font=foot)
            self.draw.text((self.w - m - hw, self.h - m - 40), handle, font=foot, fill=c["muted"])
        split = int(self.w * 0.72)
        self.draw.rectangle([0, self.h - 14, split, self.h], fill=c["ink"])
        self.draw.rectangle([split, self.h - 14, self.w, self.h], fill=c["red"])
        return m + 52 + 56

    def content_bottom(self):
        """Lowest y body content may reach without touching the footer."""
        return self.h - self.m - 70

    def save(self, out):
        """PNG for Threads; .jpg for Instagram, which accepts only JPEG."""
        path = os.path.join(ROOT, out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if out.lower().endswith((".jpg", ".jpeg")):
            self.img.save(path, "JPEG", quality=92, optimize=True)
        else:
            self.img.save(path, "PNG", optimize=True)
        return path

    def check_mark(self, cx, cy, r, ok=True):
        c = self.c
        self.draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c["teal"] if ok else c["red"])
        if ok:
            self.draw.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.4), (cx + r * 0.5, cy - r * 0.35)],
                           fill=c["white"], width=max(4, int(r * 0.28)))
        else:
            d = r * 0.4
            for a, b in (((cx - d, cy - d), (cx + d, cy + d)), ((cx - d, cy + d), (cx + d, cy - d))):
                self.draw.line([a, b], fill=c["white"], width=max(4, int(r * 0.28)))


def render_quiz(card, spec):
    c, m = card.c, card.m
    inner = card.w - 2 * m
    top = card.frame(spec["label"])
    title_end = card.paragraph(m, top, spec["title"], card.font("display", 68), c["ink"], inner, 82) + 44

    # Shrink the sentence and option rows until everything clears the footer.
    pad = 52
    for sent_size, leading, row, gap in ((54, 78, 108, 22), (48, 68, 96, 16), (44, 62, 88, 12)):
        sent_font = card.font("semibold", sent_size)
        sent_h = card.text_height(spec["sentence"], sent_font, inner - 2 * pad, leading)
        bottom = title_end + sent_h + 2 * pad + 44 + len(spec["options"]) * (row + gap) + 22 + 44
        if bottom <= card.content_bottom():
            break
    else:
        raise ValueError("%s: quiz is too long for one card; shorten the sentence or options" % spec["out"])

    y = title_end
    card.draw.rounded_rectangle([m, y, card.w - m, y + sent_h + 2 * pad - 8], radius=36, fill=c["mist"])
    card.paragraph(m + pad, y + pad, spec["sentence"], sent_font, c["ink"], inner - 2 * pad, leading)
    y += sent_h + 2 * pad + 44

    opt_font = card.font("semibold", 44 if row > 90 else 40)
    letter_font = card.font("bold", 34)
    for i, option in enumerate(spec["options"]):
        letter = "ABCD"[i]
        card.draw.rounded_rectangle([m, y, card.w - m, y + row], radius=row // 2, fill=c["white"],
                                    outline=c["mist"], width=3)
        cx, cy = m + 54, y + row // 2
        card.draw.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], fill=c["ink"])
        lw = card.draw.textlength(letter, font=letter_font)
        card.draw.text((cx - lw / 2, cy - 22), letter, font=letter_font, fill=c["white"])
        card.draw.text((m + 112, cy - opt_font.size * 0.62), option, font=opt_font, fill=c["ink"])
        y += row + gap

    card.draw.text((m, y + 22), spec["prompt"], font=card.font("bold", 36), fill=c["red"])


def render_versus(card, spec):
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.frame(spec["label"])
    y = card.paragraph(m, y, spec["title"], card.font("display", 92), c["ink"], inner, 104) + 36

    tag = card.font("bold", 28)
    line_font = card.font("semibold", 42)
    pad = 48
    lines_h = sum(card.text_height(t, line_font, inner - 2 * pad, 60) for t in spec["textbook"])
    box_h = pad + 40 + 20 + lines_h + pad - 12
    card.draw.rounded_rectangle([m, y, card.w - m, y + box_h], radius=36, fill=c["mist"])
    card.draw.text((m + pad, y + pad), "В УЧЕБНИКЕ", font=tag, fill=c["muted"])
    ty = y + pad + 60
    for text in spec["textbook"]:
        ty = card.paragraph(m + pad, ty, text, line_font, c["muted"], inner - 2 * pad, 60)
    y += box_h + 28

    answer_font = card.font("bold", 50)
    box_h = pad + 40 + 20 + 64 + 24 + 82 * len(spec["real_answers"]) + pad - 30
    card.draw.rounded_rectangle([m, y, card.w - m, y + box_h], radius=36, fill=c["ink"])
    card.draw.text((m + pad, y + pad), "В ЖИЗНИ", font=tag, fill=c["sun"])
    ty = y + pad + 60
    card.draw.text((m + pad, ty), spec["real_question"], font=line_font, fill=c["white"])
    ty += 64 + 24
    for answer in spec["real_answers"]:
        cx, cy = m + pad + 22, ty + 30
        card.draw.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=c["teal"])
        card.draw.line([(cx - 10, cy + 1), (cx - 3, cy + 9), (cx + 11, cy - 8)], fill=c["white"], width=6)
        card.draw.text((m + pad + 66, ty), answer, font=answer_font, fill=c["white"])
        ty += 82
    y += box_h + 40

    card.paragraph(m, y, spec["note"], card.font("medium", 36), c["ink"], inner, 50)


def render_mistakes(card, spec):
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.frame(spec["label"])
    y = card.paragraph(m, y, spec["title"], card.font("display", 60), c["ink"], inner, 72) + 30

    wrong_font = card.font("semibold", 38)
    right_font = card.font("display", 46)
    note_font = card.font("medium", 28)
    num_font = card.font("bold", 30)
    text_x = m + 88
    row_h = (card.h - m - 92 - y) / len(spec["items"])
    for i, item in enumerate(spec["items"], 1):
        top = y + (i - 1) * row_h
        cx, cy = m + 30, top + 40
        card.draw.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=c["sun"])
        nw = card.draw.textlength(str(i), font=num_font)
        card.draw.text((cx - nw / 2, cy - 19), str(i), font=num_font, fill=c["ink"])

        card.draw.text((text_x, top + 14), item["wrong"], font=wrong_font, fill=c["red"])
        ww = card.draw.textlength(item["wrong"], font=wrong_font)
        card.draw.line([(text_x - 4, top + 39), (text_x + ww + 4, top + 39)], fill=c["red"], width=4)
        card.draw.text((text_x, top + 62), item["right"], font=right_font, fill=c["teal"])
        card.draw.text((text_x, top + 122), item["note"], font=note_font, fill=c["muted"])
        if i < len(spec["items"]):
            card.draw.line([(text_x, top + row_h - 6), (card.w - m, top + row_h - 6)], fill=c["mist"], width=2)


def render_answer(card, spec):
    """Carousel answer slide: the right option, why, and examples marked ok / wrong."""
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.frame(spec["label"])
    y = card.paragraph(m, y, spec["title"], card.font("display", 64), c["ink"], inner, 76) + 34

    pad = 48
    ans_font = card.font("bold", 50)
    ans_h = card.text_height(spec["answer"], ans_font, inner - 2 * pad, 66)
    card.draw.rounded_rectangle([m, y, card.w - m, y + ans_h + 2 * pad - 12], radius=36, fill=c["teal"])
    card.paragraph(m + pad, y + pad, spec["answer"], ans_font, c["white"], inner - 2 * pad, 66)
    y += ans_h + 2 * pad + 30

    why_font = card.font("medium", 38)
    for line in spec.get("why", []):
        card.draw.ellipse([m + 4, y + 18, m + 20, y + 34], fill=c["sun"])
        y = card.paragraph(m + 40, y, line, why_font, c["ink"], inner - 40, 52) + 12
    y += 18

    ex_font = card.font("semibold", 40)
    for example in spec.get("examples", []):
        ok = not example.startswith("!")
        text = example.lstrip("!").strip()
        card.check_mark(m + 24, y + 26, 22, ok)
        y = card.paragraph(m + 66, y, text, ex_font, c["ink"] if ok else c["red"], inner - 66, 56) + 14


def render_phrase(card, spec):
    """Phrase of the day: the phrase, how to say it, what it means, two examples."""
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.frame(spec["label"])
    y = card.paragraph(m, y + 10, spec["phrase"], card.font("display", 96), c["ink"], inner, 108) + 6
    if spec.get("ipa"):
        card.draw.text((m, y), spec["ipa"], font=card.font("medium", 40), fill=c["muted"])
        y += 64
    y = card.paragraph(m, y, spec["meaning"], card.font("bold", 48), c["teal"], inner, 62) + 40

    pad = 44
    en_font, ru_font = card.font("semibold", 42), card.font("medium", 34)
    for ex in spec["examples"]:
        h = card.text_height(ex["en"], en_font, inner - 2 * pad, 56) + card.text_height(ex["ru"], ru_font, inner - 2 * pad, 46)
        card.draw.rounded_rectangle([m, y, card.w - m, y + h + 2 * pad - 6], radius=32, fill=c["mist"])
        ty = card.paragraph(m + pad, y + pad, ex["en"], en_font, c["ink"], inner - 2 * pad, 56)
        card.paragraph(m + pad, ty + 4, ex["ru"], ru_font, c["muted"], inner - 2 * pad, 46)
        y += h + 2 * pad + 24
    if spec.get("note"):
        card.paragraph(m, y + 8, spec["note"], card.font("medium", 34), c["ink"], inner, 48)


def render_list(card, spec):
    """Title and numbered points: tips, word lists, a short promo."""
    c, m = card.c, card.m
    inner = card.w - 2 * m
    y = card.frame(spec["label"])
    y = card.paragraph(m, y, spec["title"], card.font("display", 64), c["ink"], inner, 76) + 40
    head_font, sub_font, num_font = card.font("bold", 44), card.font("medium", 34), card.font("bold", 30)
    for i, item in enumerate(spec["items"], 1):
        head, sub = (item, None) if isinstance(item, str) else (item["text"], item.get("sub"))
        cx, cy = m + 30, y + 30
        card.draw.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=c["sun"])
        nw = card.draw.textlength(str(i), font=num_font)
        card.draw.text((cx - nw / 2, cy - 19), str(i), font=num_font, fill=c["ink"])
        y = card.paragraph(m + 88, y + 2, head, head_font, c["ink"], inner - 88, 58)
        if sub:
            y = card.paragraph(m + 88, y, sub, sub_font, c["muted"], inner - 88, 46)
        y += 30
    if spec.get("cta"):
        card.paragraph(m, y + 10, spec["cta"], card.font("bold", 38), c["red"], inner, 50)


def render_avatar(card, spec):
    """Profile picture: a speech bubble on ink, kept inside the circle crop."""
    c = card.c
    card.draw.rectangle([0, 0, card.w, card.h], fill=c["ink"])
    bw, bh = int(card.w * 0.62), int(card.h * 0.44)
    x0, y0 = (card.w - bw) // 2, int((card.h - bh * 1.25) / 2)
    card.draw.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=bh // 3, fill=c["white"])
    tail_x = x0 + bw // 4
    card.draw.polygon([(tail_x, y0 + bh - 2), (tail_x + bh // 3, y0 + bh - 2), (tail_x - bh // 12, y0 + bh + bh // 4)],
                      fill=c["white"])
    font = card.font("display", int(bh * 0.62))
    box = card.draw.textbbox((0, 0), spec["text"], font=font)
    tx = x0 + (bw - (box[2] - box[0])) / 2 - box[0]
    ty = y0 + (bh - (box[3] - box[1])) / 2 - box[1]
    card.draw.text((tx, ty), spec["text"], font=font, fill=c["ink"])


TEMPLATES = {"quiz": render_quiz, "versus": render_versus, "mistakes": render_mistakes, "answer": render_answer,
             "phrase": render_phrase, "list": render_list, "avatar": render_avatar}


def render(spec, brand=None):
    brand = brand or load_brand()
    missing = missing_glyphs(spec, brand)
    if missing:
        raise ValueError("%s: font has no glyph for %s" % (spec["out"], " ".join(missing)))
    card = Card(brand, spec.get("size"))
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
