# 驗收清單：工單 {{WORK_ORDER_ID}}（{{WORK_ORDER_TITLE}}）

<!-- 產物目錄、環境準備、驗收步驟、還原步驟、禁止事項五段必填，缺一不發派 -->
<!-- 清單只寫操作與產物檔，不寫預期結果；預期結果留在工單，verifier 不判定 -->
<!-- 只有指令的驗收由 executor 照工單執行並寫證據檔，不寫進清單；清單只放瀏覽器步驟、依賴瀏覽器操作結果的指令（例：操作後的資料庫對帳），以及涉及底線或證據檔不符憑據規則、需要重跑的指令 -->
<!-- 突變驗證（改壞程式碼、確認測試變紅、還原）不寫進清單：由 executor 在工單內執行並寫證據檔，verifier 不修改程式碼 -->

## 產物目錄

{{ARTIFACT_DIR_ABSOLUTE_PATH}} <!-- 絕對路徑，放在 Playwright 輸出目錄下的工單子目錄：預設是 `<session 工作目錄>/.playwright-mcp/`，MCP 設定帶 `--output-dir` 時是該目錄；Playwright 拒絕把檔案寫到 session 工作目錄與輸出目錄以外 -->

## 環境準備

<!-- 含證明跑的是新版程式的步驟（重建、清快取、cache-busting）；寫法同驗收步驟 -->
<!-- 先列本次驗收依賴的前提，每條寫成一個唯讀檢查指令＋機械停止條件（rc 不為 0、回應碼不是 200、查無資料列即停）：服務有回應、跑的是新版（直接重跑 build，或比對 build 時寫入的原始碼雜湊，不比較檔案修改時間）、測試帳號存在、外部服務 mock 開著、清單要用的每個工具先呼叫一次；某一步出現預期外結果時，重跑本段再繼續 -->
{{SETUP_STEPS}}

## 驗收步驟

<!-- 指令步驟：寫成可直接執行的完整指令，指令原文、完整輸出與 `rc=<exit code>` 一起重導向寫進產物檔 -->
<!-- 瀏覽器步驟：寫工具名與參數；截圖、頁面快照、console、network、evaluate 的結果一律用 Playwright 工具的 `filename` 參數存檔；`opus-lite-verifier` 的 agent 定義以 `disallowedTools` 排除 `browser_run_code_unsafe`，要用腳本檔（`page.route`、`waitForResponse` 這類扣住或等待回應的寫法）的瀏覽器步驟由 orchestrator 自己執行、不寫進清單，清單只用 `browser_navigate`、`browser_click`、`browser_evaluate` 這類 verifier 拿得到的工具（2026-10-08 實測 verifier 一步都跑不了） -->
<!-- 參數依 ToolSearch 取得的 schema 寫齊必填欄（click／type 的 `target`、截圖的 `scale`、console 的 `level`、network 的 `static`）；`target` 寫唯一的 CSS selector，寫清單時還沒有 snapshot 可取 ref -->
<!-- 點擊、輸入、導頁沒有 `filename` 參數，之後接一個帶 `filename` 的 `browser_snapshot` 存下操作結果 -->
<!-- 「失敗即停」只標在後續步驟依賴本步成功的步驟上，停止條件要能機械判定（例：rc 不為 0、頁面打不開） -->
1. {{STEP_COMMAND_OR_TOOL_WITH_PARAMS}} → `{{ARTIFACT_FILE}}` {{STOP_ON_FAILURE_CONDITION}}

## 還原步驟

<!-- 不論做完或中途停止都要執行；寫法同驗收步驟；最後一步固定把 `git status --short` 存檔，供 orchestrator 確認驗收沒有留下檔案變更 -->
{{RESTORE_STEPS}}

## 禁止事項

<!-- 只寫本次特有的項目；固定紀律在 agent 定義檔，不重抄 -->
{{EXTRA_PROHIBITIONS}}
