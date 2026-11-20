"""台北米其林 2026:每間店一頁 docs/places/taipei-michelin-2026/<編號>/index.html。

讀 docs/data/michelin_taipei_2026.json(先跑 build.py 才有 area / no),再合併:
  data/michelin_facts.json      官網地址、店家網站、暫時關閉
  data/michelin_prices.json     官網價位符號、可線上訂位
  data/michelin_editorial.json  OffDayz 自己寫的短評、必點、適合誰、訂位方式
  data/geo/taipei_base.json     街區插畫地圖封面的底圖與捷運站
照片只用店家 IG 貼文的官方嵌入:資料裡 ig_posts=[貼文網址...];沒有就放 Google 地圖相片連結。
也會把 blurb / price 寫回網頁資料,讓特輯頁卡片能顯示短評。
用法: python3 tools/michelin_map/build_pages.py
"""
import json, math, pathlib, html, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/data/michelin_taipei_2026.json"
SITE = "https://offdayz.sssuni.com"
BASE_DIR = ROOT / "docs/places/taipei-michelin-2026"
GUIDE = "https://guide.michelin.com/tw/zh_TW/taipei-region/taipei/restaurant/"
TIER = {
    "3": ("三星", "★★★", "#A8261A", "#fff"),
    "2": ("二星", "★★", "#D2482B", "#fff"),
    "1": ("一星", "★", "#E98A5F", "#fff"),
    "bib": ("必比登推介", "必比登", "#F2BC3D", "#26312E"),
}
TIER_NOTE = {"3": "值得專程造訪的料理", "2": "值得繞道前往的料理", "1": "高品質的料理", "bib": "價格親民、品質好的推介"}
BOOK = {"訂位": "建議先訂位，熱門時段常提前額滿", "排隊": "通常不接受訂位，現場排隊，避開正餐尖峰比較快",
        "現場": "多半可以直接去，假日用餐時段可能要等", "限定": "訂位或營業日不固定，出發前先看店家公告"}
PAPER, INK, MUTED, NAVY = "#FFFCF7", "#26312E", "#6E6459", "#1E4A45"
LAND_OUT, WATER, BORDER = "#EEE6D8", "#C9E0E3", "#D6C8B4"
COS = math.cos(math.radians(25.05))
esc = lambda s: html.escape(str(s or ""), quote=True)
f1 = lambda v: f"{v:.1f}"

# 九區的順路玩:吃完附近可以去哪,排成半天
ROUTES = {
    "sl": ("士林・天母・陽明山", [("士林官邸", "玫瑰園和溫室花房，散步很舒服"), ("天母商圈", "天母東路一帶小店和咖啡館多，適合慢逛"),
                            ("陽明山冷水坑・擎天崗", "上山的店吃完順遊，草原和步道半天剛好")]),
    "dz": ("大直・美麗華・內湖", [("美麗華摩天輪", "傍晚搭最漂亮，可以看到整片台北盆地"), ("劍潭山親山步道", "大約 30 分鐘爬到觀景台，看 101 夜景"),
                            ("大佳河濱公園", "沿基隆河騎腳踏車吹風")]),
    "dt": ("大稻埕・大同", [("迪化街", "南北貨、老洋樓和文創小店，一條街逛一下午"), ("霞海城隍廟", "求姻緣很有名的小廟"),
                       ("大稻埕碼頭", "黃昏看淡水河夕陽，貨櫃市集很熱鬧")]),
    "zs": ("中山・晶華一帶", [("赤峰街・中山站巷弄", "老五金行和選物店、咖啡館混在一起"), ("台北當代藝術館", "日治時期老校舍改成的美術館"),
                         ("心中山線形公園", "捷運上方的帶狀公園，晚上散步消化")]),
    "ss": ("松山・民生・南京復興", [("富錦街", "林蔭大道和小店，台北最好拍的街道之一"), ("民生社區", "老社區裡的咖啡館和公園，步調很慢"),
                            ("松山機場觀景台", "在市區看飛機起降")]),
    "zz": ("台北車站・中正", [("國立臺灣博物館", "二二八公園裡的百年古典建築"), ("北門・西區門戶", "清代城門和周邊老建築"),
                        ("中正紀念堂", "看儀隊交接，旁邊就是國家戲劇院和音樂廳")]),
    "wh": ("西門・萬華・南機場", [("龍山寺", "台北最有名的古廟，香火和建築都值得看"), ("剝皮寮歷史街區", "清代老街屋保存得很完整"),
                           ("西門町・紅樓", "逛街吃小吃，紅樓有文創市集")]),
    "da": ("大安・永康・東區", [("大安森林公園", "城市中央的大公園，飯後散步首選"), ("永康街・青田街", "小吃、茶館和日式老宿舍"),
                         ("東區巷弄", "忠孝敦化一帶的選物店和咖啡館")]),
    "xy": ("信義", [("台北 101 觀景台", "89 樓看整個台北，天氣好可以看很遠"), ("四四南村", "眷村老房子配 101，拍照很有反差"),
                   ("象山步道", "爬 20～30 分鐘看 101 夜景")]),
}


