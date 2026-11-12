#!/usr/bin/env python3
"""放假去哪：假期窗口 × 目的地 靜態頁生成器。

讀 docs/data/ 的 holidays.json（假期）、regions.json（目的地）、
city_seasons.json（季節）、seasonal.json（季節活動），
為香港、台北出發各算出未來的連假窗口，每個窗口產生一頁：
  docs/offdays/<窗口id>/index.html
  docs/offdays/index.html（總表）
  docs/data/offdays.json（給首頁或之後的 Sona 發文日曆用）

一年跑一次就好（holidays.json 補上新一年的假期之後）：
  python3 tools/build_offdays.py            # 從今天起算
  python3 tools/build_offdays.py --today 2026-11-09
只用標準庫。不改任何既有資料 JSON。
"""
import argparse
import datetime as dt
import html
import json
import shutil
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DATA = DOCS / "data"
OUT = DOCS / "offdays"
SITE = "https://sssunwl.github.io/offdayz"

# 出發地：regions.json 的 home 代碼 → 假期代碼、機場、幣別
HOMES = {
    "HK": {"hol": "HK", "name": "香港", "airport": "HKG", "en": "Hong Kong", "curr": "HKD", "slug": "hk"},
    "TPE": {"hol": "TW", "name": "台北", "airport": "TPE", "en": "Taipei", "curr": "TWD", "slug": "tw"},
}

# 假期名稱 → (網址代號, 標題用名稱)。依序比對，先中先用。
HOLIDAY_NAMES = [
    ("小年夜", "cny", "春節"), ("除夕", "cny", "春節"), ("春節", "cny", "春節"), ("農曆", "cny", "農曆新年"),
    ("耶穌受難", "easter", "復活節"), ("復活", "easter", "復活節"),
    ("清明", "qingming", "清明"), ("兒童節", "qingming", "兒童節"),
    ("和平紀念", "228", "228"),
    ("勞動", "labour", "勞動節"), ("佛誕", "buddha", "佛誕"), ("端午", "duanwu", "端午"),
    ("特別行政區成立", "july1", "七一"), ("中秋", "midautumn", "中秋"), ("教師節", "teachers", "教師節"),
    ("國慶", "national", "國慶"), ("重陽", "chungyeung", "重陽"), ("光復", "retrocession", "光復節"),
    ("聖誕", "xmas", "聖誕"), ("行憲", "xmas", "聖誕"),
    ("元旦", "newyear", "元旦"), ("開國紀念", "newyear", "元旦"),
]

WEEKDAY = "一二三四五六日"
MAX_LEAVE = 4          # 最多建議請幾天假
BOOK_WEEKS = 8         # 出發前幾週開始訂（策略文件：6–8 週）


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def d(s):
    return dt.date.fromisoformat(s)


def fmt(day):
    return f"{day.month}/{day.day}（{WEEKDAY[day.weekday()]}）"


def fmt_range(a, b):
    if a == b:
        return f"{a.month}/{a.day}"
    return f"{a.month}/{a.day}–{b.month}/{b.day}" if a.year == b.year else f"{a:%Y/%-m/%-d}–{b:%Y/%-m/%-d}"


def esc(s):
    return html.escape(str(s), quote=True)


# ---------- 假期 ----------

def holiday_map(H, code):
    """{日期: (名稱, flag)}，半日假不算放假。"""
    out = {}
    for byc in H["years"].values():
        for row in byc.get(code, {}).get("holidays", []):
            flag = row[2] if len(row) > 2 else ""
            if flag == "half":
                continue
            out[d(row[0])] = (row[1], flag)
    return out


def status_of(H, code, year):
    return H["years"].get(str(year), {}).get(code, {}).get("status", "missing")


def peaks_of(H, codes):
    out = []
    for byc in H["years"].values():
        for c in codes:
            for p in byc.get(c, {}).get("peaks", []):
                out.append((d(p["from"]), d(p["to"]), p["label"], c))
    return sorted(set(out))


def workdays_of(H, code):
    """補班日（週六要上班）。"""
    out = set()
    for byc in H["years"].values():
        out.update(d(x) for x in byc.get(code, {}).get("workdays", []))
    return out


