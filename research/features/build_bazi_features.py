"""Build versioned objective BaZi features from canonical birth data.

Two modes:
  date   - year/month/day only. Uses noon as the representative civil time, never creates an
           hour pillar, and flags dates whose year/month pillar changes within the day.
  timed  - uses the reported local birth clock time and includes the hour pillar.

This script intentionally excludes subjective conclusions such as 用神、格局高低、富贵/吉凶.
Those belong in a separate, versioned traditional-rule layer.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math,re
from collections import Counter
from pathlib import Path

from lunar_python import Solar
from lunar_python.util import LunarUtil

VERSION="bazi-objective-v0.1"
ELEMENTS=("木","火","土","金","水")
GANS=tuple("甲乙丙丁戊己庚辛壬癸")
ZHIS=tuple("子丑寅卯辰巳午未申酉戌亥")
TEN_GODS=("比肩","劫财","食神","伤官","偏财","正财","七杀","正官","偏印","正印")

LIUHE={frozenset(x) for x in [("子","丑"),("寅","亥"),("卯","戌"),("辰","酉"),("巳","申"),("午","未")]}
CHONG={frozenset(x) for x in [("子","午"),("丑","未"),("寅","申"),("卯","酉"),("辰","戌"),("巳","亥")]}
HAI={frozenset(x) for x in [("子","未"),("丑","午"),("寅","巳"),("卯","辰"),("申","亥"),("酉","戌")]}
PO={frozenset(x) for x in [("子","酉"),("丑","辰"),("寅","亥"),("卯","午"),("巳","申"),("未","戌")]}
XING_PAIRS={frozenset(x) for x in [("子","卯"),("寅","巳"),("巳","申"),("寅","申"),("丑","戌"),("戌","未"),("丑","未")]}
SELF_XING=set("辰午酉亥")
SANHE=[set("申子辰"),set("亥卯未"),set("寅午戌"),set("巳酉丑")]
SANHUI=[set("寅卯辰"),set("巳午未"),set("申酉戌"),set("亥子丑")]
GAN_HE={frozenset(x) for x in [("甲","己"),("乙","庚"),("丙","辛"),("丁","壬"),("戊","癸")]}
GAN_CHONG={frozenset(x) for x in [("甲","庚"),("乙","辛"),("丙","壬"),("丁","癸")]}

def opencsv(path:Path,mode:str):
    if "r" in mode:
        return gzip.open(path,"rt",encoding="utf-8",newline="") if path.suffix==".gz" else path.open("r",encoding="utf-8",newline="")
    path.parent.mkdir(parents=True,exist_ok=True)
    return gzip.open(path,"wt",encoding="utf-8",newline="") if path.suffix==".gz" else path.open("w",encoding="utf-8",newline="")

def parse_date(raw:str):
    if not raw:return None
    m=re.match(r"^([+-]?\d{1,4})[-/](\d{1,2})[-/](\d{1,2})",raw.strip())
    if not m:return None
    return tuple(map(int,m.groups()))

def parse_time(raw:str):
    if not raw:return None
    m=re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?",raw.strip())
    if not m:return None
    h=int(m.group(1));mi=int(m.group(2));s=int(m.group(3) or 0)
    if not (0<=h<=23 and 0<=mi<=59 and 0<=s<=59):return None
    return h,mi,s

def julian_to_gregorian(y:int,m:int,d:int):
    """Convert a positive-year Julian-calendar civil date to the Gregorian date
    representing the same physical day, via Julian Day Number."""
    if y <= 0:
        return None
    a=(14-m)//12
    yy=y+4800-a
    mm=m+12*a-3
    jdn=d+(153*mm+2)//5+365*yy+yy//4-32083
    a=jdn+32044
    b=(4*a+3)//146097
    cc=a-(146097*b)//4
    dd=(4*cc+3)//1461
    e=cc-(1461*dd)//4
    mm2=(5*e+2)//153
    day=e-(153*mm2+2)//5+1
    month=mm2+3-12*(mm2//10)
    year=100*b+dd-4800+(mm2//10)
    return year,month,day

def calendar_kind(raw:str):
    s=(raw or "").strip().lower()
    if s in {"j","julian","q1985786"} or s.endswith("/q1985786"):
        return "julian"
    if s in {"g","gregorian","q1985727"} or s.endswith("/q1985727"):
        return "gregorian"
    return "unknown"

def chart(y,m,d,h=12,mi=0,s=0):
    ec=Solar.fromYmdHms(y,m,d,h,mi,s).getLunar().getEightChar()
    return ec

def entropy(counts:Counter):
    total=sum(counts.values())
    if not total:return 0.0
    return -sum((v/total)*math.log(v/total) for v in counts.values() if v)

def relation_counts(gans,zhis):
    rel=Counter()
    for i in range(len(zhis)):
        for j in range(i+1,len(zhis)):
            pair=frozenset((zhis[i],zhis[j]))
            rel["zhi_liuhe"]+=pair in LIUHE
            rel["zhi_chong"]+=pair in CHONG
            rel["zhi_hai"]+=pair in HAI
            rel["zhi_po"]+=pair in PO
            rel["zhi_xing"]+=pair in XING_PAIRS
            if zhis[i]==zhis[j] and zhis[i] in SELF_XING:rel["zhi_self_xing"]+=1
    for i in range(len(gans)):
        for j in range(i+1,len(gans)):
            pair=frozenset((gans[i],gans[j]))
            rel["gan_he"]+=pair in GAN_HE
            rel["gan_chong"]+=pair in GAN_CHONG
    zset=set(zhis)
    rel["sanhe_complete"]=sum(group<=zset for group in SANHE)
    rel["sanhui_complete"]=sum(group<=zset for group in SANHUI)
    return rel

def features_from_ec(ec,include_time:bool):
    pillars=[ec.getYear(),ec.getMonth(),ec.getDay()]
    gans=[ec.getYearGan(),ec.getMonthGan(),ec.getDayGan()]
    zhis=[ec.getYearZhi(),ec.getMonthZhi(),ec.getDayZhi()]
    hide=[ec.getYearHideGan(),ec.getMonthHideGan(),ec.getDayHideGan()]
    if include_time:
        pillars.append(ec.getTime());gans.append(ec.getTimeGan());zhis.append(ec.getTimeZhi());hide.append(ec.getTimeHideGan())

    visible_elements=Counter()
    for g,z in zip(gans,zhis):
        visible_elements[LunarUtil.WU_XING_GAN[g]]+=1
        visible_elements[LunarUtil.WU_XING_ZHI[z]]+=1
    hidden_elements=Counter(LunarUtil.WU_XING_GAN[g] for arr in hide for g in arr)
    hidden_gans=Counter(g for arr in hide for g in arr)

    visible_tg=Counter()
    day_gan=ec.getDayGan()
    for i,g in enumerate(gans):
        if i == 2:
            continue
        god=LunarUtil.SHI_SHEN.get(day_gan+g)
        if god:visible_tg[god]+=1
    hidden_tg=Counter()
    for arr in hide:
        for g in arr:
            god=LunarUtil.SHI_SHEN.get(day_gan+g)
            if god:hidden_tg[god]+=1

    out={
      "feature_version":VERSION,
      "year_pillar":pillars[0],"month_pillar":pillars[1],"day_pillar":pillars[2],
      "hour_pillar":pillars[3] if include_time else "",
      "year_gan":gans[0],"year_zhi":zhis[0],"month_gan":gans[1],"month_zhi":zhis[1],
      "day_gan":gans[2],"day_zhi":zhis[2],"hour_gan":gans[3] if include_time else "",
      "hour_zhi":zhis[3] if include_time else "","day_master":day_gan,
      "year_nayin":ec.getYearNaYin(),"month_nayin":ec.getMonthNaYin(),"day_nayin":ec.getDayNaYin(),
      "hour_nayin":ec.getTimeNaYin() if include_time else "",
      "year_dishi":ec.getYearDiShi(),"month_dishi":ec.getMonthDiShi(),"day_dishi":ec.getDayDiShi(),
      "hour_dishi":ec.getTimeDiShi() if include_time else "",
      "year_xunkong":ec.getYearXunKong(),"month_xunkong":ec.getMonthXunKong(),"day_xunkong":ec.getDayXunKong(),
      "hour_xunkong":ec.getTimeXunKong() if include_time else "",
      "visible_element_entropy":entropy(visible_elements),
      "hidden_element_entropy":entropy(hidden_elements),
      "visible_element_imbalance":(max([visible_elements[e] for e in ELEMENTS])-min([visible_elements[e] for e in ELEMENTS])),
    }
    for e in ELEMENTS:
        out[f"visible_element_{e}"]=visible_elements[e]
        out[f"hidden_element_{e}"]=hidden_elements[e]
    for g in GANS:out[f"hidden_gan_{g}"]=hidden_gans[g]
    for god in TEN_GODS:
        out[f"visible_tengod_{god}"]=visible_tg[god]
        out[f"hidden_tengod_{god}"]=hidden_tg[god]
    out.update(relation_counts(gans,zhis))
    return out

def boundary_ambiguous(y,m,d):
    a=chart(y,m,d,0,5,0);b=chart(y,m,d,22,55,0)
    return (a.getYear(),a.getMonth())!=(b.getYear(),b.getMonth())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input");ap.add_argument("output")
    ap.add_argument("--mode",choices=["date","timed"],required=True)
    ap.add_argument("--id-column",default=None)
    ap.add_argument("--date-column",default="birth_date")
    ap.add_argument("--time-column",default="birth_time_local")
    ap.add_argument("--calendar-column",default="calendar")
    ap.add_argument("--rating-column",default="rodden_rating")
    args=ap.parse_args()

    inp=Path(args.input);outp=Path(args.output)
    rows=ok=skipped=ambiguous=0
    writer=None
    with opencsv(inp,"r") as f, opencsv(outp,"w") as w:
        for row in csv.DictReader(f):
            rows+=1
            pid=row.get(args.id_column or ("wikidata_id" if args.mode=="date" else "adb_id")) or str(rows)
            date=parse_date(row.get(args.date_column) or "")
            if not date:
                skipped+=1;continue
            source_y,source_m,source_d=date
            calendar=(row.get(args.calendar_column) or "").lower()
            kind=calendar_kind(calendar)
            conversion="none"
            if kind=="julian":
                converted=julian_to_gregorian(source_y,source_m,source_d)
                if converted is None:
                    skipped+=1;continue
                y,m,d=converted
                conversion="julian_to_gregorian"
            else:
                y,m,d=source_y,source_m,source_d
            calendar_uncertain_historical=(kind=="unknown" and y<1900)
            known_time=args.mode=="timed"
            t=parse_time(row.get(args.time_column) or "") if known_time else None
            if known_time and not t:
                skipped+=1;continue
            if args.mode=="timed":
                rr=(row.get(args.rating_column) or "").strip()
                if rr not in {"AA","A","B"}:
                    skipped+=1;continue
                ec=chart(y,m,d,*t)
                amb=False
            else:
                ec=chart(y,m,d,12,0,0)
                amb=boundary_ambiguous(y,m,d)
                ambiguous+=int(amb)
            feat=features_from_ec(ec,known_time)
            base={
              "person_id":pid,
              "source_birth_date":f"{source_y:04d}-{source_m:02d}-{source_d:02d}",
              "birth_date":f"{y:04d}-{m:02d}-{d:02d}",
              "birth_time_local":row.get(args.time_column,"") if known_time else "",
              "birth_time_known":known_time,
              "source_calendar":calendar,
              "calendar_kind":kind,
              "calendar_conversion":conversion,
              "calendar_uncertain_historical":calendar_uncertain_historical,
              "year_month_boundary_ambiguous":amb,
              "date_only_day_boundary_uncertainty":not known_time,
              "primary_feature_eligible":((not amb) and (not calendar_uncertain_historical)) if not known_time else (not calendar_uncertain_historical),
            }
            record={**base,**feat}
            if writer is None:
                writer=csv.DictWriter(w,fieldnames=list(record));writer.writeheader()
            writer.writerow(record);ok+=1
    report={"input_rows":rows,"feature_rows":ok,"skipped":skipped,"year_month_boundary_ambiguous":ambiguous,
      "feature_version":VERSION,"mode":args.mode}
    outp.with_name(outp.name[:-7]+".report.json" if outp.name.endswith(".csv.gz") else outp.stem+".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
