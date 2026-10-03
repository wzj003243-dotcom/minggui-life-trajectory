"""Acquire only the official Astro-Databank free C sample and normalize public birth fields."""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.normalize.public_cohorts import normalize_astro

URL="https://www.astro.com/adbexport/c_sample.zip"
EXPECTED_SHA256="da4a0638434dad80f1ff028e3ac898c4a9e3d2f7bb4a665d2086d5c3770844e1"

def sha256(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):
            h.update(c)
    return h.hexdigest()

def main():
    raw=Path("data/raw/timed")
    out=Path("data/processed/timed")
    raw.mkdir(parents=True,exist_ok=True)
    out.mkdir(parents=True,exist_ok=True)
    z=raw/"c_sample.zip"
    req=urllib.request.Request(URL,headers={"User-Agent":"MingGuiLifeTrajectory/0.1 public research"})
    with urllib.request.urlopen(req,timeout=180) as r,z.open("wb") as w:
        while True:
            chunk=r.read(1024*1024)
            if not chunk:
                break
            w.write(chunk)
    digest=sha256(z)
    if digest!=EXPECTED_SHA256:
        raise SystemExit(f"Astro sample checksum mismatch {digest}")
    profile=normalize_astro(z,out/"astro_public_births.csv.gz")
    print({"sha256":digest,**profile})

if __name__=="__main__":
    main()
