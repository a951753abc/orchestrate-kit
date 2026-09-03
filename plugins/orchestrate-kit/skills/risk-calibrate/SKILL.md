---
name: risk-calibrate
description: 以 risk-grade 全域 ledger 的分級與結果對照做校準：找出過度升級與漏網的重複型態，產出 risk-policy 措辭修改提案交使用者裁決，不直接改 policy。使用者要求校準、或某專案 ledger 累積約 10 筆已回填紀錄時使用。
argument-hint: "[<專案目錄>]"
---

# SOP

## Phase 1 -- 取得對照

1. DELEGATE 執行 `uv run "${CLAUDE_PLUGIN_ROOT}/skills/risk-grade/scripts/risk_ledger.py" summary --json [--repo <專案目錄>]` 取得四象限計數、過度升級候選與漏網候選；`pending` 未回填的紀錄先列給呼叫方補回填，不納入本次對照。
2. READ 讀取候選紀錄各筆的 gates／layer／reason／result，與該專案生效中的 risk-policy，定位重複型態來自哪個 gate 或白名單類別。

## Phase 2 -- 產出提案

1. THINK 讀取 `rules/校準判準.md`，判定每個重複型態屬過度升級或漏網，收斂成 gate 措辭、exclude 或白名單類別的修改方向。
2. WRITE 讀取 `templates/policy-proposal.md` 與 `templates/policy-proposal.example.md`，依骨架複製結構、參考範例填入依據 ledger id、現行措辭、建議措辭與預期影響，交使用者裁決；不直接修改 policy。
