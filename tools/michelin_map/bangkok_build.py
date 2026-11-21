"""曼谷米其林 2026 一張圖:底圖 + 編號圓點 + 郊區小窗 + 分區店名清單 → map.png。台北版是 build.py,兩份互不影響。

讀 data/michelin_bangkok_guide.json(官網事實欄位)+ data/michelin_bangkok_editorial.json(OffDayz 短評),
排好分區(area)與編號(no)後寫出 docs/data/michelin_bangkok_2026.json,網頁卡片跟圖上的編號一致。
用法: python3 tools/michelin_map/bangkok_build.py   (PNG 用本機 Chrome headless 輸出)
"""
import json, math, pathlib, subprocess, html, re
from build import TIER, TIER_ORDER, GREEN, PAPER, INK, MUTED, NAVY, LAND_OUT, WATER, BORDER, relax, halo_text, f1, esc, CHROME

ROOT = pathlib.Path(__file__).resolve().parents[2]
GUIDE = ROOT / "data/michelin_bangkok_guide.json"
EDIT = ROOT / "data/michelin_bangkok_editorial.json"
DATA = ROOT / "docs/data/michelin_bangkok_2026.json"
BASE = ROOT / "data/geo/bangkok_base.json"
OUT = ROOT / "docs/places/bangkok-michelin-2026"
UPDATED = "2026-11-21"

CUISINE = {  # 官網英文菜系 → 中文
    "German, Contemporary": "現代德國菜", "Southern Thai": "南泰菜", "French Contemporary": "現代法國菜",
    "Modern Cuisine": "時尚料理", "Indian, Contemporary": "現代印度菜", "Contemporary": "時尚料理",
    "Thai contemporary": "新派泰菜", "Street Food, Thai": "街頭小吃", "Innovative": "創新料理", "Thai": "泰國菜",
    "French": "法國菜", "Creative, European Contemporary": "創意歐陸菜", "Cantonese": "粵菜",
    "European Contemporary": "現代歐陸菜", "Alpine, Modern Cuisine": "阿爾卑斯料理", "Korean Contemporary": "新派韓國菜",
    "Sushi": "壽司", "Italian Contemporary": "現代義大利菜", "Thai, Thai contemporary": "泰國菜",
    "Noodles": "麵食", "Street Food": "街頭小吃", "Thai-Chinese, Small eats": "潮泰小吃", "Noodles, Small eats": "麵食",
    "Small eats, Thai-Chinese": "潮泰小吃", "Small eats": "甜品小吃", "Fish and Seafood, Thai": "泰式海鮮",
    "Street Food, Fish and Seafood": "海鮮小吃", "Vietnamese": "越南菜", "Fish and Seafood": "海鮮",
    "Congee, Small eats": "粥品", "Isan": "東北依善菜", "Noodles, Japanese": "日式拉麵", "Noodles and Congee": "港式粥麵",
    "Northern Thai": "北泰菜", "Southern Thai, Fish and Seafood": "南泰海鮮", "Seafood": "海鮮", "Thai-Chinese": "潮泰菜",
}

