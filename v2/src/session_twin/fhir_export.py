"""FHIR R4 research export for a HemoTwin session (v1 product).

This is a schema-shaped interoperability artifact, not a certified FHIR
server. Latent Starling-baroreflex observations use a local code system
because they have no LOINC equivalent; that is stated in each resource.
"""
from __future__ import annotations

from datetime import datetime, timezone

LOINC = "http://loinc.org"
SNOMED = "http://snomed.info/sct"
UCUM = "http://unitsofmeasure.org"
LOCAL = "https://hemotwin.local/codes"

LOINC_CODES = {
    "sbp": ("8480-6", "Systolic blood pressure", "mm[Hg]"),
    "dbp": ("8462-4", "Diastolic blood pressure", "mm[Hg]"),
    "weight": ("29463-7", "Body weight", "kg"),
    "uf": ("33050-6", "Ultrafiltration rate", "L/h"),
}
LATENT_CODES = {
    "plasma_deficit_l": ("plasma-deficit", "Plasma volume deficit", "L"),
    "refill_rate_l_h": ("refill-rate", "Transcapillary refill rate", "L/h"),
    "baro_exhaustion_pct": ("baro-exhaustion", "Baroreflex exhaustion", "%"),
}


def _obs(patient_ref: str, system: str, code: str, display: str,
         value: float, unit: str, effective: str, note: str | None = None
         ) -> dict:
    resource = {
        "resourceType": "Observation",
        "status": "final",
        "code": {"coding": [{"system": system, "code": code,
                             "display": display}]},
        "subject": {"reference": patient_ref},
        "effectiveDateTime": effective,
        "valueQuantity": {"value": float(value), "unit": unit,
                          "system": UCUM, "code": unit},
    }
    if note:
        resource["note"] = [{"text": note}]
    return {"resource": resource}


def build_fhir_bundle(*, patient_id: str, session_id: str, age=None,
                      sex=None, observations: dict | None = None,
                      latent_state: dict | None = None,
                      risk: dict | None = None,
                      detected_issue: str | None = None,
                      timestamp: str | None = None) -> dict:
    effective = timestamp or datetime.now(timezone.utc).isoformat()
    patient_ref = f"Patient/{patient_id}"
    entries: list[dict] = [{
        "resource": {
            "resourceType": "Patient",
            "id": str(patient_id),
            "identifier": [{"system": "https://hemotwin.local/session",
                            "value": str(session_id)}],
        }
    }]
    if sex in ("M", "F"):
        entries[0]["resource"]["gender"] = ("male" if sex == "M"
                                            else "female")
    if age is not None:
        entries[0]["resource"]["extension"] = [{
            "url": "http://hl7.org/fhir/StructureDefinition/patient-age",
            "valueInteger": int(age),
        }]
    entries.append({"resource": {
        "resourceType": "Procedure",
        "status": "completed",
        "code": {"coding": [{"system": SNOMED, "code": "302497006",
                             "display": "Hemodialysis"}]},
        "subject": {"reference": patient_ref},
        "performedDateTime": effective,
    }})
    observations = observations or {}
    for key, value in observations.items():
        if value is None or key not in LOINC_CODES:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        code, display, unit = LOINC_CODES[key]
        entries.append(_obs(patient_ref, LOINC, code, display, value, unit,
                            effective))
    for key, value in (latent_state or {}).items():
        if value is None or key not in LATENT_CODES:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        code, display, unit = LATENT_CODES[key]
        entries.append(_obs(
            patient_ref, LOCAL, code, display, value, unit, effective,
            note="Research latent state; no LOINC equivalent."))
    if risk is not None:
        entries.append({"resource": {
            "resourceType": "RiskAssessment",
            "status": "final",
            "subject": {"reference": patient_ref},
            "occurrenceDateTime": effective,
            "method": {"text": "Forecast-v2 shadow score (display only)"},
            "prediction": [{
                "outcome": {"text": str(risk.get("state", "unknown"))},
                "probabilityDecimal": float(risk.get("score", 0.0)),
                "rationale": str(risk.get("rationale", "")),
            }],
        }})
    if detected_issue:
        entries.append({"resource": {
            "resourceType": "DetectedIssue",
            "status": "preliminary",
            "patient": {"reference": patient_ref},
            "identifiedDateTime": effective,
            "detail": str(detected_issue),
        }})
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": effective,
        "entry": entries,
    }


def validate_fhir_r4_bundle_schema(bundle: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return False, ["bundle is not an object"]
    if bundle.get("resourceType") != "Bundle":
        errors.append("resourceType must be Bundle")
    if bundle.get("type") not in {"collection", "document", "transaction"}:
        errors.append("Bundle.type is missing or unsupported")
    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries:
        errors.append("Bundle.entry must be a non-empty list")
        return False, errors
    for i, entry in enumerate(entries):
        res = (entry or {}).get("resource")
        if not isinstance(res, dict):
            errors.append(f"entry[{i}] has no resource")
            continue
        rtype = res.get("resourceType")
        if not rtype:
            errors.append(f"entry[{i}] resourceType missing")
            continue
        if rtype == "Patient":
            if not res.get("id"):
                errors.append(f"entry[{i}] Patient.id missing")
        elif rtype == "Procedure":
            if not res.get("status") or not res.get("code") or not res.get("subject"):
                errors.append(f"entry[{i}] Procedure requires status/code/subject")
        elif rtype == "Observation":
            if not res.get("status") or not res.get("code") or not res.get("subject"):
                errors.append(f"entry[{i}] Observation requires status/code/subject")
            vq = (res.get("valueQuantity") or {}).get("value")
            if not isinstance(vq, (int, float)):
                errors.append(f"entry[{i}] Observation valueQuantity.value missing")
        elif rtype not in {"RiskAssessment", "DetectedIssue"}:
            errors.append(f"entry[{i}] unsupported resourceType {rtype}")
        subject = res.get("subject") or res.get("patient")
        if subject and not str(subject.get("reference", "")).startswith("Patient/"):
            errors.append(f"entry[{i}] subject is not a Patient reference")
    return len(errors) == 0, errors
