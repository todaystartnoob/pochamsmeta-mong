#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
포켓몬 챔피언스 사용률·랭커 파티 데이터 빌더.

데이터 취득 전략 (시즌 상태별):
  - 종료된 시즌  : champs.pokedb.tokyo 오픈데이터(JSON) 사용 (사용률 + 랭커파티 전체).
  - 진행중 시즌  : 오픈데이터 미공개 -> 사용률 순위 페이지(/pokemon/list)를 크롤링.
                   (랭커파티/트레이너 랭킹은 '시즌 시작 1주일 후' 공개되므로 그 전엔 teams=[].)

출력(시즌/룰별 champions_s{N}_{rule}.json):
  usage   : 사용률 순위  (오픈데이터=count/rate 포함, 크롤=rank/id/name)
  pokemon : 포켓몬별 최빈 도구/테라스탈 (랭커파티 집계, 오픈데이터 있을 때만)
  teams   : 랭커 파티 '상위 50개만' (각 포켓몬의 실제 지닌 도구=샘플 포함)

출처/정책: https://champs.pokedb.tokyo/guide/opendata
  - 엔드유저 기기 직접 요청 금지. CI에서 1회 받아 자기 호스팅으로 서빙. 과도한 폴링 금지.
"""
import json, os, re, time, urllib.request, urllib.error
from collections import Counter, defaultdict

OPENDATA = "https://champs.pokedb.tokyo/opendata/s{season}_{rule}_ranked_teams.json"
LIST_URL = "https://champs.pokedb.tokyo/pokemon/list?season={season}&rule={r}"
RULES = ["single", "double"]
RULE_CODE = {"single": 0, "double": 1}     # /pokemon/list 의 rule 파라미터
MAX_SEASON = 30
TOP_TEAMS = 50                              # 랭커 파티 상위 N개만 저장
UA = "ChampionsTool/1.0 (+https://github.com/todaystartnoob/pochamsmeta-mong)"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MAP_PATH = os.path.join(os.path.dirname(__file__), "champions_loc_map.json")

with open(MAP_PATH, encoding="utf-8") as f:
    M = json.load(f)
DEX2KO = {int(k): v for k, v in M["dex2ko"].items()}
ITEM   = M["item_ja2ko"]
TYPE   = M["type_ja2ko"]
FORM   = M["form_ja2ko"]

def _req(url):
    return urllib.request.Request(url, headers={"User-Agent": UA})

def fetch_json(url):
    with urllib.request.urlopen(_req(url), timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_text(url):
    with urllib.request.urlopen(_req(url), timeout=30) as r:
        return r.read().decode("utf-8", "replace")

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
        "item": ITEM.get(p.get("item", ""), p.get("item", "")),   # 실제 지닌 도구(샘플)
        "category": p.get("category", ""),
    }

def top_list(counter, n=5):
    total = sum(counter.values()) or 1
    out = []
    for v, c in counter.most_common():
        if v in ("", None):
            continue
        out.append({"value": v, "count": c, "rate": round(c / total * 100, 2)})
        if len(out) >= n:
            break
    return out

# ---------- 1) 오픈데이터(종료 시즌) ----------
def build_from_opendata(season, rule, data):
    all_teams = data.get("teams", [])
    items_by = defaultdict(Counter)
    teras_by = defaultdict(Counter)
    name_of = {}
    loc_teams = []
    for t in all_teams:
        mons = []
        for p in t.get("team", []):
            m = loc_mon(p)
            if m is None:
                continue
            mons.append(m)
            if m["id"]:
                name_of[m["id"]] = m["name"]
                items_by[m["id"]][m["item"]] += 1
                teras_by[m["id"]][m["terastal"]] += 1
        loc_teams.append({"rank": t.get("rank"), "rating": t.get("rating_value"), "team": mons})

    # 사용률: 오픈데이터의 공식 usage 우선, 없으면 팀 등장수로 계산
    usage = []
    if data.get("usage"):
        for u in data["usage"]:
            dex = safe_dex(u.get("id"))
            usage.append({
                "id": u.get("id"),
                "name": (DEX2KO.get(dex) if dex else None) or u.get("name", ""),
                "count": u.get("count"),
                "rate": u.get("rate"),
            })
    else:
        total = len(loc_teams) or 1
        cnt = Counter()
        for t in loc_teams:
            for m in t["team"]:
                if m["id"]:
                    cnt[(m["id"], m["name"])] += 1
        usage = [{"id": i, "name": n, "count": c, "rate": round(c / total * 100, 2)}
                 for (i, n), c in cnt.most_common()]

    # 포켓몬별 최빈 도구/테라스탈 (전체 팀 기준 집계 = 정확)
    pokemon = []
    for u in usage:
        i = u["id"]
        if i in items_by:
            pokemon.append({
                "id": i, "name": name_of.get(i, u["name"]),
                "top_items": top_list(items_by[i]),
                "top_terastals": top_list(teras_by[i]),
            })

    return {
        "season": data.get("season"),
        "season_number": data.get("season_number", season),
        "rule": rule,
        "updated_at": data.get("updated_at"),
        "team_count": len(all_teams),       # 전체 팀 수(집계 기준)
        "usage": usage,                     # 사용률 순위
        "pokemon": pokemon,                 # 포켓몬별 최빈 도구/테라
        "teams": loc_teams[:TOP_TEAMS],     # 랭커 파티 상위 50개만
        "source": "champs.pokedb.tokyo opendata",
    }

# ---------- 2) 사용률 페이지 크롤(진행중 시즌) ----------
SHOW_RE = re.compile(r"/pokemon/show/(\d{4}-\d{2})")
RANK_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")

def scrape_usage(season, rule):
    """진행중 시즌: /pokemon/list 페이지에서 사용률 순위(순위+id+이름)를 긁는다."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("  [warn] beautifulsoup4 필요 (pip install beautifulsoup4)")
        return []
    url = LIST_URL.format(season=season, r=RULE_CODE[rule])
    try:
        html = fetch_text(url)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  [skip] {url} -> HTTP {e.code}")
        return []
    except Exception as e:
        print(f"  [skip] {url} -> {e}")
        return []
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        m = SHOW_RE.search(a["href"])
        if not m:
            continue
        rid = m.group(1)
        if rid in seen:
            continue
        txt = a.get_text(" ", strip=True)
        rm = RANK_RE.match(txt)
        if not rm:                      # 순위 숫자로 시작하는 링크만 = 랭킹 항목
            continue
        seen.add(rid)
        rank = int(rm.group(1)); jp = rm.group(2)
        dex = safe_dex(rid)
        out.append({
            "id": rid,
            "name": (DEX2KO.get(dex) if dex else None) or jp,
            "rank": rank,
            # 사용률 %는 list 페이지에 없음 -> count/rate 없음(순위만)
        })
    out.sort(key=lambda x: x["rank"])
    return out

