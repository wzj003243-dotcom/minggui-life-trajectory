import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "models"))

from lifetime_paths import DOMAINS, Event, State, simulate_paths, summarize_paths


class LifetimePathTests(unittest.TestCase):
    def test_zero_rate_has_no_events(self):
        fn = lambda _: {d: 0.0 for d in DOMAINS}
        paths = simulate_paths(from_age=20, to_age=100, history=(), intensity=fn, n_paths=30)
        self.assertTrue(all(not p for p in paths))
        s = summarize_paths(paths, ((20, 40), (40, 100)))
        self.assertEqual(s["stages"][0]["mean_all_documented_events"], 0)

    def test_reproducible_and_multi_event(self):
        fn = lambda _: {"career": 5.0, "recognition": 0, "relationship": 0, "other": 0}
        a = simulate_paths(from_age=30, to_age=32, history=(), intensity=fn, n_paths=20, seed=17)
        b = simulate_paths(from_age=30, to_age=32, history=(), intensity=fn, n_paths=20, seed=17)
        self.assertEqual(a, b)
        self.assertTrue(any(len(p) > 2 for p in a))
        self.assertTrue(all(30 <= e.age < 32 for p in a for e in p))

    def test_future_updates_state_only_after_year(self):
        seen = []
        def fn(st):
            seen.append((st.age, len(st.history)))
            return {"career": 10.0 if st.age == 21 else 0.0, "recognition": 0.0,
                    "relationship": 0.0, "other": 0.0}
        simulate_paths(from_age=20, to_age=23, history=(Event(19, "career"),), intensity=fn, n_paths=1)
        self.assertEqual(seen[:2], [(20, 1), (21, 1)])
        self.assertGreater(seen[2][1], 1)

    def test_invalid_probabilities_and_leakage(self):
        zero = lambda _: {d: 0 for d in DOMAINS}
        with self.assertRaises(ValueError):
            simulate_paths(from_age=20, to_age=21, history=(Event(20, "other"),), intensity=zero)
        bad = lambda _: {"career": -1, "recognition": 0, "relationship": 0, "other": 0}
        with self.assertRaises(ValueError):
            simulate_paths(from_age=20, to_age=21, history=(), intensity=bad)
        with self.assertRaises(ValueError):
            simulate_paths(from_age=20, to_age=21, history=(), intensity=lambda _: {"career": 0})

    def test_summary_bounds(self):
        fn = lambda _: {d: 0.2 for d in DOMAINS}
        paths = simulate_paths(from_age=25, to_age=60, history=(), intensity=fn, n_paths=150, seed=1)
        summary = summarize_paths(paths, ((25, 35), (35, 60)))
        for stage in summary["stages"]:
            for domain in stage["domains"].values():
                self.assertTrue(0 <= domain["probability_at_least_one"] <= 1)


if __name__ == "__main__":
    unittest.main()
