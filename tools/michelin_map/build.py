"""台北米其林 2026 一張圖:底圖 + 編號圓點 + 分區店名清單 → map.svg / map.png。

也會把分區(area)與編號(no)寫回 docs/data/michelin_taipei_2026.json,讓網頁卡片跟圖上的編號一致。
用法: python3 tools/michelin_map/build.py   (PNG 用本機 Chrome headless 輸出)
"""
import json, math, pathlib, subprocess, html

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/data/michelin_taipei_2026.json"
BASE = ROOT / "data/geo/taipei_base.json"
OUT = ROOT / "docs/places/taipei-michelin-2026"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PAPER, INK, MUTED, NAVY = "#FFFCF7", "#26312E", "#6E6459", "#1E4A45"
LAND_OUT, WATER, BORDER = "#EEE6D8", "#C9E0E3", "#D6C8B4"
TIER = {  # 星越多越紅;必比登用黃
    "3": {"fill": "#A8261A", "text": "#fff", "r": 17, "label": "三星"},
    "2": {"fill": "#D2482B", "text": "#fff", "r": 15, "label": "二星"},
    "1": {"fill": "#E98A5F", "text": "#fff", "r": 13, "label": "一星"},
    "bib": {"fill": "#F2BC3D", "text": INK, "r": 13, "label": "必比登"},
}
TIER_ORDER = ["3", "2", "1", "bib"]
GREEN = "#1F7A63"

# 旅人好用的分區(不是行政區),順序=編號順序:由北往南、由西往東
AREAS = [
    ("sl", "士林・天母"),
    ("dz", "大直・美麗華・內湖"),
    ("dt", "大稻埕・大同"),
    ("zs", "中山・晶華一帶"),
    ("ss", "松山・民生・南京復興"),
    ("zz", "台北車站・中正"),
    ("wh", "西門・萬華・南機場"),
    ("da", "大安・永康・東區"),
    ("xy", "信義"),
]
OVERRIDE = {"頤宮": "zz"}  # 君品在承德路一段,座標落在中山邊界


def area_of(s):
    if s["name"] in OVERRIDE:
        return OVERRIDE[s["name"]]
    lat, lon = s["lat"], s["lon"]
    if lat >= 25.11 or (lat >= 25.085 and lon < 121.535):
        return "sl"
    if lat >= 25.07 and lon >= 121.535:
        return "dz"
    if lon < 121.515 and lat >= 25.048:
        return "dt"
    if lon < 121.512:
        return "wh"
    if lon < 121.535 and lat >= 25.048:
        return "zs"
    if lon < 121.528:
        return "zz"
    if lat >= 25.045:
        return "ss"
    if lon >= 121.56:
        return "xy"
    return "da"


# ---- 版面 ----
W = 1200
HEAD = 170
COS = math.cos(math.radians(25.05))
# 主圖範圍(北邊 4 間放小窗)
LAT_N, LAT_S, LON_W, LON_E = 25.096, 25.008, 121.490, 121.583
K = W / ((LON_E - LON_W) * COS)
MAP_H = round((LAT_N - LAT_S) * K)


def P(lat, lon, k=K, lat0=LAT_N, lon0=LON_W, ox=0, oy=HEAD):
    return (ox + (lon - lon0) * COS * k, oy + (lat0 - lat) * k)


# 北邊小窗:天母・士林
INS = {"x": 22, "y": HEAD + 22, "w": 340, "h": 300, "lat0": 25.150, "lon0": 121.503}
INS["k"] = INS["w"] / (0.078 * COS)
NORTH_LIMIT = 25.10  # 比這更北的店畫在小窗

