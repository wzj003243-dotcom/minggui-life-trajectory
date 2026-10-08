import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"/"models"))
from fit_recurrent_lookup import LONG_AGES,AGES,fit
from simulate_fitted_lifetime import run,stage_bounds


class LongSimulationTests(unittest.TestCase):
    def model(self):
        rows=[]
        for split in ("train","validation"):
            for age in LONG_AGES:
                for group in ("0","1","2-4","5+"):
                    rows.append({
                        "split_name":split,"age_band":age,"hist_band":group,"n":100,
                        "cp":5,"cc":7,"rp":0,"rc":0,
                        "lp":2,"lc":2,"op":4,"oc":6,
                    })
        return fit(rows)

    def test_stage_bounds_complete(self):
        self.assertEqual(stage_bounds(25,88)[0],(25,30))
        self.assertEqual(stage_bounds(25,88)[-1],(80,88))

    def test_research_projection_reproducible(self):
        m=self.model()
        a=run(m,from_age=25,to_age_exclusive=88,paths=40,seed=10)
        b=run(m,from_age=25,to_age_exclusive=88,paths=40,seed=10)
        self.assertEqual(a,b)
        self.assertTrue(a["not_real_life_guarantee"])
        self.assertEqual(a["to_age_exclusive"],88)
        self.assertEqual(len(a["stagewise_documented_event_probabilities"]["stages"]),7)
        q=a["sampled_path_count_quantiles_documented_events"]
        self.assertLessEqual(q["p10"],q["median"])
        self.assertLessEqual(q["median"],q["p90"])

    def test_reject_unfitted_and_overrange(self):
        m=self.model()
        with self.assertRaises(ValueError):
            run({**m,"protocol":"first-event-round5"},paths=5)
        with self.assertRaises(ValueError):
            run(m,from_age=25,to_age_exclusive=90,paths=5)


if __name__ == "__main__":
    unittest.main()