def dist_m(a, b):
    dy = (a["lat"] - b["lat"]) * 111000
    dx = (a["lon"] - b["lon"]) * 111000 * COS
    return math.hypot(dx, dy)


def walk(m):
    mins = max(1, round(m * 1.3 / 80))  # 直線×1.3≈實際路程,步速 80m/分
    return f"步行約 {mins} 分" if mins <= 25 else f"約 {m / 1000:.1f} km"


def chrome(feature_html):
    """從特輯頁拿 header/footer,路徑多退一層。"""
    head = feature_html[feature_html.index("<body>") + 6: feature_html.index('<main id="main"')]
    foot = feature_html[feature_html.index("<footer"): feature_html.index("</footer>") + 9]
    fix = lambda s: re.sub(r'href="((?:\.\./)+)', r'href="../\1', s)
    return fix(head), fix(foot)


# ---------- 街區插畫地圖封面 ----------
CW, CH = 1200, 560


def cover_svg(s, near, base, stations):
    # 經度寬度約 3.4 km,附近幾間米其林都進得來;山上的店離捷運遠,拉遠到看得到最近的站
    nearest = min(dist_m(s, {"lat": la, "lon": lo}) for la, lo in stations.values())
    span = 0.034 if nearest < 1500 else min(0.12, nearest * 2.6 / (111000 * COS))
    k = CW / (span * COS)
    lat0 = s["lat"] + (CH / 2) / k
    lon0 = s["lon"] - span / 2
    proj = lambda la, lo: ((lo - lon0) * COS * k, (lat0 - la) * k)
    s_, n_ = lat0 - CH / k, lat0
    w_, e_ = lon0, lon0 + span
    pad = 0.01
    vis = lambda la, lo: s_ - pad <= la <= n_ + pad and w_ - pad <= lo <= e_ + pad
    path = lambda pts, close: "M" + "L".join("{},{}".format(*map(f1, proj(la, lo))) for la, lo in pts) + ("Z" if close else "")
    g = [f'<rect width="{CW}" height="{CH}" fill="{LAND_OUT}"/>']
    for t in base["towns"]:
        rings = [r for r in t["rings"] if any(vis(*p) for p in r)]
        if not rings:
            continue
        tp = t["county"] == "台北市"
        g.append(f'<path d="{"".join(path(r, True) for r in t["rings"])}" fill="{PAPER if tp else LAND_OUT}" stroke="{BORDER}" stroke-width="2" stroke-dasharray="9 7"/>')
    water = [r for r in base["water"] if any(vis(*p) for p in r)]
    if water:
        g.append(f'<path d="{"".join(path(r, True) for r in water)}" fill="{WATER}" fill-rule="evenodd"/>')
    for wy in base["mrt"]["ways"]:
        if any(vis(*p) for p in wy["pts"]):
            g.append(f'<path d="{path(wy["pts"], False)}" fill="none" stroke="{base["mrt"]["colors"][wy["line"]]}" stroke-width="7" stroke-linecap="round" opacity=".5"/>')
    x, y = proj(s["lat"], s["lon"])
    tw_ = lambda txt, size: sum(size if ord(ch) > 0x2E80 else size * 0.58 for ch in txt)
    taken = [(x, y + 40, tw_(s["name"], 30)), (x, y - 30, 60)]  # 已放的字:(中心 x, y, 寬),避免疊字
    free_at = lambda cx, cy, w: all(abs(cx - tx) > (w + tw) / 2 + 6 or abs(cy - ty) > 26 for tx, ty, tw in taken)
    for name, (la, lo) in stations.items():
        if s_ < la < n_ and w_ < lo < e_:
            sx, sy = proj(la, lo)
            g.append(f'<rect x="{f1(sx - 7)}" y="{f1(sy - 7)}" width="14" height="14" rx="3" fill="#fff" stroke="{INK}" stroke-width="2.5"/>')
            lw = tw_(name + "站", 21)
            for dx, anc in ((13, "start"), (-13, "end")):
                cx = sx + dx + (lw / 2 if anc == "start" else -lw / 2)
                if free_at(cx, sy - 10, lw):
                    taken.append((cx, sy - 10, lw))
                    g.append(halo(sx + dx, sy - 10, name + "站", 21, INK, anchor=anc))
                    break
    for o in near:
        if not (s_ < o["lat"] < n_ and w_ < o["lon"] < e_):
            continue
        ox, oy = proj(o["lat"], o["lon"])
        _, _, c, t = TIER[o["tier"]]
        lw = tw_(o["name"], 17)
        free = free_at(ox, oy + 36, lw)
        if free:
            taken.append((ox, oy + 36, lw))
        g.append(f'<a href="../{o["no"]}/"><circle cx="{f1(ox)}" cy="{f1(oy)}" r="15" fill="{c}" stroke="#fff" stroke-width="3"/>'
                 f'<text x="{f1(ox)}" y="{f1(oy + 5.5)}" text-anchor="middle" font-size="15" font-weight="800" fill="{t}" font-family="Helvetica Neue,Arial,sans-serif">{o["no"]}</text>'
                 + (halo(ox, oy + 36, o["name"], 17, MUTED) if free else "") + "</a>")
    _, _, c, t = TIER[s["tier"]]
    g.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="62" fill="{c}" opacity=".16"/>')
    g.append(f'<path d="M{f1(x)},{f1(y)} c-8,-14 -24,-26 -24,-44 a24,24 0 1 1 48,0 c0,18 -16,30 -24,44z" fill="{c}" stroke="#fff" stroke-width="4"/>')
    g.append(f'<text x="{f1(x)}" y="{f1(y - 37)}" text-anchor="middle" font-size="19" font-weight="800" fill="{t}" font-family="Helvetica Neue,Arial,sans-serif">{s["no"]}</text>')
    g.append(halo(x, y + 40, s["name"], 30, INK, weight=900))
    # 比例尺
    m = 500 if span < 0.05 else 2000
    km = k / 111000 * m
    g.append(f'<path d="M{CW - 40 - km:.0f},{CH - 34}v8h{km:.0f}v-8" fill="none" stroke="{INK}" stroke-width="3"/>'
             f'<text x="{CW - 40}" y="{CH - 44}" text-anchor="end" font-size="17" font-weight="700" fill="{INK}">{m if m < 1000 else m // 1000} {"m" if m < 1000 else "km"}</text>')
    return (f'<svg viewBox="0 0 {CW} {CH}" role="img" aria-label="{esc(s["name"])} 附近街區地圖" '
            f'font-family="PingFang TC,Noto Sans TC,Heiti TC,sans-serif">{"".join(g)}</svg>')