def build(season, rule):
    # 1) 오픈데이터 시도
    od_url = OPENDATA.format(season=season, rule=rule)
    try:
        data = fetch_json(od_url)
        return build_from_opendata(season, rule, data)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  [skip] {od_url} -> HTTP {e.code}")
            return None
        # 404 -> 진행중 시즌일 수 있음 -> 크롤로 폴백
    except Exception as e:
        print(f"  [skip] {od_url} -> {e}")
        return None

    # 2) 크롤(진행중 시즌 사용률)
    usage = scrape_usage(season, rule)
    if not usage:
        return None
    return {
        "season": f"M-{season}",
        "season_number": season,
        "rule": rule,
        "updated_at": None,
        "team_count": 0,
        "usage": usage,        # 순위+id+이름 (rate 없음)
        "pokemon": [],         # 랭커파티 미공개 -> 집계 불가
        "teams": [],           # 트레이너 랭킹은 시즌 시작 1주 후 공개
        "source": "champs.pokedb.tokyo /pokemon/list (crawl)",
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
            print(f"  생성: {os.path.basename(path)} "
                  f"(usage {len(res['usage'])}, teams {len(res['teams'])}, src={res['source'].split()[-1]})")
        if not found_any and season > 1:
            break
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"files": wrote,
                   "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())},
                  f, ensure_ascii=False, indent=2)
    print("완료:", wrote)

if __name__ == "__main__":
    main()