# 旅人好用的分區,順序=編號順序:北郊先,再由老城往東,最後西郊、東郊。郊區三區畫在小窗
AREAS = [
    ("nb", "北郊・恰圖恰・暖武里"),
    ("ds", "律實・勝利紀念碑"),
    ("ok", "老城・考山路"),
    ("cn", "中國城・Talat Noi"),
    ("tb", "河西・吞武里"),
    ("rv", "河畔・石龍軍路"),
    ("sr", "是隆・沙吞・倫披尼"),
    ("sm", "暹羅・奇隆・水門"),
    ("sk", "素坤逸・通羅・伊卡邁"),
    ("ws", "西郊・塔林燦"),
    ("es", "東郊・挽甲必・巴威"),
]
AREA_OF = {
    "nb": "suan-thip hong-seng-pochana akkee chai-phochana kaeng-pa-loong-sa-nga beer-hima-prachachuen pae-jok-38-years",
    "ds": "prik-yuak chim-by-siam-wisdom jay-ngor-beef-noodle krua-apsorn-sam-sen wana-yook machri",
    "ok": "ten-suns mae-prapha-crispy-pancake-phra-nakhon eat-pad-thai bunloet mae-thum-padthai-kheng kolun-h jay-fai k-panich thai-tham nusara-1192382",
    "cn": "potong urai-braised-goose liana duck-noodle-house 80-20 samlor",
    "tb": "bokkia-tha-din-daeng ann-tha-din-daeng tharn blue-by-alain-ducasse somsak-pu-ob-charoen-rat grim-nguan-noodle",
    "rv": "aksorn the-china-house-by-chef-fei le-normandie mezzaluna chef-s-table1184372 sushi-saito-1208794 cote-by-mauro-colagreco hia-wan-khao-tom-pla",
    "sr": "maison-dunand aunglo-by-yangrak sartoria-by-paulo-airaudo le-du cannubi-by-umberto-bombana samrub-samrub-thai kao-soy-prin thien-duong plu nahm suhring",
    "sm": "signature-1194955 etcha elements thai-niyom i-sang igniv inddee avant coda-1206365 saneh-jaan duet-by-david-toutain",
    "sk": "kam-kin-suk haoma gaggan-anand juksunchae r-haan gokfayuen guay-tiew-mu-rung-rueang bo-lan gaa-1194845 nawa goat sorn mia no-name-noodle resonance keawloon",
    "ws": "sann sane phed-phed-bistro lucky-seafood kin-kub-koi",
    "es": "maan-muang baan-tepa janhom baan-pee-lek rue-poh",
}
AREA_OF = {slug: a for a, v in AREA_OF.items() for slug in v.split()}
INSET_AREAS = ("nb", "ws", "es")

# ---- 版面 ----
W = 1200
HEAD = 170
COS = math.cos(math.radians(13.75))
LAT_N, LAT_S, LON_W, LON_E = 13.800, 13.692, 100.465, 100.600
K = W / ((LON_E - LON_W) * COS)
MAP_H = round((LAT_N - LAT_S) * K)


def P(lat, lon, k=K, lat0=LAT_N, lon0=LON_W, ox=0, oy=HEAD):
    return (ox + (lon - lon0) * COS * k, oy + (lat0 - lat) * k)


# 主圖上標的站(太多會亂),其他站只畫小點
MAIN_STATIONS = {
    "Siam": "r", "Chit Lom": "b", "Phloen Chit": "r", "Nana": "b", "Asok": "r", "Phrom Phong": "b", "Thong Lo": "r",
    "Ekkamai": "b", "Sala Daeng": "l", "Chong Nonsi": "l", "Surasak": "b", "Saphan Taksin": "l", "Krung Thon Buri": "bl",
    "Wongwian Yai": "l", "Charoen Nakhon": "l", "National Stadium": "l", "Ratchathewi": "l", "Phaya Thai": "r",
    "Victory Monument": "r", "Sanam Chai": "l", "Sam Yot": "r", "Wat Mangkon": "b", "Hua Lamphong": "r", "Sam Yan": "b",
    "Lumphini": "b", "Khlong Toei": "b", "Phetchaburi": "r", "Phra Ram 9": "r", "Ratchadamri": "bl", "Itsaraphap": "l",
    "Bang Pho": "l", "Ari": "r", "Si Lom": "b", "Khlong San": "b", "Queen Sirikit National Convention Centre": "skip",
}
LABEL_POS = {"r": (9, -7, "start"), "l": (-9, -7, "end"), "b": (6, 21, "start"), "bl": (-6, 21, "end")}
DISTRICT_AT = {  # 區名位置(手調,避開密集區)
    "Phra Nakhon": (13.7655, 100.4935), "Dusit": (13.7825, 100.5160), "Pathum Wan": (13.7385, 100.5300),
    "Ratchathewi": (13.7690, 100.5440), "Bang Rak": (13.7175, 100.5325), "Sathon": (13.7040, 100.5340),
    "Khlong Toei": (13.7085, 100.5620), "Vadhana": (13.7545, 100.5820), "Khlong San": (13.7190, 100.4995),
    "Thon Buri": (13.7030, 100.4860), "Bangkok Yai": (13.7385, 100.4720), "Bangkok Noi": (13.7720, 100.4720),
    "Huai Khwang": (13.7800, 100.5840), "Phaya Thai": (13.7920, 100.5430), "Bang Phlat": (13.7930, 100.4950),
    "Din Daeng": (13.7745, 100.5660),
}
INSETS = [  # 郊區小窗:(區 id, 標題, 南, 西, 北, 東)
    ("nb", "往北・恰圖恰・暖武里", 13.800, 100.470, 13.940, 100.570),
    ("ws", "往西・塔林燦・挽艾", 13.740, 100.380, 13.862, 100.470),
    ("es", "往東・挽甲必・巴威", 13.665, 100.595, 13.780, 100.690),
]
IW, IH, IGAP = 368, 380, 16

