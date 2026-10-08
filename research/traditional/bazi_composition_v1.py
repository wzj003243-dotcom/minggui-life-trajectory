"""Versioned, descriptive BaZi composition features; NOT a fate predictor.

Inputs are ALREADY-CALCULATED GanZhi pillars from an audited calendar engine.
This module never guesses calendar conversion, birth hour, start of DaYun,
or event probabilities. It emits traceable symbolic relations for experiments.

No relation is automatically interpreted as "good", "bad", or an actual event.
Treat all traditional correspondences as hypotheses until validated against
independent, temporally appropriate evidence.
"""
from __future__ import annotations

from itertools import combinations
from typing import Mapping

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = ("木", "火", "土", "金", "水")
STEM_ELEMENTS = dict(zip(STEMS, ("木","木","火","火","土","土","金","金","水","水")))
HIDDEN_STEMS = {
    "子": ("癸",), "丑": ("己", "癸", "辛"), "寅": ("甲", "丙", "戊"),
    "卯": ("乙",), "辰": ("戊", "乙", "癸"), "巳": ("丙", "戊", "庚"),
    "午": ("丁", "己"), "未": ("己", "丁", "乙"), "申": ("庚", "壬", "戊"),
    "酉": ("辛",), "戌": ("戊", "辛", "丁"), "亥": ("壬", "甲"),
}
BRANCH_CLASHES = {
    frozenset(x) for x in ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")
}
BRANCH_COMBINATIONS = {
    frozenset(x) for x in ("子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未")
}
STEM_COMBINATIONS = {
    frozenset(x) for x in ("甲己", "乙庚", "丙辛", "丁壬", "戊癸")
}

PILLAR_NAMES = ("year", "month", "day", "hour")
DYNAMIC_NAMES = ("luck", "annual")
SCHEMA = "minggui-bazi-composition-v1"


def validate_pillar(value: str) -> str:
    """Check that two signs could belong to the 60-GanZhi cycle."""
    if not isinstance(value, str) or len(value) != 2:
        raise ValueError("GanZhi pillar must contain one stem and one branch")
    s, b = value
    if s not in STEMS or b not in BRANCHES:
        raise ValueError(f"invalid GanZhi pillar: {value!r}")
    if STEMS.index(s) % 2 != BRANCHES.index(b) % 2:
        raise ValueError(f"stem/branch yin-yang parity mismatch: {value!r}")
    return value


def ten_god(day_stem: str, other_stem: str) -> str:
    """Classical ten-god relationship, never an asserted life-event outcome."""
    if day_stem not in STEMS or other_stem not in STEMS:
        raise ValueError("unknown heavenly stem")
    base = ELEMENTS.index(STEM_ELEMENTS[day_stem])
    other = ELEMENTS.index(STEM_ELEMENTS[other_stem])
    same_polarity = STEMS.index(day_stem) % 2 == STEMS.index(other_stem) % 2
    if base == other:
        return "比肩" if same_polarity else "劫财"
    if (base + 1) % 5 == other:
        return "食神" if same_polarity else "伤官"
    if (base + 2) % 5 == other:
        return "偏财" if same_polarity else "正财"
    if (other + 2) % 5 == base:
        return "七杀" if same_polarity else "正官"
    if (other + 1) % 5 == base:
        return "偏印" if same_polarity else "正印"
    raise AssertionError("invalid five-element relation")


def _relation(a_name: str, a: str, b_name: str, b: str) -> list[dict]:
    results = []
    stem_pair = frozenset((a[0], b[0]))
    branch_pair = frozenset((a[1], b[1]))
    if stem_pair in STEM_COMBINATIONS:
        results.append({"source": a_name, "target": b_name, "kind": "stem_combine",
                        "symbols": [a[0], b[0]]})
    if branch_pair in BRANCH_COMBINATIONS:
        results.append({"source": a_name, "target": b_name, "kind": "branch_combine",
                        "symbols": [a[1], b[1]]})
    if branch_pair in BRANCH_CLASHES:
        results.append({"source": a_name, "target": b_name, "kind": "branch_clash",
                        "symbols": [a[1], b[1]]})
    return results