def halo(x, y, txt, size, fill, weight=700, anchor="middle"):
    a = f'x="{f1(x)}" y="{f1(y)}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}"'
    return (f'<text {a} fill="none" stroke="{PAPER}" stroke-width="6" stroke-linejoin="round">{esc(txt)}</text>'
            f'<text {a} fill="{fill}">{esc(txt)}</text>')


CSS = """
    .rs-mast .dateline span:last-child{text-transform:none}
    .rs-hero{padding-top:8px}
    .rs-crumb{font:700 12px var(--type);letter-spacing:.06em;color:var(--muted);margin-bottom:12px}
    .rs-crumb a{color:var(--blue)}
    .rs-kicker{font:700 13px var(--type);letter-spacing:.18em;color:var(--coral);text-transform:uppercase;margin:0 0 10px}
    .rs-title{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
    .rs-no{display:inline-grid;place-items:center;min-width:46px;height:46px;padding:0 8px;border-radius:23px;font:800 20px/1 'Helvetica Neue',Arial,sans-serif}
    .rs-no.green{box-shadow:0 0 0 3px var(--paper),0 0 0 6px var(--good)}
    .rs-title h1{margin:0}
    .rs-en{font:italic 500 19px var(--serif);color:var(--muted);margin:6px 0 0}
    .rs-lead{font:500 19px/1.85 var(--serif-zh);color:var(--ink);max-width:680px;margin:18px 0 0;padding-left:16px;border-left:4px solid var(--c)}
    .rs-tags{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 0}
    .rs-tags span{font:700 13px var(--type);padding:4px 10px;border:1px solid var(--line);background:var(--paper)}
    .rs-tags .tier{color:var(--t);background:var(--c);border-color:var(--c)}
    .rs-tags .green{border-color:var(--good);color:var(--good)}
    .rs-tags .note{border-color:var(--coral);color:var(--coral)}
    .rs-closed{margin:18px 0 0;padding:12px 16px;background:#FBE9E3;border:1px solid var(--coral);color:#8E2F14;font-weight:700;font-size:14.5px}
    .rs-cover{margin:26px 0 0;border:1px solid var(--line);background:var(--paper);box-shadow:0 10px 30px rgba(38,49,46,.12)}
    .rs-cover{overflow:hidden}
    .rs-cover svg{display:block;width:100%;height:auto}
    .rs-cover figcaption{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px 14px;font:12px var(--type);color:var(--muted);border-top:1px solid var(--line)}
    .rs-grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:28px;align-items:start}
    @media(max-width:860px){.rs-grid{grid-template-columns:1fr}}
    .rs-order{list-style:none;margin:0;padding:0;counter-reset:o}
    .rs-order li{counter-increment:o;display:flex;gap:14px;align-items:baseline;padding:12px 0;border-bottom:1px dashed var(--line);font:900 18px/1.4 var(--serif-zh);color:var(--navy)}
    .rs-order li::before{content:counter(o,decimal-leading-zero);font:700 13px var(--type);color:var(--coral);letter-spacing:.08em}
    .rs-fit{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
    .rs-fit span{font:700 13px var(--type);padding:6px 12px;background:var(--lagoon-soft,#E6F1EC);color:var(--navy);border-radius:999px}
    .rs-info{background:var(--paper);border:1px solid var(--line);padding:18px 20px}
    .rs-info dl{display:grid;grid-template-columns:76px 1fr;gap:12px 12px;margin:0;font-size:14.5px;line-height:1.6}
    .rs-info dt{font:700 12px var(--type);color:var(--muted);letter-spacing:.06em;padding-top:3px}
    .rs-info dd{margin:0}
    .rs-info dd small{display:block;color:var(--muted);font-size:12.5px}
    .rs-info a{color:var(--blue);font-weight:700}
    .rs-btns{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}
    .rs-photos{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
    .rs-photos .instagram-media{min-width:0!important;margin:0!important}
    .rs-nophoto{padding:22px;border:1px dashed var(--line);background:var(--paper);color:var(--muted);line-height:1.8;font-size:14px}
    .rs-nophoto a{font-weight:700;color:var(--blue)}
    .rs-route{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
    .rs-route li{position:relative;padding:16px 16px 14px 54px;background:var(--paper);border:1px solid var(--line)}
    .rs-route li::before{content:attr(data-step);position:absolute;left:14px;top:14px;width:28px;height:28px;display:grid;place-items:center;border-radius:50%;background:var(--navy);color:#fff;font:800 13px 'Helvetica Neue',Arial,sans-serif}
    .rs-route b{display:block;font:900 17px/1.35 var(--serif-zh);color:var(--navy)}
    .rs-route span{display:block;margin-top:4px;font-size:13.5px;color:var(--muted);line-height:1.6}
    .rs-route .eat::before{background:var(--c)}
    .rs-near{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
    .rs-near a{display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--paper);border:1px solid var(--line);color:var(--ink)}
    .rs-near a:hover{border-color:var(--navy)}
    .rs-near .n{display:inline-grid;place-items:center;min-width:26px;height:26px;border-radius:13px;font:800 13px/1 'Helvetica Neue',Arial,sans-serif;flex:none}
    .rs-near b{font:900 15px/1.3 var(--serif-zh);color:var(--navy)}
    .rs-near small{display:block;font:12px var(--type);color:var(--muted)}
    .rs-sub{font:900 18px var(--serif-zh);color:var(--navy);margin:28px 0 12px}
    .rs-pager{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-top:36px;font:700 14px var(--type)}
    .rs-pager a{color:var(--blue)}
"""


