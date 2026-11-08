"""機酒速報管線：Travelpayouts aviasales/v3/prices_for_dates → docs/data/deals.json

每筆價格都帶：
  observed_on  Aviasales 用戶實際搜到呢個價嘅日期（由 link 的 search_date 解析）
  fetched_at   我哋抓取時間（UTC）
  expires_at   過期時間 = min(observed_on + MAX_AGE_DAYS, 出發前一日)
  source       來源名 + 可點擊連結（有 TRAVELPAYOUTS_MARKER 就掛聯盟碼）
過期嘅唔會寫入；前端讀取時會用 expires_at 再過濾一次（雙重保險）。

規格：DEALS_PLAN.md。flights.json / hotels.json 由 flight_scraper.py 照舊產出。
"""
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import requests

API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
OUT = "docs/data/deals.json"
MAX_AGE_DAYS = int(os.environ.get("DEALS_MAX_AGE_DAYS", "4"))
MONTHS_AHEAD = 6
HKT = timezone(timedelta(hours=8))

# 出發地 → (幣別, 顯示名)
ORIGINS = {
    "HKG": ("hkd", "香港"),
    "TPE": ("twd", "台北"),
}

# 日本優先。用城市碼，涵蓋同城多機場（TYO=成田+羽田、OSA=關西、SPK=新千歲）
DESTS = {
    "OKA": "沖繩",
    "TYO": "東京",
    "OSA": "大阪",
    "FUK": "福岡",
    "SPK": "札幌",
    "NGO": "名古屋",
}

AIRLINE = {
    "UO": "香港快運", "CX": "國泰", "HX": "香港航空", "HB": "大灣區航空",
    "IT": "台灣虎航", "MM": "樂桃", "VZ": "VietJet", "JL": "日航", "NH": "全日空",
    "BR": "長榮", "CI": "中華航空", "JX": "星宇", "TR": "酷航", "GK": "捷星日本",
    "3K": "捷星亞洲", "7C": "濟州航空", "TW": "德威", "LJ": "真航空", "ZE": "易斯達",
    "SL": "泰國獅航", "FD": "泰亞航", "DJ": "日本亞航", "D7": "亞航X", "5J": "宿霧太平洋", "BX": "釜山航空",
    "KE": "大韓航空", "OZ": "韓亞航空", "MU": "東方航空", "CA": "國航", "CZ": "南航",
}

# 俄語市場代理商：港台讀者用唔到，唔當「速報價」（2026-10-26 試跑見到）
BLOCKED_GATES = {"Biletix", "Tickets", "City.Travel", "Aviakassa", "Clickavia",
                 "Kupibilet", "OneTwoTrip", "Tutu.ru", "Ozon.travel", "Pobeda"}
_CYRILLIC = re.compile(r"[\u0400-\u04FF]")


def gate_ok(gate: str) -> bool:
    return bool(gate) and gate not in BLOCKED_GATES and not _CYRILLIC.search(gate)


_SEARCH_DATE = re.compile(r"search_date=(\d{2})(\d{2})(\d{4})")


def observed_on(link: str):
    """link 內 search_date=DDMMYYYY → date；搵唔到回 None（呢類一律唔用）。"""
    m = _SEARCH_DATE.search(link or "")
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    try:
        return date(int(yyyy), int(mm), int(dd))
    except ValueError:
        return None


def source_url(link: str, marker: str) -> str:
    url = "https://www.aviasales.com" + link
    if marker:
        url += ("&" if "?" in url else "?") + "marker=" + quote(marker)
    return url


def month_list(today: date, n: int) -> list:
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def fetch(token: str, origin: str, dest: str, month: str, currency: str, one_way: bool) -> list:
    params = {
        "origin": origin, "destination": dest, "departure_at": month,
        "currency": currency, "one_way": "true" if one_way else "false",
        "sorting": "price", "limit": 30, "token": token,
    }
    for attempt in range(3):
        try:
            r = requests.get(API, params=params, timeout=20,
                             headers={"Accept-Encoding": "gzip, deflate"})
            if r.status_code == 429:
                time.sleep(2 + attempt * 3)
                continue
            if not r.ok:
                print(f"  {origin}→{dest} {month} {'OW' if one_way else 'RT'}: HTTP {r.status_code}")
                return []
            d = r.json()
            return d.get("data") or [] if d.get("success") else []
        except Exception as e:  # noqa: BLE001 — 網絡錯誤唔好拖死整條管線
            print(f"  {origin}→{dest} {month}: {e}")
            time.sleep(1)
    return []


