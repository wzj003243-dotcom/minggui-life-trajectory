"""Construct annual recurrent-event learning rows from a *frozen* event export.

This operates on source records only; it does not train a model or silently
turn missing biography evidence into negative real-life outcomes. All date
windows are [start, end). A row is marked ambiguous if an event's uncertainty
interval crosses the annual boundary.

Expected cohort fields: person_id, split_name, cutoff_date, observation_end_date.
Expected event fields: person_id, canonical_event_key, domain,
  event_date_min, event_date_max, observable_from.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Iterable, Mapping

DOMAINS = ("career", "recognition", "relationship", "other")


def _date(v: str | date) -> date:
    return v if isinstance(v, date) else date.fromisoformat(v)


def _plus_years(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        # Feb 29 -> Feb 28, consistently.
        return d.replace(year=d.year + n, day=28)


def _domain(raw: str | None) -> str:
    return raw if raw in DOMAINS else "other"


def build_annual_rows(
    cohort: Iterable[Mapping],
    events: Iterable[Mapping],
    *,
    max_years: int = 20,
) -> list[dict]:
    """One row per fully administratively followed-up person-year.

    Retrospective source timing is not genuinely prospective availability:
    observable_from alone is NOT proof a biography was published by that year.
    For that reason, zero counts MUST NOT be certified as real-world negatives.
    """
    if not 1 <= max_years <= 100:
        raise ValueError("max_years must be 1..100")
    indexed = defaultdict(list)
    dedup = set()
    for e in events:
        person = int(e["person_id"])
        key = str(e["canonical_event_key"])
        if (person, key) in dedup:
            raise ValueError("duplicate canonical event key")
        dedup.add((person, key))
        start = _date(e["event_date_min"])
        end = _date(e["event_date_max"])
        if start > end:
            raise ValueError("event_date_min > event_date_max")
        indexed[person].append((
            start, end, _date(e["observable_from"]), _domain(e.get("domain")), key,
        ))

    seen_split = {}
    rows = []
    for p in cohort:
        person = int(p["person_id"])
        split = str(p["split_name"])
        if person in seen_split and seen_split[person] != split:
            raise ValueError("person assigned to multiple partitions")
        seen_split[person] = split
        cutoff = _date(p["cutoff_date"])
        followup = _date(p["observation_end_date"])
        if followup < cutoff:
            raise ValueError("observation end before cutoff")
        evs = indexed[person]
        for step in range(max_years):
            d0 = _plus_years(cutoff, step)
            d1 = _plus_years(cutoff, step + 1)
            if d1 > followup:
                break
            history = [e for e in evs if e[1] < d0 and e[2] <= d0]
            within = [e for e in evs if e[0] >= d0 and e[1] < d1]
            ambiguous = [
                e for e in evs
                if e[0] < d1 and e[1] >= d0
                and not (e[0] >= d0 and e[1] < d1)
            ]
            hcount = Counter(e[3] for e in history)
            recent = Counter(e[3] for e in history if e[1] >= _plus_years(d0, -5))
            targets = Counter(e[3] for e in within)
            rows.append({
                "person_id": person,
                "split_name": split,
                "year_index": step,
                "year_start": d0.isoformat(),
                "year_end_exclusive": d1.isoformat(),
                "history_event_count": len(history),
                "history_domain_counts": {d: hcount[d] for d in DOMAINS},
                "history_recent_5y_counts": {d: recent[d] for d in DOMAINS},
                "years_since_last_history_event": (
                    (d0 - max(e[1] for e in history)).days / 365.25
                    if history else None
                ),
                "target_documented_event_counts": {d: targets[d] for d in DOMAINS},
                "ambiguous_temporal_events": len(ambiguous),
                "label_temporally_evaluable": len(ambiguous) == 0,
                "administratively_followed_up": True,
                "real_world_no_event_certified": False,
                "label_scope": "retrospective_documented_events_only",
            })
    return rows
