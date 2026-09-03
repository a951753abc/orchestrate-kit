# 工單 {{WORK_ORDER_ID}}：{{WORK_ORDER_TITLE}}

<!-- 目標、允許修改的檔案、驗收條件、禁止事項四段必填，缺一不發派 -->

- 任務形狀：{{TASK_SHAPE}}
- 路由：{{EXECUTOR_AGENT}}
- baseline manifest：{{BASELINE_MANIFEST_PATH}} <!-- Phase 3 snapshot 後回填 -->

## 目標

{{GOAL_ONE_SENTENCE}}

## 允許修改的檔案

{{ALLOWED_FILES_LIST}}

- 可新增檔案：{{MAY_ADD_FILES}}
- 可安裝套件：{{MAY_INSTALL_PACKAGES}}
- 預期 generated artifacts：{{EXPECTED_GENERATED_ARTIFACTS}}

## 驗收條件

{{ACCEPTANCE_COMMANDS_AND_EXPECTED_RESULTS}}

## 禁止事項

- 不順手重構、不改善無關程式碼、不擴大 scope、不放鬆既有測試或 gate
- 允許清單外的檔案一律禁區；需要動清單外檔案時停止並回報，不自行擴權
- git 寫入操作（add／commit／reset／checkout／restore／clean／stash）一律禁止，除非本工單下方明示授權
{{EXTRA_PROHIBITIONS}}

<!-- 以下各段選填：不適用時整段刪除 -->

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
