"""把 SS 自己拍、而且點頭可以公開的照片放上網站(source=own,前端優先顯示)。

用法:
  python3 tools/photos_own.py city tokyo 照片路徑 [--months 11,12,1,2,3]
  python3 tools/photos_own.py event japan-autumn-leaves 照片路徑

會做的事:縮到長邊 1600、轉 JPEG、**清掉 EXIF/GPS**(repo 是公開的),
存到 docs/assets/photos/<key>-<n>.jpg,再寫進 docs/data/photos.json。
只放 SS 親自挑過的照片;有人臉、家人、住處附近的照片不要放。"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "docs" / "data" / "photos.json"
OUT = ROOT / "docs" / "assets" / "photos"


def load_rgb(src):
    try:
        img = Image.open(src)
        img.load()
    except Exception:  # HEIC:用 macOS sips 先轉 JPEG
        tmp = Path(tempfile.mkdtemp()) / "x.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", str(src), "--out", str(tmp)], check=True, capture_output=True)
        img = Image.open(tmp)
    return ImageOps.exif_transpose(img).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["city", "event"])
    ap.add_argument("key")
    ap.add_argument("src")
    ap.add_argument("--months", help="逗號分隔，例如 11,12,1")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    n = len(list(OUT.glob(a.key + "-*.jpg"))) + 1
    name = "{}-{}.jpg".format(a.key, n)
    img = load_rgb(a.src)
    img.thumbnail((1600, 1600))
    img.save(OUT / name, "JPEG", quality=82, optimize=True, progressive=True)  # 不帶 exif=,GPS 不會留下

    data = json.loads(PHOTOS.read_text(encoding="utf-8")) if PHOTOS.exists() else {}
    entry = {"url": "assets/photos/" + name, "source": "own"}
    if a.months:
        entry["months"] = [int(x) for x in a.months.split(",")]
    data.setdefault("cities" if a.kind == "city" else "events", {}).setdefault(a.key, []).insert(0, entry)
    PHOTOS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("已放上", name)


if __name__ == "__main__":
    main()
