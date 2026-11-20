"""把原始地理資料整理成米其林地圖用的底圖 data/geo/taipei_base.json(只需跑一次)。

原始檔(不進 repo):
  towns.json  https://cdn.jsdelivr.net/npm/taiwan-atlas@1.0.0/towns-10t.json (內政部鄉鎮界 topojson)
  water.json  Overpass: natural=water + water=river (way/relation, out geom)
  mrt.json    Overpass: relation route=subway (out geom)
用法: python3 tools/michelin_map/prep_geo.py <towns.json> <water.json> <mrt.json>
"""
import json, sys, pathlib

BBOX = (24.97, 121.44, 25.17, 121.67)  # south, west, north, east
ROOT = pathlib.Path(__file__).resolve().parents[2]


def inside(lat, lon, pad=0.03):
    s, w, n, e = BBOX
    return s - pad <= lat <= n + pad and w - pad <= lon <= e + pad


def r5(ring):
    return [[round(la, 5), round(lo, 5)] for la, lo in ring]


def thin(ring, eps=0.00008):
    """丟掉跟上一點太近的點,檔案小一點、肉眼看不出差別。"""
    out = [ring[0]]
    for p in ring[1:-1]:
        if abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    out.append(ring[-1])
    return out


def topo_towns(path):
    t = json.load(open(path))
    sx, sy = t["transform"]["scale"]
    tx, ty = t["transform"]["translate"]
    arcs = []
    for arc in t["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append([y * sy + ty, x * sx + tx])  # [lat, lon]
        arcs.append(pts)

    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts.extend(a if not pts else a[1:])
        return pts

    out = []
    for g in t["objects"]["towns"]["geometries"]:
        p = g["properties"]
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        rings = [ring(r) for poly in polys for r in poly]
        rings = [r for r in rings if any(inside(*q) for q in r)]
        if rings:
            out.append({"county": p["COUNTYNAME"], "name": p["TOWNNAME"],
                        "rings": [r5(thin(r)) for r in rings]})
    return out


def stitch(ways):
    """把 multipolygon 的成員 way 頭尾接成封閉環。"""
    ways = [w[:] for w in ways if len(w) > 1]
    rings = []
    while ways:
        cur = ways.pop(0)
        changed = True
        while cur[0] != cur[-1] and changed:
            changed = False
            for i, w in enumerate(ways):
                if w[0] == cur[-1]:
                    cur += w[1:]
                elif w[-1] == cur[-1]:
                    cur += w[::-1][1:]
                elif w[-1] == cur[0]:
                    cur = w + cur[1:]
                elif w[0] == cur[0]:
                    cur = w[::-1] + cur[1:]
                else:
                    continue
                ways.pop(i)
                changed = True
                break
        rings.append(cur)
    return rings


def water(path):
    out = []
    for e in json.load(open(path))["elements"]:
        if e["tags"].get("natural") != "water":
            continue
        if e["type"] == "way":
            rings = [[[g["lat"], g["lon"]] for g in e["geometry"]]]
        else:
            ways = [[[g["lat"], g["lon"]] for g in m["geometry"]]
                    for m in e["members"] if m["type"] == "way" and m.get("geometry")]
            rings = stitch(ways)
        rings = [r for r in rings if len(r) > 3 and any(inside(*q) for q in r)]
        out.extend(r5(thin(r, 0.00004)) for r in rings)
    return out


LINES = {"BL": "#0070BD", "BR": "#C48C31", "G": "#008659", "R": "#E3002C", "O": "#F8B61C", "Y": "#FFDB00"}


def mrt(path):
    seen, out = set(), []
    for e in json.load(open(path))["elements"]:
        ref = e["tags"].get("ref", "")
        ref = "R" if "新北投" in ref else ref
        if ref not in LINES:
            continue
        for m in e["members"]:
            if m["type"] != "way" or m.get("role") not in ("", None) or not m.get("geometry"):
                continue
            if m["ref"] in seen:
                continue
            seen.add(m["ref"])
            pts = [[g["lat"], g["lon"]] for g in m["geometry"]]
            if any(inside(*q, pad=0) for q in pts):
                out.append({"line": ref, "pts": r5(pts)})
    return {"colors": LINES, "ways": out}


if __name__ == "__main__":
    towns_p, water_p, mrt_p = sys.argv[1:4]
    base = {"source": "內政部鄉鎮界(taiwan-atlas)、© OpenStreetMap contributors",
            "towns": topo_towns(towns_p), "water": water(water_p), "mrt": mrt(mrt_p)}
    dst = ROOT / "data/geo/taipei_base.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(base, ensure_ascii=False, separators=(",", ":")))
    print(dst, dst.stat().st_size, "bytes;", len(base["towns"]), "towns,",
          len(base["water"]), "water rings,", len(base["mrt"]["ways"]), "mrt ways")
