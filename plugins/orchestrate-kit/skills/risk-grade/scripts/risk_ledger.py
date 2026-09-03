# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""risk-grade 全域 ledger：append-only JSONL，記錄每次分級與其後續結果，供校準對照。

用法：
  uv run risk_ledger.py record --repo DIR --grade {high,low} --layer {gate,safe,judgement}
                               [--gates NAME...] --reason TEXT [--source TEXT] [--files-count N]
  uv run risk_ledger.py outcome --id ID --result TEXT [--findings N]
  uv run risk_ledger.py summary [--repo DIR] [--json]

預設 ledger：~/.claude/risk-grade/ledger.jsonl（--ledger 可覆寫）。
record 印出新 id；outcome 以 id 關聯；summary 依 repo 過濾並列出四象限。
exit 0＝成功；exit 2＝參數或檔案錯誤；outcome 找不到 id exit 1。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import secrets
import sys
from pathlib import Path

DEFAULT_LEDGER = Path.home() / ".claude" / "risk-grade" / "ledger.jsonl"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_all(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def cmd_record(args: argparse.Namespace) -> int:
    rid = f"rg-{now()}-{secrets.token_hex(2)}"
    append(
        args.ledger,
        {
            "type": "grade",
            "id": rid,
            "at": now(),
            "repo": str(Path(args.repo).resolve()),
            "grade": {"中高": "high", "低": "low"}.get(args.grade, args.grade),
            "layer": args.layer,
            "gates": args.gates or [],
            "reason": args.reason,
            "source": args.source,
            "files_count": args.files_count,
        },
    )
    print(rid)
    return 0


def cmd_outcome(args: argparse.Namespace) -> int:
    rows = read_all(args.ledger)
    if not any(r.get("type") == "grade" and r.get("id") == args.id for r in rows):
        print(f"unknown id: {args.id}", file=sys.stderr)
        return 1
    append(args.ledger, {"type": "outcome", "id": args.id, "at": now(), "result": args.result, "findings": args.findings})
    print(f"outcome recorded: {args.id}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    rows = read_all(args.ledger)
    repo = str(Path(args.repo).resolve()) if args.repo else None
    grades = {r["id"]: r for r in rows if r.get("type") == "grade" and (repo is None or r.get("repo") == repo)}
    outcomes: dict[str, dict] = {}
    for r in rows:
        if r.get("type") == "outcome" and r["id"] in grades:
            outcomes[r["id"]] = r  # 最後一筆為準
    quad = {"high_with_findings": [], "high_no_findings": [], "low_with_findings": [], "low_no_findings": [], "pending": []}
    for rid, g in grades.items():
        o = outcomes.get(rid)
        if o is None:
            quad["pending"].append(rid)
            continue
        has = bool(o.get("findings"))
        key = f"{g['grade']}_{'with' if has else 'no'}_findings"
        quad[key].append(rid)
    report = {
        "repo": repo,
        "total": len(grades),
        "counts": {k: len(v) for k, v in quad.items()},
        "over_escalation_candidates": [
            {"id": rid, "gates": grades[rid]["gates"], "layer": grades[rid]["layer"], "reason": grades[rid]["reason"]}
            for rid in quad["high_no_findings"]
        ],
        "missed_signal_candidates": [
            {"id": rid, "layer": grades[rid]["layer"], "reason": grades[rid]["reason"], "result": outcomes[rid]["result"]}
            for rid in quad["low_with_findings"]
        ],
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"分級總數 {report['total']}（repo：{repo or '全部'}）")
    for k, v in report["counts"].items():
        print(f"  {k}: {v}")
    if report["over_escalation_candidates"]:
        print("過度升級候選（中高、無 findings）：")
        for c in report["over_escalation_candidates"]:
            print(f"  {c['id']} gates={c['gates']} layer={c['layer']} :: {c['reason']}")
    if report["missed_signal_candidates"]:
        print("漏網候選（低、有 findings）：")
        for c in report["missed_signal_candidates"]:
            print(f"  {c['id']} layer={c['layer']} :: {c['reason']} → {c['result']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="ledger 路徑，預設 ~/.claude/risk-grade/ledger.jsonl")
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("record", help="記錄一次分級，印出 id")
    r.add_argument("--repo", required=True)
    r.add_argument("--grade", required=True, choices=["high", "low", "中高", "低"], help="中高→high、低→low")
    r.add_argument("--layer", required=True, choices=["gate", "safe", "judgement"], help="最終定案的層")
    r.add_argument("--gates", nargs="*", default=[], help="命中的 gate 名；無命中時省略本參數")
    r.add_argument("--reason", required=True)
    r.add_argument("--source", default="manual")
    r.add_argument("--files-count", type=int)
    r.set_defaults(func=cmd_record)

    o = sub.add_parser("outcome", help="回填分級的後續結果")
    o.add_argument("--id", required=True)
    o.add_argument("--result", required=True)
    o.add_argument("--findings", type=int, default=0, help="實質 findings 數；0 表示無")
    o.set_defaults(func=cmd_outcome)

    s = sub.add_parser("summary", help="四象限對照，供校準")
    s.add_argument("--repo")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ledger error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
