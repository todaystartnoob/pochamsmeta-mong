#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pokedb 포켓몬 상세 페이지에서 사용률 상위 N종의
채용 기술 / 특성 / 성격 / 도구 / 노력치(능력포인트)를 긁어와 한국어로 저장.
build_ranked_teams.py 가 먼저 돌아서 data/champions_s{n}_{rule}.json 생성 후 실행.
서버 배려: 상위 TOP_N 종만, 요청마다 SLEEP 딜레이, 하루 1회.
"""
import json, os, re, time, glob, urllib.request
from bs4 import BeautifulSoup

TOP_N = 50
SLEEP = 1.5
UA = "ChampionsTool/1.0 (+https://github.com/todaystartnoob/pochamsmeta-mong)"
HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "..", "data")
PAGE = "https://champs.pokedb.tokyo/pokemon/show/{id}?season={season}&rule={r}"
RULE_CODE = {"single": 0, "double": 1}

with open(os.path.join(HERE, "champions_loc_map.json"), encoding="utf-8") as f:
    M = json.load(f)
MOVE = M.get("move_ja2ko", {})
NAT  = M.get("nature_ja2ko", {})
ABIL = M.get("ability_ja2ko", {})
ITEM = M.get("item_ja2ko", {})

ORDER = ["技", "特性", "能力補正", "持ち物", "能力ポイント", "同じチーム"]
RATE  = re.compile(r"^(\d+(?:\.\d+)?)%$")
PAREN = re.compile(r"^[（()）]$|^[A-Za-zＡ-Ｚ]*[↑↓]$|^[↑↓]$")

def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def page_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script", "style"]):
        s.extract()
    return [ln.strip() for ln in soup.get_text("\n").split("\n") if ln.strip()]

def seq_pos(lines):
    """헤더를 순서대로 탐색 (상단 '特性' 라벨 오인 방지: 技 다음부터 찾음)."""
    pos = {}
    if "技" not in lines:
        return pos
    i = lines.index("技"); pos["技"] = i; cur = i
    for h in ORDER[1:]:
        try:
            j = lines.index(h, cur + 1); pos[h] = j; cur = j
        except ValueError:
            pos[h] = None
    return pos

def sect(lines, h):
    pos = seq_pos(lines)
    if pos.get(h) is None:
        return []
    start = pos[h]
    ends = [p for p in pos.values() if p is not None and p > start]
    return lines[start + 1:(min(ends) if ends else len(lines))]

def merge_pct(lines):
    """'99.0' + '%' (분리된 줄) -> '99.0%' 로 병합 (기술 섹션 대응)."""
    out, i = [], 0
    while i < len(lines):
        if i + 1 < len(lines) and re.fullmatch(r"\d+(?:\.\d+)?", lines[i]) and lines[i + 1] == "%":
            out.append(lines[i] + "%"); i += 2
        else:
            out.append(lines[i]); i += 1
    return out

def pct_entries(lines, mapping=None, strip_paren=False, limit=10):
    """이름/순번/괄호조각/% 가 줄로 흩어진 구조에서 (이름, %) 추출."""
    lines = merge_pct(lines)
    out, seen, name = [], set(), None
    for ln in lines:
        if len(out) >= limit:
            break
        m = RATE.match(ln)
        if m:
            if name:
                nm = re.split(r"\s*[（(]", name)[0].strip() if strip_paren else name
                ko = mapping.get(nm, nm) if mapping else nm
                if ko and ko not in seen:
                    seen.add(ko); out.append({"name": ko, "rate": float(m.group(1))})
                name = None
            continue
        if re.fullmatch(r"\d{1,3}", ln):   # 순번
            continue
        if PAREN.match(ln):                # ( ) S↑ C↓
            continue
        if name is None:
            name = ln
    return out

def ev_entries(lines, limit=12):
    """능력포인트: 라벨/%/(H 2 A 32 S 32...) 흩어진 구조에서 배분 추출."""
    out, seen, i, label, n = [], set(), 0, None, len(lines)
    while i < n and len(out) < limit:
        ln = lines[i]
        if ln in ("合算", "個別", "+", "余り") or ln.endswith("件を合算") or re.fullmatch(r"\d{1,3}", ln):
            i += 1; continue
        m = RATE.match(ln)
        if m:
            rate = float(m.group(1)); evs = {}; j = i + 1
            while j + 1 < n and lines[j] in "HABCDS" and re.fullmatch(r"\d+", lines[j + 1]):
                evs[lines[j]] = int(lines[j + 1]); j += 2
            key = (tuple(sorted(evs.items())), rate)
            if evs and key not in seen:
                seen.add(key); out.append({"label": label, "evs": evs, "rate": rate})
            i = j; continue
        label = ln; i += 1
    return out

def scrape(poke_id, season, rule):
    url = PAGE.format(id=poke_id, season=season, r=RULE_CODE[rule])
    try:
        lines = page_lines(fetch_html(url))
    except Exception as e:
        print(f"    [skip] {poke_id} -> {e}")
        return None
    return {
        "id": poke_id,
        "moves":     pct_entries(sect(lines, "技"), MOVE, limit=12),
        "abilities": pct_entries(sect(lines, "特性"), ABIL, limit=5),
        "natures":   pct_entries(sect(lines, "能力補正"), NAT, strip_paren=True, limit=8),
        "items":     pct_entries(sect(lines, "持ち物"), ITEM, limit=10),
        "ev_spreads": ev_entries(sect(lines, "能力ポイント"), limit=12),
        "source": "champs.pokedb.tokyo (pokemon page)",
    }

def main():
    files = sorted(set(glob.glob(os.path.join(DATA_DIR, "champions_s*_single.json")) +
                       glob.glob(os.path.join(DATA_DIR, "champions_s*_double.json"))))
    for path in files:
        base = os.path.basename(path)
        m = re.match(r"champions_s(\d+)_(single|double)\.json", base)
        if not m:
            continue
        season, rule = int(m.group(1)), m.group(2)
        with open(path, encoding="utf-8") as f:
            usage = json.load(f).get("usage", [])
        top = usage[:TOP_N]
        print(f"[{base}] 상위 {len(top)}종 스크래핑...")
        result = []
        for u in top:
            s = scrape(u["id"], season, rule)
            time.sleep(SLEEP)
            if s is None:
                continue
            s["name"] = u.get("name", "")
            s["usage_rate"] = u.get("rate")
            result.append(s)
        out_path = os.path.join(DATA_DIR, f"champions_s{season}_{rule}_sets.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"season_number": season, "rule": rule, "top_n": TOP_N,
                       "pokemon": result, "source": "champs.pokedb.tokyo"},
                      f, ensure_ascii=False, indent=2)
        print(f"  생성: {os.path.basename(out_path)} ({len(result)}종)")

if __name__ == "__main__":
    main()
