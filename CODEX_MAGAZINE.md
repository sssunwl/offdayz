# 工單:拿掉機酒速報 + 前台雜誌化(2026-11-12)

> 給 Codex。Claude 規劃與審查,SS 拍板。
> 工作目錄:`offdayz/.worktrees/magazine`(分支 `feat/magazine`,已從 origin/main 開好)。
> **不要 commit、不要碰 `.git`、不要 push。** 做完在本檔最後的「交付回報」寫下改了哪些檔、測試結果、未完成項。

## 0. 為什麼要改

SS 2026-11-12 拍板兩件事:

1. **機酒速報不做了。** 前台所有機票價、酒店價、「最抵」、「機酒」字眼和 `/deals/` 頁全部拿掉。
2. **前台不夠雜誌。** 現在前台只套了 `magazine.css` 的紙紋和字體,版面骨架仍是「大標+一排按鈕+一段段卡片」的一般網站(見 `.ref/now_front.png`)。反而 SS 內部的 Sona 後台頁才像一本雜誌(見 `.ref/ref_sona_overview.png`、`.ref/ref_sona_brandbook.png`)。前台要改成那個樣子。

品牌真相來源:`../../../SonaSNS-Platform/offdayz-brand.html` + `../../../SonaSNS-Platform/assets/brandbook/offdayz.css`(唯讀,可以照抄做法和 CSS,不要改那邊)。

## 1. 範圍

### A. 拿掉機酒(全站)

| 位置 | 動作 |
|---|---|
| 所有頁的桌面導覽、手機選單 | 刪「機票・酒店」「機酒速報」 |
| 所有頁的頁尾 | 刪「機票價格」「酒店精選」連結;刪「機酒價格每日自動更新」「價格僅供參考…」句;改成假期資料來源說明 |
| `docs/index.html` | 刪 hero「看今日最抵」按鈕、「今日最低機票」卡、`#deals`、`#hotels` 兩段,以及讀 `flights.json`/`hotels.json`/`deals.json` 的 JS |
| `docs/destinations/city.html` | 刪「即時機票最低價」「週末酒店報價」兩段與相關 JS |
| `docs/destinations/index.html`、`docs/seasonal/index.html` | 刪讀 `flights.json` 的地方和顯示價格的 UI;meta description 去掉「機酒報價」 |
| `docs/assets/site.js` | `updateStatus` 那套「價格更新時間」pill/頁尾/notice 拿掉或改成不依賴價格資料;其他頁不能因此報錯 |
| `docs/deals/index.html` | 改成極簡轉址頁:`<meta name="robots" content="noindex">` + meta refresh 到 `../`,保留一行文字連結。舊連結不能 404 |
| `docs/offdays/` | 「查機票/查酒店」外部搜尋連結**保留**(那是幫讀者查,不是速報);只把頁尾「機酒速報」連結和價格免責句改掉 |

**不要動**:`flight_scraper.py`、`deals.py`、`.github/workflows/`、`docs/data/*.json` 及其欄位、`data/history/`。排程是否停由 SS 另外決定。資料檔留著沒關係,只是前台不再讀。

### B. 首頁雜誌化(`docs/index.html`)

照 `.ref/ref_sona_overview.png` 的版式,首頁是一期雜誌,由上到下:

1. **刊頭**:大字 `OffDayz`(Off 深綠、Dayz 朱紅斜體,Fraunces),上方粗線、下方雙線;右側打字機字 `ISSUE NN · MMM YYYY`(期數 = 2026-11 起算的第幾個月,JS 依今天算)、`HK · TPE DEPARTURES`;左下小字「放假,去哪?」。頂部貼一條紙膠帶。
2. **封面故事**:eyebrow `COVER STORY`;大標「先看你什麼時候有假,<br>再告訴你去哪裡。」(「什麼時候有假」芥末螢光筆底);一段導言;斜體英文 `Off days, well spent.`。右側疊 3 個**入境章**(圓章/方章混搭,城市中文+英文+機場代碼+日期,略旋轉),城市從 `docs/destinations/data/*.json` 取,日期用下一個共同連假的日期。
3. **下一個假期(登機證)**:沿用現有 `SoSol.nextWindow(CAL)` 的計算,但呈現成登機證卡:`BOARDING · N PAX`、日期區間、`HKG → ???`、天數、虛線撕口、右側直排 `SEAT`。空狀態照舊處理。連到 `calendar/`。
4. **目次**(牛皮紙底、頂部打孔圓點、底部撕頁邊):P.02 放假去哪 / P.03 目的地 / P.04 口袋地點 / P.05 季節限定 / P.06 假期年曆,每列「中文標題+小字說明 ··· 頁碼」,整列是連結。**取代現在 hero 那排按鈕。**
5. 每個內容段落都是一張**紙**(米白底、撕頁邊、紙紋),段頭格式 `P.0N 中文標題 English italic`(見 Sona 頁):
   - **P.02 放假去哪**:從 `offdays.json` 取最近 3 個窗口,每個做成 Sona 「GATE A1」那種票根卡(左邊內容、右邊直排 `OPEN`/`READ` 撕口)。
   - **P.03 目的地**:每城一張「入境章+旅行資料欄」卡(資料欄列:時區、簽證、貨幣、最佳月份,取自城市 JSON;**不放價格**)。
   - **P.04 口袋地點**:沿用現有資料,改成貼紙膠帶的拍立得/底片框樣式。
   - **P.05 季節限定**:目次式清單(日期 ··· 地點),最多 6 條。
