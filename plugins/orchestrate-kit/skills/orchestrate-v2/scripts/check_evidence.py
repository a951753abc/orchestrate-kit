# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""orchestrate-v2 證據檔檢查：一次讀完工單證據檔目錄，取代逐檔 cat 與時間比對。

用法：
  uv run check_evidence.py --dir <證據檔目錄> [--repo <專案目錄>] [--allow <允許檔> ...] [--expect V1,V2,...] [--tail N] [--json]

--repo：--allow 相對路徑的基準目錄，預設 cwd。--expect：每個列出的驗收編號都要有 after-<編號>…txt。

只掃目錄第一層的 before-*.txt／after-*.txt；驗收編號＝前綴之後到第一個 "." 為止。
每檔抽出指令原文（行首 "$ "、"COMMAND:"、"CMD:"）、exit code（行首 exit code／exit／rc（前面可有 "---"）接 : 或 = 與整數，數字後可接說明文字；
多個取最後一個，runs＝數量）、末段 N 個非空白行原文；cmd 取最後一個 exit 行之前最近的指令行（即最後一段的指令）。
每檔旗標：no_command、no_exit_code、earlier_nonzero（最後一段之前有非 0 的 exit code）、final_nonzero（after 檔最後一段 exit code 非 0）、
decode_errors（解碼出現替換字元 U+FFFD）、stale（after 檔早於存在的允許檔最大 mtime）、missing_after（before 無對應 after）。
全域旗標：missing_allow（允許檔不存在）、missing_evidence（--expect 列出的編號沒有 after 檔）。
ok 只表示格式完整；通過與否看 exit 與末段原文。
文字輸出每檔一段，最後一行 files=<n> flagged=<n> skipped=<n>，有全域旗標時接 missing_allow=<路徑,…>、missing_evidence=<編號,…>；
--json 輸出結構化結果（含 missing_allow、missing_evidence）。
結束碼：無旗標 0，有任何旗標 1，目錄不存在 2。可 import check_dir(path, allow, tail, repo, expect)。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^(before|after)-([^.]*)\..*txt$")
CMD_RE = re.compile(r"^(?:\$ |command:|cmd:)(.*)$", re.IGNORECASE)
EXIT_RE = re.compile(r"^(?:-+\s*)?(?:exit code|exit|rc)\s*[:=]\s*(-?\d+)(?![\w.])", re.IGNORECASE)


def read_text(p: Path) -> str:
    data = p.read_bytes()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def check_dir(path, allow=None, tail: int = 8, repo=None, expect=None) -> dict:
    d = Path(path)
    allow = allow or []
    base = Path(repo) if repo is not None else Path.cwd()
    existing = [base / a for a in allow if (base / a).exists()]
    missing_allow = [str(a) for a in allow if not (base / a).exists()]
    allow_max = max((a.stat().st_mtime for a in existing), default=None)

    files, skipped = [], []
    for p in sorted(x for x in d.iterdir() if x.is_file()):
        m = NAME_RE.match(p.name)
        if not m or not p.name.endswith(".txt"):
            skipped.append(p.name)
            continue
        kind, vid = m.group(1), m.group(2)
        text = read_text(p)
        lines = text.splitlines()
        cmds = [(i, cm.group(1).strip()) for i, ln in enumerate(lines) if (cm := CMD_RE.match(ln))]
        exits = [(i, int(em.group(1))) for i, ln in enumerate(lines) if (em := EXIT_RE.match(ln))]
        codes = [c for _, c in exits]
        # 多段時取最後一段的指令；最後一個 exit 行之前沒有指令行時退回第一個指令行
        before_last = [c for i, c in cmds if exits and i < exits[-1][0]]
        command = before_last[-1] if before_last else (cmds[0][1] if cmds else None)
        flags = []
        if command is None:
            flags.append("no_command")
        if not codes:
            flags.append("no_exit_code")
        # 一檔多段時只取最後一段會蓋掉中間失敗的指令；分不出是重跑還是多個指令，交給人讀整檔
        if any(c != 0 for c in codes[:-1]):
            flags.append("earlier_nonzero")
        if kind == "after" and codes and codes[-1] != 0:
            flags.append("final_nonzero")
        if "\ufffd" in text:
            flags.append("decode_errors")
        if kind == "after" and allow_max is not None and p.stat().st_mtime <= allow_max:
            flags.append("stale")
        files.append({
            "name": p.name, "id": vid, "kind": kind, "command": command,
            "exit_code": codes[-1] if codes else None, "runs": len(codes), "exit_codes": codes,
            "flags": flags, "tail": [ln for ln in lines if ln.strip()][-tail:] if tail > 0 else [],
        })
    after_ids = {f["id"] for f in files if f["kind"] == "after"}
    for f in files:
        if f["kind"] == "before" and f["id"] not in after_ids:
            f["flags"].append("missing_after")
    expect = expect or []
    missing_evidence = [v for v in expect if v not in after_ids]
    return {"files": files, "skipped": skipped, "missing_allow": missing_allow, "missing_evidence": missing_evidence}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="檢查工單證據檔目錄")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--repo", default=None, help="--allow 相對路徑的基準目錄，預設 cwd")
    ap.add_argument("--allow", nargs="*", action="extend", default=[])
    ap.add_argument("--expect", default="", help="逗號分隔的驗收編號，例 V1,V2,V3")
    ap.add_argument("--tail", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not Path(a.dir).is_dir():
        print(f"目錄不存在：{a.dir}", file=sys.stderr)
        return 2
    expect = [v.strip() for v in a.expect.split(",") if v.strip()]
    r = check_dir(a.dir, a.allow, a.tail, a.repo, expect)
    flagged = sum(1 for f in r["files"] if f["flags"])
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for f in r["files"]:
            ec = "-" if f["exit_code"] is None else f["exit_code"]
            runs = f"runs={f['runs']}" + (f" ({','.join(map(str, f['exit_codes']))})" if f["runs"] > 1 else "")
            print(f"{f['name']} | exit={ec} | {runs} | {','.join(f['flags']) or 'ok'}")
            print(f"  cmd: {(f['command'] or '')[:200]}")
            for ln in f["tail"]:
                print(f"  {ln}")
        if r["skipped"]:
            print(f"略過 {len(r['skipped'])} 個檔")
        summary = f"files={len(r['files'])} flagged={flagged} skipped={len(r['skipped'])}"
        if r["missing_allow"]:
            summary += " missing_allow=" + ",".join(r["missing_allow"])
        if r["missing_evidence"]:
            summary += " missing_evidence=" + ",".join(r["missing_evidence"])
        print(summary)
    return 1 if flagged or r["missing_allow"] or r["missing_evidence"] else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
