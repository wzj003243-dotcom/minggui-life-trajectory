"""Acquire public research datasets into data/raw without committing raw data.

Designed for CI or a research workstation with internet access.
- Pantheon 1.0: resolves and downloads pantheon.tsv through the official Harvard Dataverse API,
  then validates the published MD5 (c5ba6e1e5e5352f5469801f883e1559a).
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

def dataverse_file(host: str, persistent_id: str, matcher):
    meta_url=f"{host}/api/datasets/:persistentId/?"+urllib.parse.urlencode({"persistentId":persistent_id})
    meta=get_json(meta_url)
    files=meta.get("data",{}).get("latestVersion",{}).get("files",[])
    matches=[]
    for item in files:
        df=item.get("dataFile",{})
        label=item.get("label") or df.get("filename") or ""
        if matcher(label):
            matches.append((label,df.get("id"),df))
    if not matches:
        raise RuntimeError(f"no matching Dataverse file; files={[item.get('label') or item.get('dataFile',{}).get('filename') for item in files]}")
    return meta_url,matches

def pantheon():
    expected="c5ba6e1e5e5352f5469801f883e1559a"
    meta_url,matches=dataverse_file(
        "https://dataverse.harvard.edu","doi:10.7910/DVN/28201",
        lambda label: label.lower()=="pantheon.tsv"
    )
    label,file_id,df=matches[0]
    url=f"https://dataverse.harvard.edu/api/access/datafile/{file_id}"
    out=ROOT/"pantheon.tsv"
    meta=download(url,out)
    actual=md5(out)
    if actual != expected:
        out.unlink(missing_ok=True)
        raise RuntimeError(f"Pantheon checksum mismatch: {actual} != {expected}")
    meta.update({"status":"ok","url":url,"metadata_url":meta_url,"dataverse_file_id":file_id,"md5":actual,"verified_against":"Harvard Dataverse published MD5"})
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
    return {"status":"ok","files":rows}

def bhht():
    meta_url,candidates=dataverse_file(
        "https://data.sciencespo.fr","doi:10.21410/7E4/RDAG3O",
        lambda label: "cross-verified" in label.lower() and label.lower().endswith((".csv",".csv.gz",".dta",".tab",".tab.gz"))
    )
    got=[]
    for label,file_id,df in candidates:
        if not file_id: continue
        url=f"https://data.sciencespo.fr/api/access/datafile/{file_id}"
        path=ROOT/label
        got.append({"label":label,"file_id":file_id,"url":url,**download(url,path)})
    if not got:
        raise RuntimeError("BHHT metadata resolved but no downloadable matching file had an id")
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
required=("pantheon","astro_databank_free","bhht_cross_verified")
bad=[x for x in required if REPORT["sources"][x].get("status")!="ok"]
raise SystemExit(1 if bad else 0)
