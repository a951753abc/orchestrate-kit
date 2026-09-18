---
name: debug-by-evidence
description: Diagnose bugs, test failures, flaky behavior, performance regressions, and unexpected technical behavior using reproducible evidence before proposing or implementing fixes. Use before fixing a defect, when a previous fix failed, or when the root cause is uncertain. Do not use for ordinary feature implementation or documentation-only changes.
---

# Debug by Evidence

證據先於修法。「從 code 看起來可能是」永遠不是已確認根因。

## 適用範圍

- 用於：bug／非預期行為、test／build／integration failure、flaky 或間歇性問題、效能退化、前次修復無效、證據不足時被要求提出修法。
- 不用於：一般功能開發、文件修改、單純設定調整、已明確定義的機械修改。
- 分工線：**能用實驗否證的技術假說歸本 skill；只能由人裁決的產品／規格／架構假設，上報使用者裁決**，不要混進同一份診斷。

## 流程

### 1. 建立失敗證據

- 症狀若是「以前沒有、最近才有」的退化：先釘首見時間，列出該時間點前後的變更清單（新裝軟體、驅動、系統更新、設定、擴充），逐項還原或停用做二分。變更清單優先於任何儀器；儀器只在變更清單走完仍無解時才上。
- 優先重現原始症狀；保存最小重現步驟、輸入、actual／expected output 與環境資訊。
- 取得重現後收緊迴路：更快（秒級，快取 setup、縮小測試範圍）、訊號更尖（斷言具體症狀，而非「沒 crash」）、更確定（釘時間、固定 seed、隔離檔案系統）。30 秒且不穩定的迴路只比沒有好一點；2 秒且確定的迴路才足以支撐後續診斷。
- 無法重現時，收集 log、stack trace、時間序列與環境差異。
- flaky 類問題：單次結果不構成證據——重現與修復驗證都必須重複執行（如連跑 20 次）取得統計證據。診斷目標是把重現率拉高到可除錯的程度（迴圈執行、平行化、加壓、注入 sleep），不是等待一次乾淨的單次重現。

### 2. 定位首次偏離

- 沿資料流、狀態流或呼叫鏈向上游追蹤；在 UI、API、service、queue、DB、外部依賴等邊界比較輸入與輸出。
- 找出 expected 與 actual 第一次不一致的位置，不停在最後拋錯的地方。

### 3. 建立並否證假說

- 明確分開 `Observed facts` 與 `Hypotheses`；每次只驗證一個主要假說，為它設計能使其成立或失敗的最小檢查。
- 臨時 log／instrumentation 一律加同一組唯一前綴（如 `[DEBUG-a4f2]`），收尾用一次 grep 即可全部清除。
- 記錄被排除的假說，避免後續重複探索。
- 停損：同一思路失敗兩次即換思路；歸咎環境前先做一個能區分環境與程式的實驗；連續兩輪沒有進展就停下，回報卡點與已排除的假設。
- 證據不足時如實回報「尚未定位」＋下一個最小診斷步驟，不硬給根因。

### 4. 建立回歸保護

- 可自動測試就新增（或沿用既有的）一個修正前失敗的 regression test。
- 不適合自動化時說明原因，並定義可重複執行的替代驗證。

### 5. 最小修復與驗證

- 只修改根因所需的最小範圍。
- 先驗證原始症狀已消失，再跑 regression test、相關 test suite、typecheck／build。
- 未執行或無法執行的驗證必須明示。
- 宣告完成前 grep 該前綴，確認臨時 instrumentation 已全數移除。

## Provisional fix 出口

僅限兩種情況：無法重現（production-only、heisenbug），或繼續診斷成本明顯高於帶保險的修復。條件：

- 明示「根因為假說、未經證實」，不得寫成已確認。
- 附觀測性增強（log／instrumentation），讓下次發生時能定位。
- 附還原方式（如何撤掉這次修改）。

止血修復（revert 肇事 commit）不需完整根因，但要留下診斷線索供後續追查。

## 輸出格式

1. Failure evidence
2. Observed facts
3. Root cause and supporting evidence（或「尚未定位」＋下一步）
4. Rejected hypotheses
5. Regression protection
6. Fix scope
7. Verification evidence
8. Remaining uncertainty

## 非目標

模型路由、派工 subagent、worktree、決定允許修改的檔案、review 與 findings 仲裁、git 操作、對所有 coding task 強制 TDD——這些由 `/orchestrate-kit:orchestrate-v2` 管理。
