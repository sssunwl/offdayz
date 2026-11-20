"""台北米其林 2026:每間店一頁 docs/places/taipei-michelin-2026/<編號>/index.html。

讀 docs/data/michelin_taipei_2026.json(先跑 build.py 才有 area / no)。
照片只用店家 IG 貼文的官方嵌入:資料裡 ig_posts=[貼文網址...];沒有就只放 ig 帳號連結。
用法: python3 tools/michelin_map/build_pages.py
"""
import json, math, pathlib, html, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/data/michelin_taipei_2026.json"
SITE = "https://offdayz.sssuni.com"
BASE_DIR = ROOT / "docs/places/taipei-michelin-2026"
TIER = {
    "3": ("三星", "★★★", "#A8261A", "#fff"),
    "2": ("二星", "★★", "#D2482B", "#fff"),
    "1": ("一星", "★", "#E98A5F", "#fff"),
    "bib": ("必比登推介", "必比登", "#F2BC3D", "#26312E"),
}
esc = lambda s: html.escape(str(s or ""), quote=True)


def dist_m(a, b):
    dy = (a["lat"] - b["lat"]) * 111000
    dx = (a["lon"] - b["lon"]) * 111000 * math.cos(math.radians(25.05))
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


CSS = """
    .rs-hero{padding-top:18px}
    .rs-crumb{font:700 12px var(--type);letter-spacing:.06em;color:var(--muted);margin-bottom:14px}
    .rs-crumb a{color:var(--blue)}
    .rs-title{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
    .rs-no{display:inline-grid;place-items:center;min-width:44px;height:44px;padding:0 8px;border-radius:22px;font:800 20px/1 'Helvetica Neue',Arial,sans-serif}
    .rs-no.green{box-shadow:0 0 0 3px var(--paper),0 0 0 6px var(--good)}
    .rs-title h1{margin:0}
    .rs-en{font:italic 500 18px var(--serif);color:var(--muted);margin:6px 0 0}
    .rs-tags{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 0}
    .rs-tags span{font:700 13px var(--type);padding:4px 10px;border:1px solid var(--line);background:var(--paper)}
    .rs-tags .tier{color:var(--t);background:var(--c);border-color:var(--c)}
    .rs-tags .green{border-color:var(--good);color:var(--good)}
    .rs-tags .note{border-color:var(--coral);color:var(--coral)}
    .rs-grid{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:28px;align-items:start}
    @media(max-width:860px){.rs-grid{grid-template-columns:1fr}}
    .rs-photos{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
    .rs-photos .instagram-media{min-width:0!important;margin:0!important}
    .rs-nophoto{padding:26px 22px;border:1px dashed var(--line);background:var(--paper);color:var(--muted);line-height:1.8;font-size:14px}
    .rs-nophoto a{font-weight:700;color:var(--blue)}
    .rs-info{background:var(--paper);border:1px solid var(--line);padding:18px 20px}
    .rs-info dl{display:grid;grid-template-columns:72px 1fr;gap:10px 12px;margin:0;font-size:14.5px;line-height:1.6}
    .rs-info dt{font:700 12px var(--type);color:var(--muted);letter-spacing:.06em;padding-top:3px}
    .rs-info dd{margin:0}
    .rs-btns{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
    #rsMap{height:300px;margin-top:16px;border:1px solid var(--line)}
    .rs-near{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
    .rs-near a{display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--paper);border:1px solid var(--line);color:var(--ink)}
    .rs-near a:hover{border-color:var(--navy)}
    .rs-near .n{display:inline-grid;place-items:center;min-width:26px;height:26px;border-radius:13px;font:800 13px/1 'Helvetica Neue',Arial,sans-serif;flex:none}
    .rs-near b{font:900 15px/1.3 var(--serif-zh);color:var(--navy)}
    .rs-near small{display:block;font:12px var(--type);color:var(--muted)}
    .rs-pager{display:flex;justify-content:space-between;gap:12px;margin-top:36px;font:700 14px var(--type)}
    .rs-pager a{color:var(--blue)}
"""


