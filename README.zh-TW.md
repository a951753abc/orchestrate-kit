# orchestrate-kit

[English](README.md) | 正體中文

讓 Claude 以 tech lead 的方式做事的 Claude Code plugin：診斷任務、切窄工單、發派 Opus executor subagent、親自驗收、對變更做風險分級、中高風險交對抗式 reviewer、仲裁 findings、最後出 close 報告。

## 內容

| 元件 | 類型 | 角色 |
| --- | --- | --- |
| `orchestrate-v2` | skill（手動呼叫） | 七個 Phase：診斷 → 切工單 → 發派 → 驗收 → 分級 review → 仲裁 → close。判準、樣板與腳本只在對應步驟按需載入。 |
| `risk-grade` | skill | 對一組程式碼變更做三層漏斗分級：硬性 gate → safe-change 白名單 → 裁量。每次分級記入 ledger。 |
| `risk-calibrate` | skill | 以 ledger 的分級與實際結果對照做校準，產出 risk-policy 措辭修改提案；不直接改 policy。 |
| `debug-by-evidence` | skill | 證據先於修法。Phase 1 遇到 bug／測試失敗／flaky／效能退化時使用。 |
| `executable-spec` | skill | 三層可執行規格。任務需要 SPEC 而尚無時，流程會停下來要求先產出。 |
| `opus-lite-executor`、`opus-executor` | agents | 工單執行者，依難度與風險訊號路由（opus-lite 為 effort low，opus 為 effort high）。只做工單上寫的事，不碰 git。 |
| `opus-lite-explorer` | agent | 唯讀搜尋與精讀，取代內建 Explore／general-purpose（內建 agent 無法指定 effort）。 |
| `opus-reviewer` | agent | 中高風險變更的對抗式 reviewer。只回傳原始 findings，仲裁由 orchestrator 做。 |
| `opus-lite-verifier` | agent | 瀏覽器驗收：執行工單的瀏覽器檢查，回傳截圖與量測結果作為證據。 |
| `check_evidence.py` | script（在 `orchestrate-v2` 內） | 一次讀完 executor 的證據檔目錄，逐檔列出指令原文、最後的 exit code 與輸出末段，並標出缺 exit code、最後 exit 非 0、驗收項目缺 after 檔。 |
| baseline hook | 內附 `PreToolUse` hook | 每次發派 executor（`Agent`／`Task` tool）前把 working tree 拍成 baseline；非 executor 的 agent 立即結束。 |

## 需求

