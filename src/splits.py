"""Deterministic patient partitions for the corrected experiments.

Frozen procedure (seed 20261107):

1. Outer folds: sort every patient by SHA-256("seed|outer|pid") and cut the
   order into three contiguous chunks. Each patient is outer-test in exactly
   one fold.
2. Inner roles: sort every patient by SHA-256("seed|role|pid") and assign
   70% fit / 10% early-stop / 10% calibration / 10% operating-point with
   largest-remainder rounding. A patient has one inner role, which applies
   in both outer-development folds. This keeps a patient from serving
   different roles in different folds.

Within every outer-development set the roles are disjoint. Counts per fold
are reported; they are close to, but not always exactly, 70/10/10/10 because
the role is a patient-level assignment rather than a per-fold one.

No patient ID is ever used as a Python hash seed; SHA-256 is stable across
processes and platforms.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Iterable, Mapping

from .config import CONFIG

ROLE_NAMES = ("fit", "early_stop", "calibration", "operating")
ROLE_FRACTIONS = CONFIG["INNER_ROLE_FRACTIONS"]
SEED = int(CONFIG["SPLIT_SEED"])
N_FOLDS = int(CONFIG["N_OUTER_FOLDS"])


def _digest(seed: int, purpose: str, pid: str) -> str:
    return hashlib.sha256(f"{seed}|{purpose}|{pid}".encode("utf-8")).hexdigest()


def _largest_remainder(n: int, fractions: Mapping[str, float]) -> dict[str, int]:
    raw = {k: n * float(fractions[k]) for k in ROLE_NAMES}
    out = {k: int(math.floor(raw[k])) for k in ROLE_NAMES}
    left = n - sum(out.values())
    order = sorted(ROLE_NAMES, key=lambda k: (-(raw[k] - out[k]), ROLE_NAMES.index(k)))
    for k in order[:left]:
        out[k] += 1
    return out


def build_manifest(pids: Iterable[str], seed: int = SEED, n_folds: int = N_FOLDS) -> dict:
    """Return the frozen manifest for a patient list.

    The same set of patients always yields the same manifest, independent of
    input order. `manifest_sha256` hashes the canonical JSON body (without
    the hash field itself).
    """
    patients = sorted({str(p) for p in pids})
    if n_folds < 2:
        raise ValueError("n_folds must be >= 2")
    if len(patients) < n_folds:
        raise ValueError(f"need at least {n_folds} patients, got {len(patients)}")

    outer_order = sorted(patients, key=lambda p: (_digest(seed, "outer", p), p))
    sizes = [len(patients) // n_folds + (1 if i < len(patients) % n_folds else 0)
             for i in range(n_folds)]
    fold_of: dict[str, int] = {}
    start = 0
    for fold, size in enumerate(sizes):
        for pid in outer_order[start:start + size]:
            fold_of[pid] = fold
        start += size

    role_order = sorted(patients, key=lambda p: (_digest(seed, "role", p), p))
    role_counts = _largest_remainder(len(patients), ROLE_FRACTIONS)
    role_of: dict[str, str] = {}
    start = 0
    for role in ROLE_NAMES:
        for pid in role_order[start:start + role_counts[role]]:
            role_of[pid] = role
        start += role_counts[role]

    folds = []
    for fold in range(n_folds):
        test_p = sorted(p for p in patients if fold_of[p] == fold)
        dev_p = sorted(p for p in patients if fold_of[p] != fold)
        roles = {r: sorted(p for p in dev_p if role_of[p] == r) for r in ROLE_NAMES}
        folds.append({
            "fold": fold,
            "test_patients": test_p,
            "development_patients": dev_p,
            "roles": roles,
            "counts": {
                "test": len(test_p),
                "development": len(dev_p),
                **{r: len(roles[r]) for r in ROLE_NAMES},
            },
        })

    manifest = {
        "seed": seed,
        "n_outer_folds": n_folds,
        "procedure": (
            "outer: SHA-256(seed|outer|pid) ascending, equal contiguous chunks; "
            "inner: SHA-256(seed|role|pid) ascending, one global role per patient, "
            "largest-remainder 70/10/10/10"
        ),
        "patients": {
            p: {"outer_fold": fold_of[p], "inner_role": role_of[p]}
            for p in patients
        },
        "folds": folds,
        "counts": {
            "patients": len(patients),
            "outer": sizes,
            "inner": role_counts,
        },
    }
    manifest["manifest_sha256"] = manifest_hash(manifest)
    validate_manifest(manifest)
    return manifest


def manifest_hash(manifest: Mapping) -> str:
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def validate_manifest(manifest: Mapping) -> None:
    """Raise ValueError if a manifest violates the frozen invariants."""
    patients = manifest["patients"]
    pids = set(patients)
    if len(pids) != int(manifest["counts"]["patients"]):
        raise ValueError("patient count does not match manifest")

    fold_ids = {int(f["fold"]) for f in manifest["folds"]}
    if fold_ids != set(range(int(manifest["n_outer_folds"]))):
        raise ValueError("fold ids are not 0..n-1")

    test_sets: list[set[str]] = []
    for f in manifest["folds"]:
        test = set(f["test_patients"])
        dev = set(f["development_patients"])
        if test & dev:
            raise ValueError(f"fold {f['fold']}: test and development overlap")
        if test | dev != pids:
            raise ValueError(f"fold {f['fold']}: does not cover all patients")
        role_sets = {r: set(f["roles"][r]) for r in ROLE_NAMES}
        if sum(len(s) for s in role_sets.values()) != len(dev):
            raise ValueError(f"fold {f['fold']}: roles do not cover development set")
        for i, a in enumerate(ROLE_NAMES):
            for b in ROLE_NAMES[i + 1:]:
                if role_sets[a] & role_sets[b]:
                    raise ValueError(f"fold {f['fold']}: roles {a}/{b} overlap")
        for pid in dev:
            if sum(pid in s for s in role_sets.values()) != 1:
                raise ValueError(f"fold {f['fold']}: {pid} has != 1 role")
        test_sets.append(test)

    for i in range(len(test_sets)):
        for j in range(i + 1, len(test_sets)):
            if test_sets[i] & test_sets[j]:
                raise ValueError("a patient appears in more than one outer test fold")

    for pid, rec in patients.items():
        if int(rec["outer_fold"]) not in fold_ids:
            raise ValueError(f"{pid}: invalid outer fold")
        if rec["inner_role"] not in ROLE_NAMES:
            raise ValueError(f"{pid}: invalid inner role")
        seen_test = sum(pid in s for s in test_sets)
        if seen_test != 1:
            raise ValueError(f"{pid}: appears in {seen_test} outer test folds")

    if manifest_hash(manifest) != manifest.get("manifest_sha256"):
        raise ValueError("manifest hash does not match canonical body")


def role_patients(manifest: Mapping, fold: int, role: str) -> set[str]:
    """Patients with `role` in the outer-development set for `fold`."""
    f = manifest["folds"][int(fold)]
    return set(f["roles"][role])


def fit_patients(manifest: Mapping, fold: int) -> set[str]:
    return role_patients(manifest, fold, "fit")


def outer_test_patients(manifest: Mapping, fold: int) -> set[str]:
    return set(manifest["folds"][int(fold)]["test_patients"])


def patient_of_session(session_id: str) -> str:
    return str(session_id).rsplit("_", 1)[0]


def sessions_of_patients(session_ids: Iterable[str], pids: set[str]) -> list[str]:
    return sorted(s for s in session_ids if patient_of_session(s) in pids)
