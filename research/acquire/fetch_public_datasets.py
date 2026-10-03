"""Acquire public research datasets into data/raw without committing raw data.

Designed for CI or a research workstation with internet access.
- Pantheon 1.0: uses a public GitHub mirror, but validates against the MD5 published for the
  Harvard Dataverse pantheon.tsv (c5ba6e1e5e5352f5469801f883e1559a).
- Astro-Databank: downloads Astrodienst's official free sample JSON and c_sample.zip.
- BHHT: attempts the official Sciences Po Dataverse API only. If anti-bot protection blocks
  machine access, records the failure and does not fall back to an unverified mirror.
"""
from __future__ import annotations
import hashlib, json, os, sys, urllib.parse, urllib.request, zipfile
from pathlib import Path

ROOT=Path(os.environ.get("MINGGUI_DATA_DIR","data/raw/acquired"))
ROOT.mkdir(parents=True,exist_ok=True)
REPORT={"sources":{}}

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def md5(path):
    h=hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def download(url,path,timeout=180):
    req=urllib.request.Request(url,headers={"User-Agent":"MingGuiLifeTrajectory/0.1 research data acquisition"})
    with urllib.request.urlopen(req,timeout=timeout) as r, path.open("wb") as w:
        while True:
            chunk=r.read(1024*1024)
            if not chunk: break
            w.write(chunk)
    return {"bytes":path.stat().st_size,"sha256":sha256(path)}

def get_json(url,timeout=120):
    req=urllib.request.Request(url,headers={"User-Agent":"MingGuiLifeTrajectory/0.1 research data acquisition","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read()
        ct=r.headers.get("content-type","")
    if b"<html" in raw[:500].lower() or "json" not in ct.lower():
        raise RuntimeError(f"expected JSON, received content-type={ct!r}, prefix={raw[:120]!r}")
    return json.loads(raw)

def pantheon():
    out=ROOT/"pantheon.tsv"
    url="https://raw.githubusercontent.com/EdisonFu/history-graph-notes-data/main/pantheon.tsv"
    meta=download(url,out)
    expected="c5ba6e1e5e5352f5469801f883e1559a"
    actual=md5(out)
    if actual != expected:
        out.unlink(missing_ok=True)
        raise RuntimeError(f"Pantheon checksum mismatch: {actual} != {expected}")
    meta.update({"status":"ok","url":url,"md5":actual,"verified_against":"Harvard Dataverse published MD5"})
    return meta

def astro():
    rows={}
    for name in ("adb_export_sample.json","c_sample.zip"):
        url=f"https://www.astro.com/adbexport/{name}"
        path=ROOT/name
        rows[name]={"status":"ok","url":url,**download(url,path)}
    z=ROOT/"c_sample.zip"
    try:
        with zipfile.ZipFile(z) as archive:
            rows["c_sample.zip"]["entries"]=archive.namelist()
            rows["c_sample.zip"]["zip_test"]=archive.testzip()
    except zipfile.BadZipFile as e:
        rows["c_sample.zip"]["zip_error"]=str(e)
        raise
    return rows

def bhht():
    pid="doi:10.21410/7E4/RDAG3O"
    meta_url="https://data.sciencespo.fr/api/datasets/:persistentId/?"+urllib.parse.urlencode({"persistentId":pid})
    meta=get_json(meta_url)
    files=meta.get("data",{}).get("latestVersion",{}).get("files",[])
    candidates=[]
    for item in files:
        df=item.get("dataFile",{})
        label=item.get("label") or df.get("filename") or ""
        if "cross" in label.lower() and label.lower().endswith((".csv",".dta",".tab")):
            candidates.append((label,df.get("id")))
    if not candidates:
        return {"status":"metadata-ok-no-cross-verified-file-found","metadata_url":meta_url,"files_seen":[(x.get("label") or x.get("dataFile",{}).get("filename")) for x in files[:50]]}
    got=[]
    for label,file_id in candidates:
        if not file_id: continue
        url=f"https://data.sciencespo.fr/api/access/datafile/{file_id}"
        path=ROOT/label
        got.append({"label":label,"file_id":file_id,"url":url,**download(url,path)})
    return {"status":"ok","metadata_url":meta_url,"downloaded":got}

def run(name,fn):
    try:
        REPORT["sources"][name]=fn()
    except Exception as e:
        REPORT["sources"][name]={"status":"blocked-or-failed","error":repr(e)}

for name,fn in [("pantheon",pantheon),("astro_databank_free",astro),("bhht_cross_verified",bhht)]:
    run(name,fn)

report_path=ROOT/"acquisition_report.json"
report_path.write_text(json.dumps(REPORT,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(REPORT,indent=2,ensure_ascii=False))

# Pantheon and the official Astro sample are expected to work. BHHT may be anti-bot blocked.
required=("pantheon","astro_databank_free")
bad=[x for x in required if REPORT["sources"][x].get("status")!="ok"]
raise SystemExit(1 if bad else 0)
