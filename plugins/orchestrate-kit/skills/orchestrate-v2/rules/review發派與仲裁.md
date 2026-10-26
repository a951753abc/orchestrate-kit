# Rule 1 - focus 文字涵蓋四面向與使用情境，findings 依面向分組並標觸發分類

- Level: `SHOULD`
- focus 文字須涵蓋四個面向：
  1. 需求與驗收條件是否實際滿足
  2. root cause 與修改是否對應
  3. correctness／邊界條件／回歸風險
  4. 是否存在不必要修改或 scope drift
- risk-grade 回報的命中 gate 與裁量理由要寫進 focus，讓 reviewer 知道這輪為何被判中高。
- focus 帶本次的使用情境（誰在用、什麼環境、資料可否重建、誰負責復原），取自工單「使用情境」段。
- 要求每條 finding 在觸發情境之外標觸發分類：「正常使用可觸發」或「特殊條件才觸發」，並寫出觸發依據與影響；依據不足時觸發分類寫「不確定」，不猜發生機率。
- 不為不同面向分別啟動 reviewer；一次 review 帶齊四面向。
- 預設 reviewer 為 `opus-reviewer`；已選配 `codex-reviewer`（接法見 README）時先派它，失敗一次即 fallback 到 `opus-reviewer`，帶同一份 focus，不重試。
- findings 須依面向分組回報，各面向內自行排嚴重度；不做跨面向的總排名，避免一個面向的問題遮蔽另一面向。

## Good Example

- 這個例子是好的，因為四面向各有本輪改動的具體對照物，帶入了分級命中的 gate，也帶入了使用情境，reviewer 能據此判斷觸發分類與影響。

````md
focus（risk-grade：中高，命中 payment gate）：
使用情境：會員在前台申請退款，資料寫進正式訂單庫、不可重建，退款錯誤由客服人工沖正
1. 需求與驗收：工單 #5 要求退款金額不得超過原付款；對照 `tests/refund.spec.ts` 新增案例
2. root cause 對應：修改是否只針對 `calcRefundable()` 的 off-by-one，未動其他路徑
3. correctness／邊界／回歸：部分退款重複呼叫、金額為 0、幣別不同
4. scope drift：`refund.ts` 以外的檔案是否被動到
````

## Bad Example

- 這個例子是壞的，因為 focus 只有一句話，reviewer 只能泛泛而談，findings 也混成一份總排名。

````md
focus：幫我看看有沒有 bug。
````

# Rule 2 - 分批一次分好、不重審、禁巢狀

- Level: `SHOULD`
- review／終審對象超過一個 agent 能讀的量（risk-grade 回報超過注意力上限，或超過 20 檔）時，orchestrator 先按 ≤20 檔一批切好，再並行發派。
- reviewer 禁止巢狀再派 subagent。
- 已審過的範圍不因換批次方式再審一次。
- 可機械判定的檢查項（詞庫、regex）先由專案的 lint／validation 跑掉，AI review 只看剩下的語意項。

## Good Example

- 這個例子是好的，因為批次在發派前一次切好，機械項已由 lint 先過濾。

````md
review 對象 47 檔 → 先跑 `npm run lint:terms`（詞庫檢查，0 錯）
→ 切三批（16／16／15 檔），三個 reviewer 並行，各帶同一份 focus
````

## Bad Example

- 這個例子是壞的，因為它是 2026-08-27 的實際事故：終審 agent 巢狀派了 6 個子 agent，主線之後又把同一批對象重拆成七批重跑，終審做了兩遍。

````md
reviewer：「檔案太多，我再開 6 個 subagent 分頭看。」
orchestrator：「這輪改依模組重拆七批，全部再審一次。」
````

# Rule 3 - 每個交付範圍只做一輪完整 review，修正工單只確認修好沒有與新風險

- Level: `SHOULD`
- 交付範圍＝同一個請求在 close 前要一起交付的工單；使用者改設計造成的重做算新的交付範圍。
- 交付範圍內最後一張一般工單通過 compare 後，對整個交付範圍做一輪完整 review（必要分批算同一輪）；前面的工單不各自 review。
- 修正工單（仲裁後為了修 findings 開的工單）不做完整 review：工單的驗收條件列原 finding 的重現與受影響的驗收，由 executor 執行並寫證據檔；orchestrator 讀證據檔確認原 finding 已修好，並讀修正 diff。
- 修正 diff 的 `risk_signals.py --files` 結果只用來決定要不要加做針對性 review，不當作修好的證據：`gate_hits` 出現交付範圍分級時沒有的 gate，才只對這段修正 diff 做一次針對性 review。
- 修正 diff 涉及底線（刪改資料、改變授權、波及其他系統）時，不論命中哪個 gate，都停止本工單的後續驗收、回報使用者裁定，不再開自動 review。路徑類 gate 看的是檔案路徑，同一支檔的危險修正仍命中原本的 gate，只看有沒有新 gate 會漏掉。
- review 只做一輪，不代表必要修正可以不修完；未解決的必要修正不能因此結案。

## Good Example

- 這個例子是好的，因為整個交付範圍只做一輪完整 review，修正工單只確認原 finding 已修好，並以 `gate_hits` 與是否涉及底線判定不必再 review。

````md
交付範圍「CSV 匯入修正」含工單 #1～#3
→ #3 通過 compare 後 risk-grade 判中高 → 一次 reviewer 審 #1～#3 全部 diff
→ 仲裁 F1 真問題 → 修正工單 #4 只改 `src/csv/parse.ts`
→ 讀修正 diff 與 executor 的證據檔（F1 的重現與受影響的驗收），確認 F1 已修好
→ `risk_signals.py --files src/csv/parse.ts` 的 `gate_hits` 空、與原分級相同；修正只改字串處理、不涉及底線 → 不再 review
````

## Bad Example

- 這個例子是壞的，因為照『只看新 gate』處理 2026-10-06 部署案的那張修正工單，會放過刪除整個資料庫的修正：三支部署腳本實測都只命中 `infra_ci`，修正改的是同一支檔；涉及底線時應停下交使用者裁定。

````md
修正工單把 `scripts/deploy/import-db.ps1` 的 `-Reset` 改成刪除整個資料庫（同一顆 MySQL 上還有舊系統的資料庫）
→ `risk_signals.py --files scripts/deploy/import-db.ps1` 的 `gate_hits` 只有 `infra_ci`，與原分級相同
→ 判「沒有新 gate，不 review」，直接 close
````
