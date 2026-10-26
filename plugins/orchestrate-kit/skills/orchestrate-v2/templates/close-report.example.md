# Close 報告：parseCsv 去除 UTF-8 BOM

## 做了什麼

- 工單 #1（opus-lite-executor）：`parseCsv()` 讀入後去除首位 `\uFEFF`，新增 regression test 與 fixture；一次通過

## diff 摘要

- `src/csv/parse.ts`：+1 行，`split` 前加 `replace(/^\uFEFF/, '')`
- `tests/csv/bom.spec.ts`：新增 12 行
- `tests/fixtures/bom.csv`：新增 3 行
- 越界檔：無（`baseline.py compare` exit 0）

## 親自查核的測試證據

- `uv run baseline.py compare --baseline …/baseline-20260903T081500Z.json --allow src/csv/parse.ts --allow tests/csv/bom.spec.ts --allow-new tests/csv/bom.spec.ts --allow-new tests/fixtures/bom.csv` → exit 0，無 finding；通過（主控重跑）
- V1 `npm test -- tests/csv/bom.spec.ts` → `before-V1.txt` 1 failed、`after-V1.txt` 1 passed；通過（採 executor 證據，`after-V1.txt` 時間比對 True）
- V2 `node scripts/import.js tests/fixtures/bom.csv` → `after-V2.txt` 為 `headers: [ 'id', 'name', 'email' ]`；通過（採 executor 證據，時間比對 True）
- V3 `npm run typecheck` → `after-V3.txt` exit 0；通過（採 executor 證據，時間比對 True）
- V4 `npm test` → `before-V4.txt` 12 suites／86 passed／1 failed、`after-V4.txt` 12 suites／87 passed；通過（採 executor 證據，時間比對 True）

## 風險分級

- rg-20260903T081700Z-4c2e：低（judgement，無 gate；`src/csv/parse.ts` 3 個呼叫者、revert 即恢復、凍結測試覆蓋兩分支）；outcome 已回填 findings 0

## 待人工判斷事項

| 事項 | 類別 | 可能影響 | 需要人工做什麼 | 狀態 |
|---|---|---|---|---|
| V1～V4 沿用 executor 證據，未由主控重跑 | 沿用 executor 證據 | 證據不實時 BOM 修正可能沒有生效 | 需要時抽驗：重跑 `npm test -- tests/csv/bom.spec.ts` | 待接受 |
| UTF-16 BOM 未處理 | 已知限制 | UTF-16 編碼的 CSV 首欄名仍會帶 BOM | 決定接受或另開工單 | 待接受 |

## 未執行項目

- 外部 review：低風險（judgement 層判低），自驗取代

## 殘餘風險與仲裁紀錄

- 無 findings 需仲裁

## baseline manifest

- 位置：C:/Users/x/AppData/Local/Temp/claude-orchestrate/3f2a9c1e/baseline-20260903T081500Z.json
- 清理狀態：保留（同目錄的 .patch 一併保留，供追溯）

## commit

未 commit，等待指示
