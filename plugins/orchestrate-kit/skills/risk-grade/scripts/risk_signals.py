# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pyyaml>=6,<7",
# ]
# ///
"""risk-grade 機械訊號：把變更檔案清單對 policy 的 gate 與 safe-change pattern 比對，輸出 JSON。

用法：
  uv run risk_signals.py --repo DIR [--policy FILE] --files PATH...
  uv run risk_signals.py --repo DIR [--policy FILE] --git

policy 順序：--policy → <repo>/.claude/risk-policy.yaml → 本 skill templates/risk-policy.example.yaml。
--git 取 working tree 相對 HEAD 的變更（含 untracked），並算 diff 統計與 formatting-only。
mechanical_layer 為 gate／safe／judgement／empty 之一；verdict 對應 high／low／judgement／none：
high 與 low 是機械層的最終等級，judgement 交呼叫方依 rule 判定（語意類 gate、形狀類白名單、裁量）。
policy `ignore` 清單命中的檔案（建置產物、lock 檔）不參與分類，另列於 ignored。
--executor-failed 表示 executor 同一工單曾失敗或逾時，直接命中 executor_history gate（gate 是下限，優先於 safe）。
exit 0＝正常輸出；exit 2＝policy 讀不到、非 git 目錄或參數錯誤。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

DEFAULT_POLICY = Path(__file__).resolve().parent.parent / "templates" / "risk-policy.example.yaml"


def glob_to_regex(pattern: str) -> re.Pattern:
    """glob → regex：** 跨目錄、* 不跨目錄、? 單字元；pattern 不含 / 時可匹配任一層的檔名。"""
    p = pattern.replace("\\", "/")
    if "/" not in p.rstrip("/"):
        p = "**/" + p
    out = ""
    i = 0
    while i < len(p):
        c = p[i]
        if p.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif p.startswith("**", i):
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile("^" + out + "$")


def load_policy(repo: Path, explicit: str | None) -> tuple[dict, str]:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(repo / ".claude" / "risk-policy.yaml")
    candidates.append(DEFAULT_POLICY)
    for path in candidates:
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            source = "skill 預設" if path == DEFAULT_POLICY else str(path)
            return data, source
    raise FileNotFoundError("no policy file found")


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=off", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return proc.stdout


def git_changes(repo: Path) -> tuple[list[str], dict]:
    tracked = [l for l in git(repo, "diff", "--name-only", "HEAD").splitlines() if l]
    untracked = [l for l in git(repo, "ls-files", "--others", "--exclude-standard").splitlines() if l]
    ins = dele = 0
    for line in git(repo, "diff", "--numstat", "HEAD").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            ins += int(parts[0])
            dele += int(parts[1])
    for path in untracked:
        p = repo / path
        if p.is_file():
            try:
                ins += sum(1 for _ in p.open("rb"))
            except OSError:
                pass
    ws_only = git(repo, "diff", "-w", "--ignore-blank-lines", "--numstat", "HEAD").strip() == "" and not untracked
    files = sorted(set(tracked) | set(untracked))
    return files, {"files": len(files), "insertions": ins, "deletions": dele, "formatting_only": ws_only and bool(files)}


def classify(files: list[str], policy: dict) -> dict:
    gates = policy.get("gates") or []
    safe = policy.get("safe_changes") or {}
    ignore = [glob_to_regex(p) for p in (policy.get("ignore") or [])]
    ignored = [f.replace("\\", "/").lstrip("./") for f in files if any(r.match(f.replace("\\", "/").lstrip("./")) for r in ignore)]
    files = [f for f in files if f.replace("\\", "/").lstrip("./") not in ignored]
    compiled_gates = [
        (g["name"], [glob_to_regex(p) for p in g.get("paths", [])], [glob_to_regex(p) for p in g.get("exclude", [])])
        for g in gates
    ]
    compiled_safe = {cat: [glob_to_regex(p) for p in pats] for cat, pats in safe.items()}
    result_files = []
    gate_hits: dict[str, list[str]] = {}
    unclassified: list[str] = []
    for raw in files:
        path = raw.replace("\\", "/").lstrip("./")
        hit = []
        for name, pats, excl in compiled_gates:
            if any(r.match(path) for r in pats) and not any(r.match(path) for r in excl):
                hit.append(name)
                gate_hits.setdefault(name, []).append(path)
        safe_cat = next((cat for cat, pats in compiled_safe.items() if any(r.match(path) for r in pats)), None)
        if not hit and safe_cat is None:
            unclassified.append(path)
        result_files.append({"path": path, "gates": hit, "safe": safe_cat})
    all_safe = bool(files) and not gate_hits and not unclassified
    if not files:
        layer = "empty"
    elif gate_hits:
        layer = "gate"
    elif all_safe:
        layer = "safe"
    else:
        layer = "judgement"
    return {
        "files": result_files,
        "ignored": ignored,
        "gate_hits": gate_hits,
        "unclassified": unclassified,
        "all_safe": all_safe,
        "mechanical_layer": layer,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="專案根目錄，預設 cwd")
    parser.add_argument("--policy", help="policy 檔路徑；省略時依序找 <repo>/.claude/risk-policy.yaml、skill 預設")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--files", nargs="+", help="變更檔案清單（相對 repo）")
    src.add_argument("--git", action="store_true", help="取 working tree 相對 HEAD 的變更（含 untracked）")
    parser.add_argument("--executor-failed", action="store_true", help="executor 同一工單曾失敗或逾時：直接命中 executor_history gate")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    try:
        policy, source = load_policy(repo, args.policy)
    except (FileNotFoundError, yaml.YAMLError) as exc:
        print(f"policy error: {exc}", file=sys.stderr)
        return 2

    diff = None
    if args.git:
        try:
            files, diff = git_changes(repo)
        except RuntimeError as exc:
            print(f"git error: {exc}", file=sys.stderr)
            return 2
    else:
        files = args.files

    out = classify(files, policy)
    if args.executor_failed:
        out["gate_hits"]["executor_history"] = []
        out["all_safe"] = False
        out["mechanical_layer"] = "gate"
    if diff and diff["formatting_only"] and not out["gate_hits"] and out["mechanical_layer"] == "judgement":
        for f in out["files"]:
            if f["safe"] is None:
                f["safe"] = "formatting"
        out.update({"unclassified": [], "all_safe": True, "mechanical_layer": "safe"})
    limit = int(policy.get("attention_limit_lines") or 0)
    changed_lines = (diff["insertions"] + diff["deletions"]) if diff else None
    verdict = {"gate": "high", "safe": "low", "judgement": "judgement", "empty": "none"}[out["mechanical_layer"]]
    out.update(
        {
            "verdict": verdict,
            "repo": str(repo),
            "policy_source": source,
            "diff": diff,
            "attention_limit_lines": limit,
            "over_attention_limit": bool(limit and changed_lines is not None and changed_lines > limit),
        }
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
