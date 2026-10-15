import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"research"/"traditional"))
from evaluate_r7b import score


class R7BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads((ROOT/"research"/"traditional"/"results"/"r7b_context_grouped.json").read_text())["rows"]

    def test_frozen_exposure_and_negative_result(self):
        s=score(self.rows)
        self.assertEqual(s["train_person_years"],115288)
        self.assertEqual(s["validation_person_years"],24464)
        self.assertFalse(s["screen_pass"])
        self.assertAlmostEqual(s["models"]["relationship"]["age_only"]["log_loss"],0.05073226176372906,places=11)
        self.assertAlmostEqual(s["models"]["relationship"]["shift_0"]["log_loss"],0.051300336243086546,places=11)
        self.assertAlmostEqual(s["models"]["career"]["shift_0"]["log_loss"],0.1464863759107583,places=11)
        for domain in ("career","relationship"):
            self.assertGreater(s["models"][domain]["shift_0"]["log_loss"],
                               s["models"][domain]["natal_context"]["log_loss"])

    def test_forbid_test_split_and_duplicates(self):
        new=copy.deepcopy(self.rows)
        new[0]["split_name"]="test"
        with self.assertRaises(ValueError):score(new)
        with self.assertRaises(ValueError):score(self.rows+[copy.deepcopy(self.rows[0])])

    def test_invalid_counts_cannot_pass(self):
        new=copy.deepcopy(self.rows)
        new[0]["relationship_0"]=new[0]["exposure_0"]+1
        with self.assertRaises(ValueError):score(new)

    def test_validation_labels_change_scores_not_career(self):
        new=copy.deepcopy(self.rows)
        for r in new:
            if r["split_name"]=="validation":
                r["relationship_cases"]=0
                for shift in (0,1,3,5):
                    r["relationship_"+str(shift)]=0
        revised=score(new)
        base=score(self.rows)
        self.assertNotEqual(revised["models"]["relationship"],base["models"]["relationship"])
        self.assertEqual(revised["models"]["career"],base["models"]["career"])


if __name__=="__main__":
    unittest.main()
