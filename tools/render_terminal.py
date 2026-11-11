#!/usr/bin/env python3
"""Render a mixin-stubber CLI session as a terminal-window PNG (README screenshots).

The tool prints plain Java, so this renderer applies Java syntax highlighting
itself. Input is the generated .java text; --cmd is the command line shown above
it (use a literal \\n for shell continuation lines).

Usage: python render_terminal.py input.java output.png --title "..." --cmd "..."
Requires Pillow (pip install pillow). Windows: uses Consolas / Segoe UI.
"""
import argparse
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FG = "#cccccc"
BG = "#0c0c0c"
C_ANNOT = "#f9f1a5"   # @Mixin / @Inject / @At
C_KEY = "#61d6d6"     # keywords + primitives
C_STR = "#16c60c"     # string literals
C_COMMENT = "#767676"
C_TYPE = "#3b78ff"    # capitalized type names
C_NUM = "#b4009e"
C_PROMPT = "#16c60c"

FONT_SIZE = 14
LINE_H = 21
PAD_X, PAD_Y = 22, 18
TITLE_H = 38
MARGIN = 36
RADIUS = 10

KEYWORDS = {
    "package", "import", "public", "private", "protected", "abstract", "class",
    "interface", "static", "final", "void", "return", "new", "this", "super",
    "if", "else", "for", "while", "do", "switch", "case", "break", "continue",
    "try", "catch", "finally", "throw", "throws", "extends", "implements",
    "instanceof", "null", "true", "false",
    "int", "long", "float", "double", "boolean", "byte", "char", "short",
}

TOKEN_RE = re.compile(
    r"(?P<comment>//[^\n]*)"
    r"|(?P<string>\"(?:[^\"\\\n]|\\.)*\")"
    r"|(?P<annot>@[A-Za-z_$][\w$]*)"
    r"|(?P<num>\b\d[\w.]*)"
    r"|(?P<word>[A-Za-z_$][\w$]*)"
    r"|(?P<other>.)"
)


def highlight_line(text):
    """Return list of (text, color, bold) spans for one line of Java."""
    spans = []
    for m in TOKEN_RE.finditer(text):
        kind = m.lastgroup
        t = m.group(0)
        if kind == "comment":
            color = C_COMMENT
        elif kind == "string":
            color = C_STR
        elif kind == "annot":
            color = C_ANNOT
        elif kind == "num":
            color = C_NUM
        elif kind == "word":
            if t in KEYWORDS:
                color = C_KEY
            elif t[0].isupper():
                color = C_TYPE
            else:
                color = None
        else:
            color = None
        spans.append((t, color, False))
    return spans


def blend(hex_color, other, t):
    a = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(other[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(int(a[i] * t + b[i] * (1 - t)) for i in range(3))


def build_lines(java_text, cmd):
    lines = []
    if cmd:
        cmd_lines = cmd.split("\n")
        for i, cl in enumerate(cmd_lines):
            prefix = "$ " if i == 0 else "    "
            lines.append([(prefix, C_PROMPT, True), (cl, None, False)])
        lines.append([])
    for raw in java_text.rstrip("\n").split("\n"):
        lines.append(highlight_line(raw))
    return lines


def render(lines, title, out_path):
    reg = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", FONT_SIZE)
    boldf = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", FONT_SIZE)
    uif = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 12)
    cw = reg.getlength("M")

    cols = max(sum(len(t) for t, _, _ in ln) for ln in lines)
    win_w = int(cols * cw) + 2 * PAD_X
    win_h = TITLE_H + 2 * PAD_Y + len(lines) * LINE_H
    W, H = win_w + 2 * MARGIN, win_h + 2 * MARGIN

    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    top, bot = (26, 27, 38), (15, 16, 21)
    for y in range(H):
        t = y / max(H - 1, 1)
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([MARGIN, MARGIN + 12, MARGIN + win_w, MARGIN + 12 + win_h],
                         RADIUS, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
    d = ImageDraw.Draw(img)

    x0, y0 = MARGIN, MARGIN
    d.rounded_rectangle([x0, y0, x0 + win_w, y0 + win_h], RADIUS, fill=BG, outline="#2a2a2a")
    d.rounded_rectangle([x0, y0, x0 + win_w, y0 + TITLE_H + RADIUS], RADIUS, fill="#1f1f1f")
    d.rectangle([x0, y0 + TITLE_H - RADIUS, x0 + win_w, y0 + TITLE_H], fill="#1f1f1f")
    d.line([(x0, y0 + TITLE_H), (x0 + win_w, y0 + TITLE_H)], fill="#2a2a2a")
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        cx = x0 + 20 + i * 20
        cy = y0 + TITLE_H // 2
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=c)
    tw = d.textlength(title, font=uif)
    d.text((x0 + (win_w - tw) / 2, y0 + TITLE_H / 2 - 8), title, font=uif, fill="#9a9a9a")

    y = y0 + TITLE_H + PAD_Y
    for ln in lines:
        x = x0 + PAD_X
        for text, color, bold in ln:
            f = boldf if bold else reg
            d.text((x, y), text, font=f, fill=color or FG)
            x += f.getlength(text)
        y += LINE_H
    img.save(out_path)
    print(f"{out_path}: {W}x{H}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--title", default="mixin-stubber")
    ap.add_argument("--cmd", default=None)
    args = ap.parse_args()
    with open(args.input, "r", encoding="utf-8") as f:
        lines = build_lines(f.read(), args.cmd)
    render(lines, args.title, args.output)


if __name__ == "__main__":
    main()