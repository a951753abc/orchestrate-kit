# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""稽核角色 agent 的工具呼叫有沒有守住「只看畫面操作」的限制。

只讀 subagent 的 transcript（jsonl），只取工具呼叫的名稱與輸入；不印工具回傳，也不印程式全文。

用法：
  uv run audit_agent_tools.py --transcript <subagent 的 jsonl> --run-dir <run 目錄>
      [--allow-goto <網址前綴> ...] [--upload-dir <目錄> ...] [--allow-tool <工具名稱> ...] [--json]

檢查項目：
  tool        用了允許清單以外的工具（預設允許 ToolSearch、Read、Write、
              browser_run_code_unsafe、browser_file_upload、browser_handle_dialog；--allow-tool 可追加）
  read        Read 的對象不是 <run 目錄>/shots/ 底下的 PNG
  write       Write 的對象不在 <run 目錄>/log/ 底下
  code        run_code 的程式含元素定位、讀取頁面內容、改視窗、開分頁等寫法，或以 filename 執行
  goto        page.goto 的網址不是 --allow-goto 列出的前綴開頭（沒給 --allow-goto 時任何 goto 都算）
  upload      browser_file_upload 的檔案不在 --upload-dir（預設 <run 目錄>/album/）底下
  toolsearch  ToolSearch 載入了允許清單以外的工具
  clipboard   按了 Control／Meta 加 V、C、X（可能把電腦剪貼簿的內容帶進頁面）

每筆附步驟編號：取自同一次 run_code 內截圖路徑的三位數檔名；其他工具歸在最近一個步驟之後。
輸出：各工具次數、goto 網址、步驟範圍、剪貼簿按鍵的步驟、違規清單。--json 輸出同一份結構化結果。
結束碼：沒有違規也沒有剪貼簿按鍵 0；有任何一項 1；參數或檔案錯誤 2。
可 import：audit(transcript, run_dir, allow_goto=(), upload_dirs=(), extra_tools=())。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

RUN_CODE = "mcp__playwright__browser_run_code_unsafe"
FILE_UPLOAD = "mcp__playwright__browser_file_upload"
DEFAULT_TOOLS = frozenset(
    {"ToolSearch", "Read", "Write", RUN_CODE, FILE_UPLOAD, "mcp__playwright__browser_handle_dialog"}
)
FORBIDDEN_RE = re.compile(
    r"locator|getBy|\$\(|\$\$|evaluate|content\(|innerText|innerHTML|textContent|fullPage|"
    r"waitForSelector|querySelector|setViewportSize|newPage|context\(|JSON\.stringify|clipboard"
)
CLIP_RE = re.compile(r"(?:Control|Meta)\+[VvCcXx]\b")
GOTO_RE = re.compile(r"goto\(\s*['\"`]([^'\"`]+)")
STEP_RE = re.compile(r"(\d{3})a?\.png")


def norm(path) -> str:
    return str(path).replace("\\", "/").lower().rstrip("/")


def under(path: str, directory: str) -> bool:
    return norm(path).startswith(norm(directory) + "/")


def tool_uses(obj):
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and "name" in obj:
            yield obj
        for value in obj.values():
            yield from tool_uses(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from tool_uses(value)


def audit(transcript, run_dir, allow_goto=(), upload_dirs=(), extra_tools=()) -> dict:
    run = norm(run_dir)
    shots, logs = run + "/shots", run + "/log"
    uploads = [norm(d) for d in upload_dirs] or [run + "/album"]
    allowed = set(DEFAULT_TOOLS) | set(extra_tools)

    counts: Counter = Counter()
    gotos: Counter = Counter()
    violations: list[dict] = []
    clipboard: list[dict] = []
    steps: list[str] = []
    last_step = "000"
    seen: set = set()

    def flag(kind: str, tool: str, detail: str, step: str) -> None:
        violations.append({"step": step, "kind": kind, "tool": tool, "detail": detail[:160]})

    with Path(transcript).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            for use in tool_uses(record):
                uid = use.get("id")
                if uid is not None:
                    if uid in seen:
                        continue
                    seen.add(uid)
                name = use["name"]
                inp = use.get("input") or {}
                counts[name] += 1
                short = name.replace("mcp__playwright__", "")
                if name not in allowed:
                    flag("tool", short, json.dumps(inp, ensure_ascii=False), f"{last_step}+")
                    continue
                if name == RUN_CODE:
                    code = inp.get("code") or ""
                    found = STEP_RE.findall(code)
                    step = found[-1] if found else f"{last_step}+"
                    if found:
                        last_step = found[-1]
                        steps.append(last_step)
                    if inp.get("filename"):
                        flag("code", short, "filename=" + str(inp.get("filename")), step)
                    hit = FORBIDDEN_RE.search(code)
                    if hit:
                        flag("code", short, "forbidden: " + hit.group(0), step)
                    for key in CLIP_RE.findall(code):
                        clipboard.append({"step": step, "key": key})
                    for url in GOTO_RE.findall(code):
                        gotos[url] += 1
                        if not any(url.startswith(prefix) for prefix in allow_goto):
                            flag("goto", short, url, step)
                elif name == "Read":
                    path = norm(inp.get("file_path", ""))
                    if not (under(path, shots) and path.endswith(".png")):
                        flag("read", short, path, f"{last_step}+")
                elif name == "Write":
                    path = norm(inp.get("file_path", ""))
                    if not under(path, logs):
                        flag("write", short, path, f"{last_step}+")
                elif name == FILE_UPLOAD:
                    for path in inp.get("paths") or []:
                        if not any(under(path, d) for d in uploads):
                            flag("upload", short, norm(path), f"{last_step}+")
                elif name == "ToolSearch":
                    query = str(inp.get("query", ""))
                    wanted = [t.strip() for t in query.replace("select:", "").split(",") if t.strip()]
                    if not query.startswith("select:") or any(t not in allowed for t in wanted):
                        flag("toolsearch", short, query, f"{last_step}+")

    return {
        "tool_counts": dict(counts.most_common()),
        "goto_urls": dict(gotos),
        "steps": {"count": len(set(steps)), "first": min(steps, default=None), "last": max(steps, default=None)},
        "clipboard": clipboard,
        "violations": violations,
        "ok": not violations and not clipboard,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="稽核角色 agent 的工具呼叫")
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--allow-goto", action="append", default=[])
    parser.add_argument("--upload-dir", action="append", default=[])
    parser.add_argument("--allow-tool", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not Path(args.transcript).is_file():
        print(f"transcript 不存在：{args.transcript}", file=sys.stderr)
        return 2

    result = audit(args.transcript, args.run_dir, args.allow_goto, args.upload_dir, args.allow_tool)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0 if result["ok"] else 1

    label = Path(norm(args.run_dir)).name
    steps = result["steps"]
    print(f"[{label}] tool counts: {result['tool_counts']}")
    print(f"[{label}] goto urls: {result['goto_urls']}")
    print(f"[{label}] steps: {steps['count']} ({steps['first']}–{steps['last']})")
    clip_steps = sorted({c["step"] for c in result["clipboard"]})
    print(f"[{label}] clipboard key presses: {len(result['clipboard'])} steps={clip_steps}")
    print(f"[{label}] violations: {len(result['violations'])}")
    for v in result["violations"]:
        print(f"    step {v['step']}  {v['kind']}  {v['tool']}  {v['detail']}")
    print("OK" if result["ok"] else "FAIL")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
