#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[임시 디버그] 한카리아스 페이지 1개만 받아서 실제 텍스트 줄 구조를 data/_debug.json에 저장."""
import json, os, re, urllib.request
from bs4 import BeautifulSoup

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "..", "data")
UA = "ChampionsTool/1.0 (+https://github.com/todaystartnoob/pochamsmeta-mong)"
URL = "https://champs.pokedb.tokyo/pokemon/show/0445-00?season=1&rule=0"

req = urllib.request.Request(URL, headers={"User-Agent": UA})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
soup = BeautifulSoup(html, "html.parser")

# 1) script 안에 들어있는 JSON(하이드레이션) 후보 탐색
scripts = []
for s in soup.find_all("script"):
    t = (s.string or "")[:200]
    if any(k in (s.get("type","")+ (s.get("id","")) + t) for k in ["json","__NEXT","__NUXT","application/json"]):
        scripts.append({"type": s.get("type"), "id": s.get("id"),
                        "len": len(s.string or ""), "head": (s.string or "")[:300]})

# 2) get_text 줄 구조
for s in soup(["script","style"]):
    s.extract()
lines = [ln.strip() for ln in soup.get_text("\n").split("\n") if ln.strip()]
# 技 ~ 同じチーム 구간만 추려서
def around(headers):
    idxs = [(h, lines.index(h)) for h in headers if h in lines]
    return idxs
heads = around(["技","特性","能力補正","持ち物","能力ポイント","同じチーム"])

os.makedirs(DATA_DIR, exist_ok=True)
json.dump({
    "url": URL,
    "total_lines": len(lines),
    "header_positions": heads,
    "lines": lines,
    "script_json_candidates": scripts,
}, open(os.path.join(DATA_DIR, "_debug.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("디버그 저장: data/_debug.json | 헤더 위치:", heads, "| script후보:", len(scripts))