def num(s, cls="rs-no"):
    _, _, c, t = TIER[s["tier"]]
    g = " green" if s.get("green") else ""
    return f'<span class="{cls}{g}" style="background:{c};color:{t}">{s["no"]}</span>'


def photos(s, gmap):
    posts = s.get("ig_posts") or []
    if posts:
        items = "".join(
            f'<blockquote class="instagram-media" data-instgrm-permalink="{esc(u)}" data-instgrm-version="14">'
            f'<a href="{esc(u)}" target="_blank" rel="noopener">在 Instagram 查看這則貼文</a></blockquote>' for u in posts)
        return (f'<div class="rs-photos">{items}</div>'
                '<p class="mi-src">照片為店家在 Instagram 公開的貼文，透過官方嵌入顯示，版權屬原作者。</p>'
                '<script async src="https://www.instagram.com/embed.js"></script>')
    ig = (f'・<a href="https://www.instagram.com/{esc(s["ig"])}/" target="_blank" rel="noopener">店家 Instagram @{esc(s["ig"])}</a>'
          if s.get("ig") else "")
    return (f'<div class="rs-nophoto">店家照片整理中。想先看菜色與環境：'
            f'<a href="{gmap}" target="_blank" rel="noopener">Google 地圖上的相片</a>{ig}</div>')


