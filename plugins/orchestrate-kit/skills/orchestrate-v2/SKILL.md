---
name: orchestrate-v2
description: tech lead 派工流程：診斷→切工單→發派 executor→驗收→分級 review→仲裁→close；判準、樣板與腳本只在對應步驟按需載入
argument-hint: <要完成的任務描述>
disable-model-invocation: true
---

# SOP

## Phase 1 -- 診斷與假設分類

1. READ 讀取任務描述與相關 code，判定影響範圍並產出任務分解；若任務屬 bug／測試失敗／flaky／效能退化，先依 `orchestrate-kit:debug-by-evidence` skill 取得證據；若任務需要功能 SPEC 而尚無使用者核可版本，停止並回報，由 `orchestrate-kit:executable-spec` skill 另行產出，本 skill 不撰寫 SPEC。
2. THINK 讀取 `rules/假設分類與衝突處理.md`，明列會影響產品行為、架構或修法的假設並分類；須使用者裁決的未決假設釐清後才進 Phase 2。

## Phase 2 -- 切工單

1. THINK 在同一回合一次讀取 `rules/工單判準與形狀補充.md`、`templates/work-order.md` 與 `templates/work-order.example.md`，判定任務形狀並收斂每張工單的邊界、允許檔清單、驗收加項與所屬交付範圍。
2. DELEGATE 對每張工單執行 `uv run "${CLAUDE_PLUGIN_ROOT}/skills/risk-grade/scripts/risk_signals.py" --repo <專案目錄> --files <允許檔>...`，取輸出的 `gate_hits` 附記於該工單供 Phase 3 路由使用；此估算不記 ledger、不產分級報告。
3. WRITE 依已讀骨架複製結構、參考範例填入每張工單，含使用情境與證據檔目錄，驗收條件逐條標「修改前要跑」或「只在修改後跑」；必填段缺一不發派；路由為主控自己做的工單（`rules/委派門檻與路由.md` Rule 2）只需在回合內列出目標、允許檔、驗收條件，不寫工單檔。

## Phase 3 -- 發派

1. THINK 判斷是否委派、派給哪個 executor、可否平行時，讀取 `rules/委派門檻與路由.md` 決定路由；路由結果為主控自己做時，跳過步驟 2～3，直接照工單修改並執行驗收，完成後進 Phase 4（Phase 4 步驟 1 的 compare 與步驟 5 的 `check_evidence.py` 對主控自做工單不適用，步驟 5 改為讀自己執行的終端輸出判定）。
2. DELEGATE 發派 `opus-executor`／`opus-lite-executor` 時，plugin 內建的 PreToolUse hook（`scripts/baseline_hook.py`）會從工單的「專案目錄」行（沒有就用 session cwd）自動 snapshot working tree，記下 additionalContext 給的 manifest 路徑供驗收比對；hook 回報未自動 snapshot（不是 git repo）時，才手動執行 `uv run "${CLAUDE_SKILL_DIR}/scripts/baseline.py" snapshot`；hook 失敗會擋下這次派工，照擋下訊息手動執行同一指令，並在工單加一行 `baseline manifest：<manifest 路徑>` 後重新發派（hook 見到此行即沿用、不另外 snapshot）；同一回合並行派出多張工單時，全部工單用檔名時間最早的那份 manifest（`rules/委派門檻與路由.md` Rule 6 的「baseline 在全部發派前拍一次」）。
3. DELEGATE 依路由以 Agent tool 發派工單，要求 executor 修改前先跑標為「修改前要跑」的驗收、修改後跑全部驗收，每次執行都寫進工單的證據檔目錄，並依該 executor agent 定義檔的回報格式回報；發派後不呼叫任何工具，直接結束回合，等完成通知喚醒再續行。
4. THINK 只有 executor 失敗、逾時、退回或回報缺件時才讀取 `rules/失敗分類與partial交接.md`，分類後改派、回 Phase 2 改寫工單，或還原後回步驟 2 重發。

## Phase 4 -- 驗收

