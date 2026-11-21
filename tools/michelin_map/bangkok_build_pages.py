"""曼谷米其林 2026:每間店一頁 docs/places/bangkok-michelin-2026/<編號>/index.html。台北版是 build_pages.py,版型共用。

讀 docs/data/michelin_bangkok_2026.json(先跑 bangkok_build.py 才有 area / no),再合併:
  data/michelin_bangkok_editorial.json  OffDayz 自己寫的短評、必點、適合誰、訂位方式
  data/geo/bangkok_base.json            街區插畫地圖封面的底圖與 BTS/MRT 站
照片先放 Google 地圖相片連結;資料裡有 ig_posts=[貼文網址...] 就改成 IG 官方嵌入(之後補)。
用法: python3 tools/michelin_map/bangkok_build_pages.py
"""
import json, math, pathlib, html
from build_pages import TIER, TIER_NOTE, BOOK, CSS, PAPER, INK, MUTED, LAND_OUT, WATER, BORDER, esc, f1, chrome, halo, num, photos

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/data/michelin_bangkok_2026.json"
SITE = "https://offdayz.sssuni.com"
BASE_DIR = ROOT / "docs/places/bangkok-michelin-2026"
GUIDE = "https://guide.michelin.com/th/en/{region}/restaurant/{slug}"
COS = math.cos(math.radians(13.75))

# 十一區的順路玩:吃完附近可以去哪,排成半天
ROUTES = {
    "nb": [("恰圖恰週末市集", "週六日才開，上萬個攤位，早上去比較涼"), ("暖武里碼頭", "老市場加河景，回程可以搭昭披耶河公船進市區"),
           ("格叻島 Ko Kret", "河中小島，孟族陶器和週末小吃市集")],
    "ds": [("大理石寺 Wat Benchamabophit", "白色大理石佛寺，早上光線最好拍"), ("勝利紀念碑船麵巷", "一碗小小的船麵，幾碗一起點才夠"),
           ("阿里 Ari 巷弄", "BTS Ari 站周邊的咖啡館和小店，步調很慢")],
    "ok": [("大皇宮・玉佛寺", "曼谷必去，記得穿過膝褲裝、早點到"), ("臥佛寺 Wat Pho", "46 公尺的金色臥佛，寺裡還有泰式按摩學校"),
           ("考山路・蘭布里路", "晚上最熱鬧的背包客街，小酒吧一間接一間")],
    "cn": [("耀華力路", "入夜霓虹招牌全亮，整條街都是小吃攤"), ("Talat Noi 老巷", "老宅、汽車零件行和塗鴉牆混在一起，很好拍"),
           ("River City 河城", "河邊的古董與藝廊商場，有免費接駁船")],
    "tb": [("鄭王廟 Wat Arun", "黃昏從對岸看最美，搭渡輪一下就到"), ("ICONSIAM", "河岸大型商場，地下一樓是室內水上市場"),
           ("Talat Phlu 老市場", "吞武里的老社區市場，小吃很多")],
    "rv": [("昭披耶河公船", "從 Sathorn 碼頭上船，一路看河岸寺廟到老城"), ("Asiatique 河濱夜市", "傍晚去，夜市加摩天輪，有免費接駁船"),
           ("東方文華下午茶", "百年老飯店的作家沙龍，吃一套泰式下午茶")],
    "sr": [("倫披尼公園", "市中心的大公園，常常看得到大蜥蜴在草地散步"), ("MahaNakhon SkyWalk", "78 樓玻璃地板，看整個曼谷天際線"),
           ("帕蓬夜市・是隆路", "晚上逛街吃宵夜，人很多要顧好包包")],
    "sm": [("金湯普森之家", "泰絲大王的柚木老宅，有導覽"), ("四面佛 Erawan Shrine", "鬧區裡香火最旺的神壇，常有還願舞"),
           ("曼谷藝術文化中心 BACC", "免費入場的當代藝術館，就在 BTS 國家體育館站旁")],
    "sk": [("Benjakitti 森林公園", "高架步道穿過濕地，傍晚散步最舒服"), ("EmQuartier・Emporium", "Phrom Phong 站的百貨，吹冷氣逛街"),
           ("通羅・伊卡邁巷弄", "咖啡館、選物店和小酒吧，晚上很熱鬧")],
    "ws": [("塔林燦水上市場", "週末才開，在河邊浮台上吃海鮮"), ("Khlong Bangkok Noi 長尾船", "包船遊運河，看兩岸高腳屋和寺廟"),
           ("皇家遊船博物館", "收藏泰王典禮用的金色長船")],
    "es": [("拉瑪九世公園", "曼谷最大的公園，有泰式庭園和湖"), ("Saen Saep 運河快船", "從 Bang Kapi 搭運河船進市區，便宜又不塞車"),
           ("Seacon Square", "大型商場，下雨天的好去處")],
}


