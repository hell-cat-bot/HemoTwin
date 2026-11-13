"""Task 00 tests: deterministic patient manifests."""
from __future__ import annotations

import random
import unittest

from src.splits import (
    ROLE_NAMES,
    build_manifest,
    fit_patients,
    manifest_hash,
    outer_test_patients,
    validate_manifest,
)


class SplitManifestTest(unittest.TestCase):
    def test_deterministic_and_order_independent(self):
        pids = [f"p{i:04d}" for i in range(101)]
        a = build_manifest(pids, seed=20261107)
        shuffled = list(pids)
        random.Random(7).shuffle(shuffled)
        b = build_manifest(shuffled, seed=20261107)
        self.assertEqual(a["manifest_sha256"], b["manifest_sha256"])
        self.assertEqual(manifest_hash(a), a["manifest_sha256"])
        validate_manifest(a)

    def test_outer_folds_are_patient_disjoint(self):
        pids = [f"p{i:04d}" for i in range(120)]
        m = build_manifest(pids, seed=20261107)
        seen = set()
        for fold in range(m["n_outer_folds"]):
            test = outer_test_patients(m, fold)
            self.assertFalse(seen & test)
            seen |= test
        self.assertEqual(seen, set(pids))

    def test_one_global_role_per_patient_and_roles_disjoint(self):
        pids = [f"p{i:04d}" for i in range(200)]
        m = build_manifest(pids, seed=20261107)
        for fold in range(m["n_outer_folds"]):
            dev = set(m["folds"][fold]["development_patients"])
            seen = set()
            for role in ROLE_NAMES:
                role_set = set(m["folds"][fold]["roles"][role])
                self.assertFalse(seen & role_set)
                seen |= role_set
            self.assertEqual(seen, dev)
            # A patient has exactly one role, so role membership must agree
            # between the two folds in which that patient is development.
            if fold == 0:
                other = 1
                for pid in dev & set(m["folds"][other]["development_patients"]):
                    self.assertEqual(
                        m["patients"][pid]["inner_role"],
                        next(r for r in ROLE_NAMES
                             if pid in set(m["folds"][fold]["roles"][r])),
                    )

    def test_fit_patients_exclude_outer_test(self):
        pids = [f"p{i:04d}" for i in range(90)]
        m = build_manifest(pids, seed=20261107)
        for fold in range(m["n_outer_folds"]):
            self.assertFalse(fit_patients(m, fold) & outer_test_patients(m, fold))

    def test_largest_remainder_counts(self):
        pids = [f"p{i:04d}" for i in range(101)]
        m = build_manifest(pids, seed=20261107)
        self.assertEqual(sum(m["counts"]["inner"].values()), 101)
        self.assertEqual(m["counts"]["inner"]["fit"], 71)
        self.assertEqual(m["counts"]["inner"]["early_stop"], 10)
        self.assertEqual(m["counts"]["inner"]["calibration"], 10)
        self.assertEqual(m["counts"]["inner"]["operating"], 10)

    def test_validate_rejects_overlap(self):
        m = build_manifest([f"p{i:04d}" for i in range(30)], seed=20261107)
        broken = {
            "seed": m["seed"],
            "n_outer_folds": m["n_outer_folds"],
            "procedure": m["procedure"],
            "patients": m["patients"],
            "folds": [dict(f) for f in m["folds"]],
            "counts": m["counts"],
            "manifest_sha256": m["manifest_sha256"],
        }
        # Move one test patient into the development role list without
        # updating the patient map: validation must catch the double role.
        pid = broken["folds"][0]["test_patients"][0]
        broken["folds"][0]["roles"] = {
            k: list(v) for k, v in broken["folds"][0]["roles"].items()
        }
        broken["folds"][0]["roles"]["fit"].append(pid)
        with self.assertRaises(ValueError):
            validate_manifest(broken)


if __name__ == "__main__":
    unittest.main()