def name_of(holiday_names):
    slugs, titles = [], []
    for n in holiday_names:
        for key, slug, title in HOLIDAY_NAMES:
            if key in n:
                if title not in titles:
                    titles.append(title)
                if slug not in slugs:
                    slugs.append(slug)
                break
    # 標題依 HOLIDAY_NAMES 的順序排（「清明兒童節」而不是「兒童節清明」）
    order = [t for _, _, t in HOLIDAY_NAMES]
    titles.sort(key=order.index)
    return (slugs[0] if slugs else "holiday"), "".join(titles) or "連假"


def find_windows(H, home, today, last_day):
    """回傳窗口清單。每個窗口 = 一段含公眾假期的連續放假日，
    放假日 ≥ 3 天，或請 ≤ 2 天假可以變 ≥ 4 天。"""
    code = HOMES[home]["hol"]
    hol = holiday_map(H, code)
    work = workdays_of(H, code)

    def off(x):
        return x not in work and (x.weekday() >= 5 or x in hol)

    def run_around(x):
        a = b = x
        while off(a - dt.timedelta(1)):
            a -= dt.timedelta(1)
        while off(b + dt.timedelta(1)):
            b += dt.timedelta(1)
        return a, b

    seen, windows = set(), []
    for day in sorted(hol):
        if day < today or day > last_day or not off(day):
            continue
        a, b = run_around(day)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        days = (b - a).days + 1
        names = [hol[x][0] for x in sorted(hol) if a <= x <= b]
        leave = leave_options(a, b, off)
        best_short = next((o for o in leave if o["leave"] <= 2 and o["days"] >= 4), None)
        if days < 3 and not best_short:
            continue
        slug, title = name_of(names)
        estimated = any(hol[x][1] == "est" for x in hol if a <= x <= b) or \
            status_of(H, code, a.year) != "official"
        windows.append({
            "home": home, "start": a, "end": b, "days": days, "slug": slug, "title": title,
            "holidays": [(x, hol[x][0], hol[x][1]) for x in sorted(hol) if a <= x <= b],
            "leave": leave, "needs_leave": days < 3, "estimated": estimated,
            # 12/31 起的元旦連假算新的一年
            "year": b.year if slug == "newyear" else a.year,
        })
    # 同一年同名的窗口加序號（例如一年兩次「聖誕」不會發生，但保險）
    ids = {}
    for w in windows:
        base = f"{w['year']}-{w['slug']}-{HOMES[home]['slug']}"
        ids[base] = ids.get(base, 0) + 1
        w["id"] = base if ids[base] == 1 else f"{base}-{ids[base]}"
    return windows


def leave_options(a, b, off):
    """往前或往後連續請 k 天假（1..MAX_LEAVE），能接上別段假期就一起算。
    每個 k 只留總天數最多的一種，再只留「划算」的：總天數 ≥ 請假天數 × 2 + 1。"""
    best = {}
    for k in range(1, MAX_LEAVE + 1):
        for before in range(k + 1):
            after = k - before
            s, e = a, b
            ok = True
            for _ in range(before):
                s -= dt.timedelta(1)
                if off(s):  # 前面那天本來就放假，代表不是連續請假
                    ok = False
            for _ in range(after):
                e += dt.timedelta(1)
                if off(e):
                    ok = False
            if not ok:
                continue
            while off(s - dt.timedelta(1)):
                s -= dt.timedelta(1)
            while off(e + dt.timedelta(1)):
                e += dt.timedelta(1)
            total = (e - s).days + 1
            if k not in best or total > best[k]["days"]:
                leave_days = [x for x in (a - dt.timedelta(i + 1) for i in range(before))] + \
                             [x for x in (b + dt.timedelta(i + 1) for i in range(after))]
                best[k] = {"leave": k, "days": total, "start": s, "end": e, "leave_days": sorted(leave_days)}
    base = (b - a).days + 1
    opts = [o for o in best.values() if o["days"] > base and o["days"] >= o["leave"] * 2 + 1]
    # 天數一樣時只留請假最少的
    out, seen = [], set()
    for o in sorted(opts, key=lambda o: (o["leave"], -o["days"])):
        if o["days"] in seen:
            continue
        if out and o["days"] <= out[-1]["days"]:
            continue
        seen.add(o["days"])
        out.append(o)
    # 太多時留請最少的一個，加上放最長的兩個（橋接別段假期的通常在最後）
    return out if len(out) <= 3 else [out[0]] + out[-2:]


