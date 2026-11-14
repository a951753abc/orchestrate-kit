# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""orchestrate-v2 compact reminder hook：Claude Code SessionStart hook，壓縮後提醒重讀規則檔。

用法：由 plugin 的 `hooks/hooks.json` 登記為 SessionStart hook（matcher `compact`），安裝 plugin 後自動生效。

輸入：stdin 的 SessionStart JSON（session_id、transcript_path、cwd、hook_event_name、source）。
判定載入過 orchestrate-v2：逐行串流讀 transcript_path，先以子字串 `orchestrate-v2` 過濾再解析；
assistant 紀錄的 Skill tool_use（input.skill 冒號切開後最後一段為 orchestrate-v2），
或 user 紀錄的 content 含 `<command-name>/orchestrate-v2</command-name>`
（或帶 plugin 前綴的 `<command-name>/<前綴>:orchestrate-v2</command-name>`）即成立；一般文字提及不算。
輸出：source 為 compact 且成立 → stdout 印
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":<提醒文字>}}，exit 0。
其他情況不輸出。
失敗處理：stdin 非 JSON、transcript 缺少或讀不到、任何例外 → stdout 不輸出，stderr 印一行原因，exit 0。
"""

from __future__ import annotations

import json
import re
import sys

SKILL = "orchestrate-v2"
COMMAND_TAG = re.compile(r"<command-name>/(?:[^<>:\s]+:)?orchestrate-v2</command-name>")
REMINDER = (
    "orchestrate-v2：context 剛經過壓縮，先前讀過的規則檔與樣板全文已不在 context。"
    "繼續本 skill 的流程時，下一次進入各 Phase 的 READ／THINK 步驟，照 SOP 重新讀取該步驟指定的檔案"
    "（rules/假設分類與衝突處理.md、rules/工單判準與形狀補充.md、rules/委派門檻與路由.md、rules/驗收與仲裁憑據.md、"
    "rules/review發派與仲裁.md、rules/失敗分類與partial交接.md 與各樣板），不依壓縮摘要裡的印象執行；"
    "「同一 session 已讀過就不重讀」在壓縮後不適用。待裁清單、baseline manifest、證據檔目錄的路徑若不在摘要裡，"
    "從本任務的證據檔上層目錄找回。"
)


def record_loads(rec: dict) -> bool:
    if not isinstance(rec, dict):
        return False
    msg = rec.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    if rec.get("type") == "assistant" and isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill":
                skill = (b.get("input") or {}).get("skill")
                if isinstance(skill, str) and skill.split(":")[-1] == SKILL:
                    return True
    elif rec.get("type") == "user":
        if isinstance(content, str):
            return COMMAND_TAG.search(content) is not None
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text" and COMMAND_TAG.search(b.get("text") or ""):
                    return True
    return False


def loaded(path: str) -> bool:
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if SKILL not in line:
                continue
            try:
                if record_loads(json.loads(line)):
                    return True
            except ValueError:
                continue
    return False


def main() -> None:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    if payload.get("source") != "compact":
        return
    path = payload.get("transcript_path")
    if not path or not loaded(path):
        return
    out = json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": REMINDER}},
                     ensure_ascii=False)
    sys.stdout.buffer.write((out + "\n").encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — hook 失敗不得影響 session
        print(f"compact_reminder_hook: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(0)