esc_name = lambda n: re.sub(r"\s*\(.*?\)", "", n)  # 清單上省略分店括號


def ring_path(ring, proj):
    return "M" + "L".join("{},{}".format(*map(f1, proj(la, lo))) for la, lo in ring) + "Z"


def line_path(pts, proj):
    return "M" + "L".join("{},{}".format(*map(f1, proj(la, lo))) for la, lo in pts)


def basemap(base, proj, w_px):
    out = []
    for d in base["districts"]:
        bkk = d["prov"] == "Bangkok"
        out.append(f'<path d="{"".join(ring_path(r, proj) for r in d["rings"])}" fill="{PAPER if bkk else LAND_OUT}" '
                   f'stroke="{BORDER}" stroke-width="{1.6 if bkk else 1}" stroke-dasharray="7 5"/>')
    big = w_px > 600
    out.append(f'<path d="{"".join(line_path(c, proj) for c in base["canals"])}" fill="none" stroke="{WATER}" '
               f'stroke-width="{2.6 if big else 1.6}" stroke-linecap="round" stroke-linejoin="round"/>')
    out.append(f'<path d="{"".join(ring_path(r, proj) for r in base["water"])}" fill="{WATER}" fill-rule="evenodd"/>')
    sw = 3.4 if big else 2.2
    for wy in base["rail"]["ways"]:
        if wy["line"].startswith("SRT"):
            continue
        c = base["rail"]["colors"][wy["line"]]
        out.append(f'<path d="{line_path(wy["pts"], proj)}" fill="none" stroke="{c}" stroke-width="{sw}" stroke-linecap="round" opacity=".5"/>')
    return out


def station_mark(x, y, kind, s=4):
    if kind.startswith("MRT"):  # MRT 圓、BTS/機場線方
        return f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{s + .5}" fill="#fff" stroke="{INK}" stroke-width="1.6"/>'
    return f'<rect x="{f1(x - s)}" y="{f1(y - s)}" width="{2 * s}" height="{2 * s}" rx="2" fill="#fff" stroke="{INK}" stroke-width="1.6"/>'


def dot_svg(s, x, y, scale=1):
    t = TIER[s["tier"]]
    r = t["r"] * scale
    g = []
    if s.get("green"):
        g.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{r + 4}" fill="none" stroke="{GREEN}" stroke-width="3"/>')
    g.append(f'<circle cx="{f1(x)}" cy="{f1(y)}" r="{f1(r)}" fill="{t["fill"]}" stroke="#fff" stroke-width="2"/>')
    fs = (14 if s["no"] < 100 else 12) * scale
    g.append(f'<text x="{f1(x)}" y="{f1(y + fs * 0.36)}" text-anchor="middle" font-size="{f1(fs)}" font-weight="800" fill="{t["text"]}" font-family="Helvetica Neue,Arial,sans-serif">{s["no"]}</text>')
    return "".join(g)