# ---------- 目的地評分 ----------

def overlaps(a, b, s, e):
    return a <= e and s <= b


def month_of(a, b):
    """窗口天數最多的月份。"""
    counts = {}
    x = a
    while x <= b:
        counts[x.month] = counts.get(x.month, 0) + 1
        x += dt.timedelta(1)
    return max(counts, key=lambda m: (counts[m], -m))


def season_note(season, month):
    for n in season.get("notes", []):
        if month in n["months"]:
            return n["text"]
    return ""


def score_cities(w, regions, seasons, events, H):
    home = w["home"]
    month = month_of(w["start"], w["end"])
    max_days = max([w["days"]] + [o["days"] for o in w["leave"]])
    picks = []
    for region in regions:
        if home not in region["home"]:
            continue
        dest_peaks = peaks_of(H, region["holiday_codes"] + region.get("crowd_from", []))
        dest_hols = {}
        for c in region["holiday_codes"]:
            dest_hols.update(holiday_map(H, c))
        for city in region["cities"]:
            hours = city["flight_hours"].get(home)
            season = seasons.get(city["id"])
            if hours is None or not season:
                continue
            need = city["min_days"]
            # 飛超過 3.5 小時的地方，3 天太趕
            if hours > 3.5:
                need = max(need, 4)
            fits_base = w["days"] >= need
            fit_leave = next((o for o in w["leave"] if o["days"] >= need), None)
            if not fits_base and not fit_leave:
                continue
            s = season["months"][str(month)]
            crowd = [p for p in dest_peaks if overlaps(w["start"], w["end"], p[0], p[1])]
            local = sorted({n for x, (n, _) in dest_hols.items() if w["start"] <= x <= w["end"]})
            evs = [e for e in events if month in e["months"] and any(
                dd.get("airport") in city["airports"] for dd in e.get("destinations", []))]
            score = s * 3 + (2 if fits_base else 0) - (3 if crowd else 0) - (1 if local and not crowd else 0)
            if w["days"] <= 3 and hours <= 3:
                score += 1
            if evs:
                score += 1
            picks.append({
                "region": region, "city": city, "hours": hours, "season": s, "month": month,
                "note": season_note(season, month), "en": season["en"],
                "fits_base": fits_base, "fit_leave": fit_leave, "need": need,
                "crowd": crowd, "local": local, "events": evs, "score": score,
            })
    picks.sort(key=lambda p: (-p["score"], p["hours"]))
    go = [p for p in picks if p["season"] >= 1 and not p["crowd"] and p["score"] >= 3][:5]
    if len(go) < 3:  # 選擇太少時，放寬到「擠但當季」
        go += [p for p in picks if p not in go and p["season"] >= 1][: 3 - len(go)]
    avoid = [p for p in picks if p not in go and (p["crowd"] or p["season"] == 0)]
    avoid.sort(key=lambda p: (-(p["season"] * 2 + (1 if p["crowd"] else 0)), p["hours"]))
    return go, avoid[:3], max_days


# ---------- 連結 ----------

def flight_url(home, p, a, b):
    h = HOMES[home]
    q = f"Flights from {h['en']} to {p['en']} on {a.isoformat()} through {b.isoformat()}"
    return "https://www.google.com/travel/flights?" + urlencode({"q": q, "hl": "zh-TW", "curr": h["curr"]}, quote_via=quote)


def hotel_url(p, a, b):
    return "https://www.booking.com/searchresults.zh-tw.html?" + urlencode({
        "ss": p["en"], "checkin": a.isoformat(), "checkout": b.isoformat(),
        "group_adults": 2, "no_rooms": 1, "group_children": 0,
    })


CITY_PAGES = {"tokyo", "seoul", "busan", "fukuoka", "taipei"}


# ---------- HTML ----------

def page_head(title, desc, canonical, depth):
    up = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>☀️</text></svg>">
  <title>{esc(title)} · OffDayz</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:type" content="article">
  <link rel="stylesheet" href="{up}assets/sosol.css">
  <link rel="stylesheet" href="{up}offdays/offdays.css">
  <link rel="stylesheet" href="{up}assets/magazine.css">
