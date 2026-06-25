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

TOP_N = None   # None = 전부(약209종) 다 수집
SLEEP = 6.0    # 요청 간격(초). 분당 10요청 수준 — 아주 얌전. 더 늦추려면 키워(8,10…)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")   # WAF 403 회피용
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

def fetch_html(url, retries=3):
    import urllib.error
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last = e
            if e.code in (403, 429, 500, 502, 503):
                time.sleep(3 * (i + 1)); continue
            raise
        except Exception as e:
            last = e; time.sleep(3 * (i + 1))
    raise last

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
    """능력포인트: '개별(個別)' 배분만 추출한다.
    pokedb 페이지는 '합산(合算)' 그룹 합계(예: AS=AS+h·AS+b... 총합, '余り'/'N件を合算' 표기)와
    '개별' 단일 배분을 함께 렌더링한다. 余り/件を合算이 붙은 그룹 합계는 버리고 개별만 모아
    사용률 내림차순으로 정렬한다.
    """
    out, seen, i, n = [], set(), 0, len(lines)
    while i < n:
        ln = lines[i]
        if ln in ("合算", "個別", "+", "余り") or ln.endswith("件を合算") or re.fullmatch(r"\d{1,3}", ln):
            i += 1; continue
        # 라벨 다음 줄이 % 인 경우만 항목으로 인정
        if i + 1 < n and RATE.match(lines[i + 1]):
            label = ln
            rate = float(RATE.match(lines[i + 1]).group(1))
            evs = {}; j = i + 2
            while j + 1 < n and lines[j] in "HABCDS" and re.fullmatch(r"\d+", lines[j + 1]):
                evs[lines[j]] = int(lines[j + 1]); j += 2
            # 뒤에 余り/件を合算이 따라오면 = 합산 그룹 -> 제외
            is_group = False; k = j
            while k < n and (lines[k] in ("+", "余り") or lines[k].endswith("件を合算")):
                if lines[k] == "余り" or lines[k].endswith("件を合算"):
                    is_group = True
                k += 1
            if evs and not is_group:
                key = tuple(sorted(evs.items()))
                if key not in seen:
                    seen.add(key)
                    out.append({"label": label, "evs": evs, "rate": rate})
            i = k; continue
        i += 1
    out.sort(key=lambda x: -x["rate"])
    return out[:limit]

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
    ranked = sorted(set(glob.glob(os.path.join(DATA_DIR, "champions_s*_single.json")) +
                        glob.glob(os.path.join(DATA_DIR, "champions_s*_double.json"))))
    # ★ ranked 파일이 하나도 없으면(앞 단계 차단/실패) 기존 _sets 보존하고 종료 — 절대 삭제 금지.
    if not ranked:
        print("[중단] ranked 파일이 없음 — 앞 단계 실패 의심. 기존 _sets 보존, 변경 없음.")
        return
    valid_sets = set()   # 유효한 _sets 파일명(고아 정리용)
    for path in ranked:
        base = os.path.basename(path)
        m = re.match(r"champions_s(\d+)_(single|double)\.json", base)
        if not m:
            continue
        season, rule = int(m.group(1)), m.group(2)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        usage = data.get("usage", [])
        # 진행중(크롤) 시즌 = 매일 갱신 필요 / 종료(오픈데이터) 시즌 = 안 변하니 캐시
        is_current = "crawl" in data.get("source", "")
        top = usage if TOP_N is None else usage[:TOP_N]
        out_path = os.path.join(DATA_DIR, f"champions_s{season}_{rule}_sets.json")
        valid_sets.add(os.path.basename(out_path))

        # 종료 시즌이고 이미 동일 범위 이상으로 긁어둔 캐시가 있으면 재크롤 생략
        # (pokedb 부담↓, 실행시간↓ — 종료 시즌 데이터는 변하지 않음)
        if (not is_current) and os.path.exists(out_path):
            try:
                with open(out_path, encoding="utf-8") as f:
                    cached = json.load(f)
                if len(cached.get("pokemon", [])) >= len(top):
                    print(f"[{base}] 종료 시즌 캐시 사용 - 스킵 ({len(cached.get('pokemon', []))}종)")
                    continue
            except Exception:
                pass

        print(f"[{base}] 상위 {len(top)}종 스크래핑... (요청 간격 {SLEEP}s)")
        result = []
        for u in top:
            s = scrape(u["id"], season, rule)
            time.sleep(SLEEP)
            if s is None:
                continue
            s["name"] = u.get("name", "")
            s["usage_rate"] = u.get("rate")
            result.append(s)
        # ★ 전멸(차단 등)이고 기존 캐시가 있으면 덮어쓰지 않고 보존
        if not result and top:
            if os.path.exists(out_path):
                print(f"  [보존] {os.path.basename(out_path)} — 스크랩 0종(차단 의심), 기존 파일 유지")
            else:
                print(f"  [경고] {os.path.basename(out_path)} — 스크랩 0종, 캐시도 없음 → 건너뜀")
            continue
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"season_number": season, "rule": rule,
                       "top_n": (len(top) if TOP_N is None else TOP_N),
                       "pokemon": result, "source": "champs.pokedb.tokyo"},
                      f, ensure_ascii=False, indent=2)
        print(f"  생성: {os.path.basename(out_path)} ({len(result)}종)")

    # 고아 _sets 정리: 대응하는 ranked 파일이 없는 _sets.json 삭제 (가짜 시즌 잔재 등)
    for sp in glob.glob(os.path.join(DATA_DIR, "champions_s*_sets.json")):
        if os.path.basename(sp) not in valid_sets:
            os.remove(sp)
            print(f"  [정리] 고아 sets 삭제: {os.path.basename(sp)}")

if __name__ == "__main__":
    main()