class Labels:
    """已占用的方塊;新字找不到空位就不畫,避免字壓在圓點或別的字上。"""

    def __init__(self):
        self.boxes = []

    def add_dots(self, items):
        self.boxes += [(it["x"] - it["r"] - 2, it["y"] - it["r"] - 2, it["x"] + it["r"] + 2, it["y"] + it["r"] + 2) for it in items]

    def free(self, b):
        return all(b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3] for o in self.boxes)

    def place(self, x, y, txt, size, cands):
        w = sum(size * (1 if ord(ch) > 0x2E80 else 0.58) for ch in txt)
        for dx, dy, anc in cands:
            x0 = x + dx - (w if anc == "end" else w / 2 if anc == "middle" else 0)
            b = (x0 - 2, y + dy - size * .8, x0 + w + 2, y + dy + size * .25)
            if self.free(b):
                self.boxes.append(b)
                return x + dx, y + dy, anc
        return None


def place_dots(shops, proj, labels=None):
    items = []
    for s in shops:
        x, y = proj(s["lat"], s["lon"])
        items.append({"s": s, "x": x, "y": y, "x0": x, "y0": y, "r": TIER[s["tier"]]["r"] + (4 if s.get("green") else 0)})
    relax(items)
    if labels:
        labels.add_dots(items)
    out = []
    for it in items:
        if math.hypot(it["x"] - it["x0"], it["y"] - it["y0"]) > 5:
            out.append(f'<line x1="{f1(it["x0"])}" y1="{f1(it["y0"])}" x2="{f1(it["x"])}" y2="{f1(it["y"])}" stroke="{INK}" stroke-width="1.2" opacity=".55"/>'
                       f'<circle cx="{f1(it["x0"])}" cy="{f1(it["y0"])}" r="2.4" fill="{INK}" opacity=".6"/>')
    for it in sorted(items, key=lambda it: -TIER_ORDER.index(it["s"]["tier"])):
        out.append(dot_svg(it["s"], it["x"], it["y"]))
    return out


def merge():
    guide = json.load(open(GUIDE))["shops"]
    ed = json.load(open(EDIT))
    shops = []
    for g in guide:
        e = ed[g["slug"]]
        s = {"name": g["name"], "th": g["th"]}
        if e.get("zh"):
            s["zh"] = e["zh"]
        s.update(tier=g["tier"], cuisine=CUISINE[g["cuisine_en"]], cuisine_en=g["cuisine_en"], lat=g["lat"], lon=g["lon"],
                 area=AREA_OF[g["slug"]], slug=g["slug"], address=g["address"], site=g["site"], closed=g["closed"],
                 price=g["price"], bookable=g["bookable"], province=g["province"], blurb=e["blurb"])
        shops.append(s)
    order = {a: i for i, (a, _) in enumerate(AREAS)}
    shops.sort(key=lambda s: (order[s["area"]], TIER_ORDER.index(s["tier"]), -s["lat"]))
    for i, s in enumerate(shops, 1):
        s["no"] = i
    cnt = {t: sum(s["tier"] == t for s in shops) for t in TIER}
    d = {"updated": UPDATED, "title": "曼谷米其林 2026",
         "source": f"《泰國米其林指南 2026》曼谷及周邊:三星 {cnt['3']}、二星 {cnt['2']}、一星 {cnt['1']}、必比登推介 {cnt['bib']} 間"
                   "(含官網同列在曼谷區的暖武里府 6 間)。店名、地址、價位與座標依米其林指南官網。",
         "areas": [{"id": a, "name": n} for a, n in AREAS], "shops": shops}
    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    return d


