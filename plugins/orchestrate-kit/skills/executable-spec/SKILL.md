---
name: executable-spec
description: Write feature SPECs and requirement documents as three-layer executable specifications (prose intent, SBE scenario tables, invariant contracts) and derive their executable artifacts (frozen acceptance tests, runtime assertions, property tests). Use when writing or reviewing a SPEC, requirements document, or acceptance criteria for a feature that AI will implement, or when defining verification gates for AI-generated code. Do not use for pure architecture plans, migration runbooks, or documentation-only tasks.
---

# Executable Spec（可執行規格）

核心原則：**散文只留意圖，行為與規則一律下沉為可執行形式**。散文規格會與程式碼漂移；可執行規格不一致時會當場失敗。AI 實作的兩大風險——默默假設、迎合測試——分別由不變量層與凍結／property 機制對付。

## 適用範圍

- 用於：撰寫或更新功能 SPEC、需求文件、驗收條件；為 AI 實作任務定義驗證關卡；review 既有 SPEC 的可執行性。
- 不用於：純架構計畫（PLAN 本來就是散文）、遷移 runbook、純文件任務。
- 與 `/orchestrate-kit:orchestrate-v2` 分工：本 skill 管規格產物的形狀與衍生工件；工單切分、發派、驗收流程歸 `/orchestrate-kit:orchestrate-v2`。

## SPEC 三層結構

每份 SPEC 依序包含三層。行為與規則出現在意圖層散文中時，必須同時存在於第 2 或第 3 層——散文不得是任何行為的唯一載體。

### 第 1 層：意圖層（散文）

只寫可執行形式裝不下的東西：為什麼做、取捨理由、約束、不做什麼（non-goals）。禁止在此層用散文描述具體行為規則（「系統應支援折扣」這類句子不得單獨存在）。

### 第 2 層：行為層（SBE 情境表格）

每條功能需求以具體情境列舉，一張表格一個情境，包含三要素：具體資料、明確前提、預期結果。

```markdown
#### 情境 B-3：提款金額等於餘額
| 欄位 | 值 |
|---|---|
| 前提 | 帳戶餘額 900 元，狀態正常 |
| 操作 | 提款 900 元 |
| 預期 | 成功；餘額變為 0；產生一筆提款紀錄 |
```

- 預期結果由規格作者給定（獨立來源），不得留待實作後回填。
- **業務邊界必列**：等於門檻、零、空集合、上限、互斥規則的交界。寫不出預期結果的情境就是尚未決策的需求——標記為待裁決，不得含糊帶過。
- 情境編號（B-1、B-2…）供驗收測試與工單引用。

### 第 3 層：不變量層（合約條款）

列出「任何時刻、任何呼叫都必須成立」的規則，逐條編號：

```markdown
#### 不變量
- I-1（precondition）：提款金額必須 > 0
- I-2（precondition）：提款金額不得超過可用餘額
- I-3（postcondition）：提款後餘額 = 原餘額 − 金額
- I-4（invariant）：餘額任何時刻 ≥ 0
- I-5（failure atomicity）：任何被拒絕的操作不得改變帳戶狀態
```

precondition 的作用是把隱含假設攤開：AI 寫下「輸入不會是空的」之前，這個假設必須先出現在這裡被人審過。

## 衍生可執行工件

SPEC 核可後、實作開始前，依三層衍生：

| 來源 | 衍生物 | 規則 |
|---|---|---|
| 行為層情境 | 驗收測試 | 每個情境至少一個測試，測試名含情境編號；只落在公開介面上，不 mock 內部協作者 |
| 不變量層條款 | 程式碼內 assertion | 每條 I-n 對應實作中的檢查；Python 用 assert（核心合約用明確 raise，避免 -O 失效）；TS/JS 用輕量 invariant() helper，不引入 DbC 框架 |
| 關鍵規則 | property test | 每功能 2～5 條，見下方挑選啟發式 |

### Property 挑選啟發式

挑「規則可陳述、但答案難以列舉」的規則：

- **守恆**：操作前後總量不變（轉帳前後兩帳戶合計不變）
- **Roundtrip**：編碼後解碼還原（serialize/deserialize、正逆運算）
- **idempotent**：做兩次等於做一次（sort(sort(x)) = sort(x)）
- **不變式維持**：任意操作序列後 I-n 仍成立（stateful testing）
- **失敗原子性**：被拒絕的操作不改變狀態
- **與 reference 比對**：最佳化實作與明顯正確的 baseline 在隨機輸入上結果一致

PBT 套件：優先用專案既有（hypothesis、fast-check、proptest 等）。專案沒有時先問使用者是否引入；不引入則以標準庫隨機生成寫最小驗證迴圈，並註明無 shrinking 的限制。

## 實作期紀律

1. **驗收測試凍結**：驗收測試在實作開始前完成並經核可；實作期間為唯讀。發現測試本身有誤時停下回報，不默默修改。驗收時以 diff 確認驗收測試檔未被實作方變更。
2. **assertion 隨測試執行**：dev／test 環境開啟 assertion，讓每次跑測試同時檢查全部合約（測試放大效果）。生產環境的合約保留策略由使用者決定。
3. **例子與 property 分開陳報**：驗收回報時分別列出情境測試與 property test 的結果；property 失敗附上工具縮小後的最小反例。
4. **紅燈原因確認**：驗收測試寫好後先跑一次，逐例確認失敗訊息是預期的差異（狀態碼、欄位值、筆數不符）。失敗原因是 schema 缺欄位、路由不存在、例外，代表 assertion 還沒被執行到：先補最小的 schema 或路由，讓測試紅在 assertion，再開始實作。回報時引用失敗訊息的 diff。

## 驗收 Checklist

- [ ] 意圖層無獨立存在的行為描述散文
- [ ] 每條功能需求至少一張情境表格，業務邊界情境齊備
- [ ] 每個情境有給定的預期結果，無「實作後補」
- [ ] 不變量逐條編號，每條可對應到程式碼內的檢查點
- [ ] 驗收測試在實作前存在且經核可，測試名可追溯到情境編號
- [ ] 每功能 2～5 條 property test，或明確記錄為何不適用（如純查表規則）
- [ ] 實作 diff 未觸碰驗收測試檔
- [ ] 測試框架有內建 mutation testing 時，對本次改到的產品檔跑一次，附分數與 escaped 清單；escaped 逐條補測試或寫明業務上無差異的理由
- [ ] 斷言「沒有發生某個效果」的測試，旁邊有一個會發生該效果的對照情境