def to_deal(item: dict, origin: str, dest: str, currency: str, one_way: bool,
            now: datetime, marker: str):
    if not gate_ok(item.get("gate", "")):
        return None, "blocked_gate"
    obs = observed_on(item.get("link", ""))
    if obs is None:
        return None, "no_observed"
    dep_str = (item.get("departure_at") or "")[:10]
    try:
        dep = date.fromisoformat(dep_str)
    except ValueError:
        return None, "bad_date"
    ret_str = None if one_way else (item.get("return_at") or "")[:10] or None
    if not one_way and not ret_str:
        return None, "no_return"

    today = now.astimezone(HKT).date()
    expires_on = min(obs + timedelta(days=MAX_AGE_DAYS), dep - timedelta(days=1))
    if expires_on < today:
        return None, "expired"

    trip = "one_way" if one_way else "round_trip"
    code = item.get("airline", "")
    return {
        "id": f"f-{origin}-{item.get('destination_airport', dest)}-{dep_str}"
              f"{'-' + ret_str if ret_str else ''}-{trip}",
        "kind": "flight",
        "origin": origin,
        "origin_name": ORIGINS[origin][1],
        "dest": dest,
        "dest_name": DESTS[dest],
        "origin_airport": item.get("origin_airport"),
        "dest_airport": item.get("destination_airport"),
        "depart": dep_str,
        "return": ret_str,
        "trip": trip,
        "price": int(item["price"]),
        "currency": currency.upper(),
        "airline": code,
        "airline_name": AIRLINE.get(code, code),
        "flight_number": f"{code}{item.get('flight_number', '')}",
        "stops": int(item.get("transfers") or 0),
        "return_stops": None if one_way else int(item.get("return_transfers") or 0),
        "source": {
            "name": "Aviasales",
            "agency": item.get("gate"),
            "url": source_url(item["link"], marker),
        },
        "observed_on": obs.isoformat(),
        "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        # 過期日當日 23:59 HKT 為止
        "expires_at": datetime.combine(expires_on, datetime.max.time().replace(microsecond=0),
                                       tzinfo=HKT).astimezone(timezone.utc)
                      .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, "ok"


def build(token: str, marker: str = "", now: datetime = None) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(HKT).date()
    deals, stats = [], {}
    ages = []
    for origin, (currency, _) in ORIGINS.items():
        for dest in DESTS:
            for month in month_list(today, MONTHS_AHEAD):
                for one_way in (True, False):
                    best = None
                    for item in fetch(token, origin, dest, month, currency, one_way):
                        obs = observed_on(item.get("link", ""))
                        if obs:
                            ages.append((today - obs).days)
                        deal, why = to_deal(item, origin, dest, currency, one_way, now, marker)
                        stats[why] = stats.get(why, 0) + 1
                        if deal and (best is None or deal["price"] < best["price"]):
                            best = deal
                    if best:
                        best["month"] = month
                        deals.append(best)
                    time.sleep(0.15)
    deals.sort(key=lambda d: (d["origin"], d["dest"], d["trip"], d["depart"]))
    ages.sort()
    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_age_days": MAX_AGE_DAYS,
        "source_note": "Aviasales 用戶近期搜到嘅價格快取，唔係即時報價；實際以訂購頁為準。",
        "stats": {
            "kept": len(deals),
            "items": stats,
            "observed_age_days_p50": ages[len(ages) // 2] if ages else None,
            "observed_age_days_p90": ages[int(len(ages) * 0.9)] if ages else None,
        },
        "deals": deals,
    }


def main():
    token = os.environ["TRAVELPAYOUTS_TOKEN"].strip()
    marker = os.environ.get("TRAVELPAYOUTS_MARKER", "").strip()
    data = build(token, marker)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"✅ {OUT}：{data['stats']}")


if __name__ == "__main__":
    main()
