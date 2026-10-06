"""Prepare small, hash-addressed v1.1 biography import payloads.

This runs only after the four raw shard artifacts pass union audit. The source artifacts
remain the evidence of record. These payloads are deterministic transport chunks for the
database importer; every byte-level SHA-256 is written to import-manifest.json so the
server can reject any payload not explicitly authorized.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

SHARDS = range(4)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_name(z: zipfile.ZipFile, pat: re.Pattern[str]) -> str:
    names = [n for n in z.namelist() if pat.search(n)]
    if len(names) != 1:
        raise ValueError(f"{z.filename}: expected one {pat.pattern}, got {names}")
    return names[0]


def read_csv_gz(z: zipfile.ZipFile, pat: re.Pattern[str]) -> list[dict[str, str]]:
    raw = z.read(find_name(z, pat))
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as g:
        return list(csv.DictReader(io.TextIOWrapper(g, encoding="utf-8", newline="")))


def read_jsonl_gz(z: zipfile.ZipFile, pat: re.Pattern[str]) -> list[dict]:
    raw = z.read(find_name(z, pat))
    out: list[dict] = []
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as g:
        for line in io.TextIOWrapper(g, encoding="utf-8"):
            if line.strip():
                out.append(json.loads(line))
    return out


def chunks(rows: list[dict], n: int):
    for i in range(0, len(rows), n):
        yield rows[i : i + n]


def canonical_json_bytes(obj: object) -> bytes:
    return (
        json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    )


def write_payload(out: Path, name: str, payload: dict, manifest_rows: list[dict]) -> None:
    data = canonical_json_bytes(payload)
    path = out / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    manifest_rows.append(
        {
            "chunk_name": name.replace("\\", "/"),
            "phase": payload["phase"],
            "shard": int(payload["shard"]),
            "row_count": int(len(payload.get("rows") or payload.get("biographies") or [])),
            "sha256": sha256_bytes(data),
            "size_bytes": len(data),
        }
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-metadata", type=Path, required=True)
    ap.add_argument("--source-run-id", required=True)
    ap.add_argument("--source-git-sha", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("artifacts", nargs="+", type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    metadata = json.loads(args.artifact_metadata.read_text(encoding="utf-8"))
    artifact_rows = metadata.get("artifacts") or []
    by_name = {str(x["name"]): x for x in artifact_rows}

    zips: dict[int, Path] = {}
    for path in args.artifacts:
        m = re.search(r"shard-(\d+)\.zip$", path.name)
        if not m:
            raise ValueError(f"cannot identify shard from {path}")
        zips[int(m.group(1))] = path
    if set(zips) != set(SHARDS):
        raise ValueError(f"expected four shard zips, got {sorted(zips)}")

    manifest: dict = {
        "version": "v11-biography-import-chunks-v1",
        "source_workflow_run_id": str(args.source_run_id),
        "source_git_sha": str(args.source_git_sha),
        "target_snapshot_id": "7fce3b79-ebfc-40b2-a5f0-e91b28db6a02",
        "importer_key": "v11-biography-shard-v1",
        "shards": {},
    }

    for shard in SHARDS:
        artifact_name = f"minggui-v11-biography-shard-{shard}"
        meta = by_name.get(artifact_name)
        if not meta:
            raise ValueError(f"GitHub artifact metadata missing {artifact_name}")
        digest = str(meta.get("digest") or "")
        if not digest.startswith("sha256:"):
            raise ValueError(f"{artifact_name}: missing sha256 digest")
        source_sha = digest.split(":", 1)[1]
        source_id = str(meta["id"])

        with zipfile.ZipFile(zips[shard]) as z:
            bios = read_jsonl_gz(z, re.compile(r"biographies-shard-\d+\.jsonl\.gz$"))
            candidates = read_csv_gz(z, re.compile(r"candidates-shard-\d+\.csv\.gz$"))
            rules = read_csv_gz(z, re.compile(r"rule-events-shard-\d+\.csv\.gz$"))

        # Keep raw wikitext only in the immutable source ZIP. The DB import needs
        # revision metadata, not a second copy of full article text.
        biography_meta = [
            {
                "person_id": r.get("person_id"),
                "site": r.get("site"),
                "language": r.get("language"),
                "title": r.get("title"),
                "pageid": r.get("pageid"),
                "revision_id": r.get("revision_id"),
                "revision_parent_id": r.get("revision_parent_id"),
                "revision_timestamp": r.get("revision_timestamp"),
                "revision_sha1": r.get("revision_sha1"),
                "content_chars": r.get("content_chars"),
                "license": r.get("license"),
                "source_url": r.get("source_url"),
            }
            for r in bios
        ]

        candidate_by_id = {str(r.get("candidate_id") or ""): r for r in candidates}
        enriched_rules = []
        for r in rules:
            c = candidate_by_id.get(str(r.get("candidate_id") or "")) or {}
            enriched_rules.append(
                {
                    **r,
                    "site": c.get("site"),
                    "pageid": c.get("pageid"),
                    "revision_timestamp": c.get("revision_timestamp"),
                    "license": c.get("license"),
                }
            )

        base = {
            "source_artifact_id": source_id,
            "source_artifact_sha256": source_sha,
            "source_workflow_run_id": str(args.source_run_id),
            "source_git_sha": str(args.source_git_sha),
            "target_snapshot_id": "7fce3b79-ebfc-40b2-a5f0-e91b28db6a02",
        }
        rows: list[dict] = []
        shard_dir = Path(f"shard-{shard}")

        write_payload(
            args.out,
            str(shard_dir / "prepare.json"),
            {
                **base,
                "phase": "prepare",
                "shard": shard,
                "biographies": biography_meta,
            },
            rows,
        )

        for i, batch in enumerate(chunks(candidates, 400)):
            write_payload(
                args.out,
                str(shard_dir / f"candidates-{i:04d}.json"),
                {**base, "phase": "candidates", "shard": shard, "rows": batch},
                rows,
            )

        for i, batch in enumerate(chunks(enriched_rules, 250)):
            write_payload(
                args.out,
                str(shard_dir / f"events-{i:04d}.json"),
                {**base, "phase": "events", "shard": shard, "rows": batch},
                rows,
            )

        write_payload(
            args.out,
            str(shard_dir / "finalize.json"),
            {**base, "phase": "finalize", "shard": shard, "rows": []},
            rows,
        )

        manifest["shards"][str(shard)] = {
            "artifact_name": artifact_name,
            "provider_artifact_id": source_id,
            "source_artifact_sha256": source_sha,
            "source_artifact_size_bytes": int(meta.get("size_in_bytes") or 0),
            "biographies": len(bios),
            "candidates": len(candidates),
            "rule_events": len(rules),
            "chunks": rows,
        }

    manifest_bytes = canonical_json_bytes(manifest)
    (args.out / "import-manifest.json").write_bytes(manifest_bytes)
    manifest_sha = sha256_bytes(manifest_bytes)
    (args.out / "import-manifest.sha256").write_text(
        manifest_sha + "  import-manifest.json\n",
        encoding="utf-8",
    )

    sql_lines = [
        "-- Generated from audited v1.1 biography artifacts.",
        "-- Apply only after v11-biography-audit.json reports status=pass.",
        "begin;",
    ]
    for shard, info in sorted(manifest["shards"].items(), key=lambda kv: int(kv[0])):
        chunk_map = {x["chunk_name"]: x["sha256"] for x in info["chunks"]}
        metadata_obj = {
            "shard": int(shard),
            "source_workflow_run_id": str(args.source_run_id),
            "source_git_sha": str(args.source_git_sha),
            "source_artifact_size_bytes": int(info["source_artifact_size_bytes"]),
            "import_manifest_sha256": manifest_sha,
            "import_chunks": chunk_map,
        }
        metadata_json = (
            json.dumps(metadata_obj, ensure_ascii=False, sort_keys=True)
            .replace("'", "''")
        )
        artifact_id = str(info["provider_artifact_id"]).replace("'", "''")
        source_sha = str(info["source_artifact_sha256"]).replace("'", "''")
        sql_lines.append(
            "insert into research.artifact_import_authorizations("
            "importer_key,provider,provider_artifact_id,sha256,target_snapshot_id,status,metadata"
            ") values("
            "'v11-biography-shard-v1','github-actions','" + artifact_id + "','" + source_sha + "',"
            "'7fce3b79-ebfc-40b2-a5f0-e91b28db6a02'::uuid,'approved','" + metadata_json + "'::jsonb"
            ") on conflict(importer_key,provider,provider_artifact_id) do update set "
            "sha256=excluded.sha256,target_snapshot_id=excluded.target_snapshot_id,"
            "status=case when research.artifact_import_authorizations.status='imported' then 'imported' else 'approved' end,"
            "metadata=research.artifact_import_authorizations.metadata||excluded.metadata;"
        )
    sql_lines += ["commit;", ""]
    (args.out / "artifact-authorizations.sql").write_text(
        "\n".join(sql_lines), encoding="utf-8"
    )

    summary = {
        "manifest_sha256": manifest_sha,
        "shards": {
            k: {
                "artifact_id": v["provider_artifact_id"],
                "source_sha256": v["source_artifact_sha256"],
                "biographies": v["biographies"],
                "candidates": v["candidates"],
                "rule_events": v["rule_events"],
                "chunk_count": len(v["chunks"]),
                "max_chunk_bytes": max(x["size_bytes"] for x in v["chunks"]),
            }
            for k, v in manifest["shards"].items()
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
