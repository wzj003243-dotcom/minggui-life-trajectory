"""Verify cached public source files against the pinned MingGui source snapshot."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path

EXPECTED={
  "pantheon.tsv":{"md5":"c5ba6e1e5e5352f5469801f883e1559a","sha256":"b5c7eb6830e66e796fe91b30a543041e24de7aeb794337dcd03eac786116284a"},
  "cross-verified-database.csv.gz":{"sha256":"fe44aa6f97cf9f6c12d040137f92a9f4d0fd1f50e28f7f5d80eeae29b487828d"},
  "c_sample.zip":{"sha256":"da4a0638434dad80f1ff028e3ac898c4a9e3d2f7bb4a665d2086d5c3770844e1"},
  "adb_export_sample.json":{"sha256":"1b98b664c44e006ea81dcbd6497a2e268bd94a7100428a7ec83e7dd4ed864354"}
}
def digest(path,alg):
    h=hashlib.new(alg)
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else "data/raw/acquired")
    report={};ok=True
    for name,checks in EXPECTED.items():
        p=root/name
        if not p.exists():
            report[name]={"status":"missing"};ok=False;continue
        row={"status":"ok","bytes":p.stat().st_size}
        for alg,expected in checks.items():
            actual=digest(p,alg);row[alg]=actual
            if actual!=expected:
                row["status"]="checksum_mismatch";row[f"expected_{alg}"]=expected;ok=False
        report[name]=row
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if ok else 1)
if __name__=="__main__":main()
