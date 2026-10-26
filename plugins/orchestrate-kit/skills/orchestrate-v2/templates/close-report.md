# Close 報告：{{TASK_TITLE}}

## 做了什麼

<!-- 以工單為單位：編號、目標、路由、結果 -->
- 工單 {{WORK_ORDER_ID}}（{{EXECUTOR_AGENT}}）：{{WORK_ORDER_OUTCOME}}

## diff 摘要

<!-- 依檔案列出改了什麼；越界檔若有，單獨標示 -->
- `{{CHANGED_FILE}}`：{{CHANGE_SUMMARY}}

## 親自查核的測試證據

<!-- 每條驗收一列：指令或產物檔、實際結果、結果來源；來源填「通過（主控重跑）」（verifier 照清單執行的也算）、「通過（採 executor 證據）」（附證據檔路徑與時間比對結果）或「未查證」；未查證的不寫成通過 -->
- {{ACCEPTANCE_ID}} `{{VERIFICATION_COMMAND}}` → {{OBSERVED_RESULT}}；{{VERIFICATION_SOURCE}}

## 風險分級

<!-- 每個 ledger id 一列：等級、判定層、命中 gate、outcome 是否已回填 -->
- {{LEDGER_ID}}：{{GRADE}}（{{DECISION_LAYER}}，{{GATE_NAMES}}）；outcome 已回填 findings {{FINDINGS_COUNT}}

## 待人工判斷事項

<!-- 同一事項只列一次；類別填「沿用 executor 證據」「未查證 finding」「PLAUSIBLE」「已知限制」；狀態填「待接受」「已接受」或「需先裁定」（涉及底線，使用者裁定前不 close），依使用者裁定或既有明確授權填寫；涉及底線的排在最前；沒有就寫「無」 -->

| 事項 | 類別 | 可能影響 | 需要人工做什麼 | 狀態 |
|---|---|---|---|---|
| {{PENDING_ITEM}} | {{PENDING_CATEGORY}} | {{POSSIBLE_IMPACT}} | {{HUMAN_ACTION}} | {{PENDING_STATUS}} |

## 未執行項目

<!-- 本輪略過的驗證、review 或工單與理由；沒有就寫「無」 -->
- {{SKIPPED_ITEM_WITH_REASON}}

## 殘餘風險與仲裁紀錄

<!-- 否決的 findings 與理由、已修正的真問題；PLAUSIBLE、未查證 finding 與已知限制列在「待人工判斷事項」，不在此重複 -->
- {{RESIDUAL_RISK_OR_ADJUDICATION}}

## baseline manifest

- 位置：{{BASELINE_MANIFEST_PATH}}
- 清理狀態：{{BASELINE_CLEANUP_STATUS}}

## commit

{{COMMIT_STATUS}} <!-- 只依使用者指示；未指示則寫「未 commit，等待指示」 -->
