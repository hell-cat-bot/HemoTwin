"""Build the HemoTwin summit decks (11-slide and 14-slide) with python-pptx.

The slide geometry mirrors the HTML proof at 1280x720 px (1 px = 9525 EMU,
font pt = px * 0.75), so the editable deck matches the reviewed design.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "deck" / "summit_2026" / "assets"
OUT11 = ROOT / "deck" / "summit_2026" / "HemoTwin_Summit_2026.pptx"
OUT14 = ROOT / "deck" / "summit_2026" / "HemoTwin_Summit_2026_14.pptx"

IVORY = (247, 242, 233)
INK = (22, 26, 25)
MUTED = (110, 103, 93)
TERRA = (180, 71, 47)
SAGE = (63, 107, 94)
AMBER = (169, 118, 31)
BAY = (11, 13, 14)
CREAM = (237, 227, 211)
PAPER = (252, 251, 248)
LINE = (226, 217, 201)
TERRA_SOFT = (243, 228, 222)
SAGE_SOFT = (231, 238, 231)


def px(v: float) -> Emu:
    return Emu(round(v * 9525))


def pt(v: float) -> Pt:
    return Pt(v * 0.75)


def rgb(c: tuple[int, int, int]) -> RGBColor:
    return RGBColor(*c)


def text(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    s: str,
    size: float = 17,
    font: str = "Segoe UI",
    color: tuple[int, int, int] = INK,
    bold: bool = False,
    italic: bool = False,
    align=PP_ALIGN.LEFT,
    line: float = 1.0,
    anchor=MSO_ANCHOR.TOP,
    caps: bool = False,
    spc: float | None = None,
    space_after: float = 0,
):
    tb = slide.shapes.add_textbox(px(x), px(y), px(w), px(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, raw in enumerate(s.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line
        p.space_after = Pt(space_after)
        r = p.add_run()
        r.text = raw.upper() if caps else raw
        r.font.name = font
        r.font.size = pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = rgb(color)
        if spc is not None:
            r.font._element.set("spc", str(int(spc * 100)))
        if caps:
            r.font._element.set("cap", "all")
    return tb


def rich(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    paragraphs: list[dict],
    anchor=MSO_ANCHOR.TOP,
    align=PP_ALIGN.LEFT,
    line: float = 1.0,
    space_after: float = 0,
):
    tb = slide.shapes.add_textbox(px(x), px(y), px(w), px(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, para in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = para.get("align", align)
        p.line_spacing = para.get("line", line)
        p.space_after = Pt(para.get("space_after", space_after))
        for run in para["runs"]:
            r = p.add_run()
            r.text = run["text"]
            r.font.name = run.get("font", "Segoe UI")
            r.font.size = pt(run.get("size", 17))
            r.font.bold = run.get("bold", False)
            r.font.italic = run.get("italic", False)
            r.font.color.rgb = rgb(run.get("color", INK))
            if run.get("spc") is not None:
                r.font._element.set("spc", str(int(run["spc"] * 100)))
            if run.get("caps"):
                r.font._element.set("cap", "all")
    return tb


def rect(slide, x, y, w, h, fill=None, line=None, radius=None, line_width=1):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(shape_type, px(x), px(y), px(w), px(h))
    if radius:
        shp.adjustments[0] = min(0.5, radius / min(w, h))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(fill)
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = rgb(line)
        shp.line.width = Pt(line_width)
    shp.shadow.inherit = False
    return shp


def line(slide, x1, y1, x2, y2, color=LINE, width=1, dash=None):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, px(x1), px(y1), px(x2), px(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    if dash is not None:
        c.line.dash_style = dash
    return c


def image(slide, name, x, y, w, h):
    slide.shapes.add_picture(str(ASSETS / name), px(x), px(y), px(w), px(h))


def bg(slide, color=IVORY):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(color)


PRS = None
TOTAL_SLIDES = 11


def chrome(slide, page: int, total: int | None = None, final: bool = False):
    if final:
        return
    if TOTAL_SLIDES == 14 and PRS is not None:
        page = list(PRS.slides).index(slide) + 1
    total = total or TOTAL_SLIDES
    text(slide, 64, 684, 760, 16, "HemoTwin · Research prototype · Not a medical device", size=8.5, color=MUTED, caps=True, spc=0.7)
    text(slide, 1130, 684, 86, 16, f"{page:02d} / {total:02d}", size=9, color=MUTED, caps=True, spc=1.0, align=PP_ALIGN.RIGHT)


def source(slide, s: str, y: float = 650):
    text(slide, 64, y, 1080, 30, s, size=8, color=MUTED, caps=True, spc=0.5, line=1.2)


def notes(slide, s: str):
    slide.notes_slide.notes_text_frame.text = s


def kicker(slide, s: str):
    text(slide, 64, 54, 620, 18, s, size=11, color=TERRA, caps=True, spc=1.3)


def headline(slide, s: str, y: float = 92, w: float = 1100, size: float = 54, h: float = 68):
    text(slide, 64, y, w, h, s, size=size, font="Georgia", color=INK, bold=True, line=0.98)


def new_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


# ---------------------------------------------------------------- slides

def slide_cover(prs):
    s = new_slide(prs)
    bg(s, BAY)
    image(s, "cover_bg.png", 0, 0, 1280, 720)
    # brand
    rect(s, 64, 46, 31, 31, fill=None, line=(237, 227, 211), radius=7, line_width=0.8)
    text(s, 64, 52, 31, 22, "H", size=18, font="Georgia", color=CREAM, bold=True, align=PP_ALIGN.CENTER)
    text(s, 107, 55, 130, 20, "HEMOTWIN", size=15, color=CREAM, bold=True, caps=True, spc=2.6)
    rect(s, 245, 52, 30, 19, fill=None, line=(160, 155, 145), radius=3, line_width=0.6)
    text(s, 245, 55, 30, 14, "V2", size=9, color=(205, 198, 186), caps=True, spc=1.2, align=PP_ALIGN.CENTER)
    # eyebrow
    slide_rect = s.shapes.add_shape(MSO_SHAPE.OVAL, px(64), px(199), px(5), px(5))
    slide_rect.fill.solid(); slide_rect.fill.fore_color.rgb = rgb(TERRA); slide_rect.line.fill.background()
    text(s, 78, 196, 700, 18, "Happiest Health Digital Twin Challenge 2026 · Finals", size=11, color=(218, 209, 195), caps=True, spc=1.6)
    text(s, 64, 238, 760, 190, "See the drop\nbefore it lands.", size=76, font="Georgia", color=CREAM, bold=True, line=0.98)
    text(s, 64, 432, 700, 40, "A chair-side digital twin for dialysis.", size=21, color=(232, 224, 210))
    line(s, 64, 498, 148, 498, color=TERRA, width=2)
    text(s, 64, 522, 700, 45, "Reimagining and Reforming Healthcare in India Summit\nBengaluru · 20 November 2026", size=11, color=(196, 187, 174), line=1.3)
    text(s, 900, 684, 316, 30, "Research prototype. Not a medical device.\nNo treatment-effect, alert-utility, or outcome claim.", size=9, color=(198, 190, 178), align=PP_ALIGN.RIGHT, line=1.4)
    notes(s, "20-second opening: In a dialysis unit in India, a patient's blood pressure is falling. The nephrologist is remote. The technician at the chair has minutes to decide: taper the fluid, pause it, or call. HemoTwin gives that technician the next hour before the crash lands — and shows the trade-off. Frame: one session, one falling line, one shared state. Do not tour the 3D bay; it is the cover, not the product.")
    return s


def slide_problem(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "The problem")
    headline(s, "The crash hides\nbetween two cuffs.", w=540, size=52, h=120)
    text(s, 64, 252, 470, 110, "In one in ten sessions, systolic pressure falls below 90 mmHg. The drop starts before the next reading — and the decision lands on the technician at the chair.", size=17, color=MUTED, line=1.2)
    text(s, 64, 398, 420, 120, "1 in 10", size=106, font="Georgia", color=TERRA, bold=True, line=0.9)
    text(s, 68, 512, 330, 60, "sessions in our cohort fall below 90 mmHg. The dangerous gap is not the number; it is the time between readings.", size=12, color=MUTED, line=1.25)
    text(s, 64, 596, 470, 64, "“The doctor is remote. The person at the chair has minutes.”", size=19, font="Georgia", color=INK, italic=True, line=1.15)
    image(s, "problem_chart.png", 620, 104, 596, 486)
    text(s, 64, 664, 1080, 16, "HEMOBP COHORT, TAIWAN · 205,482 SESSIONS · 10.4% WITH NADIR <90 MMHG", size=8, color=MUTED, caps=True, spc=0.5)
    chrome(s, 2)
    notes(s, "The problem is not a missing number. It is a gap in time and a gap in shared state. One in ten sessions in our cohort falls below 90 mmHg. The chart shows the drop starting between two cuffs. The technician sees the next reading; the remote doctor sees a call. This is the decision HemoTwin is built around.")
    return s


def slide_scale(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "The ground reality")
    headline(s, "The bottleneck is attention,\nnot machines.", w=1000, h=132)
    for x, num, cap, sub in [
        (64, "34M", "dialysis sessions a year in India", "ESTIMATE · LABEL IT AS AN ESTIMATE"),
        (452, "13,800", "dialysis machines across 751 PMNDP districts", "1,856–1,925 CENTRES"),
        (840, "1–1.5", "nephrologists per million people", "VS ~25 PER MILLION IN HIGH-INCOME SYSTEMS"),
    ]:
        text(s, x, 246, 360, 90, num, size=78, font="Georgia", color=INK, bold=True, line=0.95)
        text(s, x, 340, 350, 40, cap, size=13, color=INK, line=1.2)
        text(s, x, 382, 350, 18, sub, size=8.5, color=MUTED, caps=True, spc=0.8)
    rect(s, 64, 470, 1152, 156, fill=SAGE_SOFT, radius=8)
    text(s, 90, 492, 500, 18, "Current deal at the chair", size=11, color=SAGE, caps=True, spc=1.3)
    cols = [
        (90, "Alarms fire after the number falls.", "The technician is already reacting, not preparing."),
        (460, "Dashboards document; they do not decide.", "The state lives in the machine, the chart and a phone call."),
        (830, "Staff already taper UF in 87.2% of sessions.", "Without a shared plan, the fluid moves to the next session."),
    ]
    for x, lead, body in cols:
        rich(s, x, 520, 330, 86, [
            {"runs": [{"text": lead, "size": 10.5, "bold": True, "color": INK}], "line": 1.15, "space_after": 3},
            {"runs": [{"text": body, "size": 9.5, "color": MUTED}], "line": 1.15},
        ])
    source(s, "Sources: PMNDP; HEMOBP cohort; FACTS.md. 34M is an estimate. 87.2% = sessions with a >20% mid-session UF reduction.", 650)
    chrome(s, 3)
    notes(s, "India does not lack machines as much as it lacks nephrologist attention. Roughly 34 million sessions a year (estimate), about 13,800 machines, 1–1.5 nephrologists per million. The current deal is alarms after the number falls, dashboards that document, and a phone call. Staff already taper UF in 87.2% of sessions — the response exists; the shared plan does not.")
    return s


def slide_why(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "Why a twin")
    headline(s, "A number is not a plan.", w=900)
    text(s, 64, 176, 900, 40, "A score ends at a prediction. A twin carries the session state to the decision.", size=17, color=MUTED)
    line(s, 64, 238, 1216, 238, color=LINE, width=1)
    # icons
    # mirror
    for ox in (0, 10):
        o = s.shapes.add_shape(MSO_SHAPE.OVAL, px(64 + ox), px(252), px(22), px(22))
        o.fill.background(); o.line.color.rgb = rgb(INK); o.line.width = Pt(1.1)
    dot = s.shapes.add_shape(MSO_SHAPE.OVAL, px(77), px(259), px(6), px(6))
    dot.fill.solid(); dot.fill.fore_color.rgb = rgb(TERRA); dot.line.fill.background()
    # forecast
    line(s, 458, 282, 480, 262, INK, 1.2)
    line(s, 480, 262, 514, 252, TERRA, 1.2, MSO_LINE_DASH_STYLE.DASH)
    line(s, 480, 262, 514, 264, SAGE, 1.1)
    line(s, 480, 262, 514, 282, SAGE, 1.1)
    fd = s.shapes.add_shape(MSO_SHAPE.OVAL, px(477), px(259), px(6), px(6))
    fd.fill.solid(); fd.fill.fore_color.rgb = rgb(INK); fd.line.fill.background()
    # trade-off
    line(s, 851, 250, 851, 292, INK, 1.2)
    line(s, 832, 258, 870, 258, INK, 1.2)
    for cx in (837, 861):
        tri = s.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, px(cx), px(268), px(14), px(13))
        tri.fill.background(); tri.line.color.rgb = rgb(INK); tri.line.width = Pt(1.0)
        tri.rotation = 180
    line(s, 840, 292, 862, 292, INK, 1.2)
    # columns
    for x, title, body in [
        (64, "Mirror", "Cuffs, ultrafiltration, history, symptoms. One patient-specific state, updated at the chair."),
        (448, "Forecast", "The next 60 minutes, with a 90% band. Refreshed at every cuff — and withheld when the data is stale."),
        (832, "Price the trade-off", "Every UF option in litres left today and UF carried into the next session. Arithmetic, not a prescription."),
    ]:
        text(s, x, 312, 340, 34, title, size=24, font="Georgia", color=INK, bold=True)
        text(s, x, 348, 340, 70, body, size=14, color=MUTED, line=1.2)
    # timeline
    line(s, 64, 466, 1216, 466, color=LINE, width=1)
    for x, lab, body in [
        (64, "Before the first cuff", "Risk band from history and the planned UF goal."),
        (448, "During the session", "A calibrated +60 min forecast, refreshed at every cuff."),
        (832, "At the decision", "The fluid arithmetic behind each UF option."),
    ]:
        d = s.shapes.add_shape(MSO_SHAPE.OVAL, px(x), px(462), px(9), px(9))
        d.fill.solid(); d.fill.fore_color.rgb = rgb(INK); d.line.fill.background()
        text(s, x, 484, 300, 16, lab, size=9, color=INK, caps=True, spc=1.2)
        text(s, x, 504, 300, 36, body, size=12, color=MUTED, line=1.2)
    text(s, 64, 596, 1000, 40, "“The twin does not choose. It makes the choice legible.”", size=22, font="Georgia", color=INK, italic=True)
    chrome(s, 4)
    notes(s, "Define the twin in plain language: it mirrors one patient's session state, forecasts the next hour, and prices the fluid trade-off. A score ends at a prediction; a twin carries the state to the decision. The timeline maps the three layers to the three moments at the chair: before the first cuff, during the session, at the decision.")
    return s


def slide_chairs(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "Before the first cuff")
    headline(s, "Five chairs. One is different.", w=1160)
    image(s, "chairs_frame.png", 50, 160, 728, 356)
    text(s, 64, 520, 700, 18, "Chair board · revealed after the pre-session estimate", size=9, color=MUTED, caps=True, spc=1.0)
    text(s, 800, 162, 416, 16, "Chair 04 · the one to watch", size=11, color=TERRA, caps=True, spc=1.2)
    image(s, "chair4_frame.png", 788, 180, 440, 177)
    for x, num, unit, cap in [
        (800, "112", " min", "RECORDED CRASH"),
        (948, "78", "", "MMHG NADIR"),
        (1080, "1.00", "", "PRIOR IDH RATE"),
    ]:
        rich(s, x, 360, 130, 44, [{"runs": [
            {"text": num, "size": 30, "font": "Georgia", "bold": True, "color": INK},
            {"text": unit, "size": 15, "color": MUTED},
        ]}], line=0.95)
        text(s, x, 404, 130, 16, cap, size=8.5, color=MUTED, caps=True, spc=0.8)
    rich(s, 800, 458, 400, 70, [
        {"runs": [{"text": "No BP taken. No current UF.", "size": 13, "bold": True, "color": INK}], "line": 1.15, "space_after": 3},
        {"runs": [{"text": "History, static fields and the planned UF goal alone — computed before the first cuff.", "size": 13, "color": MUTED}], "line": 1.15},
    ])
    text(s, 800, 528, 400, 30, "Curated five-chair story · not an accuracy estimate · low band is not safe", size=8, color=MUTED, caps=True, spc=0.5, line=1.3)
    text(s, 64, 590, 1000, 40, "“The high chair crashed. The four low chairs did not.”", size=19, font="Georgia", color=INK, italic=True)
    chrome(s, 5)
    notes(s, "Opening product beat: five chairs before the first cuff. No BP, no current UF — history, static fields and the planned UF goal alone. One chair comes up high at 70.2%; the four low chairs do not. Reveal: the high chair crashed at 112 minutes, nadir 78. Say clearly: this is a curated five-chair story, not an accuracy estimate, and a low band is not safe.")
    return s


def slide_fluid(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "At the decision")
    headline(s, "Every option has a price.", w=1000)
    text(s, 64, 160, 1000, 36, "The forecast is shared across policies. What changes is the fluid arithmetic.", size=17, color=MUTED)
    image(s, "fluid_frame.png", 50, 194, 768, 318)
    text(s, 64, 516, 720, 18, "Fluid arithmetic · all policies share the same calibrated +60 min", size=9, color=MUTED, caps=True, spc=1.0)
    rows = [
        (208, "Hold current UF", "0.00", " L", "left today", "Next-session UF 18.2 mL/kg/h", INK),
        (318, "Taper to 50%", "0.25", " L", "left today", "Next-session UF 19.1 mL/kg/h", INK),
        (428, "Keep open · 0.10 L/h", "1.44", " L", "left today", "Next-session UF 23.6 mL/kg/h", TERRA),
    ]
    for y, lab, num, unit, left, sub, color in rows:
        text(s, 840, y, 360, 16, lab, size=11, color=MUTED, caps=True, spc=1.1)
        rich(s, 840, y + 20, 330, 44, [{"runs": [
            {"text": num, "size": 34, "font": "Georgia", "bold": True, "color": color},
            {"text": unit, "size": 12, "color": MUTED},
            {"text": " " + left, "size": 12, "color": MUTED},
        ]}], line=0.95)
        text(s, 840, y + 62, 360, 16, sub, size=8.5, color=MUTED, caps=True, spc=0.5)
    line(s, 840, 306, 1216, 306, color=LINE, width=1)
    line(s, 840, 416, 1216, 416, color=LINE, width=1)
    text(s, 64, 566, 1000, 40, "“Stop the UF and the fluid does not disappear. It moves to the next session.”", size=19, font="Georgia", color=INK, italic=True)
    source(s, "Expected SBP is an uncalibrated sketch; the fluid arithmetic is exact. Neither is a prescription.", 650)
    chrome(s, 6)
    notes(s, "The forecast is shared across policies. What changes is the fluid arithmetic: hold leaves 0.00 L today and 18.2 mL/kg/h next session; taper to 50% leaves 0.25 L and 19.1; keep open leaves 1.44 L and 23.6. The expected-SBP column is an uncalibrated sketch; the arithmetic is exact. Neither is a prescription. The point is that stopping UF does not make fluid disappear — it moves to the next session.")
    return s


def slide_replay(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "Prediction, then the record")
    headline(s, "Two minutes ahead of the first low.", w=1160)
    image(s, "replay_frame.png", 50, 166, 648, 353)
    text(s, 64, 540, 620, 18, "Recorded session · forecast drawn first, then the cuffs", size=9, color=MUTED, caps=True, spc=1.0)
    text(s, 64, 570, 620, 30, "Dashed line = 90 mmHg floor · teal = research forecast · black = recorded cuffs · amber ticks = UF changes.", size=9.5, color=MUTED, line=1.3)
    stats = [
        (720, 170, "128", " min", "FORECAST CROSSED 90", INK),
        (1010, 170, "130", " min", "FIRST MEASURED LOW", INK),
        (720, 260, "88", " mmHg", "ACTUAL LOW", INK),
        (1010, 260, "84.4", " mmHg", "FORECAST LOW", TERRA),
    ]
    for x, y, num, unit, cap, color in stats:
        rich(s, x, y, 230, 50, [{"runs": [
            {"text": num, "size": 46, "font": "Georgia", "bold": True, "color": color},
            {"text": unit, "size": 16, "color": MUTED},
        ]}], line=0.95)
        text(s, x, y + 50, 230, 16, cap, size=8.5, color=MUTED, caps=True, spc=0.8)
    line(s, 720, 350, 1216, 350, color=LINE, width=1)
    text(s, 720, 370, 496, 76, "The forecast crossed 90 two minutes before the first measured low.", size=21, font="Georgia", color=INK, italic=True, line=1.2)
    text(s, 720, 456, 496, 50, "Retrospective replay. The forecast is observational; it is not an alert and did not trigger one. The scene is a synthetic illustration; the readings are recorded.", size=9.5, color=MUTED, line=1.3)
    chrome(s, 7)
    notes(s, "This is the first demo replay. The forecast crossed 90 at 128 minutes; the first measured low was 88 at 130 minutes — two minutes later. The forecast low was 84.4. Be precise: this is a retrospective replay, the forecast is observational, and it is not an alert. It did not trigger anything. The scene is synthetic; the readings are recorded.")
    return s


def slide_trust_combined(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "The boundary")
    headline(s, "The twin knows what it cannot do.", w=1160)
    # claims
    text(s, 64, 168, 500, 18, "We claim", size=11, color=SAGE, caps=True, spc=1.3)
    text(s, 660, 168, 500, 18, "We refuse to claim", size=11, color=TERRA, caps=True, spc=1.3)
    claims = [
        ("A calibrated next-hour forecast.", " 10.99 mmHg average miss on patients never seen in training."),
        ("A pre-session risk band.", " AUROC 0.83 from history and the planned UF goal; no BP needed."),
        ("Exact fluid arithmetic and a review pathway.", " Nothing adjusts the machine."),
    ]
    refusals = [
        ("A what-if treatment effect.", " We tested it; it failed. The counterfactual is retired."),
        ("Alert utility or fewer crashes.", " No outcome data; the event model is shadow-only."),
        ("Indian or external validation.", " No Indian cohort; the Spanish transport check failed at 0.474."),
    ]
    for i, ((l1, l2), (r1, r2)) in enumerate(zip(claims, refusals)):
        y = 196 + i * 58
        line(s, 64, y, 574, y, color=LINE, width=1)
        line(s, 660, y, 1170, y, color=LINE, width=1)
        rich(s, 64, y + 8, 500, 46, [{"runs": [
            {"text": l1, "size": 14, "bold": True, "color": INK},
            {"text": l2, "size": 14, "color": INK},
        ]}], line=1.2)
        rich(s, 660, y + 8, 510, 46, [{"runs": [
            {"text": r1, "size": 14, "bold": True, "color": INK},
            {"text": r2, "size": 14, "color": INK},
        ]}], line=1.2)
    # G7 band
    rect(s, 64, 470, 1152, 160, fill=TERRA_SOFT, radius=8)
    image(s, "g7_plot.png", 90, 494, 560, 92)
    text(s, 700, 490, 480, 18, "The test we ran", size=11, color=TERRA, caps=True, spc=1.3)
    text(s, 700, 510, 480, 34, "Does less ultrafiltration raise pressure?", size=21, font="Georgia", color=INK, bold=True)
    text(s, 700, 550, 480, 50, "+0.13 mmHg per 0.25 L/h less UF · 95% CI -2.63 to +3.06. The interval crosses zero. We retired the what-if.", size=12.5, color=INK, line=1.2)
    source(s, "Seven pre-registered checks. The twin test failed; the forecast and risk surfaces remain. A pass is an engineering check, not clinical validation.", 650)
    chrome(s, 8)
    notes(s, "This is the trust beat. We claim a calibrated hour, a pre-session band, and exact fluid arithmetic. We refuse a what-if treatment effect, alert utility or fewer crashes, and Indian or external validation. The test: does less ultrafiltration raise pressure? +0.13 mmHg per 0.25 L/h less UF, 95% CI -2.63 to +3.06, crossing zero. We retired the what-if. State each once, precisely, then stop.")
    return s


def slide_impact_combined(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "Impact & integration")
    headline(s, "From one chair to one unit.", w=1160)
    groups = [
        (64, SAGE, "Impact we can measure", [
            ("Time-to-review.", " How long before a falling session is escalated."),
            ("Shared state.", " One screen for the technician and the remote doctor."),
            ("Fluid carry-forward.", " Every UF choice logged against the next session."),
        ]),
        (448, MUTED, "How it fits", [
            ("Device-agnostic.", " Manual entry or CSV today; no machine integration."),
            ("FHIR R4 export.", " ABDM path; DPDP-aware local deployment."),
            ("No runtime network.", " A stale cuff withholds the projection instead of guessing."),
        ]),
        (832, TERRA, "Next step", [
            ("One unit. 2–4 weeks.", " Silent mode: no machine control, no alarms."),
            ("Local recalibration.", " Indian labels, local cuff cadence, local practice."),
            ("Pre-registered workflow study.", " Time-to-review first; outcomes later."),
        ]),
    ]
    for x, color, lab, items in groups:
        text(s, x, 170, 340, 18, lab, size=11, color=color, caps=True, spc=1.2)
        for i, (lead, body) in enumerate(items):
            y = 198 + i * 58
            line(s, x, y, x + 340, y, color=LINE, width=1)
            rich(s, x, y + 8, 330, 46, [{"runs": [
                {"text": lead, "size": 13.5, "bold": True, "color": INK},
                {"text": body, "size": 13.5, "color": MUTED},
            ]}], line=1.2)
    rect(s, 64, 486, 1152, 126, fill=SAGE_SOFT, radius=8)
    text(s, 90, 506, 620, 80, "Give us one unit\nfor four weeks.", size=29, font="Georgia", color=INK, bold=True, line=1.05)
    text(s, 750, 520, 440, 70, "No machine control. No alarms. A log of what the twin would have said — and every claim it refused.", size=12.5, color=MUTED, align=PP_ALIGN.RIGHT, line=1.25)
    source(s, "CDSCO Class B intent · DPDP Act 2023 · no Indian cohort yet. Impact measures are the next study, not current claims.", 650)
    chrome(s, 9)
    notes(s, "Impact we can measure: time-to-review, shared state, fluid carry-forward. Not claimed: fewer crashes, fewer admissions, saved lives. How it fits: device-agnostic manual/CSV today, FHIR R4 export, ABDM path, no runtime network. Next step: one unit, 2–4 weeks, silent mode, local recalibration, then a pre-registered workflow study. The ask is deliberately cheap and reversible.")
    return s


def slide_models(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "The models")
    headline(s, "Two models, two questions.", w=1160)
    # left
    text(s, 64, 160, 520, 16, "Who is likely to crash today?", size=10, color=SAGE, caps=True, spc=1.2)
    text(s, 64, 180, 520, 16, "Pre-session risk · A2 · LightGBM", size=9, color=MUTED, caps=True, spc=1.1)
    text(s, 64, 200, 520, 92, "0.831", size=82, font="Georgia", color=INK, bold=True, line=0.9)
    text(s, 64, 300, 520, 18, "AUROC · fold 2 · no BP, no current UF", size=12, color=MUTED, caps=True, spc=0.7)
    text(s, 64, 330, 520, 20, "Recall@25 0.60 · PPV@25 0.59 · ECE10 0.018", size=12.5, color=INK)
    text(s, 64, 354, 520, 40, "History, static fields and the planned UF goal. One high chair, four low — before the first cuff.", size=12.5, color=MUTED, line=1.2)
    # right
    text(s, 680, 160, 520, 16, "What will the next hour look like?", size=10, color=TERRA, caps=True, spc=1.2)
    text(s, 680, 180, 520, 16, "60-minute forecast · v4.1 · LightGBM", size=9, color=MUTED, caps=True, spc=1.1)
    text(s, 680, 200, 520, 92, "10.99", size=82, font="Georgia", color=INK, bold=True, line=0.9)
    text(s, 680, 300, 520, 18, "mmHg MAE · fold 2 · 59 pre-anchor features", size=12, color=MUTED, caps=True, spc=0.7)
    text(s, 680, 330, 520, 20, "RMSE 14.65 · 90% band 89.2 / 90.1% coverage", size=12.5, color=INK)
    text(s, 680, 354, 520, 40, "No future-UF oracle. A calibrated trajectory, refreshed at every cuff — not a treatment effect.", size=12.5, color=MUTED, line=1.2)
    line(s, 636, 160, 636, 490, color=LINE, width=1)
    # data fusion
    text(s, 64, 398, 300, 16, "Static history", size=11, color=MUTED, caps=True, spc=1.1)
    text(s, 64, 416, 380, 16, "Age · vintage · prior IDH rate · prior nadirs", size=11, color=INK)
    text(s, 450, 404, 30, 24, "+", size=20, font="Georgia", color=TERRA)
    text(s, 500, 398, 300, 16, "Medical IoT", size=11, color=MUTED, caps=True, spc=1.1)
    text(s, 500, 416, 340, 16, "Cuffs · UF · machine settings", size=11, color=INK)
    text(s, 850, 404, 30, 24, "→", size=20, font="Georgia", color=TERRA)
    text(s, 900, 398, 300, 16, "One session state", size=11, color=SAGE, caps=True, spc=1.1)
    text(s, 900, 416, 300, 16, "Mirror · forecast · arithmetic", size=11, color=INK)
    line(s, 64, 500, 1216, 500, color=LINE, width=1)
    text(s, 64, 512, 1080, 30, "205,482 sessions · 1,070 patients · 4.19M medical-IoT rows · HEMOBP Taiwan (CC BY 4.0) · fold 2 untouched", size=9, color=MUTED, caps=True, spc=0.6)
    image(s, "dotplot.png", 64, 558, 640, 74)
    text(s, 740, 558, 476, 90, "Not directly comparable. Zhang and Hong are intra-session, different horizons and cohorts. Our 0.831 asks a harder question: no BP, no current UF. No published MAE comparator for the forecast; the retired v3 twin scored 15.6 on the same taper slice (n=374).", size=10, color=MUTED, line=1.35)
    chrome(s, 10)
    notes(s, "Two models, two questions. Pre-session risk: A2, AUROC 0.8313, recall@25 0.60, PPV@25 0.59, calibrated. 60-minute forecast: MAE 10.99, RMSE 14.65, 90% band coverage 89.2/90.1, 59 pre-anchor features, no future-UF oracle. The data: 205,482 sessions, 1,070 patients, 4.19M rows, Taiwan HEMOBP, fold 2 untouched. The comparison to Zhang 0.89 and Hong 0.86 is not head-to-head: intra-session, different horizons and cohorts. The retired v3 twin scored 15.6 on the same taper slice (n=374).")
    return s


def slide_drivers(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "What drives them")
    headline(s, "What the models actually read.", w=1160)
    text(s, 64, 166, 500, 18, "Pre-session risk · A2", size=11, color=SAGE, caps=True, spc=1.2)
    text(s, 64, 190, 520, 18, "29 fields + 20 missingness flags · no BP · no current UF", size=10, color=MUTED)
    image(s, "bars_risk.png", 64, 220, 520, 190)
    text(s, 680, 166, 520, 18, "60-minute forecast · v4.1", size=11, color=TERRA, caps=True, spc=1.2)
    text(s, 680, 190, 520, 18, "59 pre-anchor fields · no future-UF oracle", size=10, color=MUTED)
    image(s, "bars_forecast.png", 680, 220, 536, 196)
    text(s, 64, 452, 560, 60, "Associations, not causes. Planned UF goal encodes clinician behaviour; BP sensitivity is not an intervention effect. *Internal projection is a model input — not evidence the counterfactual works.", size=10, color=MUTED, line=1.3)
    text(s, 700, 452, 516, 40, "5 pass or partial · 2 fail. No alert authority · no Indian validation · no clinical-benefit claim.", size=10, color=MUTED, align=PP_ALIGN.RIGHT, line=1.3)
    text(s, 64, 536, 1000, 30, "The model is not a black box: every input is named, and every boundary is printed.", size=16, font="Georgia", color=MUTED, italic=True)
    rect(s, 0, 646, 1280, 74, fill=BAY)
    text(s, 64, 664, 900, 40, "The twin knows what it cannot do. That is what makes it safe to try.", size=23, font="Georgia", color=CREAM)
    text(s, 950, 674, 266, 16, "One unit · four weeks · silent mode", size=9, color=(205, 198, 186), caps=True, spc=1.1, align=PP_ALIGN.RIGHT)
    notes(s, "Feature importance is association, not causation. The risk model reads prior IDH rate, prior 3/10-session mean nadir, prior nadir, vintage, planned UF goal. The forecast reads an internal session projection, recent SBP minima, prior nadirs, and patient BP sensitivity. The projection is an input feature, not evidence the counterfactual works. Close: the twin knows what it cannot do; that is what makes it safe to try. Ask for one unit, four weeks, silent mode.")
    return s


def slide_console(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "One console")
    headline(s, "One console. Five views.", w=1160)
    text(s, 64, 176, 1000, 36, "The twin is a chair-side workflow, not another dashboard.", size=17, color=MUTED)
    thumbs = [
        (64, "thumb_chairs.png", "Chairs", "Before the first cuff."),
        (298, "thumb_case.png", "Case lab", "Forecast + fluid arithmetic."),
        (532, "thumb_live.png", "Live", "Enter a real session."),
        (766, "thumb_replay.png", "Replay", "Prediction, then record."),
        (1000, "thumb_evidence.png", "Evidence", "Claims and refusals."),
    ]
    for x, img, lab, desc in thumbs:
        image(s, img, x, 220, 216, 136)
        text(s, x + 8, 372, 200, 16, lab, size=11, color=INK, caps=True, spc=1.2)
        text(s, x + 8, 392, 200, 32, desc, size=10.5, color=MUTED, line=1.2)
    line(s, 64, 470, 1216, 470, color=LINE, width=1)
    text(s, 64, 492, 1000, 30, "Demo path · Chairs → Case lab → Fluid arithmetic → Replay → Evidence", size=15, font="Georgia", color=INK, italic=True)
    text(s, 64, 524, 1000, 18, "One state follows the session from the board to the handoff.", size=11, color=MUTED)
    text(s, 64, 580, 1000, 34, "“The demo is the console. The product is the shared state.”", size=20, font="Georgia", color=INK, italic=True)
    source(s, "One Streamlit console · five views · no runtime network · local demo", 650)
    chrome(s, 5)
    notes(s, "This is the map of the console: Chairs, Case lab, Live, Replay, Evidence. Do not tour every view. Say one sentence: the same state follows the session from the board to the handoff. The three deep dives that follow are Chairs, the fluid arithmetic, and Replay.")
    return s


def slide_g7(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "The test we ran")
    headline(s, "The what-if did not survive.", w=1160)
    cols = [
        (64, "The claim", "If we reduce UF early, pressure should rise. That is the claim that would make the twin a treatment engine."),
        (448, "The test", "Pre-registered, non-reactive UF step-down; matched within-patient; protocol hash frozen before estimation."),
        (832, "The result", "+0.13 mmHg per 0.25 L/h less UF. 95% CI -2.63 to +3.06. The interval crosses zero."),
    ]
    for x, lab, body in cols:
        text(s, x, 180, 330, 16, lab, size=11, color=TERRA, caps=True, spc=1.3)
        line(s, x, 200, x + 330, 200, color=LINE, width=1)
        text(s, x, 208, 330, 100, body, size=13, color=MUTED, line=1.25)
    rect(s, 64, 340, 1152, 200, fill=TERRA_SOFT, radius=8)
    image(s, "g7_plot.png", 200, 375, 880, 145)
    text(s, 64, 560, 1000, 34, "No detectable effect. We retired the what-if.", size=24, font="Georgia", color=INK, italic=True)
    text(s, 64, 600, 1050, 30, "What survived: the calibrated forecast, the risk band, the fluid arithmetic.", size=13, color=MUTED)
    source(s, "G7 protocol SHA-256 frozen before estimation · census 205,113 sessions · 581 matched events (dev) · 65 pre-anchor events (fold 2).", 650)
    chrome(s, 9)
    notes(s, "We built the what-if engine, then ran the two pre-registered tests that could prove it. Actual and hold were identical; early UF reduction moved 30-minute SBP by +0.13 mmHg per 0.25 L/h, interval -2.63 to +3.06, which includes zero. A sham-time control moved more. That is a null. We retired the counterfactual and kept it as a labelled illustration. What survived: the forecast, the risk band, the arithmetic.")
    return s


def slide_boundary(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "The boundary")
    headline(s, "The twin knows what it cannot do.", w=1160)
    text(s, 64, 168, 500, 18, "We claim", size=11, color=SAGE, caps=True, spc=1.3)
    text(s, 660, 168, 500, 18, "We refuse to claim", size=11, color=TERRA, caps=True, spc=1.3)
    claims = [
        ("A calibrated next-hour forecast.", " 10.99 mmHg average miss on patients never seen in training."),
        ("A pre-session risk band.", " AUROC 0.83 from history and the planned UF goal; no BP needed."),
        ("Exact fluid arithmetic and a review pathway.", " Nothing adjusts the machine."),
    ]
    refusals = [
        ("A what-if treatment effect.", " We tested it; it failed. The counterfactual is retired."),
        ("Alert utility or fewer crashes.", " No outcome data; the event model is shadow-only."),
        ("Indian or external validation.", " No Indian cohort; the Spanish transport check failed at 0.474."),
    ]
    for i, ((l1, l2), (r1, r2)) in enumerate(zip(claims, refusals)):
        y = 196 + i * 58
        line(s, 64, y, 574, y, color=LINE, width=1)
        line(s, 660, y, 1170, y, color=LINE, width=1)
        rich(s, 64, y + 8, 500, 46, [{"runs": [{"text": l1, "size": 14, "bold": True, "color": INK}, {"text": l2, "size": 14, "color": INK}]}], line=1.2)
        rich(s, 660, y + 8, 510, 46, [{"runs": [{"text": r1, "size": 14, "bold": True, "color": INK}, {"text": r2, "size": 14, "color": INK}]}], line=1.2)
    rect(s, 64, 410, 1152, 170, fill=SAGE_SOFT, radius=8)
    text(s, 90, 430, 500, 16, "What ships", size=11, color=SAGE, caps=True, spc=1.3)
    text(s, 90, 452, 500, 50, "A calibrated forecast · a pre-session band · fluid arithmetic · FHIR handoff.", size=13, color=INK, line=1.2)
    text(s, 660, 430, 500, 16, "What is retired", size=11, color=TERRA, caps=True, spc=1.3)
    text(s, 660, 452, 500, 50, "A what-if treatment effect · alert authority · Indian or external validation claims.", size=13, color=INK, line=1.2)
    text(s, 90, 540, 900, 18, "A pass is an engineering check, not clinical validation.", size=11, color=MUTED)
    source(s, "Seven pre-registered checks. Five pass or partial; two fail. The twin test failed; the forecast and risk surfaces remain.", 650)
    chrome(s, 10)
    notes(s, "This is the boundary in one slide. We claim the calibrated hour, the pre-session band, the arithmetic, and the handoff. We refuse the what-if treatment effect, alert authority, and Indian or external validation. State each once, precisely, then stop. The boundary is part of the product; it is why the rest is trustworthy.")
    return s


def slide_impact(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "Impact")
    headline(s, "What we can measure now.", w=1160)
    text(s, 64, 176, 1000, 36, "We do not claim fewer crashes. We claim a workflow that can be measured.", size=17, color=MUTED)
    cols = [
        (64, "Time-to-review", "From a falling forecast to a documented review. Logged locally; no network."),
        (448, "Shared state", "One screen for the technician and the remote doctor. Count sessions with a complete state."),
        (832, "Fluid carry-forward", "Every UF choice logged against the next session. Count explicit trade-offs."),
    ]
    for x, title, body in cols:
        text(s, x, 240, 340, 16, "Measure", size=11, color=SAGE, caps=True, spc=1.3)
        line(s, x, 258, x + 340, 258, color=LINE, width=1)
        text(s, x, 268, 340, 30, title, size=22, font="Georgia", color=INK, bold=True)
        text(s, x, 304, 340, 80, body, size=13, color=MUTED, line=1.3)
    line(s, 64, 466, 1216, 466, color=LINE, width=1)
    for x, lab, body in [
        (64, "Silent mode", "2–4 weeks. No machine control. No alarms."),
        (448, "Local recalibration", "Indian labels, cuff cadence, practice."),
        (832, "Workflow study", "Pre-registered. Time-to-review first."),
    ]:
        d = s.shapes.add_shape(MSO_SHAPE.OVAL, px(x), px(462), px(9), px(9))
        d.fill.solid(); d.fill.fore_color.rgb = rgb(INK); d.line.fill.background()
        text(s, x, 484, 300, 16, lab, size=9, color=INK, caps=True, spc=1.2)
        text(s, x, 504, 300, 36, body, size=12, color=MUTED, line=1.2)
    text(s, 64, 590, 1000, 34, "“Outcomes are the next study, not this demo.”", size=20, font="Georgia", color=INK, italic=True)
    source(s, "Impact measures are the next study, not current claims. No outcome data; no clinical-benefit claim.", 650)
    chrome(s, 11)
    notes(s, "Impact is a workflow, not a number we can claim yet. We can measure time-to-review, shared state, and fluid carry-forward in a silent pilot. We do not claim fewer crashes, fewer admissions, or saved lives. Those are the next study. The ladder is silent mode, local recalibration, then a pre-registered workflow study.")
    return s


def slide_integration(prs):
    s = new_slide(prs)
    bg(s)
    kicker(s, "Integration & next step")
    headline(s, "One unit. Four weeks. Silent mode.", w=1160)
    text(s, 64, 170, 500, 16, "How it fits", size=11, color=SAGE, caps=True, spc=1.3)
    items = [
        ("Device-agnostic.", " Manual entry or CSV today; no machine integration."),
        ("FHIR R4 export.", " ABDM path; DPDP-aware local deployment."),
        ("No runtime network.", " A stale cuff withholds the projection instead of guessing."),
        ("No machine control.", " Display-only; the clinician decides."),
    ]
    for i, (lead, body) in enumerate(items):
        y = 200 + i * 48
        line(s, 64, y, 584, y, color=LINE, width=1)
        rich(s, 64, y + 8, 520, 38, [{"runs": [{"text": lead, "size": 13, "bold": True, "color": INK}, {"text": body, "size": 13, "color": MUTED}]}], line=1.2)
    text(s, 660, 170, 500, 16, "The pilot", size=11, color=TERRA, caps=True, spc=1.3)
    line(s, 680, 210, 680, 430, color=LINE, width=1)
    steps = [
        (210, "Week 0", "Local labels and cuff cadence."),
        (310, "Weeks 1–4", "Silent mode: log what the twin would have shown."),
        (410, "After", "Pre-registered workflow study; outcomes later."),
    ]
    for y, lab, body in steps:
        d = s.shapes.add_shape(MSO_SHAPE.OVAL, px(676), px(y - 4), px(9), px(9))
        d.fill.solid(); d.fill.fore_color.rgb = rgb(INK); d.line.fill.background()
        text(s, 700, y - 12, 400, 16, lab, size=9, color=INK, caps=True, spc=1.2)
        text(s, 700, y + 8, 440, 36, body, size=12, color=MUTED, line=1.2)
    rect(s, 64, 500, 1152, 126, fill=SAGE_SOFT, radius=8)
    text(s, 90, 520, 620, 80, "Give us one unit\nfor four weeks.", size=28, font="Georgia", color=INK, bold=True, line=1.05)
    text(s, 750, 532, 440, 70, "No machine control. No alarms. A log of what the twin would have said — and every claim it refused.", size=12.5, color=MUTED, align=PP_ALIGN.RIGHT, line=1.25)
    source(s, "CDSCO Class B intent · DPDP Act 2023 · no Indian cohort yet. Outcomes are the next study.", 650)
    chrome(s, 12)
    notes(s, "Integration is deliberately boring: device-agnostic, manual or CSV today, FHIR R4 export, ABDM path, no runtime network, no machine control. The pilot is one unit for four weeks in silent mode: log what the twin would have shown, no alarms, no machine action. Then local recalibration and a pre-registered workflow study. The ask is cheap and reversible.")
    return s


# ---------------------------------------------------------------- build

def build_11() -> None:
    global PRS, TOTAL_SLIDES
    prs = Presentation()
    prs.slide_width = Emu(12192000)
    prs.slide_height = Emu(6858000)
    PRS = prs
    TOTAL_SLIDES = 11
    slide_cover(prs)
    slide_problem(prs)
    slide_scale(prs)
    slide_why(prs)
    slide_chairs(prs)
    slide_fluid(prs)
    slide_replay(prs)
    slide_trust_combined(prs)
    slide_impact_combined(prs)
    slide_models(prs)
    slide_drivers(prs)
    prs.save(OUT11)
    print("wrote", OUT11, "slides", len(prs.slides))


def build_14() -> None:
    global PRS, TOTAL_SLIDES
    prs = Presentation()
    prs.slide_width = Emu(12192000)
    prs.slide_height = Emu(6858000)
    PRS = prs
    TOTAL_SLIDES = 14
    slide_cover(prs)
    slide_problem(prs)
    slide_scale(prs)
    slide_why(prs)
    slide_console(prs)
    slide_chairs(prs)
    slide_fluid(prs)
    slide_replay(prs)
    slide_g7(prs)
    slide_boundary(prs)
    slide_impact(prs)
    slide_integration(prs)
    slide_models(prs)
    slide_drivers(prs)
    prs.save(OUT14)
    print("wrote", OUT14, "slides", len(prs.slides))


if __name__ == "__main__":
    build_11()
    build_14()