STATIONS = [  # 捷運站/地標,只當定位參考
    ("台北車站", 25.0478, 121.5170, "b"), ("西門", 25.0421, 121.5081), ("中山", 25.0527, 121.5204),
    ("雙連", 25.0577, 121.5205), ("圓山", 25.0713, 121.5201), ("劍潭", 25.0847, 121.5251),
    ("大橋頭", 25.0633, 121.5130), ("北門", 25.0494, 121.5103), ("龍山寺", 25.0353, 121.4999),
    ("中正紀念堂", 25.0327, 121.5181, "bl"), ("東門", 25.0337, 121.5288, "l"), ("古亭", 25.0263, 121.5229),
    ("公館", 25.0149, 121.5342), ("大安", 25.0330, 121.5435, "l"), ("忠孝復興", 25.0416, 121.5437),
    ("南京復興", 25.0520, 121.5443, "b"), ("松江南京", 25.0518, 121.5330), ("國父紀念館", 25.0413, 121.5577),
    ("市政府", 25.0411, 121.5651), ("台北101", 25.0330, 121.5637, "b"), ("松山機場", 25.0630, 121.5519),
    ("大直", 25.0794, 121.5469), ("劍南路", 25.0848, 121.5555), ("西湖", 25.0821, 121.5672),
]
LABEL_POS = {"r": (8, -7, "start"), "l": (-8, -7, "end"), "b": (6, 20, "start"), "bl": (-6, 20, "end")}
DISTRICT_AT = {  # 行政區名放的位置(手調,避開密集區)
    "中山區": (25.0745, 121.5355), "大同區": (25.0700, 121.5095), "萬華區": (25.0255, 121.4975),
    "中正區": (25.0230, 121.5160), "大安區": (25.0215, 121.5440), "信義區": (25.0245, 121.5735),
    "松山區": (25.0560, 121.5730), "士林區": (25.0920, 121.5125), "內湖區": (25.0900, 121.5780),
    "文山區": (25.0115, 121.5550), "三重區": (25.0720, 121.4925), "永和區": (25.0105, 121.5130),
    "南港區": (25.0440, 121.5800),
}

esc = lambda s: html.escape(str(s), quote=True)
f1 = lambda v: f"{v:.1f}"


def ring_path(ring, proj):
    pts = [proj(la, lo) for la, lo in ring]
    return "M" + "L".join(f"{f1(x)},{f1(y)}" for x, y in pts) + "Z"


def line_path(pts, proj):
    return "M" + "L".join("{},{}".format(*map(f1, proj(la, lo))) for la, lo in pts)


def basemap(base, proj, w_px):
    out = []
    tp = [t for t in base["towns"] if t["county"] == "台北市"]
    other = [t for t in base["towns"] if t["county"] != "台北市"]
    for t in other:
        out.append(f'<path d="{"".join(ring_path(r, proj) for r in t["rings"])}" fill="{LAND_OUT}" stroke="{BORDER}" stroke-width="1"/>')
    for t in tp:
        out.append(f'<path d="{"".join(ring_path(r, proj) for r in t["rings"])}" fill="{PAPER}" stroke="{BORDER}" stroke-width="1.6" stroke-dasharray="7 5"/>')
    out.append(f'<path d="{"".join(ring_path(r, proj) for r in base["water"])}" fill="{WATER}" fill-rule="evenodd"/>')
    sw = 3.2 if w_px > 600 else 2
    for wy in base["mrt"]["ways"]:
        c = base["mrt"]["colors"][wy["line"]]
        out.append(f'<path d="{line_path(wy["pts"], proj)}" fill="none" stroke="{c}" stroke-width="{sw}" stroke-linecap="round" opacity=".45"/>')
    return out


def relax(items, rounds=400):
    """推開重疊的圓點,保留一條細線指回真實位置。"""
    for _ in range(rounds):
        moved = False
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                dx, dy = b["x"] - a["x"], b["y"] - a["y"]
                d = math.hypot(dx, dy) or 0.01
                need = a["r"] + b["r"] + 2
                if d < need:
                    if d == 0.01:
                        dx, dy = math.cos(i), math.sin(i)
                    push = (need - d) / 2
                    ux, uy = dx / d, dy / d
                    a["x"] -= ux * push; a["y"] -= uy * push
                    b["x"] += ux * push; b["y"] += uy * push
                    moved = True
        for a in items:  # 微弱拉回原位
            a["x"] += (a["x0"] - a["x"]) * 0.02
            a["y"] += (a["y0"] - a["y"]) * 0.02
        if not moved:
            break


def dot_svg(s, x, y):
    t = TIER[s["tier"]]
    r = t["r"]
    g = []
    if s.get("green"):
        g.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{r + 4}" fill="none" stroke="{GREEN}" stroke-width="3"/>')
    g.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{r}" fill="{t["fill"]}" stroke="#fff" stroke-width="2"/>')
    fs = 14 if s["no"] < 100 else 12
    g.append(f'<text x="{f1(x)}" y="{f1(y + fs * 0.36)}" text-anchor="middle" font-size="{fs}" font-weight="800" fill="{t["text"]}" font-family="Helvetica Neue,Arial,sans-serif">{s["no"]}</text>')
    return "".join(g)


