# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""risk-grade 全域 ledger：append-only JSONL，記錄每次分級與其後續結果，供校準對照。

用法：
  uv run risk_ledger.py record --repo DIR --grade {high,low} --layer {gate,safe,judgement}
                               [--gates NAME...] --reason TEXT [--source TEXT] [--files-count N]
  uv run risk_ledger.py outcome --id ID --result TEXT [--findings N]
                                [--fixed N] [--deferred N] [--rejected N] [--category NAME=N ...]
  uv run risk_ledger.py outcome --id ID --result TEXT --merged-into ID
  uv run risk_ledger.py summary [--repo DIR] [--json]

預設 ledger：~/.claude/risk-grade/ledger.jsonl（--ledger 可覆寫）。
record 印出新 id；outcome 以 id 關聯；summary 依 repo 過濾並列出四象限。
outcome 的 --fixed／--deferred／--rejected／--category 為 review 處置結構化欄位，
  有給任一個時寫入 dispositions 鍵；省略 --findings 時 findings＝fixed＋deferred。
  類別：test_gap、logic、security_data、doc、other；各類加總須等於 --fixed。
outcome 的 --merged-into：這筆的 review 併入另一筆 id 一起做，findings 記在那一筆；
  不可與 --findings 及結構化欄位併用、不可指向自己；summary 依目標最後一筆 outcome 判斷象限。
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
CATEGORIES = ("test_gap", "logic", "security_data", "doc", "other")


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


def parse_dispositions(args: argparse.Namespace) -> dict | None:
    """回傳 dispositions dict；沒給結構化參數回 None；不合法時丟 ValueError。"""
    counts = {"fixed": args.fixed, "deferred": args.deferred, "rejected": args.rejected}
    if all(v is None for v in counts.values()) and not args.category:
        return None
    for name, v in counts.items():
        if v is not None and v < 0:
            raise ValueError(f"--{name} 不得為負數：{v}")
    categories: dict[str, int] = {}
    for item in args.category or []:
        name, sep, num = item.partition("=")
        if not sep or not name:
            raise ValueError(f"--category 格式須為 NAME=N：{item}")
        if name not in CATEGORIES:
            raise ValueError(f"--category 類別不在清單內（{', '.join(CATEGORIES)}）：{name}")
        try:
            n = int(num)
        except ValueError:
            raise ValueError(f"--category 的 N 須為整數：{item}") from None
        if n < 0:
            raise ValueError(f"--category 的 N 不得為負數：{item}")
        categories[name] = categories.get(name, 0) + n
    if categories:
        if args.fixed is None:
            raise ValueError("給了 --category 必須同時給 --fixed")
        if sum(categories.values()) != args.fixed:
            raise ValueError(f"--category 加總 {sum(categories.values())} 不等於 --fixed {args.fixed}")
    return {**{k: v or 0 for k, v in counts.items()}, "categories": categories}


