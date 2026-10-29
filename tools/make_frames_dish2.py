"""Synthetic frames for the second eval dish (garlic shrimp fried rice).

Same contract as the dish-1 generator: PIL frames at 854x480, one
ingredient per frame, depicting the exact ground-truth amounts from
data/ground_truth_garlic_shrimp_fried_rice.json. Synthetic only.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "dish1", HERE.parent / "first-live-run" / "make_synthetic_frames.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FRAMES = HERE / "frames"
FRAMES.mkdir(parents=True, exist_ok=True)

def save(img, n, short):
    img.save(FRAMES / f"frame_{n:02d}_{short}.jpg", quality=90)

def draw_shrimp(d):
    for cx, cy in [(300, 220), (390, 200), (480, 224), (345, 248), (440, 252), (530, 205)]:
        d.arc([cx - 34, cy - 26, cx + 34, cy + 26], start=300, end=200, fill=(240, 150, 130), width=13)

def draw_peas_banner(d):
    m.count_banner(d, "1/2 cup peas")

# 01 rice: 3 cups in a measuring cup scene (full cup shown, readout states 3 cups)
img, d = m.base("cooked jasmine rice")
m.cup_scene(d, 1.0, "3 cups", "rice", (246, 242, 230))
save(img, 1, "rice")
# 02 shrimp: 200 g on a scale
img, d = m.base("shrimp, peeled")
draw_shrimp(d)
m.scale_scene(d, "200 g", "shrimp on the scale")
save(img, 2, "shrimp")
# 03 eggs: 3 counted (reuse egg drawing, 3 ellipses)
img, d = m.base("large eggs")
for cx in (300, 427, 554):
    d.ellipse([cx - 55, 150, cx + 55, 300], fill=(250, 246, 238), outline=(190, 180, 160), width=3)
m.count_banner(d, "3 eggs")
save(img, 3, "eggs")
# 04 garlic: 3 cloves
img, d = m.base("garlic, minced")
for cx in (300, 427, 554):
    d.ellipse([cx - 46, 168, cx + 46, 292], fill=(245, 240, 222), outline=(180, 170, 140), width=3)
    d.polygon([(cx - 14, 178), (cx + 14, 178), (cx, 138)], fill=(245, 240, 222), outline=(180, 170, 140), width=3)
m.count_banner(d, "3 cloves")
save(img, 4, "garlic")
# 05 peas: 1/2 cup
img, d = m.base("peas")
m.cup_scene(d, 0.5, "1/2 cup", "peas", (140, 190, 90))
save(img, 5, "peas")
# 06 carrots: 1/2 cup
img, d = m.base("carrots, diced")
m.cup_scene(d, 0.5, "1/2 cup", "carrots", (232, 138, 54))
save(img, 6, "carrots")
# 07 soy sauce: 15 ml jug
img, d = m.base("soy sauce")
m.jug_scene(d, 0.375, "15 ml", "soy sauce")
save(img, 7, "soy_sauce")
# 08 cooking oil: 15 ml jug
img, d = m.base("cooking oil")
m.jug_scene(d, 0.375, "15 ml", "cooking oil")
save(img, 8, "cooking_oil")
# 09 green onion: 2 stalks
img, d = m.base("green onion, chopped")
m.draw_green_onion(d)
m.count_banner(d, "2 green onions")
save(img, 9, "green_onion")
# 10 salt: 1/2 tsp spoon
img, d = m.base("salt")
m.spoon_scene(d, "1/2 tsp", "salt", (250, 250, 246))
save(img, 10, "salt")
print("wrote", len(list(FRAMES.glob('*.jpg'))), "frames")