- 支援 plugin 的 Claude Code，方案要能跑 Opus（agent 定義檔釘了 model 與 effort）。
- [`uv`](https://docs.astral.sh/uv/)：腳本都是 PEP 723 單檔腳本，以 `uv run` 執行。
- Python 3.10 以上、`git` 在 PATH 上。
- 選配：Playwright MCP，只有瀏覽器驗收（`opus-lite-verifier`）需要。
- Windows：設一次 `PYTHONUTF8=1`（`setx PYTHONUTF8 1`），避免腳本輸出的中文被 CP950 主控台咬壞。

## 安裝

```
/plugin marketplace add a951753abc/orchestrate-kit
/plugin install orchestrate-kit@orchestrate-kit
```

安裝後開新的 Claude Code session。

## 何時用、何時不用

任務是可以寫成工單、有驗收指令的修改時才呼叫：跨多檔的功能或修正、從症狀修到驗證通過的 bug、批次編輯、任何結果要靠執行某個指令來確認的事。流程的價值在 executor 周圍的機械驗證：baseline snapshot 與 compare、orchestrator 親自跑驗收指令、依風險分級的 review、附證據的 close 報告。

寫工單比改動本身還貴、改完也沒有東西可跑的修改，直接自己改，不走流程：typo、文件裡的一句話、一個常數、小幅 CSS 調整。每跑一輪的固定成本是幾支 script（baseline、風險訊號、risk-grade、ledger）加上 orchestrator 要讀的樣板；條件式步驟（失敗處理、外部 review、仲裁）沒觸發就不會執行。

複雜度與風險由流程的不同部分處理，所以改動小不代表流程輕：

| 複雜度 | 風險 | 流程怎麼走 |
| --- | --- | --- |
| 低 | 低 | 一張工單，`opus-lite-executor`，orchestrator 自驗 |
| 低 | 高 | 一張工單，`opus-executor`（命中 gate），對抗式 review，仲裁 |
| 高 | 低 | 多張工單序列或並行，orchestrator 自驗 |
| 高 | 高 | 多張工單，`opus-executor`，逐批對抗式 review |

複雜度決定切幾張工單、派哪個 executor。風險由 `risk-grade` 依 gate 判定（auth、secrets、金流、migration、infra／CI、公開介面、核心商業規則、concurrency、資料安全），從不看 diff 大小：改 authorization 檢查一行會被 review，唯讀 UI 改三百行不會。任務起初很小、途中變大（動到第二個 subsystem、出現未決的產品決策、驗收無法寫成可執行指令）時，流程回到診斷重切工單，不在原工單上繼續。

## 使用

```
/orchestrate-kit:orchestrate-v2 <任務描述>
```

流程：

1. **診斷**：讀任務與 code，把假設分類；需要你裁決的產品決策會在切工單前先問。
2. **切工單**：每張工單有目標、允許修改的檔案清單、可執行的驗收指令與禁止事項；每張工單先跑一次風險訊號估算，決定派哪個 executor。
3. **發派**：驗收指令先在現況跑一次，確認修正前會失敗；每次發派前拍 baseline snapshot。
4. **驗收**：baseline compare（越界檔即退回）加上 orchestrator 親自重跑每條驗收指令。executor 的回報不算證據。
5. **Review**：由 `risk-grade` 決定；中高風險帶四面向 focus 派 `opus-reviewer`，低風險自驗。
6. **仲裁**：每條 finding 對照 code 查證：真問題開新窄工單、假陽性記錄否決理由、PLAUSIBLE 交給你裁決。
7. **Close**：出報告並回填 ledger outcome。沒有你的指示不會 commit。

單獨使用：

- `/orchestrate-kit:risk-grade <變更範圍與脈絡>`：不走完整流程，只做分級。
- `/orchestrate-kit:risk-calibrate [專案目錄]`：某專案 ledger 累積約十筆已回填結果後使用。
- `debug-by-evidence` 與 `executable-spec` 會依 description 自動觸發，也可直接以名稱呼叫。

狀態放哪裡：

- 專案的風險 policy：`.claude/risk-policy.yaml`（要求時依內附樣板建立；宣告敏感路徑與 safe-change 範圍）。
- 全域 ledger：`~/.claude/risk-grade/ledger.jsonl`。
- baseline manifest：`<系統 temp>/claude-orchestrate/<repo hash>/`。

## 0.3.0 新增內容

1. **自動 baseline**：plugin 的 `PreToolUse` hook 在每次發派 executor 前拍 working tree snapshot；snapshot 失敗時擋下該次派工，不影響其他工具。
2. **證據檔一次判讀**：orchestrator 以 `check_evidence.py` 讀 executor 的證據檔，不逐檔打開（`--dir` 證據檔目錄、`--expect` 驗收編號、`--allow` 允許檔）。
3. **小工單直接做**：單一模組、未命中 risk gate、預估 15 個工具呼叫內、不並行、無瀏覽器驗收的工單，由 orchestrator 自己做，不派 executor。在作者的歷史工單重播中，小工單直接做約省一半時間與 token。
4. **分級更輕**：機械風險訊號已能定案分級時，不載入 `risk-grade` skill。
5. **瀏覽器驗收**：交給 `opus-lite-verifier`。

## 選配：用 Codex 做 reviewer 或 rescue

未內附。預設 review 派 `opus-reviewer`；同一張工單 executor 失敗兩次後停下回報，不再改派其他 executor。有 OpenAI Codex CLI 且想引進異質模型的話：

1. 安裝 [ai-orchestra](https://github.com/jason201385-commits/ai-orchestra)。其 `dispatch.py` 提供唯讀的 `codex-review` provider 與完整權限的 `codex-full` provider。
2. 新增 `~/.claude/agents/codex-reviewer.md`（tools：`Bash`）。契約：把 focus 文字寫進暫存檔，背景執行 `cd <repo> && cat <檔> | PYTHONUTF8=1 python <ai-orchestra>/scripts/dispatch.py codex-review --label <名稱> --timeout <秒>`，等完成通知後把 Codex 的最終訊息原樣當 findings 回傳，不修復、不過濾。review sandbox 是唯讀的，prompt 要叫 Codex 自己跑 `git diff`。
3. 不用再設定別的：review 規則在 `codex-reviewer` 存在時優先派它，失敗一次即 fallback 到 `opus-reviewer`，不重試。rescue 也可同樣接到 `codex-full`。

## 語言

skill 本文、rules 與 templates 以正體中文撰寫。任何 session 語言下 Claude 都照著做；想要英文報告就在 `CLAUDE.md` 寫明。

## 更新

```
/plugin update orchestrate-kit@orchestrate-kit
```

之後開新 session。

## 授權

MIT
