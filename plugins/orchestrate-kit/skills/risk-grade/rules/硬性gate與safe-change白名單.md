# Rule 1 - 命中任一硬性 gate 即中高風險，變更性質不得降級

- Level: `MUST`
- 等級只有中高／低兩級：中高＝呼叫方派外部 review，低＝呼叫方自驗。
- gate 是下限：多個訊號同時命中時取最高；safe-change 分類、diff 小、凍結測試已覆蓋、executor 一次通過，都不能把命中 gate 的等級拉低。
- 路徑類 gate 由 `scripts/risk_signals.py` 依 policy 的 `gates[].paths` 比對，預設類別：
  - `auth`：登入、session、token、權限檢查、授權 middleware
  - `secrets`：憑證、金鑰、加解密、`.env`
  - `payment`：改變金額計算、扣款、退款或對帳路徑的邏輯；金流目錄內的 log、註解、文件、格式由 policy `exclude` 排除
  - `migration`：schema migration、資料搬移腳本、`.sql`
  - `infra_ci`：部署設定、CI workflow、IaC、Dockerfile
  - `audit_logging`：稽核紀錄、監控、告警
  - `public_contract`：protobuf、OpenAPI、公開 SDK 型別、跨模組介面定義
  - `approval_governance`：改變誰能核准未來變更的設定（CODEOWNERS、branch protection、本 policy 檔）
- 語意類 gate 無法用路徑比對，機械層落在 judgement 時由 Phase 2 依工單目標、任務形狀與 diff 內容判定（機械層已判 safe 的檔案是文件、測試、格式與資產，不再檢查語意類 gate）：
  - `core_business_rule` 核心商業規則：改變定價、折扣、額度、結算、狀態轉移條件等業務結果的邏輯
  - `concurrency` concurrency／狀態機：lock、queue、transaction 邊界、狀態轉移表、重試與冪等處理
  - `data_safety` 資料安全：批次刪除、批次更新、個資匯出、跨租戶存取
  - `cross_module_contract` 跨模組介面：改變被多個模組呼叫的共用函式簽章、事件格式、公開型別或回傳契約（路徑類 `public_contract` 只接得到 proto／OpenAPI／型別宣告檔，其餘靠此項）
- 執行歷史 gate `executor_history`：executor 同一工單曾失敗或逾時；呼叫方以 `--executor-failed` 傳給 script，script 直接判 gate 層（優先於 safe）。
- 語意類 gate 在 judgement 層命中時，ledger `--layer` 記 `gate`。
- 「大 diff」不是 gate。變更行數超過 policy `attention_limit_lines` 只產生分批建議，不改變等級。

## Good Example

- 這個例子是好的，因為單函式捨入修正雖然 diff 只有 3 行且凍結測試已覆蓋，仍因命中 payment 路徑 gate 判中高，理由寫明命中依據與不降級的原因。

````md
變更：pricing.py 的 apply_discount() 由截斷改為 Decimal half-up 捨入（+4／-1 行）
機械訊號：payment 路徑 gate 命中（`**/*pricing*`）；safe-change 無
判定：中高（gate 層，不讀 rule）。凍結測試已覆蓋是裁量層的降級理由，gate 命中時不適用。
````

## Bad Example

- 這個例子是壞的，因為它是 2026-09-03 orchestrate-v2 eval 的實際分歧：同一個捨入修正，讀 v1 流程檔的 subagent 以「單檔小 diff、既有測試完整涵蓋的機械修改」判低，讀 v2 流程檔的 subagent 以「金額計算屬核心商業規則」判中高；兩邊在 v1 清單裡都找得到依據，因為清單沒有規定領域與性質同時命中時誰優先。

````md
v1 側（executor 用 int(x+0.5)，diff 1 行）：單一函式、既有測試完整涵蓋 → 低風險自驗
v2 側（executor 用 Decimal，diff +4／-1）：折扣金額計算屬核心商業規則 → 中高風險派 reviewer
````

# Rule 2 - safe-change 白名單只在未命中 gate 時生效，且須全部變更落在白名單內