</head>
<body>
<a class="skip-link" href="#main">跳到主要內容</a>
<header class="site-header" id="hdr">
  <div class="shell nav">
    <a class="brand" href="{up}">Off<i>Dayz</i></a>
    <nav class="desktop-nav" aria-label="主要導覽">
      <a href="{up}">首頁</a>
      <a href="{up}offdays/" aria-current="page">放假去哪</a>
      <a href="{up}destinations/">目的地</a>
      <a href="{up}seasonal/">季節限定</a>
      <a href="{up}calendar/">假期年曆</a>
      
    </nav>
    <div class="nav-actions">
      <button class="icon-btn menu-btn" id="menuBtn" aria-label="選單" aria-controls="dropNav" aria-expanded="false">☰</button>
    </div>
  </div>
  <nav class="drop-nav shell" id="dropNav" aria-label="手機導覽" hidden>
    <a href="{up}">首頁</a><a href="{up}offdays/" aria-current="page">放假去哪</a>
    <a href="{up}destinations/">目的地</a><a href="{up}seasonal/">季節限定</a>
    <a href="{up}calendar/">假期年曆</a>
  </nav>
</header>
<main id="main" class="column-main">
<div class="column-masthead"><div class="masthead"><a class="mast-logo" href="{up}">Off<i>Dayz</i></a><span class="issue">HK · TPE DEPARTURES</span></div><div class="dateline"><span>P.02 放假去哪</span><span>Off Days</span></div></div>
"""


def page_foot(depth, updated):
    up = "../" * depth
    return f"""</main>
<footer class="site-footer">
  <div class="shell">
    <div class="footer-grid">
      <div class="footer-brand">
        <a class="brand" href="{up}">Off<i>Dayz</i></a>
        <p>放假，去哪？先看你什麼時候有假，再看這段假最適合去哪裡。</p>
      </div>
      <div class="footer-col"><strong>逛逛</strong>
        <a href="{up}offdays/">放假去哪</a><a href="{up}calendar/">假期年曆</a>
        <a href="{up}destinations/">目的地</a><a href="{up}seasonal/">季節限定</a>
      </div>
      <div class="footer-col"><strong>關於</strong>
        <a href="https://www.instagram.com/offdayz_/" target="_blank" rel="noopener">Instagram</a>
        <a href="https://www.threads.net/@offdayz_" target="_blank" rel="noopener">Threads</a>
        <a href="{up}calendar/">假期資料來源</a>
      </div>
    </div>
    <div class="footer-base"><span>假期資料依官方公告整理，頁面更新：{esc(updated)}</span><span>假期依政府公告整理，出發前請再核對官方日期</span></div>
  </div>
</footer>
<script src="{up}assets/site.js"></script>
<script src="{up}offdays/offdays.js"></script>
</body>
</html>
"""


def chip(text, kind=""):
    return f'<span class="od-chip{" od-chip-" + kind if kind else ""}">{esc(text)}</span>'


def window_heading(w):
    home = HOMES[w["home"]]
    return f"{w['year']} {w['title']}連假 {w['days']} 天，去哪？", f"從{home['name']}出發"


def short_heading(w):
    if w["needs_leave"]:
        o = next(o for o in w["leave"] if o["days"] >= 4)
        return f"{w['year']} {w['title']}：請 {o['leave']} 天變 {o['days']} 天"
    return f"{w['year']} {w['title']}連假 {w['days']} 天"


def render_city(p, w, home):
    r, c = p["region"], p["city"]
    chips = [chip(f"飛約 {p['hours']:g} 小時")]
    if p["fits_base"]:
        chips.append(chip(f"{w['days']} 天剛好" if w["days"] - p["need"] <= 1 else f"{w['days']} 天玩得從容", "good"))
    else:
        o = p["fit_leave"]
        chips.append(chip(f"要請 {o['leave']} 天假才夠", "warn"))
    chips.append(chip({2: "正當季", 1: "季節還可以", 0: "不是好季節"}[p["season"]], {2: "good", 1: "", 0: "bad"}[p["season"]]))
    if p["crowd"]:
        chips.append(chip("撞到" + "、".join(sorted({x[2] for x in p["crowd"]})), "bad"))
    elif p["local"]:
        chips.append(chip("當地放假：" + "、".join(p["local"][:2]), "warn"))
    else:
        chips.append(chip("當地沒放假", "good"))
    a, b = w["start"], w["end"]
    if not p["fits_base"]:
        a, b = p["fit_leave"]["start"], p["fit_leave"]["end"]
    ev = ""
    if p["events"]:
        ev = '<p class="od-ev">這段時間有：' + "、".join(
            f'<a href="../../seasonal/">{esc(e["icon"])} {esc(e["title"])}</a>' for e in p["events"][:2]) + "</p>"
    note = f'<p class="od-note">{esc(p["month"])} 月：{esc(p["note"])}</p>' if p["note"] else ""
    extra = f'<p class="od-note">{esc(c["note"])}</p>' if c.get("note") else ""
    guide = f'<a class="od-link" href="../../destinations/city.html?key={c["id"]}">城市指南</a>' if c["id"] in CITY_PAGES else ""
    return f"""<article class="card od-city" data-need-leave="{'0' if p['fits_base'] else '1'}">
  <div class="od-city-head"><span class="city-tag">{esc(r['name'])}</span><h3>{esc(c['name'])}</h3></div>
  <div class="od-chips">{''.join(chips)}</div>
  {note}{extra}{ev}
  <div class="od-links">
    <a class="btn btn-primary od-book" data-kind="flight" href="{esc(flight_url(home, p, a, b))}" target="_blank" rel="noopener">查機票 {fmt_range(a, b)}</a>
    <a class="btn btn-ghost od-book" data-kind="hotel" href="{esc(hotel_url(p, a, b))}" target="_blank" rel="noopener">查酒店</a>
    {guide}
  </div>
