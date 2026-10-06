"""Audit v1.1 Wikipedia biography shard artifacts before database import.

This audit is artifact-first and read-only. It validates:
- deterministic cohort partition coverage,
- recovery-aware fetch accounting,
- revision-pinned biography integrity,
- candidate/event provenance links,
- cross-shard uniqueness,
- conservative date sanity.

Missing Wikipedia coverage is retained as an explicit warning, not converted into
synthetic data.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

QID = re.compile(r"^Q\d+$")


def find_exact(z: zipfile.ZipFile, pattern: re.Pattern[str]) -> str:
    names = [n for n in z.namelist() if pattern.search(n)]
    if len(names) != 1:
        raise ValueError(f"{z.filename}: expected one {pattern.pattern}, got {names}")
    return names[0]


def read_json(z: zipfile.ZipFile, pattern: re.Pattern[str]) -> dict:
    return json.loads(z.read(find_exact(z, pattern)))


def read_csv_gz(z: zipfile.ZipFile, pattern: re.Pattern[str]) -> list[dict[str, str]]:
    raw = z.read(find_exact(z, pattern))
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as g:
        return list(csv.DictReader(io.TextIOWrapper(g, encoding="utf-8", newline="")))


def read_jsonl_gz(z: zipfile.ZipFile, pattern: re.Pattern[str]) -> list[dict]:
    raw = z.read(find_exact(z, pattern))
    rows: list[dict] = []
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as g:
        for lineno, line in enumerate(io.TextIOWrapper(g, encoding="utf-8"), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                raise ValueError(
                    f"{z.filename}: invalid biography JSONL line {lineno}: {exc}"
                ) from exc
    return rows


def optional_fetch_report(z: zipfile.ZipFile, shard: int) -> dict:
    pat = re.compile(
        rf"(^|/)(?:new-)?biographies-shard-{shard}\.report\.json$"
    )
    names = [n for n in z.namelist() if pat.search(n)]
    if len(names) > 1:
        raise ValueError(f"{z.filename}: multiple fetch reports: {names}")
    return json.loads(z.read(names[0])) if names else {}


def intv(value, default: int = 0) -> int:
    if value in (None, ""):
        return default
    return int(value)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("artifacts", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expected-shards", type=int, default=4)
    args = ap.parse_args()

    if args.expected_shards not in (4, 8):
        raise SystemExit("--expected-shards must be 4 or 8")
    if len(args.artifacts) != args.expected_shards:
        raise SystemExit(
            f"expected {args.expected_shards} artifacts, got {len(args.artifacts)}"
        )

    args.out.mkdir(parents=True, exist_ok=True)
    expected = set(range(args.expected_shards))

    reports: dict[int, dict] = {}
    fetch_reports: dict[int, dict] = {}
    cohorts: dict[int, list[dict[str, str]]] = {}
    bios: dict[int, list[dict]] = {}
    candidates: dict[int, list[dict[str, str]]] = {}
    rules: dict[int, list[dict[str, str]]] = {}

    for artifact in args.artifacts:
        with zipfile.ZipFile(artifact) as z:
            report = read_json(z, re.compile(r"(^|/)shard-\d+\.report\.json$"))
            shard = int(report["shard"])
            if shard in reports:
                raise ValueError(f"duplicate shard artifact {shard}")
            reports[shard] = report
            fetch_reports[shard] = optional_fetch_report(z, shard)
            cohorts[shard] = read_csv_gz(
                z, re.compile(rf"(^|/)cohort-shard-{shard}\.csv\.gz$")
            )
            bios[shard] = read_jsonl_gz(
                z, re.compile(rf"(^|/)biographies-shard-{shard}\.jsonl\.gz$")
            )
            candidates[shard] = read_csv_gz(
                z, re.compile(rf"(^|/)candidates-shard-{shard}\.csv\.gz$")
            )
            rules[shard] = read_csv_gz(
                z, re.compile(rf"(^|/)rule-events-shard-{shard}\.csv\.gz$")
            )

    if set(reports) != expected:
        raise ValueError(f"expected shards {sorted(expected)}, got {sorted(reports)}")

    errors: list[str] = []
    warnings: list[str] = []

    all_cohort: list[tuple[int, dict[str, str]]] = []
    all_bios: list[tuple[int, dict]] = []
    all_candidates: list[tuple[int, dict[str, str]]] = []
    all_rules: list[tuple[int, dict[str, str]]] = []

    for shard in sorted(expected):
        cohort = cohorts[shard]
        biography = bios[shard]
        cand = candidates[shard]
        rule = rules[shard]
        rep = reports[shard]
        fetch = fetch_reports.get(shard) or {}

        # Final artifact self-report.
        expected_counts = {
            "cohort_rows": len(cohort),
            "biographies_fetched": len(biography),
            "candidate_rows": len(cand),
            "rule_event_rows": len(rule),
        }
        for key, actual in expected_counts.items():
            if intv(rep.get(key), -1) != actual:
                errors.append(
                    f"shard {shard}: {key} report mismatch "
                    f"({rep.get(key)!r} != {actual})"
                )

        recovered = intv(rep.get("recovered_complete_biographies"), 0)
        new_fetched = intv(
            rep.get("new_biographies_fetched"),
            len(biography) - recovered,
        )
        if recovered < 0 or new_fetched < 0:
            errors.append(f"shard {shard}: negative recovery/fetch counts")
        if recovered + new_fetched != len(biography):
            errors.append(
                f"shard {shard}: final biography accounting mismatch "
                f"({recovered}+{new_fetched}!={len(biography)})"
            )

        # Fetch report describes only the network fetch performed in this run.
        if fetch:
            requested = intv(fetch.get("requested_people"), -1)
            resolved = intv(fetch.get("resolved_sitelinks"), -1)
            fetched = intv(fetch.get("biographies_fetched"), -1)
            failed = intv(fetch.get("failed_fetch_qids"), 0)
            expected_requested = len(cohort) - recovered

            if requested != expected_requested:
                errors.append(
                    f"shard {shard}: fetch requested_people mismatch "
                    f"({requested} != {expected_requested})"
                )
            if fetched != new_fetched:
                errors.append(
                    f"shard {shard}: network fetch count mismatch "
                    f"({fetched} != {new_fetched})"
                )
            if failed:
                errors.append(
                    f"shard {shard}: {failed} biography fetch requests failed"
                )
            if resolved < 0:
                errors.append(f"shard {shard}: invalid resolved_sitelinks={resolved}")
            elif resolved != fetched:
                errors.append(
                    f"shard {shard}: resolved sitelinks were not fully materialized "
                    f"({resolved} resolved, {fetched} fetched)"
                )
        else:
            # Mirrored/repacked artifacts should still carry their original fetch report.
            errors.append(f"shard {shard}: missing biography fetch report")

        # Deterministic partition and per-shard QID uniqueness.
        cohort_qids = []
        for row in cohort:
            q = (row.get("wikidata_id") or "").strip()
            cohort_qids.append(q)
            if not QID.match(q):
                errors.append(f"shard {shard}: invalid cohort QID {q!r}")
            elif int(q[1:]) % args.expected_shards != shard:
                errors.append(f"shard {shard}: QID assigned to wrong shard: {q}")
        if len(cohort_qids) != len(set(cohort_qids)):
            errors.append(f"shard {shard}: duplicate cohort QIDs")

        bio_qids = [str(r.get("person_id") or "").strip() for r in biography]
        if len(bio_qids) != len(set(bio_qids)):
            errors.append(f"shard {shard}: duplicate biography QIDs")
        outside = sorted(set(bio_qids) - set(cohort_qids))
        if outside:
            errors.append(
                f"shard {shard}: {len(outside)} biographies outside shard cohort"
            )

        # Every biography must be revision pinned.
        missing_revision = [
            q
            for q, row in zip(bio_qids, biography)
            if not str(row.get("revision_id") or "").strip()
            or not str(row.get("site") or "").strip()
            or not str(row.get("pageid") or "").strip()
        ]
        if missing_revision:
            errors.append(
                f"shard {shard}: {len(missing_revision)} biographies lack revision/site/pageid"
            )

        # Candidate provenance must point to a biography revision in this artifact.
        bio_revision_keys = {
            (
                str(row.get("person_id") or "").strip(),
                str(row.get("site") or "").strip(),
                str(row.get("revision_id") or "").strip(),
            )
            for row in biography
        }
        orphan_candidates = []
        for row in cand:
            key = (
                str(row.get("person_id") or "").strip(),
                str(row.get("site") or "").strip(),
                str(row.get("revision_id") or "").strip(),
            )
            if key not in bio_revision_keys:
                orphan_candidates.append(str(row.get("candidate_id") or ""))
        if orphan_candidates:
            errors.append(
                f"shard {shard}: {len(orphan_candidates)} candidates reference absent revisions"
            )

        all_cohort.extend((shard, row) for row in cohort)
        all_bios.extend((shard, row) for row in biography)
        all_candidates.extend((shard, row) for row in cand)
        all_rules.extend((shard, row) for row in rule)

    # Cross-shard cohort integrity.
    cohort_qids = [(s, (r.get("wikidata_id") or "").strip()) for s, r in all_cohort]
    cohort_counts = Counter(q for _, q in cohort_qids)
    bad_cohort_multiplicity = sorted(q for q, n in cohort_counts.items() if n != 1)
    if len(cohort_qids) != 3398:
        errors.append(f"expected 3398 cohort rows, got {len(cohort_qids)}")
    if bad_cohort_multiplicity:
        errors.append(
            f"cohort duplicate/multiplicity QIDs: {len(bad_cohort_multiplicity)}"
        )
    cohort_set = set(cohort_counts)

    # Biography integrity across shards.
    bio_qids = [(s, str(r.get("person_id") or "").strip()) for s, r in all_bios]
    bio_counts = Counter(q for _, q in bio_qids)
    duplicate_bios = sorted(q for q, n in bio_counts.items() if n > 1)
    bad_bio_people = sorted(set(bio_counts) - cohort_set)
    if duplicate_bios:
        errors.append(f"duplicate biography QIDs across shards: {len(duplicate_bios)}")
    if bad_bio_people:
        errors.append(f"biography records outside cohort: {len(bad_bio_people)}")

    missing_bio = sorted(cohort_set - set(bio_counts), key=lambda q: int(q[1:]))
    if missing_bio:
        warnings.append(
            f"{len(missing_bio)} cohort people have no enwiki/zhwiki revision-pinned biography"
        )

    # Candidate/event uniqueness and provenance.
    candidate_ids = [str(r.get("candidate_id") or "") for _, r in all_candidates]
    duplicate_candidates = sorted(
        k for k, n in Counter(candidate_ids).items() if not k or n > 1
    )
    if duplicate_candidates:
        errors.append(
            f"blank/duplicate candidate IDs across shards: {len(duplicate_candidates)}"
        )
    candidate_set = set(candidate_ids)

    rule_ids = [str(r.get("event_id") or "") for _, r in all_rules]
    duplicate_rules = sorted(
        k for k, n in Counter(rule_ids).items() if not k or n > 1
    )
    if duplicate_rules:
        errors.append(
            f"blank/duplicate rule event IDs across shards: {len(duplicate_rules)}"
        )

    missing_candidate_refs = [
        str(r.get("candidate_id") or "")
        for _, r in all_rules
        if str(r.get("candidate_id") or "") not in candidate_set
    ]
    if missing_candidate_refs:
        errors.append(
            f"rule events with missing candidate reference: {len(missing_candidate_refs)}"
        )

    outside_candidate_people = sorted(
        set(str(r.get("person_id") or "") for _, r in all_candidates) - cohort_set
    )
    outside_rule_people = sorted(
        set(str(r.get("person_id") or "") for _, r in all_rules) - cohort_set
    )
    if outside_candidate_people:
        errors.append(
            f"candidate people outside cohort: {len(outside_candidate_people)}"
        )
    if outside_rule_people:
        errors.append(f"rule-event people outside cohort: {len(outside_rule_people)}")

    invalid_rule_dates = 0
    future_rule_dates = 0
    for _, row in all_rules:
        try:
            y0 = int(str(row.get("event_date_min") or "")[:4])
            y1 = int(str(row.get("event_date_max") or "")[:4])
            if not (1000 <= y0 <= y1 <= 2099):
                invalid_rule_dates += 1
            if y0 > 2026:
                future_rule_dates += 1
        except Exception:
            invalid_rule_dates += 1
    if invalid_rule_dates:
        errors.append(f"invalid rule-event date intervals: {invalid_rule_dates}")
    if future_rule_dates:
        warnings.append(
            f"{future_rule_dates} rule events begin after 2026; importer must retain them "
            "but mark them snapshot-model-ineligible"
        )

    domain_counts = Counter(str(r.get("domain") or "") for _, r in all_rules)
    candidate_domain_hits = Counter()
    for _, row in all_candidates:
        for domain in str(row.get("candidate_domains") or "").split("|"):
            if domain:
                candidate_domain_hits[domain] += 1

    missing_path = args.out / "missing-biography-qids.csv.gz"
    with gzip.open(missing_path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["wikidata_id"])
        writer.writeheader()
        writer.writerows({"wikidata_id": q} for q in missing_bio)

    summary = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "expected_shards": args.expected_shards,
        "shards": {str(k): reports[k] for k in sorted(reports)},
        "fetch_reports": {str(k): fetch_reports.get(k, {}) for k in sorted(reports)},
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
            "bad_cohort_multiplicity": len(bad_cohort_multiplicity),
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
