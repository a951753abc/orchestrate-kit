# 風險分級：{{CHANGE_SCOPE_TITLE}}

- ledger id：{{LEDGER_ID}} <!-- 沒有 working tree 變更時寫「以允許檔清單估算，以驗收後判定為準」 -->
- 等級：{{GRADE}} <!-- 中高／低 -->
- 判定層：{{DECISION_LAYER}} <!-- gate／safe／judgement -->
- policy 來源：{{POLICY_SOURCE}} <!-- 專案檔路徑，或「skill 預設」 -->
- 呼叫來源：{{SOURCE}} <!-- orchestrate-v2、manual 等，與 ledger --source 同值 -->

## 命中 gate

<!-- 路徑類列命中檔案；語意類列工單目標或 diff 中的判定線索；executor_history 列失敗／逾時次數；無則寫「無」 -->
- {{GATE_NAME}}：{{GATE_HIT_EVIDENCE}}

## safe-change 分類

<!-- 每個類別列檔案；有未分類檔案要列出；無則寫「無」 -->
- {{SAFE_CATEGORY}}：{{SAFE_FILES}}

## 裁量理由

<!-- 只在判定層為 judgement 時填：哪個檔案的哪個行為，出錯時影響什麼；blast radius 與可逆性 -->
{{JUDGEMENT_REASON}}

## diff 統計與分批建議

- 檔案 {{FILE_COUNT}}、+{{INSERTIONS}}／-{{DELETIONS}}
- {{BATCH_ADVICE}} <!-- 超過 attention_limit 時寫分批方式；否則寫「不需分批」 -->

## 建議處置

{{RECOMMENDED_ACTION}} <!-- 中高：派外部 review 並附 focus 重點；低：呼叫方自驗，列自驗項 -->
