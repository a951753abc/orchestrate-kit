# 工單 {{WORK_ORDER_ID}}：{{WORK_ORDER_TITLE}}

<!-- 目標、使用情境、允許修改的檔案、驗收條件、禁止事項五段與證據檔目錄必填，缺一不發派 -->

- 任務形狀：{{TASK_SHAPE}}
- 路由：{{EXECUTOR_AGENT}}
- 交付範圍：{{DELIVERY_SCOPE_NAME}} <!-- 同一輪 review 一起交付的工單；修正工單填「修正：<原交付範圍>」 -->
- 專案目錄：{{REPO_DIR}} <!-- baseline hook 從這行取 repo；與 session cwd 相同也要填 -->
- baseline manifest：{{BASELINE_MANIFEST_PATH}} <!-- hook 自動 snapshot 後回填 -->
- 證據檔目錄：{{EVIDENCE_DIR}} <!-- 放 repo 外；executor 修改前寫 before-<驗收編號>.txt、修改後寫 after-<驗收編號>.txt，每檔第一行 `$ <指令原文>`、下一行 `exit code: <n>`，再接完整輸出；同一檔多次執行依序附加；executor 的回報全文在完成通知的最後訊息裡，orchestrator 要留存時自己存成本目錄的 report.md，不要求 executor 另建報告檔（2026-10-10 實測背景 agent 的 task output 檔是空的） -->

## 目標

{{GOAL_ONE_SENTENCE}}

## 使用情境

<!-- 誰在用、什麼環境、資料可否重建、誰負責復原；review focus 沿用 -->
{{USAGE_CONTEXT}}

## 允許修改的檔案

{{ALLOWED_FILES_LIST}}

- 可新增檔案：{{MAY_ADD_FILES}}
- 可安裝套件：{{MAY_INSTALL_PACKAGES}}
- 預期 generated artifacts：{{EXPECTED_GENERATED_ARTIFACTS}}

## 驗收條件

<!-- 逐條編號；執行時點填「修改前要跑」（問題重現、比較基準）或「只在修改後跑」；修改前＝改動被測程式之前，工單要求新增的測試與 fixture 可先寫好；前景 Bash 指令 10 分鐘會被停掉，輸出沒有 exit code、不能當證據，容器內（`docker exec`）的行程不會跟著停：預估超過 10 分鐘的驗收指令寫明以 `run_in_background` 執行並指定 timeout，或留給 orchestrator 自己跑 -->
<!-- 測試分快慢兩層寫：改動中只跑本工單相關的測試（filter 或變更檔），工單收尾跑一次全套快測試，瀏覽器或 e2e 只在收尾或工單改到畫面流程時跑；每條測試指令的證據檔記下秒數 -->
- {{ACCEPTANCE_ID}}（{{RUN_TIMING}}）：{{ACCEPTANCE_COMMAND_AND_EXPECTED_RESULT}}

## 禁止事項

- 不順手重構、不改善無關程式碼、不擴大 scope、不放鬆既有測試或 gate
- 允許清單外的檔案一律禁區；需要動清單外檔案時停止並回報，不自行擴權
- git 寫入操作（add／commit／reset／checkout／restore／clean／stash）一律禁止，除非本工單下方明示授權
{{EXTRA_PROHIBITIONS}}

<!-- 以下各段選填：不適用時整段刪除 -->

## 一次性操作

<!-- 替換腳本、migration、資料匯入這類再跑一次結果不同的操作填：executor 只執行一次並把輸出寫進證據檔目錄的 after-op.txt；驗收條件只寫結果檢查 -->
{{ONE_TIME_OPERATION}}

## 測試品質約束

<!-- 工單要求新增或修改測試時保留本段 -->
- 期望值必須來自獨立來源（已知字面值、規格算例），不得用與實作同邏輯重算出期望值
- 測試只落在 {{PUBLIC_SEAM}} 上斷言，不 mock 內部協作者、不驗證呼叫次數與順序

## 診斷依據

<!-- Bug 工單填：已觀察事實、根因證據、已排除假說；不得寫成 executor 必須服從的結論 -->
{{DIAGNOSIS_EVIDENCE}}

## Bug 補充驗收

<!-- Bug 工單填：修正前失敗證據、regression test 修正前失敗／修正後通過、原始症狀直接驗證、相關 suite／typecheck／build -->
{{BUG_ACCEPTANCE_ADDENDUM}}

## 最佳化補充驗收

<!-- 最佳化／資料遷移工單填：reference 比對範圍、benchmark 產物、遷移前後不變式 -->
{{OPTIMIZATION_ACCEPTANCE_ADDENDUM}}

## SPEC 情境對應

<!-- 需 SPEC 的工單填：引用的情境編號、不變量編號與衍生的凍結測試檔 -->
{{SPEC_SCENARIO_MAPPING}}

## 狀態交接

<!-- 留有 partial 修改後重發時填：已改哪些檔、哪些驗收已過、卡在哪一步、實際錯誤輸出 -->
{{PARTIAL_STATE_HANDOFF}}
