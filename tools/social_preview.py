#!/usr/bin/env python3
"""Compose the GitHub social preview card (1280x640) from docs/inject.png.

Requires Pillow. Upload the result in repo Settings -> Social preview.
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 640

img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
top, bot = (26, 27, 38), (15, 16, 21)
for y in range(H):
    t = y / (H - 1)
    d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))

shot = Image.open(os.path.join(ROOT, "docs", "inject.png"))
sh = 400
sw = int(shot.width * sh / shot.height)
shot = shot.resize((sw, sh), Image.LANCZOS)
mask = Image.new("L", (sw, sh), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, sw, sh], 14, fill=255)
img.paste(shot, (W - sw - 44, 200), mask)

title = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 76)
sub = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 27)
small = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 19)
d.text((60, 64), "mixin-stubber", font=title, fill="#61d6d6")
d.text((64, 162), "auto-Mixin stubs for Minecraft", font=sub, fill="#cccccc")
for i, line in enumerate(["@Inject · @Redirect · @At · CallbackInfo",
                          "vanilla signature in, ready class out",
                          "Python 3.9+ · stdlib only · zero deps"]):
    d.text((64, 250 + i * 34), line, font=small, fill="#9a9a9a")
d.text((64, 560), "github.com/Celine1337/mixin-stubber", font=small, fill="#767676")

out = os.path.join(ROOT, "docs", "social-preview.png")
img.save(out)
print(f"{out}: {W}x{H}")