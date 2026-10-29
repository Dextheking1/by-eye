"""Synthetic test frames for the By Eye first live run.

These frames are SYNTHETIC test images, generated with PIL. They are not
footage of any real cook. Each frame depicts one ingredient from the Pad
Woon Sen ground truth (data/ground_truth_pad_woon_sen.json) being measured:
on a digital kitchen scale, in a measuring jug or cup, on a measuring
spoon, or as a counted item. The depicted values are the exact ground-truth
amounts, so the run tests whether the live vision reader can extract
depicted measured amounts end to end.

Run: python make_synthetic_frames.py
Output: frames/frame_NN_<short>.jpg at 854x480.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FRAMES_DIR = HERE / "frames"
W, H = 854, 480

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
F_TITLE = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 40)
F_LABEL = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 30)
F_READOUT = ImageFont.truetype(str(FONT_DIR / "DejaVuSansMono-Bold.ttf"), 64)
F_SMALL = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 24)
F_BIG = ImageFont.truetype(str(FONT_DIR / "DejaVuSans-Bold.ttf"), 110)

BG = (243, 238, 228)
COUNTER = (206, 186, 158)
INK = (30, 30, 30)
SCALE_BODY = (70, 74, 82)
SCALE_TOP = (150, 156, 166)
DISPLAY = (16, 34, 24)
DISPLAY_TEXT = (126, 255, 170)
JUG_LINE = (40, 90, 160)


def base(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 330, W, H], fill=COUNTER)
    d.rectangle([0, 326, W, 330], fill=(170, 148, 118))
    d.text((427, 42), title, font=F_TITLE, fill=INK, anchor="ma")
    return img, d


def scale_scene(d: ImageDraw.ImageDraw, readout: str, unit_word: str) -> None:
    # Scale body and weighing platform.
    d.rounded_rectangle([177, 300, 677, 430], radius=18, fill=SCALE_BODY)
    d.rounded_rectangle([147, 268, 707, 306], radius=10, fill=SCALE_TOP)
    # Display.
    d.rounded_rectangle([277, 330, 577, 408], radius=8, fill=DISPLAY)
    d.text((427, 369), readout, font=F_READOUT, fill=DISPLAY_TEXT, anchor="mm")
    d.text((427, 452), unit_word, font=F_SMALL, fill=INK, anchor="ma")


def jug_scene(d: ImageDraw.ImageDraw, level: float, readout: str, caption: str) -> None:
    # Measuring jug: trapezoid with graduation lines, liquid filled to level (0..1).
    top_y, bot_y = 140, 420
    d.polygon([(330, top_y), (524, top_y), (500, bot_y), (354, bot_y)], outline=INK, width=4)
    liq_top = bot_y - int((bot_y - top_y - 16) * level)
    d.polygon([(362, liq_top), (492, liq_top), (500, bot_y - 4), (354, bot_y - 4)], fill=(214, 164, 60))
    for frac, lab in [(0.25, "10 ml"), (0.5, "20 ml"), (0.75, "30 ml"), (1.0, "40 ml")]:
        y = bot_y - int((bot_y - top_y - 16) * frac)
        d.line([470, y, 505, y], fill=JUG_LINE, width=3)
        d.text((516, y), lab, font=F_SMALL, fill=JUG_LINE, anchor="lm")
    d.text((180, 250), readout, font=F_READOUT, fill=INK, anchor="mm")
    d.text((180, 300), caption, font=F_LABEL, fill=INK, anchor="ma")


def cup_scene(d: ImageDraw.ImageDraw, level: float, readout: str, caption: str, fill_rgb) -> None:
    # Measuring cup with contents up to the level line.
    d.rounded_rectangle([300, 150, 560, 420], radius=14, outline=INK, width=4)
    fill_top = 420 - int(254 * level)
    d.rounded_rectangle([306, fill_top, 554, 414], radius=10, fill=fill_rgb)
    for frac, lab in [(0.333, "1/3 cup"), (0.5, "1/2 cup"), (1.0, "1 cup")]:
        y = 420 - int(254 * frac)
        d.line([470, y, 556, y], fill=JUG_LINE, width=3)
        d.text((566, y), lab, font=F_SMALL, fill=JUG_LINE, anchor="lm")
    d.text((150, 250), readout, font=F_READOUT, fill=INK, anchor="mm")
    d.text((150, 300), caption, font=F_LABEL, fill=INK, anchor="ma")


def spoon_scene(d: ImageDraw.ImageDraw, readout: str, caption: str, liquid_rgb) -> None:
    # Teaspoon seen from above: ellipse bowl plus handle.
    d.ellipse([240, 190, 470, 320], fill=(188, 192, 200), outline=INK, width=3)
    d.ellipse([262, 208, 448, 302], fill=liquid_rgb)
    d.rounded_rectangle([470, 232, 760, 262], radius=12, fill=(188, 192, 200), outline=INK, width=3)
    d.text((427, 380), readout, font=F_READOUT, fill=INK, anchor="ma")
    d.text((427, 452 - 18), caption, font=F_LABEL, fill=INK, anchor="ma")


def count_banner(d: ImageDraw.ImageDraw, text: str) -> None:
    d.rounded_rectangle([277, 356, 577, 436], radius=12, fill=(255, 255, 255), outline=INK, width=3)
    d.text((427, 396), text, font=F_LABEL, fill=INK, anchor="mm")


def draw_noodles(d: ImageDraw.ImageDraw) -> None:
    rnd = random.Random(7)
    for _ in range(46):
        x = rnd.randint(250, 600)
        y = rnd.randint(196, 258)
        d.line([x, y, x + rnd.randint(30, 90), y + rnd.randint(-8, 14)], fill=(238, 230, 200), width=3)


def draw_chicken(d: ImageDraw.ImageDraw) -> None:
    for cx, cy in [(300, 226), (385, 208), (462, 230), (345, 246), (430, 250), (520, 216)]:
        d.rounded_rectangle([cx - 42, cy - 18, cx + 42, cy + 18], radius=16, fill=(232, 178, 168), outline=(190, 130, 120), width=2)


def draw_garlic(d: ImageDraw.ImageDraw) -> None:
    for cx in (360, 500):
        d.ellipse([cx - 46, 168, cx + 46, 292], fill=(245, 240, 222), outline=(180, 170, 140), width=3)
        d.polygon([(cx - 14, 178), (cx + 14, 178), (cx, 138)], fill=(245, 240, 222), outline=(180, 170, 140), width=3)


def draw_onion_quarter(d: ImageDraw.ImageDraw) -> None:
    d.pieslice([297, 130, 557, 390], start=270, end=360, fill=(238, 226, 240), outline=(150, 120, 160), width=3)
    for r in (38, 66, 94):
        d.arc([427 - r, 260 - r, 427 + r, 260 + r], start=270, end=360, fill=(170, 140, 180), width=2)
    d.text((600, 250), "1/4", font=F_BIG, fill=INK, anchor="mm")


def draw_eggs(d: ImageDraw.ImageDraw) -> None:
    for cx in (355, 500):
        d.ellipse([cx - 55, 150, cx + 55, 300], fill=(250, 246, 238), outline=(190, 180, 160), width=3)


def draw_tomato(d: ImageDraw.ImageDraw) -> None:
    d.ellipse([332, 150, 522, 320], fill=(214, 62, 44), outline=(160, 40, 30), width=3)
    d.polygon([(410, 158), (444, 158), (427, 128)], fill=(60, 140, 60))


def draw_green_onion(d: ImageDraw.ImageDraw) -> None:
    for i in range(5):
        x = 330 + i * 34
        d.line([x, 330, x + 26, 150], fill=(52, 150, 66), width=9)
    d.rounded_rectangle([318, 318, 500, 352], radius=10, fill=(240, 246, 230), outline=(120, 160, 110), width=2)


def main() -> None:
    truth = json.loads((REPO / "data" / "ground_truth_pad_woon_sen.json").read_text())
    by_id = {i["id"]: i for i in truth["ingredients"]}
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    def save(img: Image.Image, n: int, short: str) -> None:
        img.save(FRAMES_DIR / f"frame_{n:02d}_{short}.jpg", quality=90)

    # 01 glass noodles, dry: 40 g on a scale.
    img, d = base(by_id["glass_noodles_dry"]["name"])
    draw_noodles(d)
    scale_scene(d, "40 g", "dry noodles on the scale")
    save(img, 1, "noodles")

    # 02 chicken: 170 g on a scale.
    img, d = base(by_id["chicken"]["name"])
    draw_chicken(d)
    scale_scene(d, "170 g", "chicken on the scale")
    save(img, 2, "chicken")

    # 03 soy sauce for the marinade: 1 tsp (5 ml) on a spoon.
    img, d = base("soy sauce, for marinating chicken")
    spoon_scene(d, "5 ml", "1 tsp", (52, 34, 20))
    save(img, 3, "soy_marinade")

    # 04 garlic: 2 cloves, counted.
    img, d = base(by_id["garlic"]["name"])
    draw_garlic(d)
    count_banner(d, "2 cloves")
    save(img, 4, "garlic")

    # 05 onion: 1/4 of a small onion.
    img, d = base(by_id["onion"]["name"])
    draw_onion_quarter(d)
    count_banner(d, "1/4 onion")
    save(img, 5, "onion")

    # 06 eggs: 2, counted.
    img, d = base(by_id["eggs"]["name"])
    draw_eggs(d)
    count_banner(d, "2 eggs")
    save(img, 6, "eggs")

    # 07 cabbage: 1 cup in a measuring cup.
    img, d = base(by_id["cabbage"]["name"])
    cup_scene(d, 1.0, "1 cup", "cabbage", (168, 204, 140))
    save(img, 7, "cabbage")

    # 08 carrots: 1/3 cup in a measuring cup.
    img, d = base(by_id["carrots"]["name"])
    cup_scene(d, 0.333, "1/3 cup", "carrots", (232, 138, 54))
    save(img, 8, "carrots")

    # 09 white pepper: 1/4 tsp on a spoon.
    img, d = base(by_id["white_pepper"]["name"])
    spoon_scene(d, "1/4 tsp", "white pepper", (226, 222, 210))
    save(img, 9, "white_pepper")

    # 10 tomato: 1, counted.
    img, d = base(by_id["tomato"]["name"])
    draw_tomato(d)
    count_banner(d, "1 tomato")
    save(img, 10, "tomato")

    # 11 green onion: 1 stalk, counted.
    img, d = base(by_id["green_onion"]["name"])
    draw_green_onion(d)
    count_banner(d, "1 green onion")
    save(img, 11, "green_onion")

    # 12 oyster sauce: 15 ml in a jug.
    img, d = base(by_id["oyster_sauce"]["name"])
    jug_scene(d, 0.375, "15 ml", "oyster sauce")
    save(img, 12, "oyster_sauce")

    # 13 soy sauce in the sauce: 7.5 ml in a jug.
    img, d = base(by_id["soy_sauce"]["name"])
    jug_scene(d, 0.1875, "7.5 ml", "soy sauce")
    save(img, 13, "soy_sauce")

    # 14 Golden Mountain sauce: 7.5 ml in a jug.
    img, d = base("Golden Mountain sauce")
    jug_scene(d, 0.1875, "7.5 ml", "seasoning sauce")
    save(img, 14, "golden_mountain")

    # 15 sugar: 1 1/2 tsp (7.5 ml) on a spoon.
    img, d = base(by_id["sugar"]["name"])
    spoon_scene(d, "7.5 ml", "1 1/2 tsp sugar", (250, 250, 246))
    save(img, 15, "sugar")

    # 16 water: 30 ml in a jug.
    img, d = base(by_id["water"]["name"])
    jug_scene(d, 0.75, "30 ml", "water")
    save(img, 16, "water")

    print(f"wrote {len(list(FRAMES_DIR.glob('*.jpg')))} frames to {FRAMES_DIR}")


if __name__ == "__main__":
    main()
