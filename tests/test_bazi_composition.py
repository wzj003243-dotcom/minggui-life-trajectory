import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "traditional"))
from bazi_composition_v1 import compose, ten_god, validate_pillar, SCHEMA

NATAL = {"year": "甲子", "month": "丙寅", "day": "甲午", "hour": None}


class BaZiCompositionTests(unittest.TestCase):
    def test_ten_gods_against_jia_daymaster(self):
        expected = {
            "甲": "比肩", "乙": "劫财", "丙": "食神", "丁": "伤官",
            "戊": "偏财", "己": "正财", "庚": "七杀", "辛": "正官",
            "壬": "偏印", "癸": "正印",
        }
        self.assertEqual({s: ten_god("甲", s) for s in expected}, expected)
        # Every stem has all ten relation categories across the ten stems.
        for stem in expected:
            self.assertEqual(set(ten_god(stem, s) for s in expected),
                             set(expected.values()))

    def test_60_cycle_parity_check(self):
        self.assertEqual(validate_pillar("甲子"), "甲子")
        self.assertEqual(validate_pillar("乙丑"), "乙丑")
        with self.assertRaises(ValueError):
            validate_pillar("甲丑")
        with self.assertRaises(ValueError):
            validate_pillar("甲甲")
        with self.assertRaises(ValueError):
            validate_pillar("庚")

    def test_no_fake_birth_hour(self):
        r = compose(NATAL)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertTrue(r["missing_hour"])
        self.assertFalse(r["known_hour"])
        self.assertNotIn("hour", r["pillars"])
        self.assertIsNone(r["prediction_probability"])
        self.assertEqual(r["pillars"]["month"]["stem_ten_god"], "食神")
        self.assertEqual(
            [x["stem"] for x in r["pillars"]["month"]["hidden_stems"]],
            ["甲", "丙", "戊"],
        )

    def test_natal_luck_annual_composition_is_traceable(self):
        r = compose(NATAL, age=28, luck_pillar="己未", luck_age_range=(21,30),
                    annual_pillar="庚子", annual_calendar_year=2026)
        self.assertEqual(r["pillars"]["luck"]["stem_ten_god"], "正财")
        self.assertEqual(r["pillars"]["annual"]["stem_ten_god"], "七杀")
        self.assertTrue(any(
            x["source"] == "year" and x["target"] == "day"
            and x["kind"] == "branch_clash"
            for x in r["natal_relations"]
        ))
        self.assertTrue(any(
            x["source"] == "luck" and x["target"] == "day"
            and x["kind"] == "branch_combine"
            for x in r["cycle_relations"]
        ))
        self.assertTrue(any(
            x["source"] == "annual" and x["target"] == "day"
            and x["kind"] == "branch_clash"
            for x in r["cycle_relations"]
        ))
        self.assertEqual(r["traditional_event_mapping"],
                         "unassigned_until_preregistered")
        self.assertFalse(r["calendar_inputs_audited_upstream"])

    def test_requires_explicit_luck_and_annual_boundary(self):
        with self.assertRaises(ValueError):
            compose(NATAL, age=25, luck_pillar="己未")
        with self.assertRaises(ValueError):
            compose(NATAL, age=25, luck_pillar="己未",
                    luck_age_range=(31,40))
        with self.assertRaises(ValueError):
            compose(NATAL, annual_pillar="庚子")
        with self.assertRaises(ValueError):
            compose(NATAL, annual_calendar_year=2026)

    def test_natal_input_does_not_mutate(self):
        snapshot = dict(NATAL)
        compose(NATAL, age=28, luck_pillar="己未", luck_age_range=(21, 30))
        self.assertEqual(NATAL, snapshot)


if __name__ == "__main__":
    unittest.main()
