# OffDayz 機酒速報｜診斷＋方案＋進度

> 2026-10-26 Claude 撰。假期資料 `docs/data/holidays.json` 唯讀，本方案冇郁佢。

## 0. 2026-10-26 實測後更正＋已上線

**實測（用 repo secret 喺 Actions 探測）推翻咗下面兩點：**
- ~~F1 單程當來回~~：`v1/prices/cheap` **其實預設回傳來回價**（帶 `return_at`），頁面寫「來回」係啱嘅；錯嘅係 JSON 寫死 `is_round_trip:false`、`return_date:null`（DATA.md「不傳 return_date 即單程」係錯嘅）。已修正。
- ~~F4 market 錯~~：`market=hk / tw / 不傳` 回傳完全一樣，冇影響。但 **約 1/3 價格來自俄語代理商**（Biletix、Авиасейлс、City.Travel…），港台讀者用唔到 → 新管線已過濾。
- **H1 確認：LiteAPI key 係 sandbox（`sand_`），酒店價全部係測試價。** 已停發（hotels.json `status: paused`，TG 酒店訊息暫停）。

**已上線（main，2026-10-26）：**
- `deals.py` → `docs/data/deals.json`：v3 `prices_for_dates`，HKG(HKD)/TPE(TWD) → 沖繩/東京/大阪/福岡/札幌/名古屋，單程＋來回分開；每筆有 `observed_on`（由連結 search_date 解析）、`fetched_at`、`expires_at`（搜到後 4 日或出發前一日）、`source.url`；過期唔入庫
- 新頁 https://sssunwl.github.io/offdayz/deals/ ：前端再過濾過期、資料 >36 小時冇更新會出警告、撞港／台公眾假期會標「撞假」（讀 holidays.json，要等 v2 合併先有）
- 首頁加「⚡ 機酒速報」入口；酒店分頁改顯示暫停說明
- 每日 08:00 HKT cron 照舊，同時產出 deals.json

**仍待 SS：** 見第 3 節（marker、LiteAPI production／Agoda、SerpApi）。

---

## 1. 診斷：而家點抓、點解唔準

### 1.1 先更正兩個前提

| 以為 | 實際 |
|---|---|
| FlightNews 係獨立 repo，Actions 06-11 起一直 fail | `sssunwl/flightNews` **早已改名成 `sssunwl/offdayz`**（GitHub 自動轉址）。爬蟲 `flight_scraper.py` + workflow `flight_deals.yml` 已經喺 offdayz repo 嘅 main 度。只有 06-02~06-11 fail 過 6 次，之後 131 次全部 success |
| OffDayz 機酒自 07-07 停更 | 真停更係 **07-13 → 09-03**（近兩個月無資料 commit），09-03 健檢後已恢復，**今日 10-26 仍每日 10:43 HKT 更新**，線上 `flights.json` 都係今日。07-07 其實係 `seasonal.json`（季節活動）最後更新日 |
| 工作區 `FlightNews/flight_scraper.py` 係現役代碼 | 係 06-11 嘅**舊副本**，比 repo 版落後（無 baseline、無寫 JSON）。README 寫「Google Flights + Skyscanner 數據來源」**係錯嘅**，從來無用過 |

所以「併入」喺代碼層面其實已經完成咗一半；問題唔係停更，係**數據本身唔可信**。

### 1.2 機票：點解唔準（按嚴重度）

來源：Travelpayouts（Aviasales）`v1/prices/cheap`，**唔係即時查價，係 Aviasales 用戶過去幾日搜尋結果嘅快取**。

