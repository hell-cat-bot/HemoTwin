"""Build the single-slide hemodialysis primer (16:9, light theme)."""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "deck" / "assets"
OUT = ROOT / "deck" / "HemoTwin_Dialysis.pptx"

SW, SH = 13.333, 7.5

INK = RGBColor(0x0C, 0x1B, 0x17)
BODY = RGBColor(0x33, 0x44, 0x3F)
MUTED = RGBColor(0x6B, 0x7D, 0x77)
TEAL = RGBColor(0x0E, 0x9F, 0x8A)
TEAL_DARK = RGBColor(0x0B, 0x6B, 0x5E)
MINT_FILL = RGBColor(0xF2, 0xF9, 0xF6)
MINT_LINE = RGBColor(0xC6, 0xE4, 0xDA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

DISPLAY = "Bahnschrift"
TEXT_FONT = "Segoe UI"
MONO = "Cascadia Mono"


def text(slide, x, y, w, h, runs, size=14, color=BODY, font=TEXT_FONT,
         bold=False, line=1.12, space_after=0, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, paragraph in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line
        p.space_after = Pt(space_after)
        for run_text, run_color, run_bold, run_font, run_size in paragraph:
            r = p.add_run()
            r.text = run_text
            r.font.name = run_font or font
            r.font.size = Pt(run_size or size)
            r.font.bold = run_bold if run_bold is not None else bold
            r.font.color.rgb = run_color or color
    return box


def pill(slide, x, y, w, h, s):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = MINT_FILL
    shape.line.color.rgb = MINT_LINE
    shape.line.width = Pt(0.75)
    shape.shadow.inherit = False
    shape.adjustments[0] = 0.5
    tf = shape.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = s
    r.font.name = MONO
    r.font.size = Pt(7.5)
    r.font.color.rgb = TEAL_DARK
    return shape


def bullets(slide, x, y, w, h, items):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, (lead, rest) in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 1.14
        p.space_after = Pt(11)
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(Emu(Inches(0.22))))
        pPr.set("indent", str(Emu(-Inches(0.22))))
        dot = p.add_run()
        dot.text = "\u2022  "
        dot.font.name = TEXT_FONT
        dot.font.size = Pt(14)
        dot.font.bold = True
        dot.font.color.rgb = TEAL
        l = p.add_run()
        l.text = lead
        l.font.name = TEXT_FONT
        l.font.size = Pt(14)
        l.font.bold = True
        l.font.color.rgb = INK
        r = p.add_run()
        r.text = " \u2014 " + rest
        r.font.name = TEXT_FONT
        r.font.size = Pt(14)
        r.font.color.rgb = BODY
    return box


def build() -> None:
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = WHITE

    # Full-height illustration panel.
    panel_x, panel_w = 7.5, SW - 7.5
    img_w, img_h = 1024, 1280
    panel_ratio = panel_w / SH
    crop = (1 - panel_ratio / (img_w / img_h)) / 2
    pic = slide.shapes.add_picture(str(ASSETS / "dialysis_scene.png"),
                                   Inches(panel_x), 0,
                                   width=Inches(panel_w), height=Inches(SH))
    pic.crop_left = crop
    pic.crop_right = crop

    text(slide, 0.75, 0.52, 6.3, 0.25, [[
        ("HEMOTWIN", INK, True, DISPLAY, 12),
        ("   CHAIR-SIDE SESSION TWIN", MUTED, None, MONO, 8.5),
    ]])

    text(slide, 0.75, 1.66, 6.3, 0.24, [[
        ("HEMODIALYSIS \u00b7 THE BASICS", TEAL, None, MONO, 9.5),
    ]])

    title_box = slide.shapes.add_textbox(Inches(0.75), Inches(1.96),
                                         Inches(6.35), Inches(1.9))
    tf = title_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, (s, color) in enumerate([("A kidney,", INK),
                                    ("outside the body.", TEAL)]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 0.94
        p.space_after = Pt(0)
        r = p.add_run()
        r.text = s
        r.font.name = DISPLAY
        r.font.size = Pt(52)
        r.font.bold = True
        r.font.color.rgb = color

    bullets(slide, 0.75, 3.98, 6.2, 1.9, [
        ("When kidneys fail", "waste and fluid build up in the blood."),
        ("A machine steps in", "a dialyzer takes over the filtering."),
        ("Clean blood returns", "waste and fluid are left behind."),
    ])

    pill(slide, 0.75, 6.08, 1.02, 0.32, "3 \u00d7 / WEEK")
    pill(slide, 1.93, 6.08, 1.36, 0.32, "\u2248 4 H / SESSION")
    pill(slide, 3.45, 6.08, 1.82, 0.32, "\u2248 70 L BLOOD / SESSION")

    text(slide, 0.75, 6.86, 6.3, 0.2, [[
        ("ILLUSTRATIVE SCENE \u00b7 RESEARCH PROTOTYPE \u00b7 NOT A MEDICAL DEVICE",
         MUTED, None, MONO, 7.5),
    ]])

    slide.notes_slide.notes_text_frame.text = (
        "Hemodialysis, the short version: when the kidneys can no longer clear "
        "waste and fluid, blood is pumped from the patient's vascular access "
        "through a dialyzer and returned. A typical in-centre schedule is three "
        "sessions a week of about four hours, with roughly 70 litres of blood "
        "passing through the filter per session. This slide is illustrative; "
        "HemoTwin is a research prototype, not a medical device."
    )

    prs.save(str(OUT))
    print("saved", OUT)


if __name__ == "__main__":
    build()
