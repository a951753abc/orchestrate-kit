# 工單 #1：parseCsv 去除 UTF-8 BOM

- 任務形狀：bug
- 路由：opus-lite-executor
- 交付範圍：CSV 匯入 BOM 修正
- 專案目錄：C:/Users/x/project
- baseline manifest：C:/Users/x/AppData/Local/Temp/claude-orchestrate/3f2a9c1e/baseline-20260903T081500Z.json
- 證據檔目錄：C:/Users/x/AppData/Local/Temp/claude-orchestrate/3f2a9c1e/evidence-wo1/

## 目標

`parseCsv()` 讀取 UTF-8 BOM 開頭的檔案時，首欄名不得帶 `\uFEFF`。

## 使用情境

內部匯入工具：維運人員在自己的電腦匯入客戶提供的 CSV；匯入結果可從原始 CSV 重新匯入，匯入錯誤由維運人員刪掉該批後重跑。

## 允許修改的檔案

- `src/csv/parse.ts`
- `tests/csv/bom.spec.ts`
- `tests/fixtures/bom.csv`

- 可新增檔案：是（僅限上列兩個測試檔）
- 可安裝套件：否
- 預期 generated artifacts：無

## 驗收條件

- V1（修改前要跑）：`npm test -- tests/csv/bom.spec.ts`，修改前失敗、修改後全綠
- V2（修改前要跑）：`node scripts/import.js tests/fixtures/bom.csv`，修改前第一個欄名為 `\uFEFFid`、修改後為 `id`
- V3（只在修改後跑）：`npm run typecheck` exit 0
- V4（修改前要跑）：`npm test`，修改後的失敗數不多於修改前，且沒有新的失敗案例

## 禁止事項

- 不順手重構、不改善無關程式碼、不擴大 scope、不放鬆既有測試或 gate
- 允許清單外的檔案一律禁區；需要動清單外檔案時停止並回報，不自行擴權
- git 寫入操作（add／commit／reset／checkout／restore／clean／stash）一律禁止，除非本工單下方明示授權
- 不改 `scripts/import.js` 的輸出格式

## 測試品質約束

- 期望值必須來自獨立來源（已知字面值、規格算例），不得用與實作同邏輯重算出期望值
- 測試只落在 `parseCsv()` 的回傳值上斷言，不 mock 內部協作者、不驗證呼叫次數與順序

## 診斷依據

- 已觀察：`tests/fixtures/bom.csv` 重現率 100%，首欄名為 `\uFEFFid`
- 根因證據：`hexdump -C tests/fixtures/bom.csv | head -1` 前三 byte 為 `ef bb bf`；`parse.ts:12` 以 `split(',')` 直接切首行
- 已排除：「readFile 編碼設定」假說（`encoding: 'utf8'` 已是預設，且 Node 不會自動去 BOM）

## Bug 補充驗收

- 修正前失敗證據：V1、V2 的 `before-V1.txt`、`before-V2.txt`
- regression test：V1 修改前失敗、修改後通過
- 原始症狀驗證：V2
