對抗式 review focus（工單 #1；批次 1／1；diff 範圍：`git diff HEAD -- src/csv/parse.ts tests/csv/bom.spec.ts tests/fixtures/bom.csv`）
risk-grade：中高，命中 executor_history；理由：sonnet-executor 第一次逾時，改派 opus-executor 後通過，依執行歷史 gate 派 review

1. 需求與驗收條件是否實際滿足：`tests/csv/bom.spec.ts` 是否真的以含 BOM 的 fixture 驗證首欄名，而非只測 `replace` 函式本身
2. root cause 與修改是否對應：修改是否只針對首行 BOM（`parse.ts:12` 的 `split` 之前），未動到其他解析路徑
3. correctness／邊界條件／回歸風險：空檔案、只有 BOM 的檔案、BOM 出現在非首位、CRLF 換行；既有 `tests/csv/*.spec.ts` 是否仍全綠
4. 是否存在不必要修改或 scope drift：允許修改的檔案只有 `src/csv/parse.ts`、`tests/csv/bom.spec.ts`、`tests/fixtures/bom.csv`，其餘任何變更都列出

findings 依上列四面向分組回報，各面向內自行排嚴重度，不做跨面向總排名；每條含 檔案:行號、嚴重度、指控內容。找不到問題就明說「無 findings」。