def cmd_outcome(args: argparse.Namespace) -> int:
    if args.merged_into is not None:
        conflicts = [f"--{n}" for n in ("findings", "fixed", "deferred", "rejected") if getattr(args, n) is not None]
        if args.category:
            conflicts.append("--category")
        if conflicts:
            print(f"invalid outcome: --merged-into 不可與 {'、'.join(conflicts)} 併用", file=sys.stderr)
            return 2
        if args.merged_into == args.id:
            print("invalid outcome: --merged-into 不可指向本筆 --id", file=sys.stderr)
            return 2
    try:
        disp = parse_dispositions(args)
    except ValueError as exc:
        print(f"invalid outcome: {exc}", file=sys.stderr)
        return 2
    rows = read_all(args.ledger)
    if not any(r.get("type") == "grade" and r.get("id") == args.id for r in rows):
        print(f"unknown id: {args.id}", file=sys.stderr)
        return 1
    if args.merged_into is not None:
        if not any(r.get("type") == "grade" and r.get("id") == args.merged_into for r in rows):
            print(f"unknown id: {args.merged_into}", file=sys.stderr)
            return 1
        append(args.ledger, {"type": "outcome", "id": args.id, "at": now(), "result": args.result,
                             "findings": 0, "merged_into": args.merged_into})
        print(f"outcome recorded: {args.id}")
        return 0
    findings = args.findings
    if findings is None:
        findings = disp["fixed"] + disp["deferred"] if disp else 0
    row = {"type": "outcome", "id": args.id, "at": now(), "result": args.result, "findings": findings}
    if disp is not None:
        row["dispositions"] = disp
    append(args.ledger, row)
    print(f"outcome recorded: {args.id}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    rows = read_all(args.ledger)
    repo = str(Path(args.repo).resolve()) if args.repo else None
    grades = {r["id"]: r for r in rows if r.get("type") == "grade" and (repo is None or r.get("repo") == repo)}
    all_outcomes: dict[str, dict] = {}
    for r in rows:
        if r.get("type") == "outcome":
            all_outcomes[r["id"]] = r  # 最後一筆為準；merged_into 目標不受 repo 過濾
    outcomes = {rid: o for rid, o in all_outcomes.items() if rid in grades}
    quad = {"high_with_findings": [], "high_no_findings": [], "low_with_findings": [], "low_no_findings": [], "pending": []}
    for rid, g in grades.items():
        o = outcomes.get(rid)
        if o is None:
            quad["pending"].append(rid)
            continue
        if o.get("merged_into") is not None:
            o = all_outcomes.get(o["merged_into"])
            if o is None or o.get("merged_into") is not None:  # 只解析一層
                quad["pending"].append(rid)
                continue
        has = bool(o.get("findings"))
        key = f"{g['grade']}_{'with' if has else 'no'}_findings"
        quad[key].append(rid)
    disp_total = {"structured": 0, "legacy": 0, "merged": 0, "fixed": 0, "deferred": 0, "rejected": 0, "categories": {}}
    for o in outcomes.values():
        if o.get("merged_into") is not None:
            disp_total["merged"] += 1
            continue
        d = o.get("dispositions")
        if d is None:
            disp_total["legacy"] += 1
            continue
        disp_total["structured"] += 1
        for k in ("fixed", "deferred", "rejected"):
            disp_total[k] += d.get(k, 0)
        for name, n in d.get("categories", {}).items():
            disp_total["categories"][name] = disp_total["categories"].get(name, 0) + n
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
        "dispositions": disp_total,
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
    d = report["dispositions"]
    print(f"review 處置（結構化 {d['structured']} 筆、舊格式 {d['legacy']} 筆、合併 {d['merged']} 筆）：fixed={d['fixed']} deferred={d['deferred']} rejected={d['rejected']}")
    if d["categories"]:
        print("  fixed 類別：" + " ".join(f"{k}={v}" for k, v in sorted(d["categories"].items())))
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
    o.add_argument("--findings", type=int, help="實質 findings 數；0 表示無。省略時：有結構化參數＝fixed＋deferred，否則 0")
    o.add_argument("--fixed", type=int, help="判為真問題，已修或已開修正工單的條數")
    o.add_argument("--deferred", type=int, help="已知限制候選、PLAUSIBLE、交使用者裁決、登記另案的條數")
    o.add_argument("--rejected", type=int, help="否決的條數")
    o.add_argument("--category", action="append", metavar="NAME=N",
                   help="可重複；fixed 條目中屬於該類的條數，各類加總須等於 --fixed。NAME：test_gap＝測試本身的缺口"
                        "（測錯對象、缺情境、fixture 過寬、斷言太弱）；logic＝產品或工具的邏輯錯誤；"
                        "security_data＝授權、個資外露、資料寫入、加密、交易；doc＝文件或規則措辭；other＝其他")
    o.add_argument("--merged-into", metavar="ID",
                   help="這筆分級的 review 已併入另一筆 id 一起做，findings 記在那一筆；不可與 --findings／--fixed／"
                        "--deferred／--rejected／--category 併用")
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
