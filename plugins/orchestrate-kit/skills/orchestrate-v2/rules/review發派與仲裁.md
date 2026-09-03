# Rule 1 - focus 文字涵蓋四面向，findings 依面向分組回報

- Level: `SHOULD`
- focus 文字須涵蓋四個面向：
  1. 需求與驗收條件是否實際滿足
  2. root cause 與修改是否對應
  3. correctness／邊界條件／回歸風險
  4. 是否存在不必要修改或 scope drift
- risk-grade 回報的命中 gate 與裁量理由要寫進 focus，讓 reviewer 知道這輪為何被判中高。
- 不為不同面向分別啟動 reviewer；一次 review 帶齊四面向。
- 預設 reviewer 為 `opus-reviewer`；已選配 `codex-reviewer`（接法見 README）時先派它，失敗一次即 fallback 到 `opus-reviewer`，帶同一份 focus，不重試。
- findings 須依面向分組回報，各面向內自行排嚴重度；不做跨面向的總排名，避免一個面向的問題遮蔽另一面向。

## Good Example

- 這個例子是好的，因為四面向各有本輪改動的具體對照物，且帶入了分級命中的 gate。

````md
focus（risk-grade：中高，命中 payment gate）：
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
