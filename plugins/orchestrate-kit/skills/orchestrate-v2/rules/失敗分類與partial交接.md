# Rule 1 - executor 失敗先分類再改派

- Level: `SHOULD`
- 額度／限流 → 停止發派，向使用者回報工單編號、失敗輸出與重置時間（有的話），等使用者指示；工單內容不動。executor 皆為 Opus，沒有其他系的 Claude executor 可改派。
- 測試失敗 → orchestrator 自己先讀輸出判斷是實作、測試還是環境問題，歸咎環境之前先做一個能區分環境與程式的實驗；再決定重派、改工單或回 Phase 1；不直接把同一張工單再丟一次。
- 逾時 → 不等、不把同一張工單原樣重派，直接照 Rule 2 的 partial 修改規則處理。
- executor 退回（工單模糊、驗收條件無法執行或互相矛盾）→ 工單切壞，回 Phase 2 重切，不催 executor 用猜的。
- 選配的 Codex job 失敗一次即 fallback 到對應的 Claude agent（reviewer → `opus-reviewer`、rescue → `opus-executor`），不重試；接法見 README。

## Good Example

- 這個例子是好的，因為 orchestrator 讀了實際輸出，把失敗歸到環境問題，改工單並附狀態交接後重派，而不是盲目重派。

````md
executor 回報：`npm test` 3 紅，全是 `ECONNREFUSED 127.0.0.1:5432`；已改 `src/csv/parse.ts`。
分類：環境（測試 DB 未啟動），非實作問題。
處置：工單 #2 驗收條件加「先 `docker compose up -d db`」，附狀態交接（已改 `parse.ts`、驗收卡在 DB 未啟動）重派同 executor。
````

## Bad Example

- 這個例子是壞的，因為它沒分類就重派，同樣的環境問題會讓第二次也失敗，白燒一輪。

````md
executor 失敗了，再派一次看看。
````

# Rule 2 - 留有 partial 修改的工單不得原封重派

- Level: `SHOULD`
- 凡 executor 已留下 partial 修改（失敗、逾時或被中止），不得把原工單原封不動重派。
- 二選一：附狀態交接後重發（已改哪些檔、哪些驗收已過、卡在哪一步、實際錯誤輸出），或用 baseline manifest 比對後還原到發派前狀態再重發。
- 還原範圍以 `scripts/baseline.py compare` 列出的檔案為準：只還原 executor 動過的檔案，使用者在 baseline 時就存在的修改以 manifest 同名 `.patch` 為原始內容。

## Good Example

- 這個例子是好的，因為交接寫清楚了已完成與卡點，接手的 executor 不必重做也不必猜。

````md
工單 #2（重發，附狀態交接）
- 已改：`src/csv/parse.ts`（BOM 去除已完成）
- 已過驗收：`tests/csv/bom.spec.ts`
- 卡點：`npm run typecheck` 報 `parse.ts:18` 型別不符，錯誤原文如下…
- 未動：`scripts/import.js`
````

## Bad Example

- 這個例子是壞的，因為工單原封重派，新 executor 不知道 working tree 已被改過，容易在半成品上疊加或把先前修改當成既有行為。

````md
上一個 executor 逾時了，同一張工單直接再派 opus-executor。
````

# Rule 3 - 連續兩輪沒有進展就停下報告，不硬闖

- Level: `SHOULD`
- 同一思路（同一張工單內容、同一修法方向）失敗兩次 → 停止微調，換思路：改工單、換 executor 層級、或依 Rule 1 回 Phase 1／Phase 2。選配的 Codex job 不適用「兩次」，失敗一次即 fallback。
- 連續兩輪發派→驗收都沒有進展 → 停下向使用者報告卡點、已排除的假設與實際輸出，由使用者決定是否繼續；不開第三輪相同方向的工單。
- 停損報告仍走 `templates/close-report.md`，在「未執行項目」與「殘餘風險與仲裁紀錄」段寫明停在哪一步、排除了什麼。

## Good Example

- 這個例子是好的，因為 orchestrator 兩輪後停下，報告列出兩輪嘗試、已排除的假設與尚未排除的卡點，把裁決交回使用者。

````md
工單 #2 兩輪（opus-lite-executor → opus-executor）皆卡在 `parse.ts:18` 型別不符。
已排除：tsconfig 差異（兩輪相同）、fixture 編碼（hexdump 確認 UTF-8）。
未排除：`csv-parse` 4.x 與 5.x 型別定義不同，升版會影響 3 個呼叫點。
→ 停下報告，不開第三輪；請使用者裁決升版或改型別。
````

## Bad Example

- 這個例子是壞的，因為第三輪只是換個措辭重派同方向的工單，沒有新假設也沒有新證據。

````md
兩次都卡型別，再派一次 opus-executor，工單加一句「請注意型別」。
````
