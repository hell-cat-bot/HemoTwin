"""Generate PPTX-ready raster assets for the HemoTwin summit deck."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "deck" / "summit_assets"
OUT = ROOT / "deck" / "summit_2026" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

FONT_DIR = Path("C:/Windows/Fonts")
GEORGIA = FONT_DIR / "georgia.ttf"
GEORGIA_B = FONT_DIR / "georgiab.ttf"
GEORGIA_I = FONT_DIR / "georgiai.ttf"
SEGOE = FONT_DIR / "segoeui.ttf"
SEGOE_B = FONT_DIR / "segoeuib.ttf"
SEGOE_I = FONT_DIR / "segoeuii.ttf"
BAHN = FONT_DIR / "bahnschrift.ttf"

INK = (22, 26, 25)
MUTED = (110, 103, 93)
TERRA = (180, 71, 47)
SAGE = (63, 107, 94)
IVORY = (247, 242, 233)
CREAM = (237, 227, 211)
PAPER = (252, 251, 248)
LINE = (226, 217, 201)
TERRA_SOFT = (243, 228, 222)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def cover_background() -> None:
    src = Image.open(ASSETS / "bay_clean.png").convert("RGB")
    w, h = 2560, 1440
    scale = max(w / src.width, h / src.height)
    resized = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    base = resized.crop((left, top, left + w, top + h)).convert("RGBA")

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = overlay.load()
    for x in range(w):
        t = x / (w - 1)
        if t < 0.38:
            a = 250
        elif t < 0.62:
            a = round(250 + (140 - 250) * (t - 0.38) / 0.24)
        elif t < 0.82:
            a = round(140 + (28 - 140) * (t - 0.62) / 0.20)
        else:
            a = round(28 + (140 - 28) * (t - 0.82) / 0.18)
        for y in range(h):
            px[x, y] = (11, 13, 14, a)

    bottom = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(bottom)
    for y in range(h):
        t = y / (h - 1)
        a = round(max(0, (t - 0.56) / 0.44) * 200)
        d.rectangle((0, y, w, y), fill=(11, 13, 14, a))

    base = Image.alpha_composite(base, overlay)
    base = Image.alpha_composite(base, bottom)
    base.convert("RGB").save(OUT / "cover_bg.png", quality=95)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def framed(name: str, src: Path, content_w: int, content_h: int, pad: int = 14, radius: int = 10) -> None:
    scale = 2
    cw, ch = content_w * scale, content_h * scale
    pw = pad * scale
    canvas_w, canvas_h = cw + 2 * pw, ch + 2 * pw + 8 * scale
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (pw, pw + 6 * scale, pw + cw, pw + ch + 6 * scale),
        radius=radius * scale,
        fill=(30, 24, 16, 46),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(10 * scale))
    canvas = Image.alpha_composite(canvas, shadow)

    plate = Image.new("RGBA", (cw, ch), (255, 255, 255, 255))
    plate_draw = ImageDraw.Draw(plate)
    plate_draw.rounded_rectangle(
        (0, 0, cw - 1, ch - 1),
        radius=radius * scale,
        fill=(255, 255, 255, 255),
        outline=LINE + (255,),
        width=scale,
    )

    image = Image.open(src).convert("RGBA")
    image = image.resize((cw, ch), Image.LANCZOS)
    mask = rounded_mask((cw, ch), radius * scale)
    plate.paste(image, (0, 0), mask)
    canvas.alpha_composite(plate, (pw, pw))
    canvas.save(OUT / name)


def bar_chart(name: str, rows: list[tuple[str, float, str, str]], width: int = 520, height: int = 190) -> None:
    scale = 2
    W, H = width * scale, height * scale
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    label_font = font(SEGOE, 12 * scale)
    value_font = font(BAHN, 10 * scale)
    label_w = 205 * scale
    gap = 10 * scale
    track_x = label_w + gap
    track_w = 220 * scale
    value_x = track_x + track_w + gap
    top_pad = 10 * scale
    row_h = (H - 2 * top_pad) / len(rows)
    max_value = max(v for _, v, _, _ in rows) or 1.0
    for i, (label, value, _color, _display) in enumerate(rows):
        cy = top_pad + row_h * i + row_h / 2
        d.text((0, cy), label, font=label_font, fill=INK, anchor="lm")
        track_y = cy - 4.5 * scale
        d.rounded_rectangle(
            (track_x, track_y, track_x + track_w, track_y + 9 * scale),
            radius=2 * scale,
            fill=(22, 26, 25, 20),
        )
        fill_w = max(3 * scale, track_w * value / max_value)
        fill_color = {"ink": INK, "terra": TERRA, "grey": (154, 148, 136)}[_color]
        d.rounded_rectangle(
            (track_x, track_y, track_x + fill_w, track_y + 9 * scale),
            radius=2 * scale,
            fill=fill_color + (255,),
        )
        d.text((value_x, cy), _display, font=value_font, fill=MUTED, anchor="lm")
    img.save(OUT / name)


def dot_plot() -> None:
    scale = 2
    W, H = 1280, 148
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    axis_y = 116
    d.line((40, axis_y, W - 40, axis_y), fill=(22, 26, 25, 120), width=1 * scale)
    lab = font(BAHN, 16)
    small = font(BAHN, 14)
    points = [(0.405, "OURS 0.831", "PRE-SESSION", INK, 20), (0.55, "HONG 0.86", "META-ANALYSIS", (154, 148, 136), 16), (0.70, "ZHANG 0.89", "INTRA-SESSION", (154, 148, 136), 16)]
    for frac, l1, l2, color, r in points:
        x = round(40 + frac * (W - 80))
        d.ellipse((x - r // 2, axis_y - r // 2, x + r // 2, axis_y + r // 2), fill=color + (255,))
        d.text((x, 66), l1, font=lab, fill=color, anchor="ms")
        d.text((x, 86), l2, font=small, fill=MUTED, anchor="ms")
    d.text((40, H - 4), "0.75", font=small, fill=MUTED, anchor="ls")
    d.text((W - 40, H - 4), "0.95", font=small, fill=MUTED, anchor="rs")
    img.save(OUT / "dotplot.png")


def g7_plot() -> None:
    scale = 2
    W, H = 1120, 184
    img = Image.new("RGBA", (W, H), TERRA_SOFT + (255,))
    d = ImageDraw.Draw(img)
    axis_y = 116
    x0, x1 = 60, 1060
    zero_x = 554
    ci0, ci1 = 332, 904
    dot_x = 566
    d.line((x0, axis_y, x1, axis_y), fill=INK + (255,), width=2)
    d.line((zero_x, 30, zero_x, 142), fill=INK + (255,), width=2)
    d.rectangle((ci0, axis_y - 9 * scale, ci1, axis_y + 9 * scale), fill=(180, 71, 47, 50))
    d.line((ci0, axis_y, ci1, axis_y), fill=TERRA + (255,), width=3)
    d.line((ci0, axis_y - 12, ci0, axis_y + 12), fill=TERRA + (255,), width=3)
    d.line((ci1, axis_y - 12, ci1, axis_y + 12), fill=TERRA + (255,), width=3)
    d.ellipse((dot_x - 10, axis_y - 10, dot_x + 10, axis_y + 10), fill=TERRA + (255,))
    lab = font(BAHN, 17)
    small = font(BAHN, 17)
    d.text((x0, 154), "LESS UF", font=small, fill=MUTED, anchor="ls")
    d.text((x1, 154), "MORE UF", font=small, fill=MUTED, anchor="rs")
    d.text((zero_x, 24), "NO EFFECT", font=small, fill=MUTED, anchor="ms")
    d.text((ci0, 88), "-2.63", font=small, fill=MUTED, anchor="ms")
    d.text((ci1, 88), "+3.06", font=small, fill=MUTED, anchor="ms")
    d.text((dot_x + 24, 60), "+0.13", font=lab, fill=TERRA, anchor="ls")
    img.save(OUT / "g7_plot.png")


def main() -> None:
    cover_background()

    framed("chairs_frame.png", ASSETS / "chairs_revealed_crop.png", 700, 320, pad=14)
    framed("chair4_frame.png", ASSETS / "chair4_card.png", 416, 145, pad=12)

    fluid = Image.open(ASSETS / "fluid_table_crop.png")
    fluid.crop((0, 0, fluid.width, 472)).save(OUT / "_fluid.png")
    framed("fluid_frame.png", OUT / "_fluid.png", 740, 282, pad=14)

    replay = Image.open(ASSETS / "replay_chart_only.png")
    replay.crop((0, 0, replay.width, 360)).save(OUT / "_replay.png")
    framed("replay_frame.png", OUT / "_replay.png", 620, 317, pad=14)

    Image.open(ASSETS / "problem_chart.png").convert("RGBA").save(OUT / "problem_chart.png")

    bar_chart(
        "bars_risk.png",
        [
            ("Prior 10-session IDH rate", 20.6, "ink", "20.6%"),
            ("Prior 3-session mean nadir", 15.7, "ink", "15.7%"),
            ("Prior 10-session mean nadir", 10.3, "ink", "10.3%"),
            ("Prior session nadir", 6.0, "ink", "6.0%"),
            ("Dialysis vintage", 3.0, "ink", "3.0%"),
            ("Planned UF goal", 2.8, "ink", "2.8%"),
        ],
        width=520,
        height=180,
    )
    bar_chart(
        "bars_forecast.png",
        [
            ("Internal session projection *", 47.4, "grey", "47.4%"),
            ("Recent SBP minimum · 30 min", 12.0, "terra", "12.0%"),
            ("Recent SBP minimum · 60 min", 4.9, "terra", "4.9%"),
            ("Prior 3-session mean nadir", 4.2, "terra", "4.2%"),
            ("Prior 10-session mean nadir", 3.8, "terra", "3.8%"),
            ("Patient BP sensitivity", 3.4, "terra", "3.4%"),
        ],
        width=536,
        height=180,
    )
    dot_plot()
    g7_plot()
    thumbs()
    print("assets written to", OUT)


def thumbs() -> None:
    jobs = [
        ("thumb_chairs.png", ASSETS / "chairs_revealed_crop.png", None),
        ("thumb_case.png", ROOT / "docs" / "img" / "case_lab.png", (320, 80, 1540, 760)),
        ("thumb_live.png", ROOT / "docs" / "img" / "live_session.png", (320, 80, 1540, 760)),
        ("thumb_replay.png", ASSETS / "replay_chart_only.png", None),
        ("thumb_evidence.png", ROOT / "docs" / "img" / "evidence.png", (320, 80, 1540, 760)),
    ]
    for name, src, box in jobs:
        im = Image.open(src).convert("RGB")
        if box:
            im = im.crop(box)
        im = ImageOps.fit(im, (400, 224), method=Image.LANCZOS)
        tmp = OUT / "_thumb.png"
        im.save(tmp)
        framed(name, tmp, 200, 112, pad=8, radius=6)


if __name__ == "__main__":
    main()
