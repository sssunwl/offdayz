"""一次性探測：Travelpayouts v3 / v2 欄位 + LiteAPI key 類型。不印 token。"""
import os, json, requests
tp = os.environ["TRAVELPAYOUTS_TOKEN"].strip()
lk = os.environ.get("LITEAPI_KEY", "").strip()
print("LITEAPI key prefix:", lk[:5] + "…", "len", len(lk))
def show(name, url, params):
    params = dict(params, token=tp)
    r = requests.get(url, params=params, timeout=20)
    print(f"\n=== {name} HTTP {r.status_code}")
    try:
        d = r.json()
    except Exception:
        print(r.text[:300]); return
    data = d.get("data")
    print("keys:", list(d.keys()), "n:", len(data) if hasattr(data, "__len__") else data)
    sample = data[:3] if isinstance(data, list) else data
    print(json.dumps(sample, ensure_ascii=False)[:1500])
base = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
for mk in ["hk", "tw", None]:
    p = dict(origin="HKG", destination="KIX", departure_at="2026-12", currency="hkd",
             one_way="true", sorting="price", limit=5)
    if mk: p["market"] = mk
    show(f"v3 HKG-KIX oneway market={mk}", base, p)
show("v3 HKG-KIX roundtrip hk", base, dict(origin="HKG", destination="KIX", departure_at="2026-12",
     return_at="2026-12", currency="hkd", one_way="false", sorting="price", limit=5, market="hk"))
show("v3 TPE-NRT oneway tw twd", base, dict(origin="TPE", destination="TYO", departure_at="2026-12",
     currency="twd", one_way="true", sorting="price", limit=5, market="tw"))
show("v3 grouped HKG-OKA", "https://api.travelpayouts.com/aviasales/v3/grouped_prices",
     dict(origin="HKG", destination="OKA", currency="hkd", group_by="departure_at", departure_at="2026-12", market="hk"))
show("v2 latest HKG", "https://api.travelpayouts.com/v2/prices/latest",
     dict(origin="HKG", destination="KIX", currency="hkd", limit=5, period_type="year", one_way="true", sorting="price", market="hk"))
show("v1 cheap HKG-TPE (current)", "https://api.travelpayouts.com/v1/prices/cheap",
     dict(origin="HKG", destination="TPE", depart_date="2026-12", currency="hkd"))
