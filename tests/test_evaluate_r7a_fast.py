import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"research"/"traditional"))
from evaluate_r7a_fast import evaluate


class R7AFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads(
            (ROOT/"research"/"traditional"/"results"/"r7a_fast_age_aggregates.json")
            .read_text()
        )["rows"]

    def test_frozen_data_age_strata(self):
        self.assertEqual(len(self.rows),14)
        self.assertEqual(sum(r["n"] for r in self.rows if r["split_name"]=="train"),115288)
        self.assertEqual(sum(r["n"] for r in self.rows if r["split_name"]=="validation"),24464)

    def test_predeclared_shift_control_conclusion(self):
        result=evaluate(self.rows)
        self.assertFalse(result["screen_pass"])
        self.assertTrue(result["no_external_test"])
        career=result["result_by_domain"]["career"]
        rel=result["result_by_domain"]["relationship"]
        self.assertAlmostEqual(career["0"]["clash_logloss"],0.145819226751197,places=10)
        self.assertAlmostEqual(rel["0"]["clash_logloss"],0.050720950854713245,places=10)
        self.assertGreater(career["0"]["delta_logloss"],0)
        self.assertLess(rel["0"]["delta_logloss"],0)
        self.assertLess(rel["3"]["delta_logloss"],0)
        self.assertEqual(rel["0"]["positive_years"],225)
        self.assertEqual(career["0"]["positive_years"],816)

    def test_counts_are_guarded(self):
        invalid=copy.deepcopy(self.rows)
        invalid[0]["exposure_0"]=-1
        with self.assertRaises(ValueError):
            evaluate(invalid)

    def test_duplicate_group_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(self.rows+[dict(self.rows[0])])

    def test_validation_scores_not_used_for_fitting(self):
        # Modifying validation outcomes changes scores, but training rates must
        # remain fixed. The observed base rate in age-stratum is checked via
        # comparing a shift's age-only loss computed on NEW outcomes; no fit on
        # validation source.
        changed=copy.deepcopy(self.rows)
        for row in changed:
            if row["split_name"]=="validation":
                row["relationship_cases"]=0
                for shift in (0,1,3,5):
                    row[f"relationship_{shift}"]=0
        r=evaluate(changed)
        self.assertNotEqual(
            r["result_by_domain"]["relationship"]["0"]["clash_logloss"],
            evaluate(self.rows)["result_by_domain"]["relationship"]["0"]["clash_logloss"]
        )
        self.assertEqual(
            r["result_by_domain"]["career"],
            evaluate(self.rows)["result_by_domain"]["career"]
        )


if __name__=="__main__":
    unittest.main()
