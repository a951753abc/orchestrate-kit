# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""orchestrate-v2 baseline hook：Claude Code PreToolUse hook，派 executor 前自動 snapshot。

用法（由 plugin 的 hooks/hooks.json 自動登記為 PreToolUse，matcher `Agent|Task`）：
  python baseline_hook.py            # stdin＝hook JSON
  python baseline_hook.py --dry-run  # 只判斷，不寫檔

輸入：stdin 的 PreToolUse JSON。只處理 tool_name 為 Agent／Task 且 tool_input.subagent_type
為 opus-executor／opus-lite-executor 者（plugin 命名空間前綴如 orchestrate-kit: 忽略），其餘不輸出、exit 0。
目標目錄取 tool_input.prompt 內第一個「專案目錄：<路徑>」行（全形或半形冒號；路徑包反引號時取反引號內完整路徑，
後面可接說明文字；未包反引號時依序截在標點、空白前），沒有則用 cwd。
prompt 已有「baseline manifest：<存在的 .json 路徑>」行 → 不 snapshot、不擋，additionalContext 回報沿用該 manifest。
輸出：git repo → 以 baseline.write_snapshot 寫 manifest（路徑同 baseline.py snapshot 預設值），
在 %TEMP%/claude-orchestrate/hook-index.jsonl 追加一行索引，stdout 印
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":...}} 回報 manifest 路徑；
非 git repo → 同格式提示需手動 snapshot。
失敗處理：import baseline、判斷 repo、snapshot 或寫索引時發生任何例外 → stdout 印
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":...}}
擋下這次派工，請 orchestrator 手動 snapshot 並在工單加 baseline manifest 行後重發；exit 0。
stdin 非 JSON 等其餘例外維持 fail-open：只在 additionalContext 回報失敗，不擋派工。
--dry-run：不寫任何檔，stdout 印一行 {"action":"snapshot"|"skip"|"deny","repo":...,"reason":...}。
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

EXECUTORS = {"opus-executor", "opus-lite-executor"}
# 第一種：反引號包住的完整路徑（可含空白，後面可接說明）；第二種：未包反引號，交給 target_dir 截斷
PROJECT_LINE = re.compile(r"專案目錄\s*[:：]\s*(?:`([^`\r\n]+)`|`?([^`\r\n]+?)`?\s*$)", re.MULTILINE)
MANIFEST_LINE = re.compile(r"baseline manifest\s*[:：]\s*`?([^`\r\n]+?\.json)`?", re.IGNORECASE)


def emit(text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}, ensure_ascii=False))


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}, ensure_ascii=False))


def given_manifest(payload: dict) -> str | None:
    for m in MANIFEST_LINE.finditer(payload.get("tool_input", {}).get("prompt") or ""):
        path = m.group(1).strip()
        if Path(path).is_file():
            return path
    return None


def target_dir(payload: dict) -> str:
    m = PROJECT_LINE.search(payload.get("tool_input", {}).get("prompt") or "")
    if not m:
        return payload.get("cwd") or "."
    if m.group(1):
        return m.group(1).strip()
    raw = m.group(2).strip()
    # 路徑後面常接說明文字（例：`D:/x（Laravel 13）`）：依序截在標點、空白前，取第一個存在的目錄
    for cut in (raw, re.split(r"[（(，,。；;]", raw)[0].strip(), raw.split()[0] if raw.split() else raw):
        if cut and Path(cut).is_dir():
            return cut
    return raw


def is_executor(payload: dict) -> bool:
    # plugin 安裝時 agent 名稱帶命名空間（例：orchestrate-kit:opus-executor），只比對最後一段
    name = str(payload.get("tool_input", {}).get("subagent_type") or "").rsplit(":", 1)[-1]
    return payload.get("tool_name") in ("Agent", "Task") and name in EXECUTORS


def run(payload: dict, dry_run: bool) -> None:
    if not is_executor(payload):
        if dry_run:
            print(json.dumps({"action": "skip", "repo": None, "reason": "非 executor"}, ensure_ascii=False))
        return
    given = given_manifest(payload)
    if given:
        if dry_run:
            print(json.dumps({"action": "skip", "repo": None, "reason": "工單已指定 manifest"}, ensure_ascii=False))
        else:
            emit(f"baseline hook：工單已指定 manifest {given}，未另外 snapshot")
        return
    try:
        snapshot(payload, dry_run)
    except Exception as exc:  # 沒有基準就不讓 executor 開工
        reason = (f"baseline hook 失敗：{type(exc).__name__}: {exc}；請手動執行 baseline.py snapshot，"
                  "並在工單加一行「baseline manifest：<manifest 路徑>」後重新發派")
        if dry_run:
            print(json.dumps({"action": "deny", "repo": None, "reason": reason}, ensure_ascii=False))
        else:
            deny(reason)


def snapshot(payload: dict, dry_run: bool) -> None:
    import baseline

    target = target_dir(payload)
    repo = baseline.repo_root(Path(target))
    if repo is None:
        if dry_run:
            print(json.dumps({"action": "skip", "repo": None, "reason": "非 git repo"}, ensure_ascii=False))
        else:
            emit(f"baseline hook：{target} 不是 git repo，未自動 snapshot；需要時手動執行 baseline.py snapshot")
        return
    if dry_run:
        print(json.dumps({"action": "snapshot", "repo": str(repo), "reason": "將 snapshot"}, ensure_ascii=False))
        return
    # 同一回合並行派工會在同一秒觸發多次，檔名加 tool_use_id 避免互相覆蓋
    out = baseline.default_out(repo)
    suffix = re.sub(r"[^A-Za-z0-9]", "", str(payload.get("tool_use_id") or ""))[-12:]
    if suffix:
        out = out.with_name(f"{out.stem}-{suffix}{out.suffix}")
    manifest, count = baseline.write_snapshot(repo, out)
    tool_input = payload.get("tool_input", {})
    index = Path(tempfile.gettempdir()) / "claude-orchestrate" / "hook-index.jsonl"
    index.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "session_id": payload.get("session_id"),
        "tool_use_id": payload.get("tool_use_id"),
        "subagent_type": tool_input.get("subagent_type"),
        "description": tool_input.get("description"),
        "repo": str(repo),
        "manifest": str(manifest),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    with index.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    emit(f"baseline hook 已自動 snapshot：{manifest}（repo {repo}，檔案 {count} 個）；Phase 4 compare 用此路徑；"
         "同一回合並行派出多張工單時，全部用檔名時間最早的那份")


def main() -> int:
    dry_run = "--dry-run" in sys.argv[1:]
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        run(payload, dry_run)
    except Exception as exc:  # fail-open：stdin 非 JSON 等，不擋派工
        emit(f"baseline hook 失敗：{type(exc).__name__}: {exc}；請手動執行 baseline.py snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
