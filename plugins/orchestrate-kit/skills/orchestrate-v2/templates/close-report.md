# Close 報告：{{TASK_TITLE}}

## 做了什麼

<!-- 以工單為單位：編號、目標、路由、結果 -->
- 工單 {{WORK_ORDER_ID}}（{{EXECUTOR_AGENT}}）：{{WORK_ORDER_OUTCOME}}

## diff 摘要

<!-- 依檔案列出改了什麼；越界檔若有，單獨標示 -->
- `{{CHANGED_FILE}}`：{{CHANGE_SUMMARY}}

## 親自執行的測試證據

<!-- orchestrator 自己跑的指令與實際輸出，不是 executor 的回報 -->
- `{{VERIFICATION_COMMAND}}` → {{OBSERVED_RESULT}}

## 風險分級

<!-- 每個 ledger id 一列：等級、判定層、命中 gate、outcome 是否已回填 -->
- {{LEDGER_ID}}：{{GRADE}}（{{DECISION_LAYER}}，{{GATE_NAMES}}）；outcome 已回填 findings {{FINDINGS_COUNT}}

## 未執行項目

<!-- 本輪略過的驗證、review 或工單與理由；沒有就寫「無」 -->
- {{SKIPPED_ITEM_WITH_REASON}}

## 殘餘風險與仲裁紀錄

<!-- 未處理的邊界、PLAUSIBLE 待裁決項、否決的 findings 與理由 -->
- {{RESIDUAL_RISK_OR_ADJUDICATION}}

## baseline manifest

- 位置：{{BASELINE_MANIFEST_PATH}}
- 清理狀態：{{BASELINE_CLEANUP_STATUS}}

## commit

{{COMMIT_STATUS}} <!-- 只依使用者指示；未指示則寫「未 commit，等待指示」 -->
