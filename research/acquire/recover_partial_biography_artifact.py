"""Recover complete JSONL records from an interrupted biography artifact.

GitHub cancellation can truncate the inner gzip footer even though the outer artifact ZIP
is valid. This tool deliberately recovers only complete JSON objects emitted before the
interruption, then creates a remaining cohort excluding those QIDs.

It never fabricates or repairs a partial JSON line.
"""
from __future__ import annotations
import argparse,csv,gzip,io,json,zlib,zipfile
from pathlib import Path


def recover_gzip_prefix(raw: bytes) -> bytes:
    d=zlib.decompressobj(16+zlib.MAX_WBITS)
    return d.decompress(raw)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("artifact_zip",type=Path)
    ap.add_argument("shard",type=int)
    ap.add_argument("out_dir",type=Path)
    args=ap.parse_args()
    out=args.out_dir;out.mkdir(parents=True,exist_ok=True)

    with zipfile.ZipFile(args.artifact_zip) as z:
        bio_name=next(n for n in z.namelist() if n.endswith(f"biographies-shard-{args.shard}.jsonl.gz"))
        cohort_name=next(n for n in z.namelist() if n.endswith(f"cohort-shard-{args.shard}.csv.gz"))
        raw_bio=z.read(bio_name)
        cohort_raw=z.read(cohort_name)

    text=recover_gzip_prefix(raw_bio).decode("utf-8","strict")
    records=[];bad_lines=[]
    for i,line in enumerate(text.splitlines(),1):
        if not line.strip():continue
        try: records.append(json.loads(line))
        except Exception: bad_lines.append(i)
    if bad_lines:
        raise SystemExit(f"refusing recovery: incomplete/invalid JSON lines {bad_lines[:10]}")

    seen=[str(r.get("person_id") or "").strip() for r in records]
    if len(seen)!=len(set(seen)):
        raise SystemExit("duplicate recovered QIDs")
    seen_set=set(seen)

    with gzip.GzipFile(fileobj=io.BytesIO(cohort_raw),mode="rb") as g:
        rows=list(csv.DictReader(io.TextIOWrapper(g,encoding="utf-8",newline="")))
    fields=list(rows[0].keys()) if rows else []
    remaining=[r for r in rows if str(r.get("wikidata_id") or "").strip() not in seen_set]

    recovered_path=out/f"recovered-biographies-shard-{args.shard}.jsonl.gz"
    with gzip.open(recovered_path,"wt",encoding="utf-8") as w:
        for r in records:w.write(json.dumps(r,ensure_ascii=False)+"\n")

    cohort_path=out/f"cohort-shard-{args.shard}.csv.gz"
    with gzip.open(cohort_path,"wt",encoding="utf-8",newline="") as w:
        cw=csv.DictWriter(w,fieldnames=fields);cw.writeheader();cw.writerows(rows)

    remaining_path=out/f"remaining-cohort-shard-{args.shard}.csv.gz"
    with gzip.open(remaining_path,"wt",encoding="utf-8",newline="") as w:
        cw=csv.DictWriter(w,fieldnames=fields);cw.writeheader();cw.writerows(remaining)

    report={
      "shard":args.shard,
      "cohort_rows":len(rows),
      "recovered_complete_biographies":len(records),
      "remaining_cohort_rows":len(remaining),
      "recovered_unique_qids":len(seen_set),
      "invalid_partial_json_lines":len(bad_lines),
      "policy":"recover complete gzip stream prefix only; never repair partial JSON"
    }
    (out/f"recovery-shard-{args.shard}.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
