"""Bilingual (English / हिन्दी) shift-handoff card for PMNDP district teams."""
from __future__ import annotations

from datetime import datetime, timezone

DISCLAIMER_EN = ("Decision-support summary only. Not a prescription, not a "
                 "safety clearance, and not a substitute for bedside review.")
DISCLAIMER_HI = ("केवल निर्णय-सहायता सारांश। यह प्रिस्क्रिप्शन नहीं है, "
                 "सुरक्षा मंजूरी नहीं है, और बेडसाइड समीक्षा का विकल्प नहीं है।")


def _fmt(value, digits: int = 0) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{v:.{digits}f}"


def build_handoff_card(*, session_id: str, sbp_now, projected_nadir,
                       band: tuple[float, float] | None = None,
                       fluid_left_l=None, next_intensity=None,
                       status: str = "NO_ALERT",
                       timestamp: str | None = None) -> dict:
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    band_txt = (f"{_fmt(band[0])}–{_fmt(band[1])} mmHg" if band else "—")
    en = (f"Shift handoff — session {session_id}: current SBP "
          f"{_fmt(sbp_now)} mmHg; calibrated 60-min nadir "
          f"{_fmt(projected_nadir)} mmHg (90% band {band_txt}); fluid carried "
          f"forward {_fmt(fluid_left_l, 2)} L; next-session UF intensity "
          f"{_fmt(next_intensity, 1)} mL/kg/h; review status {status}. "
          f"Generated {ts}.")
    hi = (f"शिफ्ट हैंडऑफ — सत्र {session_id}: वर्तमान SBP {_fmt(sbp_now)} "
          f"mmHg; 60 मिनट का अनुमानित नादिर {_fmt(projected_nadir)} mmHg "
          f"(90% बैंड {band_txt}); अगले सत्र के लिए तरल "
          f"{_fmt(fluid_left_l, 2)} L; अगले सत्र की UF गति "
          f"{_fmt(next_intensity, 1)} mL/kg/h; समीक्षा स्थिति {status}. "
          f"निर्मित {ts}.")
    return {
        "session_id": str(session_id),
        "status": str(status),
        "english": en,
        "hindi": hi,
        "disclaimer_en": DISCLAIMER_EN,
        "disclaimer_hi": DISCLAIMER_HI,
        "timestamp": ts,
    }