| # | 問題 | 證據 |
|---|---|---|
| F1 | **單程價當來回賣** | 代碼唔傳 `return_date` → 全部係單程（history 1,306 筆 `rt=false` 100%）。但 main 版頁面寫「6個月**往返**最低價」、v2 版寫「**來回**含稅」「最低來回機票」。讀者見到 HK$1,065 以為來回，實際只係去程 |
| F2 | **價格係舊嘅，但扮新** | 同一航線同一月份，連續兩日「價錢＋日期完全一樣」佔 **930/1,267（73%）**，最長同一個價連續出 9 日 → 典型快取重播。頁面顯示「更新：今日」，但價格可能係一星期前某人搜到、早已賣晒 |
| F3 | **API 有 `expires_at` 但完全無用** | Travelpayouts 回傳每筆過期時間，官方明言唔建議用過期價；代碼直接丟咗呢個欄位 |
| F4 | **市場錯（高機率）** | 無傳 `market` 參數 → 用預設市場快取（Aviasales 主力係俄語市場）。HK/TW 出發嘅搜尋量少，樣本稀，價格代理商組合都唔係港台用戶會見到嗰批。*需用 token 實測確認* |
| F5 | **用咗被淘汰嘅 endpoint** | 官方文件：`v1/prices/cheap` 已建議改用 `aviasales/v3/prices_for_dates` |
| F6 | **轉機混入最平** | 代碼喺 0/1/2 轉之間取最平，但頁面無標轉機次數 |
| F7 | **覆蓋唔夠** | 今日：OKA→HKG **0 個月有價**、TPE→HKG 只得 3 個月、OKA→TPE 只得 1 個月。日本只有沖繩，東京／大阪／福岡／札幌全部無 |
| F8 | **台灣受眾見港幣** | TPE 出發都係 `currency=hkd` |
| F9 | **無來源連結、無抓取時間、無下架** | 全站無任何訂購／來源連結（亦違反 Travelpayouts「數據要配合導流」嘅精神） |
| F10 | baseline 判斷被污染 | 「近 90 日最平 10% 🔥」係用 F2 嘅重播數據計，好多 `percentile: 0` 只係因為同一個舊價重複出現 |

### 1.3 酒店：點解存疑

來源：LiteAPI `v3.0/hotels/rates`，每城 4 星 `limit=8`，未來三個週末 2 晚 2 人。

| # | 問題 |
|---|---|
| H1 | **未確認係咪 sandbox key**。LiteAPI sandbox 會回**測試價**（唔係真價）；production key 要綁信用卡。GitHub secret 睇唔到內容 → **要 SS 確認 key 開頭係咪 `sand_`** |
| H2 | 只抽 8 間，「最平」其實係 8 揀 2 |
| H3 | 頁面寫「含稅總價」，代碼取 `retailRate.total`，未核實有無包當地稅／住宿稅 |
| H4 | LiteAPI 免費用有「搜尋：預訂比例」條款（文件寫 5000:1）；我哋只查唔訂，長遠有被收費／封 key 風險 |
| H5 | 同機票一樣：無來源連結、無抓取時間 |

---

## 2. 資料來源方案

### 2.1 已查證唔可行（唔使再諗）

| 來源 | 原因 |
|---|---|
| Amadeus Self-Service（免費） | **2026-07-17 已關閉**，只剩 Enterprise（要審批） |
| Kiwi Tequila | 2024 起停止自助申請，只限大量合作夥伴 |
| Skyscanner API | 只開放商業夥伴 |
| 自己爬 Google Flights / Trip.com / Skyscanner 網頁 | 違反對方條款，亦容易被擋，唔做 |

### 2.2 建議組合（三層）

**第 1 層｜發現（免費）— Travelpayouts 升級用法**
- 改用 `aviasales/v3/prices_for_dates`，傳 `market=hk`（香港出發）／`market=tw`（台北出發）、`currency=hkd`／`twd`
- 同一航線分開抓 `one_way=true`（單程）同 `one_way=false`（來回），頁面清楚標「單程／來回」
- **讀 `expires_at`，過期直接唔入庫**；搵唔到 `expires_at` 就以抓取時間 +48h 當過期
- 回傳嘅搜尋連結做「來源連結」（掛 Travelpayouts marker，順便有佣金）。*`link` 欄位格式未喺文件確認，第一步要實測*
- 定位誠實寫明：「Aviasales 用戶近期搜到嘅價，實際以訂購頁為準」

**第 2 層｜驗證（免費額度內，用唔用由 SS 決定）— SerpApi Google Flights**
- 免費 250 次／月 ≈ 每日 8 次。只用嚟**複查當日 Top 5 速報**，價差 >15% 就唔出或者改顯示驗證價
- 超額先要付費（約 US$25/1,000 次）→ **要 SS 批先開**
- 注意：SerpApi 本質係代爬 Google，法律責任由佢承擔，但始終係灰色地帶