6. **編輯手記**(深綠底,收尾):一句大引言+兩三點「這期怎麼用」,文字寫死即可,語氣照品牌書「懂排假的朋友」。
7. 頁尾保留,去掉價格相關字。

### C. 其他頁跟上

`destinations/`、`destinations/city.html`、`places/`、`seasonal/`、`offdays/`:不重排內容,只把頁首換成同款**刊頭小版**(OffDayz + 該頁的 `P.0N 欄目名 English`),段頭改成 `P.0N` 格式,內容區包成紙張+撕頁邊。`calendar/` 照 AGENTS.md 只准動 `calendar-theme.css`。

## 2. 規則

- 樣式寫進 `docs/assets/magazine.css`(雜誌層),不要在頁面內另開色票;色票只用 `sosol.css` + `--kraft`。可以從 Sona 的 `offdayz.css` 搬 class 過來(入境章、登機證、目次、撕頁邊、紙膠帶、票根卡),搬過來要改成本站的變數名。
- 不加任何新相依、新字型以外的 CDN;字型維持 magazine.css 已載入那三套。
- 中文大標 `line-height ≥ 1.05`、`letter-spacing ≥ -0.01em`(方塊字不能黏)。
- 手機 375px:刊頭縮小但不換行斷字;入境章縮成一排或藏到兩個;不能有橫向捲動。
- 所有資料載入失敗都要有空狀態,不能留「載入中…」。
- 不要寫任何「熱門」「最抵」「必去」字眼。
- 保留 `id="places"` 等現有錨點(別的頁有連進來);刪掉的 `#deals`/`#hotels` 錨點不用保留。

## 3. 測試

- 更新 `tests/frontend.test.cjs`:拿掉跟 deals/hotels 有關的斷言,新增「首頁不含 `flights.json`/`hotels.json`/`deals.json`」「全站 HTML 不含『機票・酒店』『機酒』」「首頁有刊頭、目次、登機證三個區塊」。
- `node --test tests/*.test.cjs` 全過;`python3 -m pytest tests -q` 照舊全過(Python 端不應受影響)。
- 你跑不了瀏覽器沒關係,版面由 Claude 用 headless Chrome 驗收。

## 4. 交付回報

2026-11-12 Codex 交付：首頁 `docs/index.html` 已改為刊頭、封面故事、入境章、共同連假登機證、牛皮紙目次、假期票根、城市旅行資料、口袋地點底片框、季節清單與編輯手記；期數按台港日期從 2026-11 起算，資料失敗與無未來假期皆提供空狀態。樣式集中在 `docs/assets/magazine.css`，沿用既有 token 與字型；沒有新增前端相依。

修改檔案：`docs/index.html`、`docs/assets/magazine.css`、`docs/assets/site.js`、`docs/deals/index.html`、`docs/destinations/index.html`、`docs/destinations/city.html`、`docs/places/index.html`、`docs/seasonal/index.html`、`docs/offdays/index.html` 及 `docs/offdays/*/index.html` 全部 25 個假期窗口頁、`docs/calendar/calendar-theme.css`、`tests/frontend.test.cjs`、本工單。次頁加入小刊頭、欄目頁碼與紙頁外觀，保持內容順序；前台報價 UI、JSON 請求、導覽及價格頁尾已移除，舊 deals 路徑保留 noindex 轉址。假期攻略的外部查機票／查酒店連結與日期切換保留。

