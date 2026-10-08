import sys
import unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "models"))

from fit_recurrent_lookup import AGES, HISTORY, fit, age_bin, history_bin, intensity_from_model
from lifetime_paths import Event, simulate_paths


def synthetic_rows():
    rows = []
    for split in ("train", "validation"):
        for age in AGES:
            for group in HISTORY:
                n = 500 if split == "train" else 75
                pc = 2 if group in ("0", "1") else 12
                count = pc + (2 if group == "5+" else 0)
                rows.append({
                    "split_name": split, "age_band": age, "hist_band": group, "n": n,
                    "cp": pc, "cc": count, "rp": 0, "rc": 0,
                    "lp": 1, "lc": 1, "op": 4, "oc": 6,
                })
    return rows


class LookupTests(unittest.TestCase):
    def test_predefined_bins_and_intensity(self):
        self.assertEqual(age_bin(18), "18-24")
        self.assertEqual(age_bin(37), "35-37")
        self.assertEqual(history_bin(4), "2-4")
        self.assertEqual(history_bin(5), "5+")
        with self.assertRaises(ValueError):
            age_bin(38)
        with self.assertRaises(ValueError):
            history_bin(-1)

    def test_fit_and_poisson_adapter(self):
        model = fit(synthetic_rows())
        self.assertEqual(model["supported_ages_inclusive"], [18, 37])
        self.assertEqual(model["train_exposure_person_years"], 4 * 4 * 500)
        rates = intensity_from_model(model, age=25, history_count=7)
        self.assertGreater(rates["career"], 0)
        self.assertEqual(rates["recognition"], 0)
        self.assertGreater(
            intensity_from_model(model, age=25, history_count=7)["career"],
            intensity_from_model(model, age=25, history_count=0)["career"]
        )
        paths = simulate_paths(
            from_age=25,to_age=27,history=(Event(24, "other"),),
            intensity=lambda st: intensity_from_model(
                model,age=st.age,history_count=len(st.history)
            ),
            n_paths=5,seed=1
        )
        self.assertEqual(len(paths), 5)

    def test_validation_labels_never_enter_fit(self):
        rows = synthetic_rows()
        a = fit(rows)
        changed = deepcopy(rows)
        for r in changed:
            if r["split_name"] == "validation":
                r["cp"] = r["cc"] = r["n"]
        b = fit(changed)
        self.assertEqual(a["age_rates"], b["age_rates"])
        self.assertEqual(a["age_history_rates"], b["age_history_rates"])
        self.assertNotEqual(a["dev_validation_metrics"], b["dev_validation_metrics"])

    def test_test_split_forbidden(self):
        rows = synthetic_rows()
        rows[0]["split_name"] = "test"
        with self.assertRaises(ValueError):
            fit(rows)

    def test_zero_event_domain_is_stable(self):
        m = fit(synthetic_rows())
        self.assertEqual(m["age_history_rates"]["18-24"]["0"]["recognition"], 0)
        self.assertTrue(0 <= m["dev_validation_metrics"]["age_only"]["recognition"]["binary_brier"] < 1)


if __name__ == "__main__":
    unittest.main()
