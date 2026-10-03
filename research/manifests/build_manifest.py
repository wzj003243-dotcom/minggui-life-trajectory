"""Create hashes and file metadata for reproducible dataset snapshots."""
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

def sha256(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def count_lines(path: Path):
    with path.open("rb") as f: return sum(1 for _ in f)

def main():
    if len(sys.argv)<2: raise SystemExit("usage: build_manifest.py file1 [file2 ...]")
    files=[]
    for raw in sys.argv[1:]:
        p=Path(raw)
        files.append({"path":str(p),"bytes":p.stat().st_size,"rows_or_lines":count_lines(p),"sha256":sha256(p)})
    print(json.dumps({
      "created_at":datetime.now(timezone.utc).isoformat(),
      "files":files
    },indent=2))
if __name__=="__main__": main()
