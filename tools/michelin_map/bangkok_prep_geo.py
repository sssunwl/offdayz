"""曼谷米其林地圖用的底圖 data/geo/bangkok_base.json(只需跑一次)。台北版是 prep_geo.py,兩份互不影響。

原始檔(不進 repo,全部來自 Overpass,© OpenStreetMap contributors):
  admin.json  relation boundary=administrative admin_level=6(曼谷的區 khet、暖武里的縣)
  water.json  natural=water(river/canal/lake…)+ waterway=riverbank
  canal.json  way waterway=canal 有名字的運河
  rail.json   relation route=subway/light_rail/monorail/train(BTS、MRT、機場線、紅線)
  st.json     node railway=station
查詢語句在 tools/michelin_map/overpass/bangkok_*.txt,用 curl --data-urlencode data@檔案 送。
用法: python3 tools/michelin_map/bangkok_prep_geo.py <admin> <water> <canal> <rail> <st>
"""
import json, sys, pathlib, re
from prep_geo import stitch, thin, r5

BBOX = (13.65, 100.37, 13.95, 100.70)  # south, west, north, east
ROOT = pathlib.Path(__file__).resolve().parents[2]


def inside(lat, lon, pad=0.02):
    s, w, n, e = BBOX
    return s - pad <= lat <= n + pad and w - pad <= lon <= e + pad


NOT_BKK = {"Bang Kruai", "Nonthaburi", "Pak Kret", "Bang Bua Thong", "Bang Yai", "Lam Luk Ka", "Pathum Thani",
           "Bang Phli", "Samut Prakan", "Phra Pradaeng"}  # bbox 裡不屬於曼谷市的縣


def ways_of(e):
    return [[[g["lat"], g["lon"]] for g in m["geometry"]]
            for m in e["members"] if m["type"] == "way" and m.get("geometry") and m.get("role") != "inner"]


def admin(path):
    out = []
    for e in json.load(open(path))["elements"]:
        t = e["tags"]
        rings = [r for r in stitch(ways_of(e)) if len(r) > 3 and any(inside(*q) for q in r)]
        if not rings:
            continue
        name = t.get("name:en") or t.get("name")
        name = re.sub(r"^(Khet|Amphoe|Mueang)\s+|\s+District$", "", name)
        prov = "" if name in NOT_BKK else "Bangkok"
        out.append({"name": name, "th": t.get("name:th") or t.get("name"), "prov": prov,
                    "rings": [r5(thin(r, 0.00015)) for r in rings]})
    return out


def water(path):
    out = []
    for e in json.load(open(path))["elements"]:
        if e["type"] == "way":
            rings = [[[g["lat"], g["lon"]] for g in e["geometry"]]]
        else:
            rings = stitch([[[g["lat"], g["lon"]] for g in m["geometry"]]
                            for m in e["members"] if m["type"] == "way" and m.get("geometry")])
        rings = [r for r in rings if len(r) > 3 and any(inside(*q, pad=0) for q in r)]
        out.extend(r5(thin(r, 0.00004)) for r in rings)
    return out


def canals(path, min_len=0.012):
    out = []
    for e in json.load(open(path))["elements"]:
        pts = [[g["lat"], g["lon"]] for g in e.get("geometry", [])]
        if len(pts) < 2 or not any(inside(*q, pad=0) for q in pts):
            continue
        ln = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(pts, pts[1:]))
        if ln >= min_len:  # 只留夠長的運河,小水溝不畫
            out.append(r5(thin(pts, 0.00008)))
    return out


# 線色依官方路線圖
LINES = {
    "BTS Sukhumvit": ("BTS", "#7DBA2F"), "BTS Silom": ("BTS", "#00786E"), "BTS Gold": ("BTS", "#C9A43A"),
    "MRT Blue": ("MRT", "#1E4F9C"), "MRT Purple": ("MRT", "#6B2C91"), "MRT Yellow": ("MRT", "#F1C40F"),
    "MRT Pink": ("MRT", "#E05298"), "ARL": ("ARL", "#C8102E"), "SRT Dark Red": ("SRT", "#A6192E"), "SRT Light Red": ("SRT", "#E87D7D"),
}


def line_of(t):
    s = " ".join(t.get(k, "") for k in ("name:en", "name", "ref", "network", "colour")).lower()
    if "airport" in s or "arl" in s:
        return "ARL"
    if "gold" in s:
        return "BTS Gold"
    if "sukhumvit" in s and ("bts" in s or "skytrain" in s):
        return "BTS Sukhumvit"
    if "silom" in s:
        return "BTS Silom"
    for c in ("blue", "purple", "yellow", "pink"):
        if c in s:
            return "MRT " + c.title()
    if "dark red" in s:
        return "SRT Dark Red"
    if "light red" in s:
        return "SRT Light Red"
    return None


def rail(path):
    seen, out = set(), []
    for e in json.load(open(path))["elements"]:
        ln = line_of(e["tags"])
        if not ln:
            continue
        for m in e["members"]:
            if m["type"] != "way" or m.get("role") not in ("", None) or not m.get("geometry") or m["ref"] in seen:
                continue
            seen.add(m["ref"])
            pts = [[g["lat"], g["lon"]] for g in m["geometry"]]
            if any(inside(*q, pad=0) for q in pts):
                out.append({"line": ln, "pts": r5(pts)})
    return {"colors": {k: c for k, (_, c) in LINES.items()}, "ways": out}


def stations(path, base_rail):
    """只留 BTS/MRT/機場線的站(離路線 250 m 內),名字用英文;同名站(轉乘)合併成 BTS/MRT。
    OSM 很多站沒有 network 標籤,所以用最近的路線判斷系統。"""
    pts = [(la, lo, LINES[wy["line"]][0]) for wy in base_rail["ways"] for la, lo in wy["pts"]]
    out = {}
    for e in json.load(open(path))["elements"]:
        t = e.get("tags", {})
        nm = t.get("name:en") or ""
        if not nm or t.get("railway") != "station":
            continue
        d, kind = min((((la - e["lat"]) * 111000) ** 2 + ((lo - e["lon"]) * 108000) ** 2, k) for la, lo, k in pts)
        if d > 250 ** 2 or kind == "SRT" or nm.startswith("Bangkok"):  # Bangkok=華藍蓬火車站,不是 MRT
            continue
        nm = re.sub(r"\b(BTS|MRT|Station|ARL|Airport Rail Link|Interchange)\b", "", nm)
        nm = re.sub(r"\s*\(.*?\)|\s+", " ", nm).strip()
        if nm in out:
            if kind not in out[nm][2].split("/"):
                out[nm][2] += "/" + kind
            continue
        out[nm] = [round(e["lat"], 5), round(e["lon"], 5), kind]
    return out


if __name__ == "__main__":
    a, w, c, r, s = sys.argv[1:6]
    rl = rail(r)
    base = {"source": "© OpenStreetMap contributors", "districts": admin(a), "water": water(w),
            "canals": canals(c), "rail": rl, "stations": stations(s, rl)}
    dst = ROOT / "data/geo/bangkok_base.json"
    dst.write_text(json.dumps(base, ensure_ascii=False, separators=(",", ":")))
    print(dst, dst.stat().st_size, "bytes;", len(base["districts"]), "districts,", len(base["water"]), "water rings,",
          len(base["canals"]), "canals,", len(rl["ways"]), "rail ways,", len(base["stations"]), "stations")