def page(s, shops, base, stations, head, foot):
    name, en = s["name"], s.get("en") or ""
    label, badge, c, t = TIER[s["tier"]]
    ed = s["_ed"]
    area_name, route = ROUTES[s["area"]]
    q = f"{name} {en} 台北市".strip()
    gmap = f"https://www.google.com/maps/search/?api=1&query={html.escape(q)}"
    others = sorted((o for o in shops if o is not s), key=lambda o: dist_m(s, o))
    near = others[:6]
    sts = sorted(((dist_m(s, {"lat": la, "lon": lo}), n) for n, (la, lo) in stations.items()))[:2]
    st_html = "".join(f'<div>{esc(n)}站 <small>{walk(d)}</small></div>' for d, n in sts) if sts[0][0] < 2000 else \
        f'<div>{esc(sts[0][1])}站 <small>{walk(sts[0][0])}，建議搭計程車或公車</small></div>'

    tags = [f'<span class="tier" style="--c:{c};--t:{t}">{label}</span>', f'<span>{esc(s["cuisine"])}</span>']
    if s.get("price"):
        tags.append(f'<span>{esc(s["price"])}</span>')
    if s.get("green"):
        tags.append('<span class="green">綠星</span>')
    if s.get("note"):
        tags.append(f'<span class="note">{esc(s["note"])}</span>')
    closed = ('<p class="rs-closed">米其林指南官網目前標示這間店「暫時關閉」，出發前請先確認是否已恢復營業。</p>'
              if s.get("closed") else "")
    addr = esc(s.get("address") or "台北市")
    book_txt = BOOK[ed["book"]] + ("；米其林官網上可以線上訂位" if s.get("bookable") else "")
    links = [f'<a href="{GUIDE}{s["slug"]}" target="_blank" rel="noopener">米其林指南</a>']
    if s.get("site"):
        links.insert(0, f'<a href="{esc(s["site"])}" target="_blank" rel="noopener">店家網站</a>')
    i = shops.index(s)
    prev_s, next_s = shops[i - 1] if i else None, shops[i + 1] if i + 1 < len(shops) else None
    near_html = "".join(
        f'<li><a href="../{o["no"]}/">{num(o, "n")}<span><b>{esc(o["name"])}</b>'
        f'<small>{TIER[o["tier"]][0]}・{esc(o["cuisine"])}・{walk(dist_m(s, o))}</small></span></a></li>' for o in near)
    # 半日行程:先吃這間,再接三個點;最後推薦附近一間不同類型的店當下一餐
    # 下一餐:1.5 km 內換個類型(星級↔必比登),沒有就挑最近的
    other_kind = next((o for o in others if dist_m(s, o) < 1500 and (o["tier"] == "bib") != (s["tier"] == "bib")), others[0])
    route_html = (f'<li class="eat" data-step="1"><b>吃 {esc(name)}</b><span>{esc(ed["order"][0])}</span></li>'
                  + "".join(f'<li data-step="{n + 2}"><b>{esc(a)}</b><span>{esc(b)}</span></li>' for n, (a, b) in enumerate(route))
                  + f'<li data-step="5"><b>下一餐：{esc(other_kind["name"])}</b><span>{TIER[other_kind["tier"]][0]}・{esc(other_kind["cuisine"])}・離這裡{walk(dist_m(s, other_kind))}'
                  f'　<a href="../{other_kind["no"]}/">看介紹 →</a></span></li>')
    desc = f"{name}{'（' + en + '）' if en else ''}：2026 台北米其林{label}，{s['cuisine']}。{ed['blurb']}"
    title = f"{name}｜台北米其林 2026 {label} · OffDayz"
    ld = json.dumps({"@context": "https://schema.org", "@type": "Restaurant", "name": name, "alternateName": en or None,
                     "servesCuisine": s["cuisine"], "address": "台北市" + (s.get("address") or ""), "priceRange": s.get("price"),
                     "geo": {"@type": "GeoCoordinates", "latitude": s["lat"], "longitude": s["lon"]},
                     "url": f"{SITE}/places/taipei-michelin-2026/{s['no']}/"}, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>☀️</text></svg>">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{SITE}/places/taipei-michelin-2026/{s['no']}/">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(ed['blurb'])}">
  <link rel="stylesheet" href="../../../assets/sosol.css">
  <link rel="stylesheet" href="../../../assets/magazine.css">
  <script type="application/ld+json">{ld}</script>
  <style>{CSS}</style>
