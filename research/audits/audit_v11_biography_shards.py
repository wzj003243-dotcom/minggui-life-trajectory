"""Audit the four v1.1 Wikipedia biography shard artifacts before import.

The audit is deliberately artifact-first: it validates the raw cohort partitions,
revision-pinned biography records, high-recall candidates, and precision-first rule
events without depending on mutable database state.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

QID = re.compile(r"^Q\d+$")


def open_zip(path: Path) -> zipfile.ZipFile:
    return zipfile.ZipFile(path)


def find_name(z: zipfile.ZipFile, pattern: re.Pattern[str]) -> str:
    names = [n for n in z.namelist() if pattern.search(n)]
    if len(names) != 1:
        raise ValueError(f"{z.filename}: expected one {pattern.pattern}, got {names}")
    return names[0]


def csv_gz_rows(z: zipfile.ZipFile, pattern: re.Pattern[str]) -> list[dict[str, str]]:
    name = find_name(z, pattern)
    raw = z.read(name)
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as g:
        text = io.TextIOWrapper(g, encoding="utf-8", newline="")
        return list(csv.DictReader(text))


def jsonl_gz_rows(z: zipfile.ZipFile, pattern: re.Pattern[str]) -> list[dict]:
    name = find_name(z, pattern)
    raw = z.read(name)
    out = []
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as g:
        for line in io.TextIOWrapper(g, encoding="utf-8"):
            if line.strip():
                out.append(json.loads(line))
    return out


def json_obj(z: zipfile.ZipFile, pattern: re.Pattern[str]) -> dict:
    name = find_name(z, pattern)
    return json.loads(z.read(name))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("artifacts", nargs="+", type=Path)
    ap.add_argument("--expected-shards", type=int, default=4)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    expected_shards = set(range(args.expected_shards))

    cohort_by_shard: dict[int, list[dict[str, str]]] = {}
    bios_by_shard: dict[int, list[dict]] = {}
    candidates_by_shard: dict[int, list[dict[str, str]]] = {}
    rules_by_shard: dict[int, list[dict[str, str]]] = {}
    reports: dict[int, dict] = {}

    for path in args.artifacts:
        with open_zip(path) as z:
            report = json_obj(z, re.compile(r"(^|/)shard-\d+\.report\.json$"))
            shard = int(report["shard"])
            if shard in reports:
                raise ValueError(f"duplicate shard artifact {shard}")
            reports[shard] = report
            cohort_by_shard[shard] = csv_gz_rows(z, re.compile(r"cohort-shard-\d+\.csv\.gz$"))
            bios_by_shard[shard] = jsonl_gz_rows(z, re.compile(r"biographies-shard-\d+\.jsonl\.gz$"))
            candidates_by_shard[shard] = csv_gz_rows(z, re.compile(r"candidates-shard-\d+\.csv\.gz$"))
            rules_by_shard[shard] = csv_gz_rows(z, re.compile(r"rule-events-shard-\d+\.csv\.gz$"))

    found = set(reports)
    if found != expected_shards:
        raise ValueError(f"expected shards {expected_shards}, got {found}")

    errors: list[str] = []
    warnings: list[str] = []

    all_cohort = []
    all_bios = []
    all_candidates = []
    all_rules = []

    for shard in sorted(expected_shards):
        cohort = cohort_by_shard[shard]
        bios = bios_by_shard[shard]
        cand = candidates_by_shard[shard]
        rules = rules_by_shard[shard]
        rep = reports[shard]

        if int(rep.get("cohort_rows", -1)) != len(cohort):
            errors.append(f"shard {shard}: cohort report mismatch")
        if int(rep.get("biographies_fetched", -1)) != len(bios):
            errors.append(f"shard {shard}: biography report mismatch")
        if int(rep.get("candidate_rows", -1)) != len(cand):
            errors.append(f"shard {shard}: candidate report mismatch")
        if int(rep.get("rule_event_rows", -1)) != len(rules):
            errors.append(f"shard {shard}: rule-event report mismatch")

        for r in cohort:
            q = (r.get("wikidata_id") or "").strip()
            if not QID.match(q):
                errors.append(f"shard {shard}: invalid cohort QID {q!r}")
            elif int(q[1:]) % 4 != shard:
                errors.append(f"shard {shard}: QID assigned to wrong shard: {q}")

        all_cohort.extend((shard, r) for r in cohort)
        all_bios.extend((shard, r) for r in bios)
        all_candidates.extend((shard, r) for r in cand)
        all_rules.extend((shard, r) for r in rules)

    cohort_qids = [(s, (r.get("wikidata_id") or "").strip()) for s, r in all_cohort]
    qid_counts = Counter(q for _, q in cohort_qids)
    duplicate_cohort = sorted(q for q, n in qid_counts.items() if n != 1)
    if duplicate_cohort:
        errors.append(f"cohort duplicate/multiplicity QIDs: {len(duplicate_cohort)}")
    if len(cohort_qids) != 3398:
        errors.append(f"expected 3398 cohort rows, got {len(cohort_qids)}")

    cohort_set = set(qid_counts)
    bio_qids = [(s, str(r.get("person_id") or "").strip()) for s, r in all_bios]
    bad_bio_people = sorted(set(q for _, q in bio_qids) - cohort_set)
    if bad_bio_people:
        errors.append(f"biography records outside cohort: {len(bad_bio_people)}")
    bio_counts = Counter(q for _, q in bio_qids)
    duplicate_bios = sorted(q for q, n in bio_counts.items() if n > 1)
    if duplicate_bios:
        errors.append(f"duplicate biography QIDs: {len(duplicate_bios)}")

    missing_bio = sorted(cohort_set - set(bio_counts), key=lambda q: int(q[1:]))
    if missing_bio:
        warnings.append(f"{len(missing_bio)} cohort people have no fetched Wikipedia biography")

    revision_keys = [
        (str(r.get("site") or ""), str(r.get("pageid") or ""), str(r.get("revision_id") or ""))
        for _, r in all_bios
    ]
    duplicate_revisions = sum(n - 1 for n in Counter(revision_keys).values() if n > 1)
    if duplicate_revisions:
        warnings.append(f"{duplicate_revisions} duplicate biography revision tuples")

    candidate_ids = [str(r.get("candidate_id") or "") for _, r in all_candidates]
    candidate_counts = Counter(candidate_ids)
    duplicate_candidates = sorted(k for k, n in candidate_counts.items() if n > 1)
    if duplicate_candidates:
        errors.append(f"duplicate candidate IDs across shards: {len(duplicate_candidates)}")

    rule_ids = [str(r.get("event_id") or "") for _, r in all_rules]
    duplicate_rules = sorted(k for k, n in Counter(rule_ids).items() if n > 1)
    if duplicate_rules:
        errors.append(f"duplicate rule event IDs across shards: {len(duplicate_rules)}")

    candidate_set = set(candidate_ids)
    missing_candidate_refs = sorted(
        str(r.get("candidate_id") or "")
        for _, r in all_rules
        if str(r.get("candidate_id") or "") not in candidate_set
    )
    if missing_candidate_refs:
        errors.append(f"rule events with missing candidate reference: {len(missing_candidate_refs)}")

    outside_candidate_people = sorted(
        set(str(r.get("person_id") or "") for _, r in all_candidates) - cohort_set
    )
    outside_rule_people = sorted(
        set(str(r.get("person_id") or "") for _, r in all_rules) - cohort_set
    )
    if outside_candidate_people:
        errors.append(f"candidate people outside cohort: {len(outside_candidate_people)}")
    if outside_rule_people:
        errors.append(f"rule-event people outside cohort: {len(outside_rule_people)}")

    invalid_rule_dates = 0
    future_rule_dates = 0
    for _, r in all_rules:
        try:
            y0 = int(str(r.get("event_date_min") or "")[:4])
            y1 = int(str(r.get("event_date_max") or "")[:4])
            if not (1000 <= y0 <= y1 <= 2099):
                invalid_rule_dates += 1
            if y0 > 2026:
                future_rule_dates += 1
        except Exception:
            invalid_rule_dates += 1
    if invalid_rule_dates:
        errors.append(f"invalid rule-event date intervals: {invalid_rule_dates}")
    if future_rule_dates:
        warnings.append(f"{future_rule_dates} rule events begin after 2026 and must be snapshot-ineligible until appropriate")

    domain_counts = Counter(str(r.get("domain") or "") for _, r in all_rules)
    candidate_domain_hits = Counter()
    for _, r in all_candidates:
        for d in str(r.get("candidate_domains") or "").split("|"):
            if d:
                candidate_domain_hits[d] += 1

    missing_path = args.out / "missing-biography-qids.csv.gz"
    with gzip.open(missing_path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["wikidata_id"])
        w.writeheader()
        w.writerows({"wikidata_id": q} for q in missing_bio)

    summary = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "shards": {str(k): reports[k] for k in sorted(reports)},
        "totals": {
            "cohort_rows": len(all_cohort),
            "unique_cohort_people": len(cohort_set),
            "biographies_fetched": len(all_bios),
            "unique_biography_people": len(bio_counts),
            "missing_biography_people": len(missing_bio),
            "candidate_rows": len(all_candidates),
            "rule_event_rows": len(all_rules),
            "unique_rule_event_ids": len(set(rule_ids)),
        },
        "candidate_domain_hits": dict(sorted(candidate_domain_hits.items())),
        "rule_event_domains": dict(sorted(domain_counts.items())),
        "integrity": {
            "duplicate_cohort_qids": len(duplicate_cohort),
            "duplicate_biography_qids": len(duplicate_bios),
            "duplicate_candidate_ids": len(duplicate_candidates),
            "duplicate_rule_event_ids": len(duplicate_rules),
            "missing_rule_candidate_refs": len(missing_candidate_refs),
            "invalid_rule_dates": invalid_rule_dates,
            "future_rule_dates": future_rule_dates,
            "biography_records_outside_cohort": len(bad_bio_people),
            "candidate_people_outside_cohort": len(outside_candidate_people),
            "rule_people_outside_cohort": len(outside_rule_people),
        },
        "missing_biography_qids_file": missing_path.name,
    }

    out = args.out / "v11-biography-audit.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