1. DELEGATE 執行 `uv run "${CLAUDE_SKILL_DIR}/scripts/baseline.py" compare --baseline <manifest> --allow <允許檔或 generated artifact> --allow … [--allow-new <允許新增檔> …]`；出現 `out_of_scope`、`new_staged`、`unauthorized_untracked` 或非 in-scope 的 `baseline_dirty_changed` 即退回重發，in-scope 的 `baseline_dirty_changed` 只需對照 manifest 同名 `.patch`，其每個 hunk 仍存在於現況即為未覆蓋使用者原有修改。
2. DELEGATE 只有本工單是所屬交付範圍最後一張一般工單時，先執行 `uv run "${CLAUDE_PLUGIN_ROOT}/skills/risk-grade/scripts/risk_signals.py" --repo <專案目錄> --git`：`verdict` 為 `high` 或 `low` 時不載入 `/orchestrate-kit:risk-grade`，直接執行 `uv run "${CLAUDE_PLUGIN_ROOT}/skills/risk-grade/scripts/risk_ledger.py" record --repo <專案目錄> --grade <high|low> --layer <gate|safe> [--gates <名稱>...] --reason <命中的 gate 或「全部 safe-change」> --source orchestrate-v2 --files-count <檔案數>` 取得 ledger id，以一行回報等級與分批建議（`over_attention_limit` 為真時依 ≤20 檔一批分批）後進步驟 3；只有 `verdict` 為 `judgement` 時才呼叫 `/orchestrate-kit:risk-grade`，以 working tree 實際變更為範圍，附各工單目標、任務形狀、交付範圍內的 executor 失敗／逾時紀錄與來源 `orchestrate-v2`，取得等級、ledger id 與分批建議後回到本步驟 3 續行；修正工單改執行 `uv run "${CLAUDE_PLUGIN_ROOT}/skills/risk-grade/scripts/risk_signals.py" --repo <專案目錄> --files <修正動到的檔>...` 取 `gate_hits` 後進步驟 3；交付範圍內其他工單不分級，直接進步驟 4。
3. DELEGATE 只有步驟 2 判為中高、或本工單是修正工單時，才讀取 `rules/review發派與仲裁.md`：中高的交付範圍在同一回合一併讀取 `templates/review-focus.md` 與 `templates/review-focus.example.md`，依骨架組 focus 文字並依分批建議對整個交付範圍發派 `opus-reviewer`（已依 README 選配 `codex-reviewer` 時改派它）；修正工單依該規則判定不做 review、只對修正 diff 做一次針對性 review（要發派時才讀兩份樣板），或因涉及底線停下：涉及底線時不再執行本工單的後續驗收，直接進 Phase 7 依步驟 2 回報後停下；發派後不結束回合，直接進步驟 4；驗收含會改動 tracked 檔的步驟（突變驗證、還原備份檔、產出進版控的 build）時，改在步驟 5 驗收判定通過後才發派；等級為低、交付範圍內其他工單不讀上述檔案。
4. READ 讀取 `rules/驗收與仲裁憑據.md`，依已載入的 `rules/委派門檻與路由.md` 決定每條驗收採用 executor 證據檔、自己重跑或派 `opus-lite-verifier`；只有派 verifier 時才在同一回合一次讀取 `templates/verification-checklist.md` 與 `templates/verification-checklist.example.md`，依骨架寫好驗收清單後發派，自己執行驗收時不讀這兩份樣板；派出 verifier 後同 Phase 3 步驟 3 結束回合等通知。
5. READ 讀證據檔前先執行 `uv run "${CLAUDE_SKILL_DIR}/scripts/check_evidence.py" --dir <證據檔目錄> --repo <專案目錄> --allow <允許檔>... --expect <本工單驗收編號，逗號分隔>`，依其輸出判定；帶旗標的檔、或預期結果無法由 exit code 與末段原文判定的條目，才讀整檔；依憑據標準讀每條驗收的證據檔或實際輸出並判定，派 verifier 時於它的完成通知之後讀驗收清單列出的產物檔；修正工單另確認原 finding 已修好；驗收失敗時讀取 `rules/失敗分類與partial交接.md` 分類後改派或回 Phase 2 重切；reviewer 仍在執行時不發派任何寫入工單（它讀的是 working tree），等它的通知後與 findings 一併處理；步驟 3 延後發派的 reviewer 在驗收判定通過後發派；交付範圍內還有未發派的工單時回 Phase 3 發派下一張，全部驗收判定完成才進 Phase 5。

## Phase 5 -- Review

1. READ 等級為低時由 orchestrator 自驗；只有交付範圍判為中高、或修正工單發派了針對性 review 時才讀 reviewer 這次回傳的 findings（發派已在 Phase 4 完成），還沒回報就同 Phase 3 步驟 3 結束回合等通知；修正工單沒有發派針對性 review 時，Phase 4 確認原 finding 已修好即直接進 Phase 7；Phase 4 的驗收判定完成、review 結果也到齊，才進 Phase 6。

## Phase 6 -- 仲裁

1. READ 有本輪新回報的 findings 時依已載入憑據規則的仲裁分類，先看每條的觸發分類決定是否親自讀 code 查證，再歸類；修正工單已確認修好的原 finding 不再仲裁；低風險自驗無 findings 時直接進 Phase 7。
2. WRITE 經使用情境判斷要修的真問題開新窄修正工單回到 Phase 3；不修的真問題與未查證的 findings 列為已知限制候選；假陽性記錄否決理由；PLAUSIBLE 與標「不確定」的交使用者裁決；仲裁完畢進 Phase 7。

## Phase 7 -- Close

1. THINK 確認全部必要驗收通過、無未仲裁 finding、無未決產品決策，且涉及底線的 PLAUSIBLE、已知限制候選與修正都已由使用者裁定，才判定 close；不涉及底線的已知限制候選與 PLAUSIBLE 列在報告待裁、不擋 close，必要驗收未通過的項目不得列為已知限制；只差使用者裁定底線項目時依步驟 2 回報後停下；其餘不能 close 且本輪沒有開出新工單時，視為流程失敗，回到 Phase 1 重新診斷；連續兩輪沒有進展時讀取 `rules/失敗分類與partial交接.md`，依其停損規則向使用者報告。
2. WRITE 在同一回合一次讀取 `templates/close-report.md` 與 `templates/close-report.example.md`（同一 session 已讀過就不重讀），依骨架填寫向使用者回報，並對本任務每一個 ledger id 執行 `uv run "${CLAUDE_PLUGIN_ROOT}/skills/risk-grade/scripts/risk_ledger.py" outcome --id <ledger id> --findings <實質 findings 數> --result <處置>` 回填分級結果。
