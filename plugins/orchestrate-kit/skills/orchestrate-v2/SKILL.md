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

1. THINK 在同一回合一次讀取 `rules/工單判準與形狀補充.md`、`templates/work-order.md` 與 `templates/work-order.example.md`，判定任務形狀並收斂每張工單的邊界、允許檔清單與驗收加項。
2. DELEGATE 對每張工單執行 `uv run "${CLAUDE_PLUGIN_ROOT}/skills/risk-grade/scripts/risk_signals.py" --repo <專案目錄> --files <允許檔>...`，取輸出的 `gate_hits` 附記於該工單供 Phase 3 路由使用；此估算不記 ledger、不產分級報告。
3. WRITE 依已讀骨架複製結構、參考範例填入每張工單；必填段缺一不發派。

## Phase 3 -- 發派

1. THINK 判斷是否委派、派給哪個 executor、可否平行時，讀取 `rules/委派門檻與路由.md` 決定路由。
2. READ 於現況親自執行工單每條驗收指令並讀實際輸出，確認修正前失敗、或給出可對照的基準值；跑不出可判定結果的指令回 Phase 2 改寫該工單。
3. DELEGATE 每次發派前執行 `uv run "${CLAUDE_SKILL_DIR}/scripts/baseline.py" snapshot` 記錄 working tree 狀態，保留輸出的 manifest 路徑供驗收比對。
4. DELEGATE 依路由以 Agent tool 發派工單，要求依該 executor agent 定義檔的回報格式回報；發派後不呼叫任何工具，直接結束回合，等完成通知喚醒再續行。
5. THINK 只有 executor 失敗、逾時或回報缺件時才讀取 `rules/失敗分類與partial交接.md`，分類後改派、或還原後回步驟 3 重發。

## Phase 4 -- 驗收

1. DELEGATE 執行 `uv run "${CLAUDE_SKILL_DIR}/scripts/baseline.py" compare --baseline <manifest> --allow <允許檔或 generated artifact> --allow … [--allow-new <允許新增檔> …]`；出現 `out_of_scope`、`new_staged`、`unauthorized_untracked` 或非 in-scope 的 `baseline_dirty_changed` 即退回重發，in-scope 的 `baseline_dirty_changed` 只需對照 manifest 同名 `.patch`，其每個 hunk 仍存在於現況即為未覆蓋使用者原有修改。
2. READ 讀取 `rules/驗收與仲裁憑據.md`，依其憑據標準親自執行每條驗收指令並讀實際輸出；驗收失敗時讀取 `rules/失敗分類與partial交接.md` 分類後改派或回 Phase 2 重切。

## Phase 5 -- Review

1. DELEGATE 呼叫 `/orchestrate-kit:risk-grade`，以 working tree 實際變更為範圍，附工單目標、任務形狀、executor 失敗／逾時紀錄與來源 `orchestrate-v2`，取得等級、ledger id 與分批建議後回到本步驟 2 續行。
2. DELEGATE 只有等級為中高時才在同一回合一次讀取 `rules/review發派與仲裁.md`、`templates/review-focus.md` 與 `templates/review-focus.example.md`，依骨架組 focus 文字並依分批建議發派 `opus-reviewer`（已依 README 選配 `codex-reviewer` 時改派它），發派後同 Phase 3 步驟 4 結束回合等通知；等級為低時由 orchestrator 自驗，不讀上述檔案。

## Phase 6 -- 仲裁

1. READ 有 findings 時逐條親自讀 code 查證，依已載入憑據規則的仲裁分類歸類；低風險自驗無 findings 時直接進 Phase 7。
2. WRITE 真問題開新窄工單回到 Phase 3；假陽性記錄否決理由；PLAUSIBLE 交使用者裁決；仲裁完畢進 Phase 7。

## Phase 7 -- Close

1. THINK 確認全部驗收條件通過、無未仲裁 finding、無未決產品決策，才判定 close；不能 close 且本輪沒有開出新工單時，視為流程失敗，回到 Phase 1 重新診斷；連續兩輪沒有進展時讀取 `rules/失敗分類與partial交接.md`，依其停損規則向使用者報告。
2. WRITE 在同一回合一次讀取 `templates/close-report.md` 與 `templates/close-report.example.md`，依骨架填寫向使用者回報，並對本任務每一個 ledger id 執行 `uv run "${CLAUDE_PLUGIN_ROOT}/skills/risk-grade/scripts/risk_ledger.py" outcome --id <ledger id> --findings <實質 findings 數> --result <處置>` 回填分級結果。