</head>
<body>{head}<main id="main" class="column-main" style="--c:{c};--t:{t}">
<div class="column-masthead rs-mast"><div class="masthead"><a class="mast-logo" href="../../../">Off<i>Dayz</i></a><span class="issue">TAIPEI · MICHELIN 2026</span></div><div class="dateline"><span>No.{s['no']:02d}・{esc(area_name)}</span><span>{esc(en or name)}</span></div></div>
  <section class="hero page-hero rs-hero"><div class="shell">
    <div class="rs-crumb"><a href="../">台北米其林 2026，按區吃</a> ／ {esc(area_name)}</div>
    <p class="rs-kicker">{label}・{esc(s['cuisine'])}</p>
    <div class="rs-title">{num(s)}<h1>{esc(name)}</h1></div>
    {f'<p class="rs-en">{esc(en)}</p>' if en else ''}
    <p class="rs-lead">{esc(ed['blurb'])}</p>
    <div class="rs-tags">{''.join(tags)}</div>
    {closed}
    <figure class="rs-cover">{cover_svg(s, near, base, stations)}
      <figcaption><span>數字圓點是附近的其他米其林，點一下就能看介紹</span><span>OffDayz 自繪示意圖・底圖 © OpenStreetMap contributors</span></figcaption></figure>
  </div></section>

  <div class="shell">
    <div class="section rs-grid">
      <div>
        <div class="section-head"><h2 class="mag-heading"><span>01</span>點這些 <i>Must Order</i></h2></div>
        <ol class="rs-order">{''.join(f'<li>{esc(o)}</li>' for o in ed['order'])}</ol>
        <div class="rs-fit">{''.join(f'<span>適合{esc(f)}</span>' for f in ed['fit'])}</div>
      </div>
      <div>
        <div class="section-head"><h2 class="mag-heading"><span>02</span>出發前 <i>Before You Go</i></h2></div>
        <div class="rs-info">
          <dl>
            <dt>等級</dt><dd>{label}{'・綠星' if s.get('green') else ''}<small>{TIER_NOTE[s['tier']]}</small></dd>
            <dt>價位</dt><dd>{esc(s.get('price') or '—')}<small>米其林指南的價位標示，$ 最便宜、$$$$ 最貴</small></dd>
            <dt>訂位</dt><dd>{esc(book_txt)}</dd>
            <dt>捷運</dt><dd>{st_html}</dd>
            <dt>地址</dt><dd>台北市{addr}</dd>
            <dt>連結</dt><dd>{'・'.join(links)}</dd>
          </dl>
          <div class="rs-btns"><a class="btn btn-primary" href="{gmap}" target="_blank" rel="noopener">Google 地圖導航</a></div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-head"><h2 class="mag-heading"><span>03</span>菜色與環境 <i>Photos</i></h2></div>
      {photos(s, gmap)}
    </div>

    <div class="section">
      <div class="section-head"><h2 class="mag-heading"><span>04</span>順路玩半天 <i>Half-day Plan</i></h2></div>
      <ol class="rs-route">{route_html}</ol>
      <h3 class="rs-sub">附近還有這些米其林</h3>
      <ul class="rs-near">{near_html}</ul>
      <div class="rs-pager">
        {f'<a href="../{prev_s["no"]}/">← {prev_s["no"]}. {esc(prev_s["name"])}</a>' if prev_s else '<span></span>'}
        <a href="../#map">回到總覽地圖</a>
        {f'<a href="../{next_s["no"]}/">{next_s["no"]}. {esc(next_s["name"])} →</a>' if next_s else '<span></span>'}
      </div>
      <p class="mi-src" style="margin-top:30px">名單、地址與價位依《臺灣米其林指南 2026》官網整理，短評與行程是 OffDayz 自己寫的。營業時間與訂位方式常有變動，出發前請以店家公告為準。</p>
    </div>
  </div>