驗證：`node --test tests/*.test.cjs`：19 項，18 通過、0 失敗、1 略過（工作樹旁沒有 SunFamilyTrip/calendar.html，無法進行副本比對）。涵蓋資料正常／全部失敗／部分城市失敗、八個城市、空狀態、季節篩選、手機選單開關與 Escape、前台無報價資料請求、全站 HTML 無退役導覽文案及舊路徑轉址。`python3 -m pytest tests -q` 已執行，環境回報 `No module named pytest`，未能完成 Python 測試。

待驗收：未執行實際瀏覽器排版驗證，375px 無橫向捲動、字型載入及桌面視覺請由 Claude headless Chrome 驗收；已加入對應的窄螢幕樣式。沒有修改 calendar HTML、抓價程式、工作流程或任何 JSON；沒有 commit、操作 .git 或 push。後續若重新執行既有假期頁產生器，需同步更新產生器模板，否則可能覆蓋本次靜態頁修改；本工單未改產生器。

### 第二輪

2026-11-12 修正 `docs/index.html`、`docs/assets/magazine.css`、`tools/build_offdays.py`、`tests/frontend.test.cjs` 與本工單。登機證改成「HKG · TPE → 去哪？」，「去哪？」使用 `--blue` 朱紅。刊頭 dateline 右側改成「EST. 2026 · OFFDAYZ.SSSUNI.COM」，封面的英文句保留。

封面與八張城市卡共用入境章規則。日本使用 `--blue`、韓國使用 `--navy`、台灣使用現有的 `--lagoon`（#8FBFB2）。圓章與方角長方章依城市索引交替，旋轉角度以 `-12 + (index * 7) % 25` 計算，八張各有不同角度，範圍為 -12° 到 12°，重載結果固定。日期仍依下一個共同連假顯示。

產生器模板已同步桌面／手機導覽、頁尾、hero 連結、小刊頭、`column-main`、段頭 `data-folio="P.02"` 與樣式載入順序。實際執行 `python3 tools/build_offdays.py --today 2026-11-09`，沿用原資料的產出日期，成功重建香港 12 頁、台北 13 頁及總表。重跑前後以 SHA-256 比對 `docs/offdays/` 全部 28 個檔案與 `docs/data/offdays.json`，共 29 個檔案逐一內容完全一致，新增／刪除／變更均為 0。因本輪要求不操作 .git，使用逐檔內容比對驗證產出一致性，未執行 `git diff --stat`。

`node --test tests/*.test.cjs` 共 20 項，19 通過、0 失敗、1 略過，略過原因仍為缺少相鄰 SunFamilyTrip 年曆副本。新增回歸測試涵蓋登機證與刊頭文案、各國章色、交替形狀、八個固定旋轉角度及封面／城市卡一致性。`python3 -m unittest discover -s tests -v` 共 21 項全部通過。

本輪未再執行瀏覽器視覺驗收，375px 版面結果以上輪 Claude 驗收為基準，新增章形與文字仍待實際瀏覽器複驗。第一輪提到的產生器模板同步與 Python 測試待辦已完成。

### 第三輪

已刪除 `docs/destinations/city.html` 殘留的 `live-flights`、`live-hotels` 載入區塊及各自多出的 `</div>`。本輪採用段頭移除 folio 的方案，城市頁四段保留 eyebrow 與標題，P.03 僅出現在小刊頭。目的地總表、季節頁與全部 25 個假期窗口頁也採同一規則，移除段頭 `data-folio`，欄目頁碼保留在小刊頭。

修改檔案為 `docs/destinations/city.html`、`docs/destinations/index.html`、`docs/seasonal/index.html`、`docs/offdays/*/index.html`、`tools/build_offdays.py`、`tests/frontend.test.cjs` 與本工單。假期產生器模板同步移除段頭 folio，實際執行 `python3 tools/build_offdays.py --today 2026-11-09` 後，比對修正後的靜態頁與重跑產出，共 29 個檔案的 SHA-256 完全一致，含總表、CSS、JS 與 `offdays.json`。

全站 33 個 HTML 的 div 開關數量相等，新增前端測試也依出現順序檢查靜態 div 巢狀，避免總數相同卻仍有孤立閉合標籤。另以 Python 標準庫 HTMLParser 檢查 33 頁靜態 HTML 的全部非空元素開關及巢狀順序，均通過。新增城市頁不得含 `live-flights`／`live-hotels`，以及次頁段頭不重複欄目 folio 的回歸斷言。

`node --test tests/*.test.cjs` 共 22 項，21 通過、0 失敗、1 略過，略過原因為缺少相鄰 SunFamilyTrip 年曆副本。`python3 -m unittest discover -s tests -v` 共 21 項全部通過。本輪尚未執行瀏覽器視覺複驗。
