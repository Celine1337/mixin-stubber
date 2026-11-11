#!/usr/bin/env python3
"""Regenerate docs/inject.png and docs/redirect.png from real CLI runs.

Requires Pillow. Run: python tools/make_shots.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import render_terminal as rt

INJECT_SIG = "net.minecraft.world.entity.player.Player#getFoodData()Lnet/minecraft/world/food/FoodData;"
REDIRECT_TARGET = "Lnet/minecraft/client/gui/Gui;->render(Lnet/minecraft/client/gui/GuiGraphics;F)V"

SHOTS = [
    ("inject", [INJECT_SIG, "--at", "RETURN"],
     f'python mixin_stubber.py "{INJECT_SIG}" --at RETURN'),
    ("redirect", ["net.minecraft.client.Minecraft#runTick()V", "--mode", "redirect",
                  "--target", REDIRECT_TARGET],
     'python mixin_stubber.py "net.minecraft.client.Minecraft#runTick()V" --mode redirect \\\n'
     f'    --target "{REDIRECT_TARGET}"'),
]


def main():
    for name, argv, cmd in SHOTS:
        out = subprocess.run([sys.executable, os.path.join(ROOT, "mixin_stubber.py"), *argv],
                             capture_output=True, text=True, check=True)
        lines = rt.build_lines(out.stdout, cmd)
        rt.render(lines, f"mixin-stubber — {name}", os.path.join(ROOT, "docs", f"{name}.png"))


if __name__ == "__main__":
    main()