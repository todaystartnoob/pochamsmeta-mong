#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pokedb 포켓몬 상세 페이지에서 사용률 상위 N종의
채용 기술 / 특성 / 성격 / 노력치(능력포인트)를 긁어와 한국어로 저장한다.

⚠️ 이 데이터는 pokedb 공식 오픈데이터엔 없는 항목이라 페이지 스크래핑이 필요하다.
   서버 배려를 위해:
   - 사용률 상위 TOP_N 종만 (전종 X)
   - 요청마다 SLEEP 초 딜레이
   - GitHub Actions에서 하루 1회만 실행
   build_ranked_teams.py 가 먼저 돌아서 data/champions_s{n}_{rule}.json 을 만든 뒤 실행할 것.
"""
import json, os, re, time, urllib.request, urllib.error, glob
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

HEADERS = ["技", "特性", "能力補正", "持ち物", "能力ポイント", "同じチーム"]
NAME_RATE = re.compile(r"^(?P<name>.+?)\s+(?P<rate>\d+(?:\.\d+)?)\s*%$")  # 한 줄에 이름+%
RATE_ONLY = re.compile(r"^(\d+(?:\.\d+)?)\s*%$")                         # %만 있는 줄
INDEX = re.compile(r"^\d{1,3}$")                                        # 순번 줄(1,2,..)
EVNUM = re.compile(r"([HABCDS])\s*(\d+)")

def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def page_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script", "style"]):
        s.extract()
    text = soup.get_text("\n")
    return [ln.strip() for ln in text.split("\n") if ln.strip()]

def section(lines, header):
    """header 라인 다음부터 다음 섹션 헤더 전까지의 라인들."""
    try:
        i = lines.index(header)
    except ValueError:
        return []
    out = []
    for ln in lines[i + 1:]:
        if ln in HEADERS:
            break
        out.append(ln)
    return out

def pct_entries(lines, mapping=None, strip_paren=False, limit=10):
    """'이름 12.3%'(한 줄) 또는 '이름' / '12.3%'(두 줄) 둘 다 처리."""
    out, seen, pending = [], set(), None
    def emit(name, rate):
        if strip_paren:
            name = re.split(r"\s*[（(]", name)[0].strip()
        name = name.strip()
        if not name or name in seen:
            return
        seen.add(name)
        out.append({"name": mapping.get(name, name) if mapping else name, "rate": rate})
    for ln in lines:
        if len(out) >= limit:
            break
        m = NAME_RATE.match(ln)
        if m:
            emit(m.group("name"), float(m.group("rate"))); pending = None; continue
        r = RATE_ONLY.match(ln)
        if r:
            if pending is not None:
                emit(pending, float(r.group(1))); pending = None
            continue                      # 직전 이름 없으면 중복 % -> 무시
        if INDEX.match(ln):
            continue
        pending = ln                      # 이름 후보
    return out

def ev_entries(lines, limit=12):
    """능력포인트: 직전 %(같은 줄/다른 줄 모두)와 숫자 배분(H32 A.. 등)을 짝지음."""
    out, seen, last = [], set(), None
    for ln in lines:
        if len(out) >= limit:
            break
        m = NAME_RATE.match(ln) or RATE_ONLY.match(ln)
        if m:
            last = float(m.group("rate") if "rate" in m.groupdict() else m.group(1))
            continue
        nums = EVNUM.findall(ln)
        if nums and "%" not in ln and last is not None:
            evs = {k: int(v) for k, v in nums}
            key = (tuple(sorted(evs.items())), last)
            if key in seen:
                continue
            seen.add(key)
            out.append({"evs": evs, "rate": last})
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
        "moves":    pct_entries(section(lines, "技"), MOVE, limit=12),
        "abilities":pct_entries(section(lines, "特性"), ABIL, limit=5),
        "natures":  pct_entries(section(lines, "能力補正"), NAT, strip_paren=True, limit=8),
        "items":    pct_entries(section(lines, "持ち物"), ITEM, limit=10),
        "ev_spreads": ev_entries(section(lines, "能力ポイント"), limit=12),
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
            json.dump({"season_number": season, "rule": rule,
                       "top_n": TOP_N, "pokemon": result,
                       "source": "champs.pokedb.tokyo"}, f, ensure_ascii=False, indent=2)
        print(f"  생성: {os.path.basename(out_path)} ({len(result)}종)")

if __name__ == "__main__":
    main()