def dist_m(a, b):
    dy = (a["lat"] - b["lat"]) * 111000
    dx = (a["lon"] - b["lon"]) * 111000 * COS
    return math.hypot(dx, dy)


def walk(m):
    mins = max(1, round(m * 1.3 / 80))  # 直線×1.3≈實際路程,步速 80m/分
    return f"步行約 {mins} 分" if mins <= 25 else f"約 {m / 1000:.1f} km"


def st_name(n, kind):
    return f"{kind} {n}"


# ---------- 街區插畫地圖封面 ----------
CW, CH = 1200, 560


def cover_svg(s, near, base, stations):
    nearest = min(dist_m(s, {"lat": la, "lon": lo}) for la, lo, _ in stations.values())
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
    for d in base["districts"]:
        if not any(vis(*p) for r in d["rings"] for p in r):
            continue
        g.append(f'<path d="{"".join(path(r, True) for r in d["rings"])}" fill="{PAPER if d["prov"] == "Bangkok" else LAND_OUT}" stroke="{BORDER}" stroke-width="2" stroke-dasharray="9 7"/>')
    canals = [c for c in base["canals"] if any(vis(*p) for p in c)]
    if canals:
        g.append(f'<path d="{"".join(path(c, False) for c in canals)}" fill="none" stroke="{WATER}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>')
    water = [r for r in base["water"] if any(vis(*p) for p in r)]
    if water:
        g.append(f'<path d="{"".join(path(r, True) for r in water)}" fill="{WATER}" fill-rule="evenodd"/>')
    for wy in base["rail"]["ways"]:
        if not wy["line"].startswith("SRT") and any(vis(*p) for p in wy["pts"]):
            g.append(f'<path d="{path(wy["pts"], False)}" fill="none" stroke="{base["rail"]["colors"][wy["line"]]}" stroke-width="7" stroke-linecap="round" opacity=".5"/>')
    x, y = proj(s["lat"], s["lon"])
    tw_ = lambda txt, size: sum(size if ord(ch) > 0x2E80 else size * 0.58 for ch in txt)
    taken = [(x, y + 40, tw_(s["name"], 30)), (x, y - 30, 60)]  # 已放的字:(中心 x, y, 寬),避免疊字
    free_at = lambda cx, cy, w: all(abs(cx - tx) > (w + tw) / 2 + 6 or abs(cy - ty) > 26 for tx, ty, tw in taken)
    for name, (la, lo, kind) in stations.items():
        if s_ < la < n_ and w_ < lo < e_:
            sx, sy = proj(la, lo)
            if kind.startswith("MRT"):
                g.append(f'<circle cx="{f1(sx)}" cy="{f1(sy)}" r="8" fill="#fff" stroke="{INK}" stroke-width="2.5"/>')
            else:
                g.append(f'<rect x="{f1(sx - 7)}" y="{f1(sy - 7)}" width="14" height="14" rx="3" fill="#fff" stroke="{INK}" stroke-width="2.5"/>')
            lbl = st_name(name, kind)
            lw = tw_(lbl, 21)
            for dx, dy, anc in ((13, -10, "start"), (-13, -10, "end"), (13, 28, "start"), (-13, 28, "end")):
                cx = sx + dx + (lw / 2 if anc == "start" else -lw / 2)
                if 8 < cx - lw / 2 and cx + lw / 2 < CW - 8 and free_at(cx, sy + dy, lw):  # 不讓站名被切掉
                    taken.append((cx, sy + dy, lw))
                    g.append(halo(sx + dx, sy + dy, lbl, 21, INK, anchor=anc))
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
    m = 500 if span < 0.05 else 2000
    km = k / 111000 * m
    g.append(f'<path d="M{CW - 40 - km:.0f},{CH - 34}v8h{km:.0f}v-8" fill="none" stroke="{INK}" stroke-width="3"/>'
             f'<text x="{CW - 40}" y="{CH - 44}" text-anchor="end" font-size="17" font-weight="700" fill="{INK}">{m if m < 1000 else m // 1000} {"m" if m < 1000 else "km"}</text>')
    return (f'<svg viewBox="0 0 {CW} {CH}" role="img" aria-label="{esc(s["name"])} 附近街區地圖" '
            f'font-family="PingFang TC,Noto Sans TC,Heiti TC,sans-serif">{"".join(g)}</svg>')