- Level: `SHOULD`
- 白名單類別（policy `safe_changes` 的路徑類由 script 分類，形狀類由呼叫方標注）：
  - `docs`：Markdown、文件目錄、LICENSE、CHANGELOG
  - `tests`：只動測試檔與 fixture，未動被測程式
  - `formatting`：`git diff -w` 無差異的純格式變更；由 script `--git` 模式的 `formatting_only` 判定，為 changeset 級（整批變更皆為格式才成立）
  - `assets`：圖片與靜態資產
  - `config_minor`：editor、lint、格式化工具設定（不含 infra／CI）
  - 純註解變更（形狀類，呼叫方確認 diff 只動註解與 docstring）
  - 唯讀 UI 形狀：工單標注「唯讀 UI」——無寫入 command、無授權變更、無演算法或 SQL 語意變更的列表／表單版面與前端接線；不看 diff 大小
  - deterministic 腳本批次替換：orchestrator 產替換表、腳本帶 `count==1` 斷言一次跑完的產出
  - typecheck／tests 完整涵蓋的機械修改：rename、純版本升級、行為不變的搬移
  - 純加法小工單（凍結測試已覆蓋、diff 小、無授權／資料／concurrency 面）：視為本白名單的一類，同樣只在未命中 gate 時生效
- 路徑類由 script 分類，落在形狀類的檔案（腳本產物、純註解、唯讀 UI）由呼叫方在 judgement 層依脈絡歸類；任一檔案在路徑類與形狀類都不涵蓋 → 不算 safe，進裁量；不得憑「大部分是文件」判低。
- 形狀類歸 safe 時，ledger `--layer` 記 `safe`。
- 白名單檔案若同時命中 gate（例如 auth 目錄下的測試），gate 優先；專案可在 policy 該 gate 的 `exclude` 排除測試目錄。

## Good Example

- 這個例子是好的，因為 16 處替換由帶 `count==1` 斷言的腳本一次產出，全部檔案落在白名單且無 gate 命中，判低。

````md
變更：docs/ch1〜ch6.md 各 1 行（腳本 scripts/replace_terms.py 產出，count==1 斷言全過）
機械訊號：judgement——safe-change docs ×6，scripts/replace_terms.py 未分類 → 讀 rule
形狀類白名單：deterministic 腳本批次替換（工單標注，腳本本身即產物）→ 全部檔案落在白名單
判定：低（safe 層）。無 gate 命中。
````

## Bad Example

- 這個例子是壞的，因為它是 2026-09-02 一次覆盤的實際事故：ledger 實測 codex review 每場 10〜28 分鐘，9 場中 4 場對象是唯讀 UI 工單，其 findings 多屬瀏覽器驗收就能更早抓到的型態；工單只因 diff 大就被判進中高風險。

````md
工單 #4：訂單列表頁加欄位與排序，diff 320 行，全在 components/OrderTable.tsx 與 CSS
判定：diff 320 行算大 → 中高風險，派 reviewer
````

# Rule 3 - 每次分級必記 ledger

- Level: `MUST`
- 每次分級完成後執行 `scripts/risk_ledger.py record`，記錄 repo、檔案數、等級、判定層、命中 gate、理由、呼叫來源；回傳的 id 寫進分級報告。
- 呼叫方拿到 review 結果、事故或 close 後，以 `outcome` 回填 findings 數與處置。
- 沒記帳的分級無法進入校準，視為分級未完成。
- 沒有 working tree 變更、只以允許檔清單做的估算不是分級，不記 ledger；只有以實際變更做的判定才記。

## Good Example

- 這個例子是好的，因為分級與後續結果都進了 ledger，校準時能對照。

````md
record：rg-20260903T031500Z-a1b2 high layer=gate gates=core_business_rule source=orchestrate-v2
outcome：rg-20260903T031500Z-a1b2 findings=1 result="F1 PLAUSIBLE 交使用者；無實害"
````

## Bad Example

- 這個例子是壞的，因為分級只留在對話輸出，兩週後校準時找不到任何可對照的紀錄。

````md
「這張工單我判中高，派 reviewer。」（未執行 record）
````
