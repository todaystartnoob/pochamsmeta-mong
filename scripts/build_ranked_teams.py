#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
포켓몬 챔피언스 상위 구축(랭커 파티) 오픈데이터를 받아서
일본어 -> 한국어로 변환하고 포켓몬 사용률까지 계산해 저장한다.
출처: champs.pokedb.tokyo 오픈데이터 (https://champs.pokedb.tokyo/guide/opendata)
정책: 엔드유저 기기 직접 요청 금지. CI에서 1회 받아 자기 호스팅으로 서빙.
"""
import json, os, time, urllib.request, urllib.error
from collections import Counter

BASE = "https://champs.pokedb.tokyo/opendata/s{season}_{rule}_ranked_teams.json"
RULES = ["single", "double"]
MAX_SEASON = 30
UA = "ChampionsTool/1.0 (+https://github.com/todaystartnoob/pochamsmeta-mong)"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MAP_PATH = os.path.join(os.path.dirname(__file__), "champions_loc_map.json")

with open(MAP_PATH, encoding="utf-8") as f:
    M = json.load(f)
DEX2KO = {int(k): v for k, v in M["dex2ko"].items()}
ITEM   = M["item_ja2ko"]
TYPE   = M["type_ja2ko"]
FORM   = M["form_ja2ko"]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def safe_dex(raw_id):
    if not raw_id:
        return None
    head = str(raw_id).split("-")[0].strip()
    return int(head) if head.isdigit() else None

def loc_mon(p):
    raw_id = (p.get("id") or "").strip()
    dex = safe_dex(raw_id)
    name = (DEX2KO.get(dex) if dex else None) or p.get("pokemon", "")
    if not raw_id and not name:
        return None
    return {
        "id": raw_id,
        "name": name,
        "form": FORM.get(p.get("form", ""), p.get("form", "")),
        "type1": TYPE.get(p.get("type1", ""), p.get("type1", "")),
        "type2": TYPE.get(p.get("type2", ""), p.get("type2", "")),
        "terastal": TYPE.get(p.get("terastal", ""), p.get("terastal", "")),
        "item": ITEM.get(p.get("item", ""), p.get("item", "")),
        "category": p.get("category", ""),
    }

def build(season, rule):
    url = BASE.format(season=season, rule=rule)
    try:
        data = fetch(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"  [skip] {url} -> HTTP {e.code}")
        return None
    except Exception as e:
        print(f"  [skip] {url} -> {e}")
        return None

    teams = []
    counts = Counter()
    for t in data.get("teams", []):
        mons = []
        for p in t.get("team", []):
            m = loc_mon(p)
            if m is None:
                continue
            mons.append(m)
            if m["id"]:
                counts[(m["id"], m["name"])] += 1
        teams.append({"rank": t.get("rank"), "rating": t.get("rating_value"), "team": mons})

    total = len(teams) or 1
    usage = [
        {"id": i, "name": n, "count": c, "rate": round(c / total * 100, 2)}
        for (i, n), c in counts.most_common()
    ]
    return {
        "season": data.get("season"),
        "season_number": data.get("season_number", season),
        "rule": rule,
        "updated_at": data.get("updated_at"),
        "team_count": total,
        "usage": usage,
        "teams": teams,
        "source": "champs.pokedb.tokyo opendata",
    }

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    wrote = []
    for season in range(1, MAX_SEASON + 1):
        found_any = False
        for rule in RULES:
            res = build(season, rule)
            time.sleep(1)
            if res is None:
                continue
            found_any = True
            path = os.path.join(OUT_DIR, f"champions_s{season}_{rule}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
            wrote.append(os.path.basename(path))
            print(f"  생성: {os.path.basename(path)} (팀 {res['team_count']})")
        if not found_any and season > 1:
            break
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"files": wrote,
                   "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())},
                  f, ensure_ascii=False, indent=2)
    print("완료:", wrote)

if __name__ == "__main__":
    main()