def build():
    d = merge()
    base = json.load(open(BASE))
    shops = d["shops"]
    main = [s for s in shops if s["area"] not in INSET_AREAS]
    cnt = {t: sum(s["tier"] == t for s in shops) for t in TIER}
    assert all(LAT_S < s["lat"] < LAT_N and LON_W < s["lon"] < LON_E for s in main), "有店落在主圖外,調整 AREA_OF 或範圍"

    svg = []
    # ---- 主圖 ----
    svg.append(f'<clipPath id="mc"><rect x="0" y="{HEAD}" width="{W}" height="{MAP_H}"/></clipPath>')
    svg.append(f'<rect x="0" y="{HEAD}" width="{W}" height="{MAP_H}" fill="{LAND_OUT}"/>')
    svg.append('<g clip-path="url(#mc)">')
    svg += basemap(base, P, W)
    lab = Labels()
    dots = place_dots(main, P, lab)
    for txt, la, lo, size in [("昭披耶河", 13.6990, 100.5440, 19), ("Chao Phraya", 13.6962, 100.5440, 13)]:
        x, y = P(la, lo)
        lab.place(x, y, txt, size, [(0, 0, "middle")])
        svg.append(halo_text(x, y, txt, size, "#4E8A93", weight=700, spacing=3, hw=0))
    for name, (la, lo) in DISTRICT_AT.items():
        x, y = P(la, lo)
        spot = lab.place(x, y, name.upper() + "  ", 19 * 1.25, [(0, 0, "middle"), (0, -26, "middle"), (0, 26, "middle")])
        if spot:
            svg.append(halo_text(spot[0], spot[1], name.upper(), 19, "#B9A992", weight=800, spacing=4, hw=0, opacity=.9))
    for name, (la, lo, kind) in base["stations"].items():
        if not (LAT_S < la < LAT_N and LON_W < lo < LON_E):
            continue
        x, y = P(la, lo)
        pos = MAIN_STATIONS.get(name)
        if not pos or pos == "skip":
            svg.append(station_mark(x, y, kind, 2.6))
            continue
        svg.append(station_mark(x, y, kind))
        cands = [LABEL_POS[pos]] + [v for k, v in LABEL_POS.items() if k != pos] + \
            [(0, -11, "middle"), (0, 24, "middle"), (12, 5, "start"), (-12, 5, "end"), (14, -18, "start"), (-14, -18, "end")]
        spot = lab.place(x, y, name, 14, cands)
        if spot:
            svg.append(halo_text(spot[0], spot[1], name, 14, INK, weight=700, anchor=spot[2], hw=4))
    svg += dots
    svg.append("</g>")
    # 比例尺
    sx, sy = W - 190, HEAD + MAP_H - 34
    km = K / 111.0
    svg.append(f'<rect x="{sx - 12}" y="{sy - 26}" width="{f1(km + 24 + 60)}" height="44" rx="8" fill="{PAPER}" opacity=".9"/>')
    svg.append(f'<path d="M{sx},{sy - 6}V{sy}H{f1(sx + km)}V{sy - 6}" fill="none" stroke="{INK}" stroke-width="2"/>')
    svg.append(f'<text x="{f1(sx + km + 10)}" y="{sy + 2}" font-size="15" font-weight="700" fill="{INK}">1 km</text>')
    svg.append(f'<text x="{sx}" y="{sy - 12}" font-size="12" fill="{MUTED}">步行約 15 分鐘</text>')

    # ---- 郊區小窗 ----
    iy = HEAD + MAP_H + 28
    svg.append(f'<rect x="0" y="{HEAD + MAP_H}" width="{W}" height="{IH + 56}" fill="{PAPER}"/>')
    for n, (aid, title, s_, w_, n_, e_) in enumerate(INSETS):
        ix = 24 + n * (IW + IGAP)
        k = min(IW / ((e_ - w_) * COS), (IH - 44) / (n_ - s_))
        lat0 = (s_ + n_) / 2 + (IH + 44) / 2 / k  # 上方留給標題
        lon0 = (w_ + e_) / 2 - IW / 2 / (k * COS)
        ip = lambda la, lo, k=k, lat0=lat0, lon0=lon0, ix=ix: P(la, lo, k=k, lat0=lat0, lon0=lon0, ox=ix, oy=iy)
        svg.append(f'<clipPath id="ic{n}"><rect x="{ix}" y="{iy}" width="{IW}" height="{IH}" rx="10"/></clipPath>')
        svg.append(f'<rect x="{ix + 4}" y="{iy + 6}" width="{IW}" height="{IH}" rx="10" fill="{INK}" opacity=".18"/>')
        svg.append(f'<rect x="{ix}" y="{iy}" width="{IW}" height="{IH}" rx="10" fill="{LAND_OUT}"/>')
        svg.append(f'<g clip-path="url(#ic{n})">')
        svg += basemap(base, ip, IW)
        vis_s, vis_n = lat0 - IH / k, lat0
        vis_w, vis_e = lon0, lon0 + IW / (k * COS)
        mine = [s for s in shops if s["area"] == aid]
        ilab = Labels()
        idots = place_dots(mine, ip, ilab)
        ilab.boxes.append((ix, iy, ix + 22 + len(title) * 16, iy + 34))
        for name, (la, lo, kind) in base["stations"].items():
            if vis_s < la < vis_n and vis_w < lo < vis_e:
                x, y = ip(la, lo)
                svg.append(station_mark(x, y, kind, 3))
                # 只標離店 2 km 內最近的站,避免小窗字太多
                if min(math.hypot((la - s["lat"]) * 111, (lo - s["lon"]) * 108) for s in mine) < 1.6:
                    spot = ilab.place(x, y, name, 12.5, [(7, -6, "start"), (-7, -6, "end"), (6, 17, "start"), (-6, 17, "end")])
                    if spot and ix + 4 < spot[0] - (len(name) * 7.3 if spot[2] == "end" else 0) and spot[0] + (len(name) * 7.3 if spot[2] == "start" else 0) < ix + IW - 4:
                        svg.append(halo_text(spot[0], spot[1], name, 12.5, INK, anchor=spot[2], hw=4))
        svg += idots
        svg.append("</g>")
        svg.append(f'<rect x="{ix}" y="{iy}" width="{IW}" height="{IH}" rx="10" fill="none" stroke="{INK}" stroke-width="2.5"/>')
        tw = 22 + len(title) * 16
        svg.append(f'<rect x="{ix}" y="{iy}" width="{tw}" height="34" rx="10" fill="{INK}"/><rect x="{ix}" y="{iy + 14}" width="{tw}" height="20" fill="{INK}"/>')
        svg.append(f'<text x="{ix + 12}" y="{iy + 23}" font-size="16" font-weight="800" fill="#fff">{esc(title)}</text>')

    # ---- 標題 ----
    svg.append(f'<rect x="0" y="0" width="{W}" height="{HEAD}" fill="{NAVY}"/>')
    svg.append(f'<text x="40" y="58" font-size="20" font-weight="700" fill="#E8A62F" letter-spacing="3">MICHELIN GUIDE THAILAND 2026・BANGKOK</text>')
    svg.append(f'<text x="40" y="122" font-size="54" font-weight="900" fill="#fff">曼谷米其林，按區吃</text>')
    svg.append(f'<text x="40" y="154" font-size="17" fill="#CFE0DA">星級 {cnt["3"] + cnt["2"] + cnt["1"]} 間＋必比登 {cnt["bib"]} 間｜圓點數字對照下方清單</text>')
    lx = 760
    for i, t in enumerate(TIER_ORDER):
        y = 52 + i * 30
        tt = TIER[t]
        svg.append(f'<circle cx="{lx}" cy="{y}" r="11" fill="{tt["fill"]}" stroke="#fff" stroke-width="2"/>')
        svg.append(f'<text x="{lx + 22}" y="{y + 6}" font-size="17" font-weight="700" fill="#fff">{tt["label"]}  {cnt[t]} 間</text>')
    svg.append(f'<rect x="{lx + 192}" y="45" width="10" height="10" rx="2" fill="#fff"/><text x="{lx + 212}" y="56" font-size="17" font-weight="700" fill="#fff">BTS 站</text>')
    svg.append(f'<circle cx="{lx + 197}" cy="80" r="5.5" fill="#fff"/><text x="{lx + 212}" y="86" font-size="17" font-weight="700" fill="#fff">MRT 站</text>')
    for i, (lbl, c) in enumerate([("BTS", "#7DBA2F"), ("MRT", "#1E4F9C"), ("機場線", "#C8102E")]):
        y = 112 + i * 0
        svg.append(f'<rect x="{lx + 192 + i * 0}" y="{104 + i * 18}" width="14" height="5" rx="2" fill="{c}"/>'
                   f'<text x="{lx + 212}" y="{111 + i * 18}" font-size="13" fill="#CFE0DA">{lbl}</text>')

    # ---- 清單 ----
    y0 = iy + IH + 28
    COLS, CW, LH, HH, GAP = 4, 266, 27, 44, 16
    blocks = [(a, n, [s for s in shops if s["area"] == a]) for a, n in AREAS]
    bh = [HH + len(l) * LH + GAP for *_, l in blocks]
    best = {}

    def split(i, k):  # 照分區順序切成 COLS 欄,讓最高那欄最矮
        if (i, k) in best:
            return best[(i, k)]
        if k == 1:
            r = (sum(bh[i:]), [len(blocks)])
        else:
            r = min(((max(sum(bh[i:j]), split(j, k - 1)[0]), [j] + split(j, k - 1)[1])
                     for j in range(i + 1, len(blocks) - k + 2)), key=lambda t: t[0])
        best[(i, k)] = r
        return r
    cuts, cols, i = split(0, COLS)[1], [], 0
    for j in cuts:
        cols.append(blocks[i:j]); i = j
    list_h = max(sum(HH + len(l) * LH + GAP for *_, l in c) for c in cols) + 40
    svg.append(f'<rect x="0" y="{y0}" width="{W}" height="{list_h + 70}" fill="{PAPER}"/>')
    svg.append(f'<rect x="0" y="{y0}" width="{W}" height="5" fill="{NAVY}"/>')
    tw = lambda txt, size: sum(size * (1 if ord(ch) > 0x2E80 else 0.56) for ch in txt)
    for ci, c in enumerate(cols):
        x = 36 + ci * (CW + 22)
        y = y0 + 40
        for a, n, lst in c:
            svg.append(f'<text x="{x}" y="{y + 22}" font-size="19" font-weight="900" fill="{NAVY}">{esc(n)}</text>')
            svg.append(f'<rect x="{x}" y="{y + 32}" width="{CW}" height="2" fill="{NAVY}"/>')
            y += HH
            for s in lst:
                t = TIER[s["tier"]]
                cy = y + LH / 2
                svg.append(f'<circle cx="{x + 12}" cy="{f1(cy)}" r="11.5" fill="{t["fill"]}"/>')
                svg.append(f'<text x="{x + 12}" y="{f1(cy + 4.5)}" text-anchor="middle" font-size="12.5" font-weight="800" fill="{t["text"]}" font-family="Helvetica Neue,Arial,sans-serif">{s["no"]}</text>')
                name = esc_name(s["name"]) + (f"・{s['zh']}" if s.get("zh") else "")
                fs = next(f for f in (16, 15, 14, 13, 12) if tw(name, f) <= CW - 34 or f == 12)
                svg.append(f'<text x="{x + 31}" y="{f1(cy + 5.5)}" font-size="{fs}" font-weight="600" fill="{INK}">{esc(name)}</text>')
                y += LH
            y += GAP
    H = y0 + list_h + 70
    svg.append(f'<text x="36" y="{H - 30}" font-size="13" fill="{MUTED}">資料：泰國米其林指南 2026（曼谷及周邊，含暖武里府 6 間）｜底圖 © OpenStreetMap contributors｜圓點依官網座標，出發前請自行確認營業狀態</text>')
    svg.append(f'<text x="{W - 36}" y="{H - 30}" text-anchor="end" font-size="15" font-weight="800" fill="{NAVY}">offdayz.sssuni.com</text>')

    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="PingFang TC,Noto Sans TC,Heiti TC,sans-serif">'
           f'<rect width="{W}" height="{H}" fill="{PAPER}"/>' + "".join(svg) + "</svg>")
    OUT.mkdir(parents=True, exist_ok=True)
    page = OUT / "_render.html"
    page.write_text(f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0}}</style>{doc}')
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                    "--force-device-scale-factor=2", f"--screenshot={OUT / 'map.png'}", page.as_uri()],
                   check=True, capture_output=True)
    page.unlink()
    print("map", W, "x", H, "→", OUT / "map.png", "｜", len(shops), "shops")


if __name__ == "__main__":
    build()