def num(s, cls="rs-no"):
    _, _, c, t = TIER[s["tier"]]
    g = " green" if s.get("green") else ""
    return f'<span class="{cls}{g}" style="background:{c};color:{t}">{s["no"]}</span>'


def photos(s):
    posts = s.get("ig_posts") or []
    if posts:
        items = "".join(
            f'<blockquote class="instagram-media" data-instgrm-permalink="{esc(u)}" data-instgrm-version="14">'
            f'<a href="{esc(u)}" target="_blank" rel="noopener">在 Instagram 查看這則貼文</a></blockquote>' for u in posts)
        return (f'<div class="rs-photos">{items}</div>'
                '<p class="mi-src">照片為店家在 Instagram 公開的貼文，透過官方嵌入顯示，版權屬原作者。</p>'
                '<script async src="https://www.instagram.com/embed.js"></script>')
    q = f'{s["name"]} {s.get("en") or ""} 台北市'.strip()
    ig = (f'・<a href="https://www.instagram.com/{esc(s["ig"])}/" target="_blank" rel="noopener">店家 Instagram @{esc(s["ig"])}</a>'
          if s.get("ig") else "")
    return (f'<div class="rs-nophoto">店家照片整理中。想先看菜色與環境：'
            f'<a href="https://www.google.com/maps/search/?api=1&query={esc(q)}" target="_blank" rel="noopener">Google 地圖相片</a>{ig}</div>')


