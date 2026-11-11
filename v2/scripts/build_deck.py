"""Build the HemoTwin V2 cinematic deck (16 slides, 16:9)."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "deck" / "assets"
OUT = ROOT / "deck" / "HemoTwin_v2.pptx"

# 16:9 canvas.
SW, SH = 13.333, 7.5

# Palette.
BG = RGBColor(0x05, 0x0A, 0x12)
PANEL = RGBColor(0x0B, 0x15, 0x24)
PANEL_2 = RGBColor(0x07, 0x11, 0x1F)
LINE = RGBColor(0x1E, 0x3A, 0x4A)
TEXT = RGBColor(0xF4, 0xF8, 0xFB)
BODY = RGBColor(0xC7, 0xD6, 0xE6)
MUTED = RGBColor(0x93, 0xA4, 0xB8)
CYAN = RGBColor(0x22, 0xD3, 0xEE)
TEAL = RGBColor(0x2D, 0xD4, 0xBF)
VIOLET = RGBColor(0xA7, 0x8B, 0xFA)
AMBER = RGBColor(0xFB, 0xBF, 0x24)
CORAL = RGBColor(0xFB, 0x71, 0x85)
GOOD = RGBColor(0x34, 0xD3, 0x99)

TITLE_FONT = "Bahnschrift"
BODY_FONT = "Segoe UI"


def new_deck() -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    return prs


def blank(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_picture(str(ASSETS / "deck_bg.png"), 0, 0,
                             width=Inches(SW), height=Inches(SH))
    return slide


def notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def text(slide, x, y, w, h, s, size=14, color=BODY, bold=False,
         font=BODY_FONT, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         line=1.08, space_after=0, italic=False, margins=(0, 0, 0, 0)):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left, tf.margin_top, tf.margin_right, tf.margin_bottom = [
        Inches(v) for v in margins]
    tf.vertical_anchor = anchor
    lines = str(s).split("\n")
    for i, line_text in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line
        p.space_after = Pt(space_after)
        run = p.add_run()
        run.text = line_text
        run.font.name = font
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color
    return box


def kicker(slide, x, y, s, color=CYAN, size=9):
    text(slide, x, y, 8.5, 0.25, s.upper(), size=size, color=color,
         bold=True, font=TITLE_FONT)


def title(slide, x, y, w, s, size=32, color=TEXT, line=0.98):
    text(slide, x, y, w, 1.35, s, size=size, color=color, bold=True,
         font=TITLE_FONT, line=line)


def body(slide, x, y, w, h, s, size=13, color=BODY, line=1.15):
    text(slide, x, y, w, h, s, size=size, color=color, font=BODY_FONT, line=line)


def bullets(slide, x, y, w, h, items, size=12, color=BODY,
            bullet_color=CYAN, space_after=7, line=1.12):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        p.line_spacing = line
        r1 = p.add_run()
        r1.text = "•  "
        r1.font.name = BODY_FONT
        r1.font.size = Pt(size)
        r1.font.bold = True
        r1.font.color.rgb = bullet_color
        r2 = p.add_run()
        r2.text = item
        r2.font.name = BODY_FONT
        r2.font.size = Pt(size)
        r2.font.color.rgb = color
    return box


def card(slide, x, y, w, h, fill=PANEL, line_color=LINE, radius=0.07):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line_color
    shape.line.width = Pt(1)
    shape.shadow.inherit = False
    try:
        shape.adjustments[0] = radius
    except Exception:
        pass
    return shape


def pill(slide, x, y, w, h, s, color=CYAN, size=8, fill=PANEL_2):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = color
    shape.line.width = Pt(0.75)
    shape.shadow.inherit = False
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = s.upper()
    r.font.name = TITLE_FONT
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.color.rgb = color
    return shape


def image_cover(slide, name, x, y, w, h, border=True):
    path = ASSETS / name
    iw, ih = Image.open(path).size
    target = w / h
    source = iw / ih
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y),
                                   width=Inches(w), height=Inches(h))
    if source > target:
        crop = (1 - target / source) / 2
        pic.crop_left = crop
        pic.crop_right = crop
    else:
        crop = (1 - source / target) / 2
        pic.crop_top = crop
        pic.crop_bottom = crop
    if border:
        frame = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                       Inches(x), Inches(y), Inches(w), Inches(h))
        frame.fill.background()
        frame.line.color.rgb = LINE
        frame.line.width = Pt(0.9)
        frame.shadow.inherit = False
    return pic


def image_fit(slide, name, x, y, w, border=True):
    """Place an image at its natural aspect ratio (no crop) and return its height."""
    path = ASSETS / name
    iw, ih = Image.open(path).size
    h = w * ih / iw
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y),
                                   width=Inches(w), height=Inches(h))
    if border:
        frame = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                       Inches(x), Inches(y), Inches(w), Inches(h))
        frame.fill.background()
        frame.line.color.rgb = LINE
        frame.line.width = Pt(0.9)
        frame.shadow.inherit = False
    return h


def footer(slide, idx: int, total: int = 16):
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(7.12),
                                  Inches(12.13), Inches(0.008))
    line.fill.solid()
    line.fill.fore_color.rgb = LINE
    line.line.fill.background()
    text(slide, 0.6, 7.18, 8.8, 0.2,
         "HEMOTWIN · RESEARCH PROTOTYPE · NOT A MEDICAL DEVICE", size=7.5,
         color=MUTED, font=TITLE_FONT)
    text(slide, 11.2, 7.18, 1.5, 0.2, f"{idx:02d} / {total:02d}", size=7.5,
         color=MUTED, font=TITLE_FONT, align=PP_ALIGN.RIGHT)


def metric_card(slide, x, y, w, h, label, value, sub, value_color=CYAN,
                value_size=26):
    card(slide, x, y, w, h)
    kicker(slide, x + 0.18, y + 0.12, label, color=MUTED, size=7.5)
    text(slide, x + 0.18, y + 0.31, w - 0.36, 0.5, value, size=value_size,
         color=value_color, bold=True, font=TITLE_FONT)
    text(slide, x + 0.18, y + h - 0.36, w - 0.36, 0.3, sub, size=7.5,
         color=MUTED, font=BODY_FONT, line=1.0)


# ---------------------------------------------------------------------------
# 01 COVER
# ---------------------------------------------------------------------------
def slide_cover(prs, idx):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.shapes.add_picture(str(ASSETS / "hero_kidney.jpg"), 0, 0,
                         width=Inches(SW), height=Inches(SH))
    s.shapes.add_picture(str(ASSETS / "fade_left.png"), 0, 0,
                         width=Inches(SW), height=Inches(SH))
    # Brand
    dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.8), Inches(0.62),
                             Inches(0.12), Inches(0.12))
    dot.fill.solid(); dot.fill.fore_color.rgb = CYAN; dot.line.fill.background()
    text(s, 1.02, 0.55, 5.0, 0.25, "HEMOTWIN", size=12, color=TEXT,
         bold=True, font=TITLE_FONT)
    text(s, 1.02, 0.78, 5.6, 0.2,
         "DIGITAL TWIN CHALLENGE 2026 · RESEARCH PROTOTYPE", size=7.5,
         color=MUTED, font=TITLE_FONT)
    # Title
    text(s, 0.8, 1.55, 7.0, 2.4,
         "Buy time\nbefore the crash.", size=54, color=TEXT, bold=True,
         font=TITLE_FONT, line=0.94)
    line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.82), Inches(4.08),
                              Inches(1.5), Inches(0.035))
    line.fill.solid(); line.fill.fore_color.rgb = CYAN; line.line.fill.background()
    text(s, 0.8, 4.28, 6.4, 0.95,
         "A chair-side session twin for dialysis: calibrated forecast, exact "
         "fluid arithmetic, and a review pathway.", size=15, color=BODY,
         font=BODY_FONT, line=1.2)
    pill(s, 0.8, 5.35, 3.55, 0.34, "RESEARCH PROTOTYPE · NOT A PRESCRIPTION",
         color=AMBER, size=7.5)
    text(s, 0.8, 6.55, 7.6, 0.35,
         "HEMOBP (Taiwan) · 205,482 sessions · 1,070 patients · CC BY 4.0",
         size=8, color=MUTED, font=BODY_FONT)
    text(s, 0.8, 6.82, 7.6, 0.25,
         "Fold 2 untouched · no treatment-effect claim · no machine control",
         size=8, color=MUTED, font=BODY_FONT)
    notes(s, "Open with the real unit: the doctor is remote, the technician is at "
             "the chair, and IDH does not wait. The product's job is time, not "
             "another prediction score.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 02 FIELD REALITY
# ---------------------------------------------------------------------------
def slide_field(prs, idx):
    s = blank(prs)
    image_cover(s, "remote_unit.jpg", 6.0, 0, 7.33, SH, border=False)
    s.shapes.add_picture(str(ASSETS / "fade_left_panel.png"), 0, 0,
                         width=Inches(SW), height=Inches(SH))
    kicker(s, 0.7, 0.62, "THE FIELD REALITY")
    title(s, 0.7, 0.92, 5.25,
          "The doctor is remote.\nThe technician is at the chair.", size=28)
    body(s, 0.7, 2.95, 5.15, 0.9,
         "We build a remotely operable, IoT-enabled hemodialysis machine. In "
         "the units it serves, the person at the chair often has to act before "
         "a doctor can be reached.", size=12.5)
    body(s, 0.7, 3.8, 5.15, 0.8,
         "IDH is one of the most common and risky events of a session. The gap "
         "is not another score. It is time and a shared trade-off.", size=12.5,
         color=TEXT)
    card(s, 0.7, 4.75, 5.1, 1.0, fill=PANEL_2, line_color=CYAN)
    text(s, 0.9, 4.92, 4.75, 0.7,
         "“The technician needs to know what to ask, not just that the pressure is falling.”",
         size=12.5, color=TEXT, italic=True, font=BODY_FONT, line=1.12)
    text(s, 0.7, 6.15, 5.15, 0.6,
         "Labelled hypotension: 10.4% of HEMOBP sessions (nadir <90 mmHg). "
         "Spanish cohort: 25.5% clinician-defined symptomatic. Two labels — "
         "never combined. 3D concept illustration.",
         size=7.5, color=MUTED, font=BODY_FONT, line=1.15)
    notes(s, "This is the user's field reality: a remote machine, an untrained "
             "or lightly trained technician, and a doctor who is not in the room. "
             "The two prevalence numbers use different labels; never add them.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 03 WHY PREDICTION FAILS
# ---------------------------------------------------------------------------
def slide_gap(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "THE GAP")
    title(s, 0.7, 0.92, 11.6, "A monitor is not a plan.", size=34)
    items = [
        ("CLIMB · 2005", "WORSE", "Blood-volume monitors plus an algorithm. "
         "Outcomes got worse, not better. More data did not equal better care.",
         CORAL),
        ("OUR EVENT MODEL · 2026", "8.2%", "Detection at the pre-registered "
         "0.26 false-alert budget — below the current-SBP rule. Ranking is not "
         "timing.", AMBER),
        ("THE FIELD", "AUROC", "Papers report ranking. The chair needs mmHg and "
         "a false-alert budget. Prediction without a response workflow fails.",
         CYAN),
    ]
    for i, (k, value, text_body, color) in enumerate(items):
        x = 0.6 + i * 4.08
        card(s, x, 1.75, 3.9, 3.55)
        kicker(s, x + 0.22, 1.92, k, color=MUTED, size=7.5)
        text(s, x + 0.22, 2.18, 3.4, 0.65, value, size=30, color=color,
             bold=True, font=TITLE_FONT)
        body(s, x + 0.22, 2.95, 3.4, 1.7, text_body, size=11.5, line=1.2)
    card(s, 0.6, 5.55, 12.13, 0.92, fill=PANEL_2, line_color=CYAN)
    text(s, 0.85, 5.68, 11.6, 0.65,
         "The one deployed system that paired prediction with a nursing "
         "response reported IDH 26.1% → 12.9% over four years. The workflow is "
         "the product.", size=13, color=TEXT, font=BODY_FONT, line=1.12)
    text(s, 0.7, 6.55, 11.6, 0.3,
         "Sources: Leung, JAMA 2005; BestShape, Clin Kidney J 2025. Our own "
         "event model remains shadow-only.", size=7.5, color=MUTED,
         font=BODY_FONT)
    notes(s, "Three failures: monitoring alone, our own ranking model, and the "
             "field's AUROC habit. The lesson is that the response workflow is "
             "the product. We do not claim ours is validated.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 04 PRODUCT
# ---------------------------------------------------------------------------
def slide_product(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "THE PRODUCT")
    title(s, 0.7, 0.92, 5.0, "One console.\nThree views.\nOne honest boundary.",
          size=30)
    blocks = [
        ("CASE LAB", "Seven chair-side stories, one calibrated chart.",
         "The showpiece."),
        ("LIVE SESSION", "Enter a real session. Get a protocol state and the "
         "fluid arithmetic.", "The working console."),
        ("EVIDENCE & HANDOFF", "Gates, G7, FHIR, audit, pod triage.",
         "The proof."),
    ]
    y = 2.85
    for k, t, sub in blocks:
        kicker(s, 0.72, y, k, color=CYAN, size=7.5)
        text(s, 0.72, y + 0.18, 4.2, 0.55, t, size=12, color=TEXT,
             font=BODY_FONT, line=1.12)
        text(s, 0.72, y + 0.58, 4.2, 0.25, sub, size=8, color=MUTED,
             font=BODY_FONT)
        y += 0.95
    pill(s, 0.7, 5.8, 3.7, 0.34, "MIRROR · SHOW · BUY TIME", color=TEAL,
         size=7.5)
    image_cover(s, "app_case_lab_main.png", 5.55, 0.75, 7.2, 5.8)
    text(s, 5.55, 6.62, 7.2, 0.22,
         "The Case lab, running locally with the bundled evidence. No raw data, "
         "no network.", size=7.5, color=MUTED, font=BODY_FONT)
    notes(s, "This is the product surface. The screenshot is the real app, not "
             "a mockup. One console, three views, and the boundary is visible "
             "from the first screen.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 05 CASE LAB
# ---------------------------------------------------------------------------
def slide_case_lab(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "CASE LAB")
    title(s, 0.7, 0.92, 11.6, "Seven stories. One honest chart.", size=32)
    image_fit(s, "fan_chart_dark.png", 0.6, 1.55, 7.55)
    text(s, 0.65, 5.95, 7.4, 0.3,
         "g1_taper_showcase · anchor 172 · calibrated 116.6 · observed 115",
         size=8, color=MUTED, font=BODY_FONT)
    metric_card(s, 8.45, 1.55, 4.28, 1.2, "OBSERVED", "115",
                "ground truth · amber diamonds", AMBER)
    metric_card(s, 8.45, 2.9, 4.28, 1.2, "CALIBRATED", "116.6",
                "fair pre-anchor · cyan line", CYAN)
    metric_card(s, 8.45, 4.25, 4.28, 1.2, "RETIRED V3", "167",
                "not used · violet X", VIOLET)
    card(s, 8.45, 5.65, 4.28, 1.2, fill=PANEL_2, line_color=AMBER)
    text(s, 8.65, 5.78, 3.9, 0.95,
         "Shaded band = 90% nadir interval, widened along the path. The dashed "
         "sketch is off by default: the twin experiment failed.", size=9.5,
         color=BODY, font=BODY_FONT, line=1.15)
    notes(s, "The chart is the product. The amber diamonds are ground truth; "
             "the cyan line is the only validated projection; the violet X is "
             "the retired v3 twin. The illustration stays hidden by default.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 06 FORECAST LINEAGE
# ---------------------------------------------------------------------------
def slide_lineage(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "FORECAST LINEAGE")
    title(s, 0.7, 0.92, 11.6, "Two forecasts. Do not mix them.", size=34)
    # Fair card
    card(s, 0.6, 1.65, 5.95, 3.95, line_color=CYAN)
    kicker(s, 0.85, 1.85, "FAIR PRE-ANCHOR TWIN", color=CYAN, size=7.5)
    text(s, 0.85, 2.12, 3.0, 0.8, "10.99", size=46, color=CYAN, bold=True,
         font=TITLE_FONT)
    text(s, 2.55, 2.35, 3.7, 0.35, "fold-2 MAE (mmHg)", size=11, color=MUTED,
         font=BODY_FONT)
    bullets(s, 0.85, 3.05, 5.2, 1.3, [
        "59 features · no future-UF oracle block.",
        "RMSE 14.65 · fold 2 untouched.",
        "This is the calibrated floor used in the console.",
    ], size=10.5, bullet_color=CYAN, space_after=6)
    pill(s, 0.85, 4.78, 2.5, 0.32, "USED IN THE CONSOLE", color=TEAL, size=7)
    # Oracle card
    card(s, 6.75, 1.65, 5.95, 3.95, line_color=VIOLET)
    kicker(s, 7.0, 1.85, "FORECAST-V2 ORACLE DISPLAY", color=VIOLET, size=7.5)
    text(s, 7.0, 2.12, 3.0, 0.8, "9.60", size=46, color=VIOLET, bold=True,
         font=TITLE_FONT)
    text(s, 8.7, 2.35, 3.7, 0.35, "fold-2 MAE (mmHg)", size=11, color=MUTED,
         font=BODY_FONT)
    bullets(s, 7.0, 3.05, 5.2, 1.3, [
        "72 features · 13 observed future-UF features.",
        "Display-only; not a treatment model.",
        "Not the G2 baseline.",
    ], size=10.5, bullet_color=VIOLET, space_after=6)
    pill(s, 7.0, 4.78, 2.9, 0.32, "DISPLAY ONLY · NOT THE BASELINE",
         color=VIOLET, size=7)
    card(s, 0.6, 5.85, 12.13, 0.8, fill=PANEL_2, line_color=AMBER)
    text(s, 0.85, 5.98, 11.6, 0.55,
         "The smaller oracle number is not a better twin. The baseline check (G2) "
         "compares the twin to its own fair baseline; the oracle comparison is "
         "a reported failure.",
         size=12.5, color=TEXT, font=BODY_FONT, line=1.12)
    text(s, 0.7, 6.8, 11.6, 0.22,
         "Fold 2 untouched by tuning. G2 plan-written baseline: FAIL.",
         size=7.5, color=MUTED, font=BODY_FONT)
    notes(s, "This is the first judge question. The app's twin uses the fair "
             "10.99 model. The 9.60 is an oracle-assisted display forecast with "
             "future UF; it is not the G2 baseline. Never compare them as if "
             "they were the same model.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 07 FLUID ARITHMETIC
# ---------------------------------------------------------------------------
def slide_fluid(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "FLUID ARITHMETIC")
    title(s, 0.7, 0.92, 11.6, "The trade-off, in litres.", size=34)
    rows = [
        ("Hold current UF", "0.50 L", "16.5", "116.6"),
        ("Taper to 75%", "0.68 L", "17.4", "116.6"),
        ("Taper to 50%", "0.88 L", "18.4", "116.6"),
        ("Keep-open 0.10 L/h", "1.18 L", "19.9", "116.6"),
        ("30-min pause, then resume", "0.88 L", "18.4", "116.6"),
    ]
    headers = ["UF policy", "Fluid left", "Next-session UF", "Calibrated +60"]
    xs = [0.75, 3.55, 5.15, 7.05]
    ws = [2.6, 1.45, 1.75, 1.55]
    for x, w, h in zip(xs, ws, headers):
        text(s, x, 1.62, w, 0.22, h.upper(), size=7.5, color=MUTED,
             font=TITLE_FONT, bold=True)
    line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.7), Inches(1.92),
                              Inches(7.9), Inches(0.008))
    line.fill.solid(); line.fill.fore_color.rgb = LINE; line.line.fill.background()
    for i, (policy, fluid, next_uf, nadir) in enumerate(rows):
        y = 2.08 + i * 0.62
        if i % 2 == 1:
            card(s, 0.62, y - 0.06, 8.02, 0.55, fill=PANEL_2, line_color=LINE)
        text(s, 0.75, y, 2.6, 0.3, policy, size=10.5, color=TEXT,
             font=BODY_FONT)
        text(s, 3.55, y, 1.45, 0.3, fluid, size=10.5, color=CYAN,
             font=TITLE_FONT, bold=True)
        text(s, 5.15, y, 1.75, 0.3, next_uf + " mL/kg/h", size=10.5,
             color=AMBER, font=TITLE_FONT)
        text(s, 7.05, y, 1.55, 0.3, nadir, size=10.5, color=MUTED,
             font=TITLE_FONT)
    text(s, 0.7, 5.48, 7.9, 0.55,
         "At calibrated gain 0 the +60 min value is identical across policies. The "
         "fluid arithmetic is what changes.", size=10, color=BODY,
         font=BODY_FONT)
    card(s, 8.55, 1.6, 4.18, 2.75, fill=PANEL_2, line_color=CYAN)
    text(s, 8.78, 1.82, 3.7, 1.9,
         "“This is the number a technician can take to a doctor. It is not a "
         "prescription.”", size=17, color=TEXT, italic=True,
         font=BODY_FONT, line=1.18)
    text(s, 8.78, 3.85, 3.7, 0.35, "The trade-off is the conversation.",
         size=9, color=MUTED, font=BODY_FONT)
    card(s, 8.55, 4.6, 4.18, 1.65, fill=PANEL, line_color=LINE)
    text(s, 8.78, 4.78, 3.7, 1.25,
         "Case g1_taper_showcase: calibrated 116.6 vs observed 115. The fair "
         "forecast is close; the arithmetic is the honest decision surface.",
         size=10, color=BODY, font=BODY_FONT, line=1.18)
    text(s, 0.7, 6.55, 11.8, 0.3,
         "Next-session UF reference flag: 13 mL/kg/h. Arithmetic only; not a "
         "feasibility, safety, or prescription determination.", size=7.5,
         color=MUTED, font=BODY_FONT)
    notes(s, "Use the g1_taper_showcase because the fair forecast is close "
             "(116.6 vs 115). The table shows that the calibrated nadir is "
             "identical across policies at gain 0; only the fluid arithmetic "
             "changes. That is the trade-off the technician can discuss.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 08 PROTOCOL
# ---------------------------------------------------------------------------
def slide_protocol(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "DECISION SUPPORT")
    title(s, 0.7, 0.92, 11.6, "The next step is a pathway, not a score.",
          size=32)
    image_fit(s, "app_protocol_panel.png", 0.6, 1.55, 6.9)
    text(s, 0.65, 4.98, 6.8, 0.22,
         "True crash case · observed nadir 59 · protocol state REVIEW NOW",
         size=7.5, color=MUTED, font=BODY_FONT)
    card(s, 0.6, 5.3, 6.9, 1.15, fill=PANEL_2, line_color=CYAN)
    text(s, 0.85, 5.45, 6.45, 0.85,
         "The protocol state is deterministic. The forecast never gates it, "
         "and the shadow score has no alert authority. The pathway is the product.",
         size=10.5, color=TEXT, font=BODY_FONT, line=1.15)
    steps = [
        ("01", "ASSESS THE PATIENT AT THE CHAIR",
         "Look, check consciousness and reported symptoms, note position. "
         "Follow the local emergency pathway for red flags."),
        ("02", "REPEAT AND VERIFY BP",
         "Repeat the measurement with the unit's routine technique. Record "
         "cuff size, arm position, observed vs interpolated."),
        ("03", "REVIEW THE UF STATE",
         "Goal, volume removed, remaining volume, rate. Only authorized roles "
         "change machine settings."),
    ]
    y = 1.5
    for num, head, text_body in steps:
        card(s, 7.85, y, 4.85, 1.45)
        text(s, 8.02, y + 0.14, 0.55, 0.4, num, size=16, color=CYAN,
             bold=True, font=TITLE_FONT)
        text(s, 8.55, y + 0.14, 3.95, 0.28, head, size=9.5, color=TEXT,
             bold=True, font=TITLE_FONT)
        body(s, 8.55, y + 0.45, 3.95, 0.85, text_body, size=8.5, line=1.15)
        y += 1.58
    text(s, 7.85, 6.35, 4.85, 0.5,
         "Measured criteria activate URGENT / REVIEW_NOW / NO_ALERT / "
         "INSUFFICIENT. The forecast never gates the state. The shadow score "
         "has no alert authority.", size=8, color=MUTED, font=BODY_FONT,
         line=1.12)
    notes(s, "The true crash case: observed 59, state REVIEW_NOW. The pathway "
             "tells the team what to check and who to call. This is how the "
             "product buys time. The protocol is a configured research artifact, "
             "not a validated workflow.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 09 G7 EXPERIMENT
# ---------------------------------------------------------------------------
def slide_g7(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "THE TWIN EXPERIMENT")
    title(s, 0.7, 0.92, 11.6, "We tested it. It failed.", size=34)
    image_fit(s, "g7_forest_dark.png", 0.6, 1.55, 7.15)
    metric_card(s, 8.0, 1.5, 4.7, 1.15, "MATCHED EVENTS", "581 / 158",
                "events / patients · within-patient", CYAN, value_size=24)
    metric_card(s, 8.0, 2.68, 4.7, 1.15, "EARLY-UF EFFECT", "+0.13",
                "mmHg per 0.25 L/h · CI [−2.63, +3.06]", CORAL, value_size=24)
    metric_card(s, 8.0, 3.86, 4.7, 1.15, "SHAM-TIME CHECK", "+2.91",
                "mmHg · CI [2.31, 3.54] · fails", CORAL, value_size=24)
    metric_card(s, 8.0, 5.04, 4.7, 1.15, "TRAJECTORY CHECK", "+0.43",
                "mmHg worse · CI [0.15, 0.65]", CORAL, value_size=24)
    card(s, 0.6, 6.22, 12.13, 0.66, fill=PANEL_2, line_color=CORAL)
    text(s, 0.85, 6.31, 11.6, 0.5,
         "VERDICT: FAIL — early UF reduction did not raise SBP more than "
         "matched controls. The effect is indistinguishable from zero; the "
         "operational gain stays 0.", size=10.5, color=CORAL, bold=True,
         font=TITLE_FONT, line=1.1)
    text(s, 0.7, 6.95, 11.6, 0.2,
         "Protocol SHA-256 frozen before estimation. 95% bootstrap CIs, "
         "patient-clustered.", size=7, color=MUTED, font=BODY_FONT)
    notes(s, "This is the trust slide. 581 matched events across 158 patients; "
             "the effect is +0.13 mmHg with a CI that includes zero; the sham "
             "control fails; P6a gets worse out of sample. Say FAIL clearly.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 10 CLAIM BOUNDARY
# ---------------------------------------------------------------------------
def slide_boundary(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "CLAIM BOUNDARY")
    title(s, 0.7, 0.92, 11.6, "What we refuse to claim.", size=34)
    card(s, 0.6, 1.6, 5.95, 4.35, line_color=TEAL)
    kicker(s, 0.85, 1.8, "WE CAN CLAIM", color=TEAL, size=7.5)
    bullets(s, 0.85, 2.1, 5.35, 3.6, [
        "A calibrated pre-anchor nadir forecast: fold-2 MAE 10.99, RMSE 14.65.",
        "Exact arithmetic for fluid left, carry-forward and next-session intensity.",
        "A deterministic, versioned review pathway with role-scoped steps.",
        "Honest negative results: G3, G7 and the oracle G2 comparison.",
        "A local FHIR export and a hash-chained demo audit trail.",
    ], size=10.5, bullet_color=TEAL, space_after=11)
    card(s, 6.75, 1.6, 5.95, 4.35, line_color=CORAL)
    kicker(s, 7.0, 1.8, "WE REFUSE TO CLAIM", color=CORAL, size=7.5)
    bullets(s, 7.0, 2.1, 5.35, 3.6, [
        "A validated what-if/treatment effect from the twin.",
        "That any UF policy will raise SBP, prevent IDH, or is minimum effective.",
        "Alert utility, clinical benefit, or a safety layer.",
        "Prospective, external, symptomatic-IDH, or Indian-unit validation.",
        "A prescription, a default dose, or autonomous machine action.",
    ], size=10.5, bullet_color=CORAL, space_after=11)
    text(s, 0.7, 6.25, 11.6, 0.5,
         "The boundary is part of the product. It is why the rest is trustworthy.",
         size=15, color=TEXT, bold=True, font=TITLE_FONT)
    notes(s, "Judges trust the refusal more than the claim. The boundary is "
             "written into the app, the README, the evidence and this deck.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 11 EVIDENCE STACK
# ---------------------------------------------------------------------------
def slide_evidence(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "THE EVIDENCE")
    title(s, 0.7, 0.92, 11.6, "205,482 sessions. 581 matched events.",
          size=32)
    image_fit(s, "cohort_funnel.png", 0.6, 1.55, 7.2)
    card(s, 0.6, 5.15, 7.2, 0.62, fill=PANEL_2, line_color=LINE)
    text(s, 0.82, 5.27, 6.8, 0.4,
         "205,482 QC-eligible → 205,113 G7 census → 581 matched events. "
         "369 sessions lack the required pre-anchor record.",
         size=8.5, color=BODY, font=BODY_FONT, line=1.1)
    metric_card(s, 8.15, 1.55, 2.18, 1.45, "SESSIONS", "205,482",
                "QC-eligible", CYAN)
    metric_card(s, 10.45, 1.55, 2.28, 1.45, "PATIENTS", "1,070",
                "de-identified", TEAL)
    metric_card(s, 8.15, 3.2, 2.18, 1.45, "TELEMETRY", "4.19M",
                "rows", VIOLET)
    metric_card(s, 10.45, 3.2, 2.28, 1.45, "LABELLED IDH", "10.4%",
                "nadir <90 mmHg", AMBER)
    pill(s, 8.15, 4.9, 2.18, 0.32, "FOLD 2 UNTOUCHED", color=GOOD, size=7)
    text(s, 0.7, 5.95, 11.9, 0.8,
         "G7 census 205,113 — 369 sessions lack the required pre-anchor record. "
         "25.5% Spanish clinician-defined symptomatic hypotension: a different "
         "label, never combined. External transport AUROC 0.474 failed. HEMOBP "
         "CC BY 4.0.", size=8, color=MUTED, font=BODY_FONT, line=1.15)
    notes(s, "Do not mix the two prevalence labels. The 369-session difference "
             "between 205,482 and 205,113 is the pre-anchor record requirement. "
             "The external transport failure is part of the honesty story.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 12 ENGINEERING
# ---------------------------------------------------------------------------
def slide_engineering(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "ENGINEERING")
    title(s, 0.7, 0.92, 11.6, "Built to be inspected.", size=34)
    cards = [
        ("217", "package tests · 0 failures",
         "28 heavy-artifact tests explicitly skip-gated. Full lab suite: 241.",
         CYAN),
        ("14/14", "claim-boundary checks",
         "Frozen G1–G7, banned claims, cohort/demo integrity, deck/README links.",
         TEAL),
        ("FHIR R4", "local export",
         "Bilingual handoff card. No network call at runtime.",
         VIOLET),
        ("SHA-256", "audit chain",
         "Demo-only local chain. Not immutable, not authenticated, not clinical.",
         AMBER),
    ]
    for i, (value, label, sub, color) in enumerate(cards):
        x = 0.6 + i * 3.11
        card(s, x, 1.65, 2.95, 2.65)
        text(s, x + 0.2, 1.82, 2.55, 0.55, value, size=24, color=color,
             bold=True, font=TITLE_FONT)
        text(s, x + 0.2, 2.38, 2.55, 0.35, label, size=10, color=TEXT,
             font=BODY_FONT, bold=True)
        body(s, x + 0.2, 2.8, 2.55, 1.3, sub, size=8.5, line=1.15)
    card(s, 0.6, 4.62, 12.13, 0.85, fill=PANEL_2, line_color=CYAN)
    text(s, 0.85, 4.75, 11.6, 0.55,
         "DATA  →  FEATURES  →  FORECAST  →  PROTOCOL  →  HANDOFF",
         size=15, color=CYAN, bold=True, font=TITLE_FONT)
    text(s, 0.7, 5.75, 11.8, 0.7,
         "One app, one README, one deck. The retired v3 console is not shipped; "
         "the current console runs from a clean V2 folder with the bundled "
         "models and evidence.", size=9, color=BODY, font=BODY_FONT, line=1.15)
    notes(s, "The package suite is 217 tests with 28 skip-gated heavy-artifact "
             "tests; the full lab suite is 241. The claim verifier is 14/14. "
             "The audit chain is demo-only and says so.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 13 PILOT ASK
# ---------------------------------------------------------------------------
def slide_pilot(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "THE ASK")
    title(s, 0.7, 0.92, 8.0, "Give us a chair, not a stage.", size=34)
    body(s, 0.7, 1.85, 8.0, 1.2,
         "We are not asking for a trial on day one. Run the console beside the "
         "team, log what it would have shown, and measure whether it buys time "
         "to react.", size=13)
    steps = [
        ("01", "SILENT MODE", "2–4 weeks beside the team. No machine control, "
         "no alert authority. Log every display."),
        ("02", "LOCAL RECALIBRATION", "Your machine, your population, your "
         "protocol. Re-fit the forecast before any claim."),
        ("03", "PROSPECTIVE EVALUATION", "Time-to-review, documentation, and "
         "workflow. Pre-register the endpoint before the pilot."),
    ]
    for i, (num, head, text_body) in enumerate(steps):
        x = 0.6 + i * 2.95
        card(s, x, 3.45, 2.75, 1.9)
        text(s, x + 0.18, 3.6, 0.5, 0.35, num, size=15, color=CYAN,
             bold=True, font=TITLE_FONT)
        text(s, x + 0.18, 3.98, 2.35, 0.3, head, size=8.5, color=TEXT,
             bold=True, font=TITLE_FONT)
        body(s, x + 0.18, 4.3, 2.35, 0.9, text_body, size=8, line=1.15)
    s.shapes.add_picture(str(ASSETS / "twin_orb_glow.png"), Inches(9.35),
                         Inches(0.95), width=Inches(3.45), height=Inches(3.45))
    text(s, 0.7, 5.75, 8.4, 0.55,
         "Built by an engineer working on a remotely operable, IoT-enabled "
         "hemodialysis machine.", size=10, color=MUTED, font=BODY_FONT)
    pill(s, 0.7, 6.4, 4.3, 0.34, "THE NEXT EXPERIMENT IS A WORKFLOW",
         color=TEAL, size=7.5)
    notes(s, "The ask is a silent-mode pilot in a real unit, not a stage demo. "
             "The next experiment is a workflow: does the console buy time to "
             "react and seek advice? Recalibrate on the partner's machine first.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 14 CLOSE
# ---------------------------------------------------------------------------
def slide_close(prs, idx):
    s = blank(prs)
    s.shapes.add_picture(str(ASSETS / "twin_orb_glow.png"), Inches(8.2),
                         Inches(0.9), width=Inches(4.6), height=Inches(4.6))
    kicker(s, 0.7, 0.8, "HEMOTWIN · DIGITAL TWIN CHALLENGE 2026")
    text(s, 0.7, 1.35, 7.2, 2.1,
         "The twin knows\nwhat it cannot do.", size=40, color=TEXT, bold=True,
         font=TITLE_FONT, line=0.98)
    text(s, 0.7, 3.65, 7.0, 0.8,
         "A chair-side decision-support layer for dialysis. Calibrated "
         "forecast, exact fluid arithmetic, and a review pathway.", size=14,
         color=BODY, font=BODY_FONT, line=1.2)
    line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.72), Inches(4.62),
                              Inches(1.4), Inches(0.035))
    line.fill.solid(); line.fill.fore_color.rgb = CYAN; line.line.fill.background()
    text(s, 0.7, 4.82, 7.2, 0.5,
         "Research prototype. Not a medical device. No treatment recommendation.",
         size=9, color=MUTED, font=BODY_FONT)
    text(s, 0.7, 6.55, 11.8, 0.3,
         "HemoTwin · one console · three views · one honest boundary",
         size=8, color=MUTED, font=BODY_FONT)
    notes(s, "Close on the boundary. The twin knows what it cannot do; that is "
             "what makes it usable as a decision-support layer.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 15 APPENDIX A — GATES
# ---------------------------------------------------------------------------
def slide_gates(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "APPENDIX A")
    title(s, 0.7, 0.92, 11.6, "Gate definitions and results.", size=30)
    rows = [
        ("G1", "MAE_v4 ≤ 0.80×MAE_v3 and |bias| ≤ 3", "PASS",
         "11.59 vs 15.55 · n=374"),
        ("G2", "vs fair base / vs oracle", "PASS vs base · FAIL vs oracle",
         "10.99 vs 9.60"),
        ("G3", "actual < hold · CI upper < 0", "FAIL",
         "397 rows · Δ 0 [0, 0]"),
        ("G4", "monotone + continuous at unit gain", "PASS",
         "0 violations / 3.09M checks"),
        ("G5", "90% band coverage 88–92%", "PASS", "89.2% HOLD · 90.1% TAPER"),
        ("G6", "cold start + future invariance", "PASS", "284 · 200/200"),
        ("G7", "does early UF reduction raise SBP?", "FAIL",
         "τ +0.13 [−2.63, +3.06]"),
    ]
    y = 1.55
    for i, (gate, crit, result, key) in enumerate(rows):
        if i % 2 == 0:
            card(s, 0.6, y - 0.04, 12.13, 0.58, fill=PANEL_2, line_color=LINE)
        text(s, 0.75, y + 0.05, 0.7, 0.3, gate, size=11, color=CYAN,
             bold=True, font=TITLE_FONT)
        text(s, 1.45, y + 0.05, 4.8, 0.3, crit, size=9, color=BODY,
             font=BODY_FONT)
        color = GOOD if result.startswith("PASS") and "FAIL" not in result else (
            AMBER if "PASS" in result and "FAIL" in result else CORAL)
        text(s, 6.25, y + 0.05, 2.9, 0.3, result, size=8.5, color=color,
             bold=True, font=TITLE_FONT)
        text(s, 9.25, y + 0.05, 3.3, 0.3, key, size=8.5, color=MUTED,
             font=BODY_FONT)
        y += 0.6
    text(s, 0.7, 6.0, 11.6, 0.3,
         "A pass is an engineering check against a pre-registered criterion — "
         "not clinical validation. G2 is a tie at gain 0, not evidence of a "
         "treatment effect. G7 asks whether early UF reduction raised SBP; it "
         "did not.", size=7.5, color=MUTED, font=BODY_FONT)
    notes(s, "Use this in Q&A. G2 is a tie at gain 0 against its own base, but "
             "fails against the oracle-assisted display forecast. G3 and G7 "
             "are the what-if failures.")
    footer(s, idx)


# ---------------------------------------------------------------------------
# 16 APPENDIX B — Q&A
# ---------------------------------------------------------------------------
def slide_qa(prs, idx):
    s = blank(prs)
    kicker(s, 0.7, 0.62, "APPENDIX B")
    title(s, 0.7, 0.92, 11.6, "Q&A ammunition.", size=30)
    items = [
        ("IF THEY ASK ABOUT THE MODEL",
         "3 patient folds; fold 2 untouched; 59 pre-anchor features; fold-2 "
         "MAE 10.99; 90% band coverage 89–90%; manual sessions are OOD-labelled.",
         CYAN),
        ("IF THEY ASK ABOUT THE TWIN",
         "The twin test (G7) found no effect: the CI includes zero; sham +2.91; "
         "P6a +0.43; operational gain 0.", VIOLET),
        ("IF THEY ASK ABOUT THE ALERT",
         "AUROC 0.880 ranking; 8.2% detection at 0.26 false alerts/session; "
         "below the current-SBP rule; shadow only, no alert authority.", AMBER),
        ("IF THEY ASK ABOUT DEPLOYMENT",
         "No auth, no machine integration, no prospective or external "
         "validation; the local JSONL audit is demo-only, not clinical.", CORAL),
    ]
    for i, (head, text_body, color) in enumerate(items):
        x = 0.6 + (i % 2) * 6.15
        y = 1.6 + (i // 2) * 2.25
        card(s, x, y, 5.95, 1.95, line_color=color)
        kicker(s, x + 0.22, y + 0.16, head, color=color, size=7.5)
        body(s, x + 0.22, y + 0.46, 5.5, 1.3, text_body, size=10, line=1.22)
    text(s, 0.7, 6.35, 11.6, 0.3,
         "Every number in this deck is traceable to evidence/ and "
         "docs/EVIDENCE_STATUS.md.", size=7.5, color=MUTED, font=BODY_FONT)
    notes(s, "Use this for Q&A. The most important answers: the two forecast "
             "numbers are different models; the twin effect is null; the alert "
             "model is shadow-only; nothing is validated prospectively.")
    footer(s, idx)


def main() -> None:
    prs = new_deck()
    builders = [
        slide_cover, slide_field, slide_gap, slide_product, slide_case_lab,
        slide_lineage, slide_fluid, slide_protocol, slide_g7, slide_boundary,
        slide_evidence, slide_engineering, slide_pilot, slide_close,
        slide_gates, slide_qa,
    ]
    for i, builder in enumerate(builders, start=1):
        builder(prs, i)
    prs.save(OUT)
    print("saved", OUT, "slides", len(prs.slides))


if __name__ == "__main__":
    main()