</article>"""


def render_days(w, peaks_home):
    """窗口（含請假版）逐日條。"""
    span_a = min([w["start"]] + [o["start"] for o in w["leave"][:1]])
    span_b = max([w["end"]] + [o["end"] for o in w["leave"][:1]])
    hol = {x: n for x, n, _ in w["holidays"]}
    leave = set(w["leave"][0]["leave_days"]) if w["leave"] else set()
    cells = []
    x = span_a
    while x <= span_b:
        if x in hol:
            cls, tag = "hol", hol[x]
        elif x in leave:
            cls, tag = "leave", "請假"
        elif x.weekday() >= 5:
            cls, tag = "wkd", "週末"
        else:
            cls, tag = "off", ""
        if w["start"] <= x <= w["end"] and cls != "hol":
            cls = "wkd"
        cells.append(f'<li class="od-day od-{cls}"><b>{x.month}/{x.day}</b><span>{WEEKDAY[x.weekday()]}</span><em>{esc(tag)}</em></li>')
        x += dt.timedelta(1)
    return '<ol class="od-days">' + "".join(cells) + "</ol>"


def render_window(w, go, avoid, today, updated, nav):
    home = HOMES[w["home"]]
    h1, sub = window_heading(w)
    if w["needs_leave"]:
        o = next(o for o in w["leave"] if o["days"] >= 4)
        h1 = f"{w['year']} {w['title']}請 {o['leave']} 天變 {o['days']} 天，去哪？"
    book_by = w["start"] - dt.timedelta(weeks=BOOK_WEEKS)
    if book_by > today:
        book = f"建議 {fmt(book_by)} 前開始訂機票。出發前 6–8 週是大多數人下訂的時候，再晚好的航班時段會先賣完。"
    else:
        book = "已經進入訂票期，連假機位通常越晚越貴，決定了就早點訂。"
    leave_html = ""
    if w["leave"]:
        rows = "".join(
            f'<li><button type="button" class="od-leave" data-start="{o["start"]}" data-end="{o["end"]}">'
            f'請 {o["leave"]} 天（{"、".join(f"{x.month}/{x.day}" for x in o["leave_days"])}）→ 放 {o["days"]} 天'
            f'<small>{fmt(o["start"])}–{fmt(o["end"])}</small></button></li>' for o in w["leave"])
        leave_html = f"""<section class="section shell od-block">
  <div class="section-head"><div><span class="eyebrow">Take Leave</span><h2>請假拼長假</h2>
  <p>點一個方案，下面的機票、酒店連結會換成那段日期。</p></div></div>
  <ul class="od-leaves">{('' if w["needs_leave"] else f'<li><button type="button" class="od-leave on" data-start="{w["start"]}" data-end="{w["end"]}">不請假 → 放 {w["days"]} 天<small>{fmt(w["start"])}–{fmt(w["end"])}</small></button></li>')}{rows}</ul>
