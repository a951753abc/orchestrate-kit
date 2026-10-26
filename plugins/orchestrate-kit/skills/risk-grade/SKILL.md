---
name: risk-grade
description: 對一組程式碼變更做風險分級：硬性 gate → safe-change 白名單 → 裁量三層漏斗，輸出等級、命中 gate 與理由並記入全域 ledger。供 orchestrate-v2 Phase 4、派 review 前、或手動查詢使用。結果回填用 scripts/risk_ledger.py outcome，定期校準走 risk-calibrate。
argument-hint: <變更範圍描述與脈絡>
---

# SOP

## Phase 1 -- 收集訊號

1. READ 讀取任務參數取得工單目標與任務形狀；若有 working tree 實際變更，另外取得 `git diff` 內容、untracked 清單與 executor 失敗／逾時紀錄。
2. WRITE 專案尚無 `.claude/risk-policy.yaml` 且呼叫方要求建立時，讀取 `templates/risk-policy.yaml` 與 `templates/risk-policy.example.yaml`，依骨架複製結構、參考範例填入專案的敏感路徑與 safe-change 範圍，寫入 `<專案>/.claude/risk-policy.yaml`。
3. DELEGATE 執行 `uv run "${CLAUDE_SKILL_DIR}/scripts/risk_signals.py" --repo <專案目錄> --git|--files <允許檔>... [--executor-failed]` 產出機械訊號 JSON；`verdict` 為 `none` 或 script exit 2 時停止並回報呼叫方，不分級。

## Phase 2 -- 判定等級

1. THINK `verdict` 為 `high` 或 `low` 時照它定案，不讀 rule，直接進 Phase 3。
2. THINK `verdict` 為 `judgement` 時，在同一回合一次讀取 `rules/硬性gate與safe-change白名單.md` 與 `rules/裁量判準.md`，判定等級與定案層，並寫出可追溯到具體檔案與行為的理由。

## Phase 3 -- 輸出報告並記帳

1. DELEGATE 以 `--git` 呼叫的判定執行 `uv run "${CLAUDE_SKILL_DIR}/scripts/risk_ledger.py" record --repo <專案目錄> --grade <high|low> --layer <gate|safe|judgement> [--gates <名稱>...] --reason <理由> --source <呼叫方> --files-count <檔案數>` 記入 `~/.claude/risk-grade/ledger.jsonl`，取得回傳的 id；以 `--files` 呼叫的估算不記 ledger。
2. WRITE 讀取 `templates/grade-report.md` 與 `templates/grade-report.example.md`，依骨架複製結構、參考範例填入本次判定結果，把分級報告交給呼叫方的後續步驟使用；以 `--files` 呼叫的估算在 ledger id 欄寫「以允許檔清單估算，以驗收後判定為準」。