**第 3 層｜速報（免費、零條款風險）— 官方促銷消息**
- HK Express、樂桃、台灣虎航、星宇、國泰等官方 newsroom／促銷頁：只抽「標題＋優惠期＋官方連結」，唔抄全文
- 呢層先係真正「速報」（快閃 sale），價格層做唔到。初期可半自動：爬標題 → Gemini 摘要 → 人手 / Sona 揀

**酒店**
- 短期：**先確認 LiteAPI key**。如果係 sandbox → 酒店價即刻落架（頁面改做「去 Agoda / Trip.com 查價」連結），唔好再展示假價
- 中期二揀一（SS 決定）：
  - A. LiteAPI production key（要綁卡；查價本身免費但有 look-to-book 風險）
  - B. 申請 Agoda 聯盟（免費，佣金約 4–7%；有 data feed，要審批）
  - 我建議 **B**：OffDayz 本身要導流變現，Agoda 對港台用戶認受性高

### 2.3 航線範圍（日本優先）

出發：HKG、TPE（第二階段再考慮 KHH）
目的地：OKA、NRT/HND（東京）、KIX（大阪）、FUK（福岡）、CTS（札幌）、NGO（名古屋）
= 2 × 6 = 12 條，每條單程＋來回，每日一次。沖繩→港台嗰兩條（OKA 出發）因為受眾唔係日本人，**建議刪走**。

---

## 3. 要 SS 拍板嘅事

1. **LiteAPI key 係咪 sandbox？**（GitHub → offdayz → Settings → Secrets 睇唔到值，要去 LiteAPI dashboard 睇）
2. **SerpApi 免費驗證層開唔開？**（開咗要註冊帳號；超額收費前會再問）
3. **酒店中期走 Agoda 定 LiteAPI production？**
4. **喺邊個分支做？** 我建議：
   - 資料管線（`flight_scraper.py`、workflow、`docs/data/deals.json`）→ **main**（因為 cron 只喺 main 跑，v2 會定期 merge main）
   - 前端「機酒速報」區塊 → **feat/v2-redesign**（main 版前端唔再投資）
   - 或者 SS 想先合併 v2 再做，都得
5. 頁面上錯寫「往返／來回」嘅字眼，**可唔可以即日先改成「單程」**（一行字嘅止血，喺新管線上線前）？

---

## 4. 實作草案（SS 確認後寫成 Codex 工單）

### 4.1 新檔 `docs/data/deals.json`（只加不改，舊 `flights.json` 保留至前端切換完）

```json
{
  "generated_at": "2026-10-27T01:00:00Z",
  "deals": [{
    "id": "f-HKG-KIX-20261205-rt",
    "kind": "flight",
    "origin": "HKG", "dest": "KIX",
    "depart": "2026-12-05", "return": "2026-12-09",
    "trip": "round_trip",
    "price": 1980, "currency": "HKD",
    "airline": "UO", "stops": 0,
    "source": { "name": "Aviasales", "url": "https://..." },
    "fetched_at": "2026-10-27T01:00:00Z",
    "expires_at": "2026-10-28T09:12:00Z",
    "verified": null,
    "window_id": "hk-2026-xmas"
  }]
}
```

- `fetched_at`＝我哋抓嘅時間；`expires_at`＝API 給嘅過期時間（無就 +48h）；`source.url` 必填，無連結唔入庫
- `window_id` 對應 `holidays.json` 嘅假期窗口（只讀），「放假，去哪？」直接用

### 4.2 過期自動下架（兩重保險）
1. **管線**：每日跑時剔走 `expires_at < now` 或 `depart < 今日+1`
2. **前端**：讀 `deals.json` 時再用瀏覽器時間過濾一次 → 就算 cron 死咗，過期價都唔會出現；`generated_at` 超過 36 小時，區塊頂顯示「資料暫停更新」而唔係扮新

### 4.3 每張卡必顯示
價錢＋幣別＋**單程／來回**＋轉機次數＋「X 小時前抓取」＋來源名＋「去訂」連結

### 4.4 收尾
- 工作區 `FlightNews/` 改 README 指向 offdayz，舊 `flight_scraper.py` 移入 `_archive/`（唔刪）
- Telegram 推播沿用，改讀 `deals.json`

### 4.5 分工
Codex 實作（管線 → 前端兩張工單），Claude 審：重點驗 F1/F2/F3 有冇真正解決（用 history 再跑一次「連續重複率」，目標 <20%）
