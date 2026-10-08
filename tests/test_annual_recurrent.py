import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "models"))
from build_annual_recurrent import build_annual_rows


class AnnualRecurrentTests(unittest.TestCase):
    def cohort(self, end="2003-01-01"):
        return [{"person_id": 3, "split_name": "train", "cutoff_date": "2000-01-01",
                 "observation_end_date": end}]

    def event(self, key, start, end=None, domain="career", available="1999-01-01"):
        return {"person_id": 3, "canonical_event_key": key, "domain": domain,
                "event_date_min": start, "event_date_max": end or start,
                "observable_from": available}

    def test_multiple_events_and_past_only(self):
        events = [self.event("a", "2000-03-01"),
                  self.event("b", "2000-09-01", domain="recognition"),
                  self.event("c", "2001-06-01", domain="relationship")]
        rows = build_annual_rows(self.cohort(), events, max_years=3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["target_documented_event_counts"]["career"], 1)
        self.assertEqual(rows[0]["target_documented_event_counts"]["recognition"], 1)
        self.assertEqual(rows[0]["history_event_count"], 0)
        self.assertEqual(rows[1]["history_event_count"], 2)
        self.assertEqual(rows[1]["target_documented_event_counts"]["relationship"], 1)
        self.assertEqual(rows[2]["history_event_count"], 3)
        self.assertFalse(rows[0]["real_world_no_event_certified"])

    def test_boundary_uncertainty_masks_years(self):
        events = [self.event("boundary", "2000-12-29", "2001-01-02")]
        rows = build_annual_rows(self.cohort(), events, max_years=3)
        self.assertFalse(rows[0]["label_temporally_evaluable"])
        self.assertFalse(rows[1]["label_temporally_evaluable"])
        self.assertEqual(rows[0]["target_documented_event_counts"]["career"], 0)

    def test_known_as_of_and_admin_censor(self):
        events = [self.event("later_revision", "2000-02-01", available="2020-01-01")]
        rows = build_annual_rows(self.cohort("2002-01-01"), events, max_years=5)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["history_event_count"], 0)
        self.assertEqual(rows[0]["target_documented_event_counts"]["career"], 1)

    def test_person_split_isolation(self):
        cohort = self.cohort() + [{**self.cohort()[0], "split_name": "test"}]
        with self.assertRaises(ValueError):
            build_annual_rows(cohort, [])

    def test_duplicate_canonical_key(self):
        e = self.event("x", "2000-01-03")
        with self.assertRaises(ValueError):
            build_annual_rows(self.cohort(), [e, e])


if __name__ == "__main__":
    unittest.main()
