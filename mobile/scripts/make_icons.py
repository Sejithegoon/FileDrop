"""Draws the phone app's icons from WiFiDrop's mark (site/assets/img/favicon.svg): a white arrow on blue.

Run from the repo root: .venv\\Scripts\\python mobile\\scripts\\make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

BLUE = (47, 123, 255, 255)
WHITE = (255, 255, 255, 255)
OUT = Path(__file__).resolve().parent.parent / "assets" / "images"
SIZE = 1024
SS = 4  # draw big, then shrink, for smooth edges

# The arrow from favicon.svg, in its 64x64 box: M32 14 48 32H38V48H26V32H16Z
ARROW = [(32, 14), (48, 32), (38, 32), (38, 48), (26, 48), (26, 32), (16, 32)]


def arrow(draw: ImageDraw.ImageDraw, box: int, scale: float, color) -> None:
    """Arrow centred in a box of `box` pixels, `scale` times the size it has in the favicon's 56px square."""
    unit = box / 56 * scale
    cx, cy = 32, 31  # the arrow's centre in favicon units
    pts = [(box / 2 + (x - cx) * unit, box / 2 + (y - cy) * unit) for x, y in ARROW]
    draw.polygon(pts, fill=color)


def image(background, arrow_scale: float, color=WHITE, size: int = SIZE) -> Image.Image:
    big = Image.new("RGBA", (size * SS, size * SS), background)
    arrow(ImageDraw.Draw(big), size * SS, arrow_scale, color)
    return big.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    clear = (0, 0, 0, 0)
    image(BLUE, 0.95).convert("RGB").save(OUT / "icon.png")  # iOS rounds the corners itself
    image(clear, 0.62).save(OUT / "android-icon-foreground.png")  # inside Android's safe zone
    Image.new("RGBA", (SIZE, SIZE), BLUE).save(OUT / "android-icon-background.png")
    image(clear, 0.62, color=(0, 0, 0, 255)).save(OUT / "android-icon-monochrome.png")
    splash = Image.new("RGBA", (SIZE, SIZE), clear)
    mark = image(BLUE, 0.95, size=SIZE)
    mask = Image.new("L", (SIZE * SS, SIZE * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE * SS - 1, SIZE * SS - 1), radius=int(SIZE * SS * 14 / 56), fill=255)
    splash.paste(mark, (0, 0), mask.resize((SIZE, SIZE), Image.LANCZOS))
    splash.save(OUT / "splash-icon.png")
    splash.resize((48, 48), Image.LANCZOS).save(OUT / "favicon.png")
    print("Icons written to", OUT)


if __name__ == "__main__":
    main()