</section>"""
    crowd_home = ""
    if w["home_peaks"]:
        crowd_home = '<p class="od-warn">這段是' + "、".join(esc(p[2]) for p in w["home_peaks"]) + \
            f"，{home['name']}出發的人很多，機票和酒店都會比平常貴。</p>"
    est = '<p class="od-warn">部分假期是預估日期，官方公布後會更新。</p>' if w["estimated"] else ""
    hol_list = "、".join(f"{x.month}/{x.day} {n}" for x, n, _ in w["holidays"])
    picks = "".join(render_city(p, w, w["home"]) for p in go)
    avoid_html = ""
    if avoid:
        items = "".join(
            f'<li><b>{esc(p["city"]["name"])}</b>：' + "；".join(
                ([("撞到" + "、".join(sorted({x[2] for x in p["crowd"]})))] if p["crowd"] else []) +
                ([f"{p['month']} 月{p['note']}"] if p["season"] == 0 and p["note"] else [])) + "</li>"
            for p in avoid)
        avoid_html = f"""<section class="section shell od-block">
  <div class="section-head"><div><span class="eyebrow">Skip</span><h2>這段時間先別去</h2></div></div>
  <ul class="od-avoid">{items}</ul>
</section>"""
    other = HOMES["TPE" if w["home"] == "HK" else "HK"]
    twin = nav.get("twin")
    twin_html = f'<a class="section-link" href="../{twin["id"]}/">看{other["name"]}出發的版本 →</a>' if twin else ""
    prev_next = "".join(
        f'<a class="od-pn" href="../{x["id"]}/"><small>{label}</small>{esc(short_heading(x))}</a>'
        for label, x in (("上一個假期", nav.get("prev")), ("下一個假期", nav.get("next"))) if x)
    desc = f"{home['name']}出發，{fmt(w['start'])}到{fmt(w['end'])}共 {w['days']} 天。" + \
        "推薦：" + "、".join(p["city"]["name"] for p in go) + "。附請假方案、當地擠不擠和當季提醒。"
    canonical = f"{SITE}/offdays/{w['id']}/"
    if w["needs_leave"]:
        lead = f"{hol_list}，前後接不上週末，只放 {w['days']} 天。請假才拼得出連假，方案在下面。"
    else:
        lead = f"{fmt(w['start'])}–{fmt(w['end'])}，共 {w['days']} 天。{hol_list}。"
    body = f"""<section class="hero page-hero"><div class="shell">
  <a class="section-link" href="../">← 所有假期</a>
  <div class="eyebrow">{esc(sub)}</div>
  <h1>{esc(h1)}</h1>
  <div class="hero-lead">{esc(lead)}</div>
  {crowd_home}{est}
  <div class="hero-cta"><a class="btn btn-sun" href="../../calendar/">📅 打開假期年曆</a></div>
  {twin_html}
</div></section>

<section class="section shell od-block">
  <div class="section-head"><div><span class="eyebrow">Dates</span><h2>這段假期的日子</h2></div></div>
  {render_days(w, w['home_peaks'])}
  <p class="od-book-tip">⏰ {esc(book)}</p>
</section>
{leave_html}
<section class="section shell od-block">
  <div class="section-head"><div><span class="eyebrow">Where to go</span><h2>這段假期去哪</h2>
  <p>依天數、季節、當地有沒有放假排序。「查機票」「查酒店」會用這段日期即時查價。</p></div></div>
  <div class="card-grid od-grid">{picks}</div>
</section>
{avoid_html}
<section class="section shell od-block"><nav class="od-pns" aria-label="其他假期">{prev_next}</nav></section>
"""
    return page_head(h1, desc, canonical, 2) + body + page_foot(2, updated)


def render_index(by_home, today, updated):
    blocks = []
    for home, ws in by_home.items():
        h = HOMES[home]
        rows = []
        for w in ws:
            n = len(w["go"])
            badge = chip("預估", "warn") if w["estimated"] else ""
            leave = ""
            if w["leave"]:
                o = max(w["leave"], key=lambda o: (o["days"], -o["leave"]))
                leave = f'<span class="od-row-leave">請 {o["leave"]} 天 → {o["days"]} 天</span>'
            rows.append(f"""<a class="od-row" href="{w['id']}/">
  <span class="od-row-date">{fmt_range(w['start'], w['end'])}</span>
  <span class="od-row-title">{esc(short_heading(w))}{badge}</span>
  <span class="od-row-picks">{esc('、'.join(p['city']['name'] for p in w['go'][:3]))}{' 等 ' + str(n) + ' 個' if n > 3 else ''}</span>
  {leave}
