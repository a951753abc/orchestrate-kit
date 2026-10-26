對抗式 review focus（交付範圍：{{DELIVERY_SCOPE_NAME}}，工單 {{WORK_ORDER_IDS}}；批次 {{BATCH_NO}}／{{BATCH_TOTAL}}；已追蹤檔 diff 指令：{{TRACKED_DIFF_COMMAND}}；新增檔清單：{{NEW_FILES}}）
risk-grade：{{GRADE}}，命中 {{GATE_NAMES}}；理由：{{GRADE_REASON}}
使用情境：{{USAGE_CONTEXT}}

1. 需求與驗收條件是否實際滿足：{{REQUIREMENT_CHECKPOINTS}}
2. root cause 與修改是否對應：{{ROOT_CAUSE_MAPPING}}
3. correctness／邊界條件／回歸風險：{{EDGE_CASES_AND_REGRESSION_SURFACES}}
4. 是否存在不必要修改或 scope drift：允許修改的檔案只有 {{ALLOWED_FILES_FOR_DRIFT_CHECK}}，其餘任何變更都列出

findings 依上列四面向分組回報，各面向內自行排嚴重度，不做跨面向總排名；每條含 檔案:行號、嚴重度、指控內容、觸發情境、觸發分類（「正常使用可觸發」或「特殊條件才觸發」）與影響；觸發依據不足時觸發分類寫「不確定」，不猜發生機率。找不到問題就明說「無 findings」。
