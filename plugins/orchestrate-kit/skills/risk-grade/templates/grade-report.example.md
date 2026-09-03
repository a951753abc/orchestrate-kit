# 風險分級：工單 #1 apply_discount 依規格四捨五入

- ledger id：rg-20260903T031500Z-a1b2
- 等級：中高
- 判定層：gate
- policy 來源：skill 預設（專案無 .claude/risk-policy.yaml）
- 呼叫來源：orchestrate-v2

## 命中 gate

- payment（路徑類）：`pricing.py` 命中 `**/*pricing*`；diff 把 `int()` 截斷改為 `ROUND_HALF_UP`，直接影響每筆訂單金額
- 語意類：不另行檢查（機械層已為 gate）

## safe-change 分類

- 無（`pricing.py` 未落在任何白名單類別）

## 裁量理由

不適用（gate 層已定案，未讀 rule）

## diff 統計與分批建議

- 檔案 1、+4／-1
- 不需分批

## 建議處置

派外部 review。focus 重點：捨入方向對負數與 .5 邊界的行為、既有算例 850／899／854 是否維持、`Decimal(str(...))` 對非 int 輸入的行為差異。