</a>""")
        blocks.append(f'<section class="section shell od-home" data-home="{h["slug"]}"><div class="od-rows">{"".join(rows)}</div></section>')
    nxt = {home: ws[0] for home, ws in by_home.items() if ws}
    body = f"""<section class="hero page-hero"><div class="shell">
  <div class="eyebrow">Off Days</div>
  <h1>放假，去哪？</h1>
  <div class="hero-lead">每段連假一頁：幾天、要不要請假、哪裡正當季、哪裡當地也在放假。</div>
  <div class="toggle od-toggle" role="group" aria-label="出發地">
    <button type="button" data-home="hk" class="on">從香港出發</button>
    <button type="button" data-home="tw">從台北出發</button>
  </div>
  {''.join(f'<p class="od-next" data-home="{HOMES[k]["slug"]}">下一個：<a href="{v["id"]}/">{esc(short_heading(v))}</a>（{fmt(v["start"])}）</p>' for k, v in nxt.items())}
</div></section>
{''.join(blocks)}
"""
    desc = "香港、台北出發的連假攻略：每段假期幾天、怎麼請假、去哪裡剛好。"
    return page_head("放假，去哪？", desc, f"{SITE}/offdays/", 1) + body + page_foot(1, updated)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", help="起算日 YYYY-MM-DD，預設今天")
    args = ap.parse_args()
    today = d(args.today) if args.today else dt.date.today()

    H = load("holidays.json")
    regions = load("regions.json")["regions"]
    seasons = load("city_seasons.json")["cities"]
    events = load("seasonal.json")["events"]
    last_year = max(int(y) for y in H["years"])
    last_day = dt.date(last_year, 12, 31)

    by_home = {}
    for home in HOMES:
        ws = find_windows(H, home, today, last_day)
        hp = peaks_of(H, [HOMES[home]["hol"]])
        for w in ws:
            w["go"], w["avoid"], _ = score_cities(w, regions, seasons, events, H)
            w["home_peaks"] = [p for p in hp if overlaps(w["start"], w["end"], p[0], p[1])]
        by_home[home] = ws

    if OUT.exists():
        for child in OUT.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
    OUT.mkdir(parents=True, exist_ok=True)
    updated = today.isoformat()

    for home, ws in by_home.items():
        other = by_home["TPE" if home == "HK" else "HK"]
        for i, w in enumerate(ws):
            twin = next((x for x in other if x["slug"] == w["slug"] and x["year"] == w["year"]), None)
            nav = {"prev": ws[i - 1] if i else None, "next": ws[i + 1] if i + 1 < len(ws) else None, "twin": twin}
            page = OUT / w["id"] / "index.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(render_window(w, w["go"], w["avoid"], today, updated, nav), encoding="utf-8")
    (OUT / "index.html").write_text(render_index(by_home, today, updated), encoding="utf-8")

    summary = {
        "_meta": {"generated_on": updated, "note": "tools/build_offdays.py 產生，不要手改。"},
        "windows": [{
            "id": w["id"], "home": home, "start": w["start"].isoformat(), "end": w["end"].isoformat(),
            "days": w["days"], "title": w["title"], "estimated": w["estimated"],
            "book_by": (w["start"] - dt.timedelta(weeks=BOOK_WEEKS)).isoformat(),
            "leave": [{"leave": o["leave"], "days": o["days"], "start": o["start"].isoformat(),
                       "end": o["end"].isoformat()} for o in w["leave"]],
            "picks": [p["city"]["id"] for p in w["go"]],
            "avoid": [p["city"]["id"] for p in w["avoid"]],
            "url": f"offdays/{w['id']}/",
        } for home, ws in by_home.items() for w in ws],
    }
    (DATA / "offdays.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    total = sum(len(ws) for ws in by_home.values())
    print(f"已產生 {total} 個假期頁（香港 {len(by_home['HK'])}、台北 {len(by_home['TPE'])}）→ docs/offdays/")


if __name__ == "__main__":
    main()
