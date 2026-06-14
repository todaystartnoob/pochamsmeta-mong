#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
포켓몬 챔피언스 상위 구축(랭커 파티) 오픈데이터를 받아서
일본어 -> 한국어로 변환하고 포켓몬 사용률까지 계산해 저장한다.

출처: 바트루데이터베이스 챔피언스 (champs.pokedb.tokyo) 오픈데이터
      https://champs.pokedb.tokyo/guide/opendata
정책: 엔드유저 기기에서 직접 요청 금지. 서버/CI에서 1회 받아 자기 호스팅으로 서빙할 것.
      => 이 스크립트는 GitHub Actions(CI)에서만 실행되어 결과 파일을 레포에 커밋한다.
"""
import json, os, time, urllib.request, urllib.error
from collections import Counter

BASE = "https://champs.pokedb.tokyo/opendata/s{season}_{rule}_ranked_teams.json"
RULES = ["single", "double"]
MAX_SEASON = 30            # 안전 상한 (404 만나면 자동 종료)
UA = "ChampionsTool/1.0 (+https://github.com/todaystartnoob/pochamsmeta-mong)"  # TODO: 본인 정보로
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MAP_PATH = os.path.join(os.path.dirname(__file__), "champions_loc_map.json")

with open(MAP_PATH, encoding="utf-8") as f:
    M = json.load(f)
DEX2KO   = {int(k): v for k, v in M["dex2ko"].items()}
ITEM     = M["item_ja2ko"]
TYPE     = M["type_ja2ko"]
FORM     = M["form_ja2ko"]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def loc_mon(p):
    """팀 내 포켓몬 1마리를 한국어로 변환."""
    dex = int(p["id"].split("-")[0])
    return {
        "id": p["id"],                                  # 0448-00 (언어중립 조인키)
        "name": DEX2KO.get(dex, p.get("pokemon", "")),  # 한국어 포켓몬명
        "form": FORM.get(p.get("form", ""), p.get("form", "")),
        "type1": TYPE.get(p.get("type1", ""), p.get("type1", "")),
        "type2": TYPE.get(p.get("type2", ""), p.get("type2", "")),
        "terastal": TYPE.get(p.get("terastal", ""), p.get("terastal", "")),
        "item": ITEM.get(p.get("item", ""), p.get("item", "")),  # 미매핑 시 원문(JP) 유지
        "category": p.get("category", ""),
    }

def build(season, rule):
    url = BASE.format(season=season, rule=rule)
    try:
        data = fetch(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None          # 없는 시즌/룰 -> 스킵
        raise
    teams = []
    counts = Counter()
    for t in data.get("teams", []):
        mons = [loc_mon(p) for p in t["team"]]
        for m in mons:
            counts[(m["id"], m["name"])] += 1
        teams.append({"rank": t["rank"], "rating": t.get("rating_value"), "team": mons})
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
        "usage": usage,        # 상위권 사용률 (등장 횟수 기반)
        "teams": teams,        # 랭커 파티 전체
        "source": "champs.pokedb.tokyo opendata",
    }

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    wrote = []
    for season in range(1, MAX_SEASON + 1):
        found_any = False
        for rule in RULES:
            res = build(season, rule)
            time.sleep(1)            # 과부하 방지 (정책 준수)
            if res is None:
                continue
            found_any = True
            path = os.path.join(OUT_DIR, f"champions_s{season}_{rule}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
            wrote.append(os.path.basename(path))
        if not found_any and season > 1:
            break                    # 더 이상 시즌 없음 -> 종료
    # 인덱스(어떤 파일이 있는지)도 같이 저장
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"files": wrote, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())},
                  f, ensure_ascii=False, indent=2)
    print("생성:", wrote)

if __name__ == "__main__":
    main()
