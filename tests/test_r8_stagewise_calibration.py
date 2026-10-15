import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"research"/"benchmarks"))
from audit_r8_stagewise_calibration import audit

class R8CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=json.loads((ROOT/"research"/"benchmarks"/"results"/"v12_r6_dev_lifetime_lookup.json").read_text())
        cls.rows=json.loads((ROOT/"research"/"benchmarks"/"data"/"v12_r6_dev_lifetime_aggregates.json").read_text())

    def test_frozen_derived_metrics_with_readable_warning_flags(self):
        got=audit(self.model,self.rows)
        self.assertEqual(got["validation_person_years"],21449)
        self.assertEqual(got["training_person_years"],100771)
        self.assertEqual(got["engineering_red_flags"],3)
        self.assertFalse(got["is_multi_year_trajectory_calibrated"])
        self.assertFalse(got["ready_for_personal_life_forecast"])
        self.assertAlmostEqual(
            next(x for x in got["by_age"] if x["age_band"]=="58-67")
             ["domains"]["other"]["age_only_expected_documented_records"],72.657,delta=.1)
        expected=json.loads((ROOT/"research"/"benchmarks"/"results"/"r8_stage_calibration_audit.json").read_text())
        self.assertEqual(got,expected)

    def test_old_test_partition_forbidden(self):
        tampered=copy.deepcopy(self.rows)
        tampered[0]["split_name"]="test"
        with self.assertRaises(ValueError): audit(self.model,tampered)

    def test_wrong_label_scope_forbidden(self):
        mod=copy.deepcopy(self.model)
        mod["label_scope"]="first_event_in_a_person"
        with self.assertRaises(ValueError):audit(mod,self.rows)

    def test_duplicate_group_forbidden(self):
        with self.assertRaises(ValueError):audit(self.model,self.rows+[self.rows[0]])

    def test_warning_not_a_significance_claim(self):
        got=audit(self.model,self.rows)
        self.assertIn("No real-life event rates",got["note"])
        for row in got["by_age"]:
            for domain,data in row["domains"].items():
                self.assertGreaterEqual(data["age_only_expected_documented_records"],0)
                self.assertNotIn("p_value",data)

if __name__=="__main__":
    unittest.main()
