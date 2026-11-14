# 主控整理的素材與判定（{{TEST_DATE}}）

產出各份文件用的共同素材。工單只引用本檔，不重抄。

## 1. 證據基準

- 查證日期：{{TEST_DATE_AND_TIME_RANGE}}
- 程式基準：`{{REPO_PATH}}`，分支 {{BRANCH}}，commit `{{COMMIT_HASH}}`；{{BUILD_STATE}}
- 系統：`{{SITE_URL}}`（{{ENVIRONMENT_DESCRIPTION}}）。資料庫：{{DATABASE_DESCRIPTION}}
- 這次建立的帳號：{{CREATED_ACCOUNTS}}。清除方式：{{PURGE_METHOD}}
- 攔截的呼叫與固定回應：{{INTERCEPTED_CALLS}}
- UI 參考頁：{{UI_REFERENCE_STATE}}
- 視窗大小與截圖：{{VIEWPORTS_AND_SHOT_RULE}}

## 2. 素材位置

| 內容 | 位置 |
| --- | --- |
| {{RUN_CONTENT}} | `{{RUN_PATHS}}` |
| 主控代做時的截圖 | `{{SETUP_SHOTS_PATH}}` |
| 各角色 agent 各輪的回報全文 | `{{AGENT_REPORTS_PATH}}` |

**隔離清單**：{{QUARANTINED_SHOTS}}

## 3. 各段的結果（現況表的資料）

狀態只用五種：做得完／做得完，有阻礙／卡住後做得完／看得到結果但資訊不足／做不完。

| # | 旅程步驟 | 角色 | 狀態 | 一句話依據 | 截圖範圍 |
| --- | --- | --- | --- | --- | --- |
| {{STEP_NUMBER}} | {{JOURNEY_STEP}} | {{ROLE}} | {{STEP_STATUS}} | {{STEP_BASIS}} | {{SHOT_RANGE}} |

這次沒有操作的範圍（現況表下方要列出）：{{NOT_COVERED_SCOPE}}

數量：{{STEP_COUNTS_BY_ROLE}}；agent 用到提示 {{HINT_COUNT}} 次，卡住 {{STUCK_COUNT}} 次。

## 4. 判讀限制（現況表與裁決報告的證據基準說明要寫）

- 事先知識：{{PRIOR_KNOWLEDGE_LIMIT}}
- 看錯字：{{MISREAD_CASES}}
- 已排除、不列入報告的回報：{{EXCLUDED_REPORTS}}
- 主控親自看過的截圖：{{SHOTS_SEEN_BY_ORCHESTRATOR}}
- 程式查證：{{CODE_CHECK_SUMMARY}}

## 5. 裁決項目清單（裁決報告的索引表與卡片照這份寫）

收尾關係的定義：{{CLOSURE_RELATION_DEFINITIONS}}

修改類別的定義：{{CHANGE_CATEGORY_DEFINITIONS}}

截圖欄寫「run/步驟」，例：`{{SHOT_REFERENCE_SAMPLE}}`。

### 群組 {{GROUP_LETTER}}：{{GROUP_NAME}}

**{{ITEM_ID}} {{ITEM_TITLE}}**｜{{CLOSURE_RELATION}}｜{{CHANGE_CATEGORY}}
- 事實：{{ITEM_FACTS}}
- 截圖：{{ITEM_SHOTS}}
- 程式：{{ITEM_CODE_REFERENCES}}
- 既有裁定與紀錄：{{ITEM_EXISTING_RULINGS}}
- 要裁定的事：{{ITEM_DECISION_NEEDED}}

## 6. 建議的裁決順序（裁決報告第一屏用）

1. {{ORDER_BLOCKING_ITEMS}}
2. {{ORDER_DIAGNOSE_ITEMS}}
3. {{ORDER_SCOPE_ITEMS}}
4. {{ORDER_DEFERRABLE_ITEMS}}
