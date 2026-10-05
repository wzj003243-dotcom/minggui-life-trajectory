"""Offline regression smoke for biography wikitext parsing."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from research.extraction.extract_timeline_candidates import wikitext_to_plain,classify,YEAR

RAW=r"""
{{Infobox person|name=Example|birth_date=1970}}
Example Person was born in 1970.
In 1992, Example Person graduated from Example University.
In 1998, Example Person moved to Paris and began working as an engineer.

== References ==
<references/>
* Citation published in 2004.
"""

plain=wikitext_to_plain(RAW)
assert "graduated from Example University" in plain,plain
assert "moved to Paris" in plain,plain
assert "Citation published in 2004" not in plain,plain
assert "1992" in YEAR.findall(plain),YEAR.findall(plain)
domains,_=classify("In 1992, Example Person graduated from Example University.")
assert "education" in domains,domains
print("biography parser smoke OK")
