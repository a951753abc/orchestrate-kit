# Close 報告：parseCsv 去除 UTF-8 BOM

## 做了什麼

- 工單 #1（sonnet-executor）：`parseCsv()` 讀入後去除首位 `\uFEFF`，新增 regression test 與 fixture；一次通過

## diff 摘要

- `src/csv/parse.ts`：+1 行，`split` 前加 `replace(/^\uFEFF/, '')`
- `tests/csv/bom.spec.ts`：新增 12 行
- `tests/fixtures/bom.csv`：新增 3 行
- 越界檔：無（`baseline.py compare` exit 0）

## 親自執行的測試證據

- `uv run baseline.py compare --baseline …/baseline-20260903T081500Z.json --allow src/csv/parse.ts --allow tests/csv/bom.spec.ts --allow-new tests/csv/bom.spec.ts --allow-new tests/fixtures/bom.csv` → exit 0，無 finding
- `npm test -- tests/csv/bom.spec.ts` → 1 passed
- `node scripts/import.js tests/fixtures/bom.csv` → `headers: [ 'id', 'name', 'email' ]`
- `npm run typecheck` → exit 0
- `npm test` → 12 suites / 87 tests passed

## 風險分級

- rg-20260903T081700Z-4c2e：低（judgement，無 gate；`src/csv/parse.ts` 3 個呼叫者、revert 即恢復、凍結測試覆蓋兩分支）；outcome 已回填 findings 0

## 未執行項目

- 外部 review：低風險（judgement 層判低），自驗取代

## 殘餘風險與仲裁紀錄

- UTF-16 BOM 未處理，不在本次範圍
- 無 findings 需仲裁

## baseline manifest

- 位置：C:/Users/x/AppData/Local/Temp/claude-orchestrate/3f2a9c1e/baseline-20260903T081500Z.json
- 清理狀態：保留（同目錄的 .patch 一併保留，供追溯）

## commit

未 commit，等待指示