def place_dots(shops, proj):
    items = []
    for s in shops:
        x, y = proj(s["lat"], s["lon"])
        items.append({"s": s, "x": x, "y": y, "x0": x, "y0": y, "r": TIER[s["tier"]]["r"] + (4 if s.get("green") else 0)})
    relax(items)
    out = []
    for it in items:
        if math.hypot(it["x"] - it["x0"], it["y"] - it["y0"]) > 5:
            out.append(f'<line x1="{f1(it["x0"])}" y1="{f1(it["y0"])}" x2="{f1(it["x"])}" y2="{f1(it["y"])}" stroke="{INK}" stroke-width="1.2" opacity=".55"/>'
                       f'<circle cx="{f1(it["x0"])}" cy="{f1(it["y0"])}" r="2.4" fill="{INK}" opacity=".6"/>')
    # 星級畫在必比登上面
    for it in sorted(items, key=lambda it: -TIER_ORDER.index(it["s"]["tier"])):
        out.append(dot_svg(it["s"], it["x"], it["y"]))
    return out


def halo_text(x, y, txt, size, fill, weight=700, anchor="middle", spacing=0, halo=PAPER, hw=5, opacity=1):
    a = f'x="{f1(x)}" y="{f1(y)}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" letter-spacing="{spacing}" opacity="{opacity}"'
    return (f'<text {a} fill="none" stroke="{halo}" stroke-width="{hw}" stroke-linejoin="round">{esc(txt)}</text>'
            f'<text {a} fill="{fill}">{esc(txt)}</text>')