</main>
{foot}
<script src="../../../assets/site.js"></script>
</body>
</html>
"""


def build():
    d = json.load(open(DATA))
    facts = json.load(open(ROOT / "data/michelin_facts.json"))
    prices = json.load(open(ROOT / "data/michelin_prices.json"))
    edit = json.load(open(ROOT / "data/michelin_editorial.json"))
    base = json.load(open(ROOT / "data/geo/taipei_base.json"))
    stations = {("台北車站" if n == "台北車" else n): v for n, v in base["stations"].items()}
    shops = sorted(d["shops"], key=lambda s: s["no"])
    for s in shops:
        slug, addr, site, closed = facts[str(s["no"])]
        s.update(slug=slug, address=addr, site=site, closed=bool(closed),
                 price=prices[slug][0], bookable=bool(prices[slug][1]), blurb=edit[str(s["no"])]["blurb"])
        s.pop("verified", None)  # 地址已改用官網
        s["_ed"] = edit[str(s["no"])]
    head, foot = chrome((BASE_DIR / "index.html").read_text())
    for s in shops:
        out = BASE_DIR / str(s["no"]) / "index.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(page(s, shops, base, stations, head, foot))
    for s in shops:
        s.pop("_ed")
    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print(len(shops), "pages →", BASE_DIR)


if __name__ == "__main__":
    build()
