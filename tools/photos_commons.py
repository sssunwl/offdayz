"""幫城市和季節活動找 Wikimedia Commons 照片(只收可商用授權，前端要標作者)。

用法:
  python3 tools/photos_commons.py search OUT_DIR [前綴...]  # 每格抓 6 張候選 + 拼一張對照圖 OUT_DIR/<slot>.jpg
  python3 tools/photos_commons.py pick OUT_DIR PICKS  # PICKS = {"city:tokyo:warm": 2, ...},寫進 docs/data/photos.json

自動挑圖會挑錯(sarayuki 挑過巴士事故照)，一定要人工看過對照圖再 pick。
自己拍的照片(source=own)由 photos_own.py 寫入，pick 不會覆蓋。"""
import json
import re
import sys
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
QUERIES = ROOT / "tools" / "photo_queries.json"
PHOTOS = ROOT / "docs" / "data" / "photos.json"
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "OffDayz/1.0 (https://offdayz.sssuni.com/)"}
OK_LICENSE = re.compile(r"^(CC0|CC BY|CC BY-SA|Public domain|PD)", re.I)
WARM, COLD = [4, 5, 6, 7, 8, 9, 10], [11, 12, 1, 2, 3]


def slots():
    q = json.loads(QUERIES.read_text(encoding="utf-8"))
    for city, seasons in q["cities"].items():
        for season, query in seasons.items():
            yield "city:{}:{}".format(city, season), query
    for event, query in q["events"].items():
        yield "event:{}".format(event), query


def candidates(query, limit=6):
    res = requests.get(API, headers=HEADERS, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": query + " filetype:bitmap",
        "gsrnamespace": 6, "gsrlimit": 20, "prop": "imageinfo", "iiprop": "url|extmetadata|size",
        "iiurlwidth": 1280,
    })
    pages = sorted((res.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    out = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        w, h = info.get("width", 0), info.get("height", 1)
        if not OK_LICENSE.search(lic) or w < h * 1.2 or w < 1200:
            continue  # 只要可商用、橫的、夠大
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
        out.append({"url": (info.get("thumburl") or "").split("?")[0], "page": info.get("descriptionurl"),
                    "credit": re.sub(r"\s+", " ", artist or "Wikimedia Commons")[:60], "license": lic,
                    "title": page.get("title", "")})
        if len(out) >= limit:
            break
    return out


def contact_sheet(cands, path):
    tiles = []
    for c in cands:
        try:
            img = Image.open(BytesIO(requests.get(c["url"], headers=HEADERS, timeout=30).content)).convert("RGB")
            img.thumbnail((420, 280))
        except Exception:
            img = Image.new("RGB", (420, 280), "#ccc")
        tiles.append(img)
    sheet = Image.new("RGB", (3 * 430, 2 * 300), "white")
    for i, t in enumerate(tiles):
        x, y = (i % 3) * 430 + 5, (i // 3) * 300 + 5
        sheet.paste(t, (x, y))
        ImageDraw.Draw(sheet).rectangle([x, y, x + 34, y + 30], fill="black")
        ImageDraw.Draw(sheet).text((x + 12, y + 8), str(i), fill="white")
    sheet.save(path, quality=80)


def search(out, only=()):
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "candidates.json"
    found = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    for slot, query in slots():
        if only and not slot.startswith(tuple(only)):
            continue
        cands = candidates(query)
        found[slot] = cands
        if cands:
            contact_sheet(cands, out / (slot.replace(":", "_") + ".jpg"))
        print(slot, len(cands), flush=True)
        cache.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")


def pick(out, picks_path):
    found = json.loads((out / "candidates.json").read_text(encoding="utf-8"))
    picks = json.loads(Path(picks_path).read_text(encoding="utf-8"))
    data = json.loads(PHOTOS.read_text(encoding="utf-8")) if PHOTOS.exists() else {}
    data.setdefault("_meta", {"note": "城市/季節活動照片。source=own 是 SS 自己拍的(優先顯示)，commons 要附作者+授權。"
                                      "只由 tools/photos_commons.py / photos_own.py 寫入。"})
    for slot, idx in picks.items():
        c = dict(found[slot][idx], source="commons")
        c.pop("title", None)
        kind, key, *rest = slot.split(":")
        if kind == "city":
            c["months"] = WARM if rest[0] == "warm" else COLD
            bucket = data.setdefault("cities", {}).setdefault(key, [])
        else:
            bucket = data.setdefault("events", {}).setdefault(key, [])
        bucket[:] = [p for p in bucket if p.get("source") == "own" or p.get("months") != c.get("months")]
        bucket.append(c)
    PHOTOS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:2] == ["search"]:
        search(Path(sys.argv[2]), sys.argv[3:])
    elif sys.argv[1:2] == ["pick"]:
        pick(Path(sys.argv[2]), sys.argv[3])
    else:
        print(__doc__)