def page(s, shops, areas, base, stations, head, foot):
    name, th, zh = s["name"], s["th"], s.get("zh")
    label, badge, c, t = TIER[s["tier"]]
    ed = s["_ed"]
    area_name, route = areas[s["area"]], ROUTES[s["area"]]
    city = "Nonthaburi" if s["province"] == "Nonthaburi" else "Bangkok"
    gmap = f"https://www.google.com/maps/search/?api=1&query={html.escape(name + ' ' + city)}"
    others = sorted((o for o in shops if o is not s), key=lambda o: dist_m(s, o))
    near = others[:6]
    sts = sorted((dist_m(s, {"lat": la, "lon": lo}), n, kind) for n, (la, lo, kind) in stations.items())[:2]
    st_html = "".join(f'<div>{esc(st_name(n, k))} 站 <small>{walk(d)}</small></div>' for d, n, k in sts if d < 2000) if sts[0][0] < 2000 else \
        f'<div>{esc(st_name(sts[0][1], sts[0][2]))} 站 <small>{walk(sts[0][0])}，建議搭 Grab 或計程車</small></div>'
    tags = [f'<span class="tier" style="--c:{c};--t:{t}">{label}</span>', f'<span>{esc(s["cuisine"])}</span>']
    if s.get("price"):
        tags.append(f'<span>{esc(s["price"])}</span>')
    if s["province"] == "Nonthaburi":
        tags.append('<span class="note">暖武里府</span>')
    closed = ('<p class="rs-closed">米其林指南官網目前標示這間店「暫時關閉」，出發前請先確認是否已恢復營業。</p>'
              if s.get("closed") else "")
    book_txt = BOOK[ed["book"]] + ("；米其林官網上可以線上訂位" if s.get("bookable") else "")
    if ed["book"] == "限定" and not s.get("bookable"):
        book_txt = "訂位方式比較特別（只收社群私訊或要先打電話預訂菜色），出發前先看店家公告"
    region = "nonthaburi-region/nonthaburi" if city == "Nonthaburi" else "bangkok-region/bangkok"
    links = [f'<a href="{GUIDE.format(region=region, slug=s["slug"])}" target="_blank" rel="noopener">米其林指南</a>']
    if s.get("site"):
        links.insert(0, f'<a href="{esc(s["site"])}" target="_blank" rel="noopener">店家網站</a>')
    i = shops.index(s)
    prev_s, next_s = shops[i - 1] if i else None, shops[i + 1] if i + 1 < len(shops) else None
    near_html = "".join(
        f'<li><a href="../{o["no"]}/">{num(o, "n")}<span><b>{esc(o["name"])}</b>'
        f'<small>{TIER[o["tier"]][0]}・{esc(o["cuisine"])}・{walk(dist_m(s, o))}</small></span></a></li>' for o in near)
    # 下一餐:1.5 km 內換個類型(星級↔必比登),沒有就挑最近的
    other_kind = next((o for o in others if dist_m(s, o) < 1500 and (o["tier"] == "bib") != (s["tier"] == "bib")), others[0])
    route_html = (f'<li class="eat" data-step="1"><b>吃 {esc(name)}</b><span>{esc(ed["order"][0])}</span></li>'
                  + "".join(f'<li data-step="{n + 2}"><b>{esc(a)}</b><span>{esc(b)}</span></li>' for n, (a, b) in enumerate(route))
                  + f'<li data-step="5"><b>下一餐：{esc(other_kind["name"])}</b><span>{TIER[other_kind["tier"]][0]}・{esc(other_kind["cuisine"])}・離這裡{walk(dist_m(s, other_kind))}'
                  f'　<a href="../{other_kind["no"]}/">看介紹 →</a></span></li>')
    alt = th + (f"・{zh}" if zh else "")
    desc = f"{name}（{alt}）：2026 曼谷米其林{label}，{s['cuisine']}。{ed['blurb']}"
    title = f"{name}｜曼谷米其林 2026 {label} · OffDayz"
    url = f"{SITE}/places/bangkok-michelin-2026/{s['no']}/"
    ld = json.dumps({"@context": "https://schema.org", "@type": "Restaurant", "name": name, "alternateName": [a for a in (th, zh) if a],
                     "servesCuisine": s["cuisine_en"], "address": s["address"], "priceRange": s.get("price"),
                     "geo": {"@type": "GeoCoordinates", "latitude": s["lat"], "longitude": s["lon"]}, "url": url}, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>☀️</text></svg>">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{url}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(ed['blurb'])}">
  <meta property="og:image" content="{SITE}/places/bangkok-michelin-2026/map.png">
  <link rel="stylesheet" href="../../../assets/sosol.css">
  <link rel="stylesheet" href="../../../assets/magazine.css">
  <script type="application/ld+json">{ld}</script>
  <style>{CSS}    .rs-th{{font:500 17px var(--type);color:var(--muted);margin:6px 0 0}}
    .column-masthead .dateline span:last-child{{text-transform:none}}
  </style>
</head>
<body>{head}<main id="main" class="column-main" style="--c:{c};--t:{t}">
<div class="column-masthead"><div class="masthead"><a class="mast-logo" href="../../../">Off<i>Dayz</i></a><span class="issue">BANGKOK · MICHELIN 2026</span></div><div class="dateline"><span>P.04 No.{s['no']:02d}・{esc(area_name)}</span><span>{esc(th)}</span></div></div>
  <section class="hero page-hero rs-hero"><div class="shell">
    <div class="rs-crumb"><a href="../">曼谷米其林 2026，按區吃</a> ／ {esc(area_name)}</div>
    <p class="rs-kicker">{label}・{esc(s['cuisine'])}</p>
    <div class="rs-title">{num(s)}<h1>{esc(name)}</h1></div>
    <p class="rs-th">{esc(alt)}</p>
    <p class="rs-lead">{esc(ed['blurb'])}</p>
    <div class="rs-tags">{''.join(tags)}</div>
    {closed}
    <figure class="rs-cover">{cover_svg(s, near, base, stations)}
      <figcaption><span>方塊是 BTS 站、圓圈是 MRT 站；數字圓點是附近的其他米其林，點一下就能看介紹</span><span>OffDayz 自繪示意圖・底圖 © OpenStreetMap contributors</span></figcaption></figure>
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
            <dt>等級</dt><dd>{label}<small>{TIER_NOTE[s['tier']]}</small></dd>
            <dt>價位</dt><dd>{esc(s.get('price') or '—')}<small>米其林指南的泰銖價位標示，฿ 最便宜、฿฿฿฿ 最貴</small></dd>
            <dt>訂位</dt><dd>{esc(book_txt)}</dd>
            <dt>捷運</dt><dd>{st_html}</dd>
            <dt>地址</dt><dd>{esc(s['address'])}</dd>
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
      <p class="mi-src" style="margin-top:30px">名單、地址與價位依《泰國米其林指南 2026》官網整理，短評與行程是 OffDayz 自己寫的。營業時間與訂位方式常有變動，出發前請以店家公告為準。</p>
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
    edit = json.load(open(ROOT / "data/michelin_bangkok_editorial.json"))
    base = json.load(open(ROOT / "data/geo/bangkok_base.json"))
    stations = base["stations"]
    areas = {a["id"]: a["name"] for a in d["areas"]}
    shops = sorted(d["shops"], key=lambda s: s["no"])
    for s in shops:
        s["_ed"] = edit[s["slug"]]
    head, foot = chrome((BASE_DIR / "index.html").read_text())
    for s in shops:
        out = BASE_DIR / str(s["no"]) / "index.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(page(s, shops, areas, base, stations, head, foot))
    print(len(shops), "pages →", BASE_DIR)


if __name__ == "__main__":
    build()
