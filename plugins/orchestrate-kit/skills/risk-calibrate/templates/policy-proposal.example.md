# risk-policy 校準提案：example-app

- policy 檔：<專案根目錄>/.claude/risk-policy.yaml
- 對照範圍：repo example-app，2026-09-03〜2026-09-30
- 分級總數 14：中高有 findings 5／中高無 findings 4／低有 findings 1／低無 findings 3／未回填 1

## 提案 1：audit_logging gate 排除 dashboard 定義檔

- 型態：過度升級
- 依據：rg-20260910T021500Z-a1b2、rg-20260912T083000Z-c3d4、rg-20260918T113000Z-e5f6、rg-20260925T070000Z-g7h8
- 現行措辭：`audit_logging.paths` 含 `**/monitoring/**`，無 exclude
- 建議措辭：`audit_logging` 加 `exclude: ["**/monitoring/dashboards/**"]`
- 預期影響：這 4 筆重跑會落到裁量層（JSON 不在白名單），依 blast radius 判定，預期為低；其餘 10 筆等級不變
- 生效方式：advisory 觀察一個週期，期間 dashboard 變更仍派 review 但標注「提案 1 觀察中」

## 提案 2：secrets gate 補 vault 目錄

- 型態：漏網
- 依據：rg-20260915T054500Z-i9j0
- 現行措辭：`secrets.paths` 以檔名子字串比對（`**/*secret*`、`**/*credential*` 等），未列 `vault/` 目錄
- 建議措辭：加 `**/vault/**`
- 預期影響：該筆（`app/vault/token_store.php`，review 找到 1 個明文寫入問題）重跑會命中 secrets gate → 中高；其餘 13 筆不變
- 生效方式：直接生效（補 gate 屬收緊，不需觀察期）

## 不提案的觀察

- rg-20260920T100000Z-k1l2：中高無 findings，命中 migration gate，只出現一次，樣本不足