def build():
    d = json.load(open(DATA))
    base = json.load(open(BASE))
    shops = d["shops"]
    for s in shops:
        s["area"] = area_of(s)
    order = {a: i for i, (a, _) in enumerate(AREAS)}
    shops.sort(key=lambda s: (order[s["area"]], TIER_ORDER.index(s["tier"]), -s["lat"]))
    for i, s in enumerate(shops, 1):
        s["no"] = i
    d["areas"] = [{"id": a, "name": n} for a, n in AREAS]
    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n")

    main = [s for s in shops if s["lat"] < NORTH_LIMIT]
    north = [s for s in shops if s["lat"] >= NORTH_LIMIT]
    cnt = {t: sum(s["tier"] == t for s in shops) for t in TIER}

    svg = []
    # ---- 主圖 ----
    svg.append(f'<clipPath id="mc"><rect x="0" y="{HEAD}" width="{W}" height="{MAP_H}"/></clipPath>')
    svg.append(f'<rect x="0" y="{HEAD}" width="{W}" height="{MAP_H}" fill="{LAND_OUT}"/>')
    svg.append(f'<g clip-path="url(#mc)">')
    svg += basemap(base, P, W)
    for name, (la, lo) in DISTRICT_AT.items():
        x, y = P(la, lo)
        col = "#B9A992" if name in {t["name"] for t in base["towns"] if t["county"] == "台北市"} else "#C3B6A2"
        svg.append(halo_text(x, y, name, 30, col, weight=800, spacing=6, hw=0, opacity=.9))
    for name, la, lo, *pos in STATIONS:
        x, y = P(la, lo)
        svg.append(f'<rect x="{f1(x - 4)}" y="{f1(y - 4)}" width="8" height="8" rx="2" fill="#fff" stroke="{INK}" stroke-width="1.6"/>')
        dx, dy, anc = LABEL_POS[(pos or ["r"])[0]]
        svg.append(halo_text(x + dx, y + dy, name, 15, INK, weight=700, anchor=anc, hw=4))
    svg += place_dots(main, P)
    svg.append("</g>")
    # 河流名
    for txt, la, lo in [("淡水河", 25.0585, 121.5045), ("基隆河", 25.0745, 121.5555), ("新店溪", 25.0175, 121.5055)]:
        x, y = P(la, lo)
        svg.append(halo_text(x, y, txt, 17, "#4E8A93", weight=700, spacing=4, hw=0))

    # ---- 北邊小窗 ----
    ix, iy, iw, ih, ik = INS["x"], INS["y"], INS["w"], INS["h"], INS["k"]
    ip = lambda la, lo: P(la, lo, k=ik, lat0=INS["lat0"], lon0=INS["lon0"], ox=ix, oy=iy)
    svg.append(f'<clipPath id="ic"><rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="10"/></clipPath>')
    svg.append(f'<rect x="{ix + 4}" y="{iy + 6}" width="{iw}" height="{ih}" rx="10" fill="{INK}" opacity=".18"/>')
    svg.append(f'<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="10" fill="{LAND_OUT}"/>')
    svg.append('<g clip-path="url(#ic)">')
    svg += basemap(base, ip, iw)
    for name, la, lo, anc in [("士林站", 25.0935, 121.5260, "start"), ("芝山站", 25.1031, 121.5225, "start"), ("石牌站", 25.1146, 121.5155, "start"), ("天母", 25.1180, 121.5285, "below")]:
        x, y = ip(la, lo)
        svg.append(f'<rect x="{f1(x - 3.5)}" y="{f1(y - 3.5)}" width="7" height="7" rx="2" fill="#fff" stroke="{INK}" stroke-width="1.4"/>')
        if anc == "below":
            svg.append(halo_text(x, y + 20, name, 14, INK, hw=4))
        else:
            svg.append(halo_text(x + 7, y - 6, name, 14, INK, anchor=anc, hw=4))
    svg.append(halo_text(*ip(25.1445, 121.553), "↑ 陽明山方向", 14, MUTED, hw=4))
    svg += place_dots(north, ip)
    svg.append("</g>")
    svg.append(f'<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="10" fill="none" stroke="{INK}" stroke-width="2.5"/>')
    svg.append(f'<rect x="{ix}" y="{iy}" width="150" height="34" rx="10" fill="{INK}"/><rect x="{ix}" y="{iy + 14}" width="150" height="20" fill="{INK}"/>')
    svg.append(f'<text x="{ix + 14}" y="{iy + 23}" font-size="16" font-weight="800" fill="#fff">往北・天母一帶</text>')
    # 比例尺
    sx, sy = W - 190, HEAD + MAP_H - 34
    km = K / 111.0  # 1km ≈ 1/111 度緯度
    svg.append(f'<rect x="{sx - 12}" y="{sy - 26}" width="{km + 24 + 60}" height="44" rx="8" fill="{PAPER}" opacity=".9"/>')
    svg.append(f'<path d="M{sx},{sy - 6}V{sy}H{f1(sx + km)}V{sy - 6}" fill="none" stroke="{INK}" stroke-width="2"/>')
    svg.append(f'<text x="{f1(sx + km + 10)}" y="{sy + 2}" font-size="15" font-weight="700" fill="{INK}">1 km</text>')
    svg.append(f'<text x="{sx}" y="{sy - 12}" font-size="12" fill="{MUTED}">步行約 15 分鐘</text>')

    # ---- 標題 ----
    svg.append(f'<rect x="0" y="0" width="{W}" height="{HEAD}" fill="{NAVY}"/>')
    svg.append(f'<text x="40" y="58" font-size="20" font-weight="700" fill="#E8A62F" letter-spacing="3">MICHELIN GUIDE TAIWAN 2026・TAIPEI</text>')
    svg.append(f'<text x="40" y="122" font-size="54" font-weight="900" fill="#fff">台北米其林，按區吃</text>')
    svg.append(f'<text x="40" y="154" font-size="17" fill="#CFE0DA">星級 {cnt["3"] + cnt["2"] + cnt["1"]} 間＋必比登 {cnt["bib"]} 間｜圓點數字對照下方清單</text>')
    lx = 760
    for i, t in enumerate(TIER_ORDER):
        y = 52 + i * 30
        tt = TIER[t]
        svg.append(f'<circle cx="{lx}" cy="{y}" r="11" fill="{tt["fill"]}" stroke="#fff" stroke-width="2"/>')
        svg.append(f'<text x="{lx + 22}" y="{y + 6}" font-size="17" font-weight="700" fill="#fff">{tt["label"]}  {cnt[t]} 間</text>')
    svg.append(f'<circle cx="{lx + 200}" cy="52" r="11" fill="{TIER["1"]["fill"]}" stroke="#fff" stroke-width="2"/><circle cx="{lx + 200}" cy="52" r="15" fill="none" stroke="#7FD1B3" stroke-width="3"/>')
    svg.append(f'<text x="{lx + 224}" y="58" font-size="17" font-weight="700" fill="#fff">綠星</text>')
    svg.append(f'<rect x="{lx + 192}" y="74" width="8" height="8" rx="2" fill="#fff" stroke="#fff"/><text x="{lx + 210}" y="84" font-size="17" font-weight="700" fill="#fff">捷運站</text>')

    # ---- 清單 ----
    y0 = HEAD + MAP_H
    COLS, CW, LH, HH, GAP = 5, 208, 27, 44, 16
    blocks = [(a, n, [s for s in shops if s["area"] == a]) for a, n in AREAS]
    bh = [HH + len(l) * LH + GAP for *_, l in blocks]
    # 照分區順序切成 COLS 欄,讓最高那欄最矮
    best = {}
    def split(i, k):
        if (i, k) in best: return best[(i, k)]
        if k == 1: r = (sum(bh[i:]), [len(blocks)])
        else:
            r = min(((max(sum(bh[i:j]), split(j, k - 1)[0]), [j] + split(j, k - 1)[1])
                     for j in range(i + 1, len(blocks) - k + 2)), key=lambda t: t[0])
        best[(i, k)] = r
        return r
    cuts, cols, i = split(0, COLS)[1], [], 0
    for j in cuts:
        cols.append(blocks[i:j]); i = j
    col_h = [sum(HH + len(l) * LH + GAP for *_, l in c) for c in cols]
    list_h = max(col_h) + 40
    svg.append(f'<rect x="0" y="{y0}" width="{W}" height="{list_h + 70}" fill="{PAPER}"/>')
    svg.append(f'<rect x="0" y="{y0}" width="{W}" height="5" fill="{NAVY}"/>')
    for ci, c in enumerate(cols):
        x = 36 + ci * (CW + 18)
        y = y0 + 40
        for a, n, lst in c:
            svg.append(f'<text x="{x}" y="{y + 22}" font-size="19" font-weight="900" fill="{NAVY}">{esc(n)}</text>')
            svg.append(f'<rect x="{x}" y="{y + 32}" width="{CW}" height="2" fill="{NAVY}"/>')
            y += HH
            for s in lst:
                t = TIER[s["tier"]]
                cy = y + LH / 2
                svg.append(f'<circle cx="{x + 12}" cy="{f1(cy)}" r="11.5" fill="{t["fill"]}"/>')
                if s.get("green"):
                    svg.append(f'<circle cx="{x + 12}" cy="{f1(cy)}" r="13.5" fill="none" stroke="{GREEN}" stroke-width="2"/>')
                svg.append(f'<text x="{x + 12}" y="{f1(cy + 4.5)}" text-anchor="middle" font-size="12.5" font-weight="800" fill="{t["text"]}" font-family="Helvetica Neue,Arial,sans-serif">{s["no"]}</text>')
                name = s["name"]
                fs = 16 if len(name.encode()) <= 15 or len(name) <= 7 else 14 if len(name) <= 18 else 13
                svg.append(f'<text x="{x + 31}" y="{f1(cy + 5.5)}" font-size="{fs}" font-weight="600" fill="{INK}">{esc(name)}</text>')
                y += LH
            y += GAP
    H = y0 + list_h + 70
    svg.append(f'<text x="36" y="{H - 30}" font-size="13" fill="{MUTED}">資料：臺灣米其林指南 2026｜底圖：內政部鄉鎮界、© OpenStreetMap contributors｜圓點位置依 Google 地圖定位，出發前請自行確認營業狀態</text>')
    svg.append(f'<text x="{W - 36}" y="{H - 30}" text-anchor="end" font-size="15" font-weight="800" fill="{NAVY}">offdayz.sssuni.com</text>')

    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="PingFang TC,Noto Sans TC,Heiti TC,sans-serif">'
           f'<rect width="{W}" height="{H}" fill="{PAPER}"/>' + "".join(svg) + "</svg>")
    page = OUT / "_render.html"
    page.write_text(f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0}}</style>{doc}')
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                    "--force-device-scale-factor=2", f"--screenshot={OUT / 'map.png'}", page.as_uri()],
                   check=True, capture_output=True)
    page.unlink()
    print("map", W, "x", H, "→", OUT / "map.png")


if __name__ == "__main__":
    build()
