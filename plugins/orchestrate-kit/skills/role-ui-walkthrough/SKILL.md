---
name: role-ui-walkthrough
description: 派角色 agent 只看畫面操作系統的操作測試：每個角色的 agent 只靠截圖與座標點擊操作本機網站、不讀程式碼，記錄每一步的預期與實際，找出畫面上做不下去或看不懂的地方；主控開截圖、對照程式與既有裁定查證後，產出現況表、圖文操作手冊與裁決報告。適用於「派 agent 扮演使用者操作系統」「只透過畫面測一趟」「做圖文操作手冊」「快速看專案現況」。
argument-hint: <角色、要走的旅程、要的產出>
---

# 角色 agent 只看畫面的操作測試

用沒讀過程式碼的 agent 代替沒看過畫面的人：它在哪裡找不到入口、看不懂狀態、等不到回饋，就是畫面要檢查的地方。操作留下的截圖同時是圖文手冊的素材。網址、帳號、要攔截的 endpoint、UX 判準與既有裁定，一律以各專案的規則檔與專案記憶為準，本 skill 不記單一專案的資料。

# SOP

## Phase 1 -- 定出範圍與分段

1. READ 讀取使用者指定的角色、旅程與產出，以及專案規則裡的環境檢查、測試帳號的命名與清除方式、付費的外部呼叫、UX 判準與既有裁定。
2. THINK 讀取 `rules/分段與角色任務說明判準.md`，把旅程排成有先後依賴的段落，決定每段由哪個角色 agent 操作、哪些交接由主控代做；專案第一次執行時選一段當試跑。專案規則沒有寫明的付費呼叫處理、產出位置與讀者，列選項問使用者，答覆前不派 agent。

## Phase 2 -- 備妥瀏覽器與任務說明

1. WRITE 讀取 `rules/瀏覽器準備與交接.md`，執行專案的環境檢查，建立 run 目錄與測試素材，為本段每個角色開隔離的 context 並完成攔截與登入狀態，再以一次座標點擊加截圖確認可以只靠截圖操作。
2. WRITE 讀取 `templates/role-brief.md` 與 `templates/role-brief.example.md`，依骨架複製結構、參考範例改寫填位符號，為本段每個角色 agent 寫出可直接發派的任務說明。

## Phase 3 -- 角色 agent 完成操作

1. DELEGATE 以 Agent tool（`general-purpose`，prompt 即任務說明全文）派出角色 agent，同一時間只有一個 agent 操作瀏覽器；agent 停下等待或回報卡住時，依本次適用規則完成交接或決定是否給提示，再以 SendMessage 通知它繼續。
2. DELEGATE 每個角色 agent 結束後，執行 `uv run "${CLAUDE_SKILL_DIR}/scripts/audit_agent_tools.py" --transcript <該 agent 的 transcript> --run-dir <run 目錄> [--allow-goto <允許的網址> ...]` 稽核它的工具呼叫，依輸出把違反工具限制的步驟從素材排除；輸出列出剪貼簿按鍵或其他可能截到與測試無關內容的步驟時，不開啟那些截圖並告知使用者。
3. WRITE 試跑段結束時向使用者回報步數、token 用量與暴露的限制，取得是否擴大的裁定；還有未操作的段落時回到 Phase 2。

## Phase 4 -- 查證後的主控筆記

1. DELEGATE 派唯讀的 `opus-lite-explorer` 做兩類查證：把每項不順對照專案的既有裁定、規格與已知限制；為觀察到的行為找出程式依據。這一步不用瀏覽器，可與 Phase 3 並行。
2. THINK 讀取 `rules/發現查證與分類.md`，逐項開截圖確認、排除誤報，判定每段的狀態與每項的收尾關係、修改類別。
3. WRITE 讀取 `templates/walkthrough-notes.md` 與 `templates/walkthrough-notes.example.md`，依骨架複製結構、參考範例改寫填位符號，把查證結果寫成主控筆記，作為各份產出的唯一來源。

## Phase 5 -- 交付產出

1. DELEGATE 讀取 `rules/產出內容與交付檢查.md`，呼叫 `/orchestrate-kit:orchestrate-v2` 以主控筆記產出使用者要的文件：裁決報告依 `orchestrate-kit:gap-adjudication-report`，旅程圖在有安裝 `diagram-design` plugin 時依它、沒有時直接畫 inline SVG；每份 HTML 的驗收含 `uv run "${CLAUDE_SKILL_DIR}/scripts/check_report_html.py" <html 檔> [--ids <id,...>] [--require-hrefs <href,...>] [--forbid <片段> ...]` 與瀏覽器實際渲染。
2. WRITE 在 `/orchestrate-kit:orchestrate-v2` 的 close 回報補上裁決項目與建議順序、判讀限制、沒有操作的範圍、留在資料庫的測試資料；把本專案下次還用得到的準備事實更新到專案記憶。