def page(s, shops, areas, head, foot):
    name, en = s["name"], s.get("en") or ""
    label, badge, c, t = TIER[s["tier"]]
    area = areas[s["area"]]
    q = f"{name} {en} 台北市".strip()
    gmap = f"https://www.google.com/maps/search/?api=1&query={html.escape(q)}"
    near = sorted((o for o in shops if o is not s), key=lambda o: dist_m(s, o))[:6]
    near_html = "".join(
        f'<li><a href="../{o["no"]}/">{num(o, "n")}<span><b>{esc(o["name"])}</b>'
        f'<small>{TIER[o["tier"]][0]}・{esc(o["cuisine"])}・{walk(dist_m(s, o))}</small></span></a></li>' for o in near)
    tags = [f'<span class="tier" style="--c:{c};--t:{t}">{label}</span>', f'<span>{esc(s["cuisine"])}</span>']
    if s.get("green"):
        tags.append('<span class="green">綠星</span>')
    if s.get("note"):
        tags.append(f'<span class="note">{esc(s["note"])}</span>')
    addr = (esc(s["address"]) + ("(門牌待確認)" if s.get("verified") is False else "")) if s.get("address") else f'<a href="{gmap}" target="_blank" rel="noopener">看 Google 地圖</a>'
    i = shops.index(s)
    prev_s, next_s = shops[i - 1] if i else None, shops[i + 1] if i + 1 < len(shops) else None
    desc = f"{name}{'（' + en + '）' if en else ''}：2026 台北米其林{label}，{s['cuisine']}，位在{area}。附地圖、附近的其他米其林餐廳。"
    title = f"{name}｜台北米其林 2026 {label} · OffDayz"
    mapdata = json.dumps([{"no": o["no"], "name": o["name"], "lat": o["lat"], "lon": o["lon"], "c": TIER[o["tier"]][2], "me": o is s}
                          for o in [s] + near], ensure_ascii=False)
    ld = json.dumps({"@context": "https://schema.org", "@type": "Restaurant", "name": name, "alternateName": en or None,
                     "servesCuisine": s["cuisine"], "address": s.get("address") or "台北市",
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
  <link rel="stylesheet" href="../../../assets/sosol.css">
  <link rel="stylesheet" href="../../../assets/magazine.css">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
        integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
  <script type="application/ld+json">{ld}</script>
  <style>{CSS}</style>
</head>
<body>{head}<main id="main" class="column-main">
  <section class="hero page-hero rs-hero"><div class="shell">
    <div class="rs-crumb"><a href="../">台北米其林 2026</a> ／ {esc(area)}</div>
    <div class="rs-title">{num(s)}<h1>{esc(name)}</h1></div>
    {f'<p class="rs-en">{esc(en)}</p>' if en else ''}
    <div class="rs-tags">{''.join(tags)}</div>
  </div></section>

  <div class="shell">
    <div class="section rs-grid">
      <div>
        <div class="section-head"><h2 class="mag-heading"><span>01</span>菜色與環境 <i>Photos</i></h2></div>
        {photos(s)}
      </div>
      <div>
        <div class="section-head"><h2 class="mag-heading"><span>02</span>怎麼去 <i>Getting there</i></h2></div>
        <div class="rs-info">
          <dl>
            <dt>等級</dt><dd>{label}{'・綠星' if s.get('green') else ''}</dd>
            <dt>料理</dt><dd>{esc(s['cuisine'])}</dd>
            <dt>區域</dt><dd>{esc(area)}</dd>
            <dt>地址</dt><dd>{addr}</dd>
          </dl>
          <div class="rs-btns">
            <a class="btn btn-primary" href="{gmap}" target="_blank" rel="noopener">Google 地圖導航</a>
            {f'<a class="btn btn-ghost" href="https://www.instagram.com/{esc(s["ig"])}/" target="_blank" rel="noopener">Instagram</a>' if s.get('ig') else ''}
          </div>
          <div id="rsMap" role="application" aria-label="{esc(name)} 與附近米其林餐廳地圖"></div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-head"><h2 class="mag-heading"><span>03</span>附近還有 <i>Nearby</i></h2></div>
      <ul class="rs-near">{near_html}</ul>
      <div class="rs-pager">
        {f'<a href="../{prev_s["no"]}/">← {prev_s["no"]}. {esc(prev_s["name"])}</a>' if prev_s else '<span></span>'}
        <a href="../#map">回到總覽地圖</a>
        {f'<a href="../{next_s["no"]}/">{next_s["no"]}. {esc(next_s["name"])} →</a>' if next_s else '<span></span>'}
      </div>
      <p class="mi-src" style="margin-top:30px">名單依《臺灣米其林指南 2026》整理。營業時間與訂位方式常有變動，出發前請以店家公告為準。</p>
    </div>
  </div>
</main>
{foot}
<script src="../../../assets/site.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
(()=>{{
  if(typeof L==='undefined'){{document.getElementById('rsMap').remove();return;}}
  const P={mapdata};
  const map=L.map('rsMap',{{scrollWheelZoom:false}});
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'&copy; OpenStreetMap'}}).addTo(map);
  P.forEach(p=>{{
    const r=p.me?13:10;
    const icon=L.divIcon({{className:'',iconSize:[r*2,r*2],html:`<div style="width:${{r*2}}px;height:${{r*2}}px;border-radius:50%;background:${{p.c}};border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.35);display:grid;place-items:center;font:800 ${{p.me?13:11}}px/1 Helvetica Neue,Arial,sans-serif;color:#fff">${{p.no}}</div>`}});
    const m=L.marker([p.lat,p.lon],{{icon,zIndexOffset:p.me?1000:0}}).addTo(map).bindTooltip(p.name);
    if(!p.me)m.on('click',()=>location.href=`../${{p.no}}/`);
  }});
  map.fitBounds(P.map(p=>[p.lat,p.lon]),{{padding:[30,30],maxZoom:16}});
}})();
</script>
</body>
</html>
"""


def build():
    d = json.load(open(DATA))
    shops = sorted(d["shops"], key=lambda s: s["no"])
    areas = {a["id"]: a["name"] for a in d["areas"]}
    head, foot = chrome((BASE_DIR / "index.html").read_text())
    for s in shops:
        out = BASE_DIR / str(s["no"]) / "index.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(page(s, shops, areas, head, foot))
    print(len(shops), "pages →", BASE_DIR)


if __name__ == "__main__":
    build()