def _record(name: str, pillar: str, day_stem: str) -> dict:
    branch = pillar[1]
    return {
        "pillar": pillar,
        "stem": pillar[0],
        "branch": branch,
        "stem_element": STEM_ELEMENTS[pillar[0]],
        "stem_ten_god": "日主" if name == "day" else ten_god(day_stem, pillar[0]),
        "hidden_stems": [
            {"stem": h, "ten_god": ten_god(day_stem, h)}
            for h in HIDDEN_STEMS[branch]
        ],
    }


def compose(
    natal: Mapping[str, str | None],
    *,
    age: int | None = None,
    luck_pillar: str | None = None,
    luck_age_range: tuple[int, int] | None = None,
    annual_pillar: str | None = None,
    annual_calendar_year: int | None = None,
) -> dict:
    """Create chart + cycle symbolic relations with explicit uncertainties.

    natal: year, month, day required; hour may be None.
    luck_pillar requires precomputed age range from calendar calculation;
      a missing or uncertain start is NOT estimated by this module.
    annual_pillar requires audited calendar year; this module does NOT assume
      Gregorian Jan 1 is the GanZhi year boundary.
    """
    if any(not natal.get(k) for k in ("year", "month", "day")):
        raise ValueError("year, month and day pillars are required")
    if set(natal) - set(PILLAR_NAMES):
        raise ValueError("unsupported natal pillar key")
    chart = {k: validate_pillar(v) for k, v in natal.items() if v is not None}
    if age is not None and (not isinstance(age, int) or age < 0 or age > 120):
        raise ValueError("invalid age")
    if luck_pillar is None and luck_age_range is not None:
        raise ValueError("luck interval without cycle pillar")
    if luck_pillar is not None:
        if age is None or luck_age_range is None:
            raise ValueError("luck pillar must have known age and interval")
        if (len(luck_age_range) != 2 or luck_age_range[0] < 0
                or not luck_age_range[0] <= age <= luck_age_range[1]):
            raise ValueError("luck age does not fall within source interval")
    if (annual_pillar is None) != (annual_calendar_year is None):
        raise ValueError("annual pillar and calendar year must be supplied together")
    if annual_calendar_year is not None and (
            not isinstance(annual_calendar_year, int) or annual_calendar_year < 1):
        raise ValueError("invalid annual calendar year")

    if luck_pillar is not None:
        chart["luck"] = validate_pillar(luck_pillar)
    if annual_pillar is not None:
        chart["annual"] = validate_pillar(annual_pillar)
    dm = chart["day"][0]
    records = {k: _record(k, v, dm) for k, v in chart.items()}

    natal_relations = [
        rel for a, b in combinations([x for x in PILLAR_NAMES if x in chart], 2)
        for rel in _relation(a, chart[a], b, chart[b])
    ]
    cycle_relations = [
        rel for cycle in DYNAMIC_NAMES if cycle in chart
        for nat in PILLAR_NAMES if nat in chart
        for rel in _relation(cycle, chart[cycle], nat, chart[nat])
    ]
    if "luck" in chart and "annual" in chart:
        cycle_relations += _relation("luck", chart["luck"], "annual", chart["annual"])

    return {
        "schema": SCHEMA,
        "age": age,
        "day_master": dm,
        "day_master_element": STEM_ELEMENTS[dm],
        "seasonal_reference_branch": chart["month"][1],
        "known_hour": "hour" in chart,
        "missing_hour": "hour" not in chart,
        "calendar_inputs_audited_upstream": False,
        "luck_interval_inclusive": list(luck_age_range) if luck_age_range else None,
        "annual_calendar_year": annual_calendar_year,
        "pillars": records,
        "natal_relations": natal_relations,
        "cycle_relations": cycle_relations,
        "prediction_probability": None,
        "traditional_event_mapping": "unassigned_until_preregistered",
        "interpretation": (
            "Descriptive traditional-symbol features only. "
            "No event, luck, health or destiny inference is asserted."
        ),
    }
