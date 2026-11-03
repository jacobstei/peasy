"""Generate the PWA icons (rerun after a color change: python scripts/make_icons.py). Needs Pillow: pip install pillow."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BG, PEA, PEA_DARK = (196, 80, 27), (156, 196, 74), (98, 140, 40)

def icon(size):
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    s = size / 512
    # pea pod with three peas, kept inside the maskable safe zone (center 80%)
    d.rounded_rectangle([110 * s, 196 * s, 402 * s, 316 * s], radius=60 * s, fill=PEA_DARK)
    for cx in (176, 256, 336):
        d.ellipse([(cx - 38) * s, 218 * s, (cx + 38) * s, 294 * s], fill=PEA)
    return img

for name, size in (("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)):
    icon(size).save(ROOT / name)
    print("wrote", name)
