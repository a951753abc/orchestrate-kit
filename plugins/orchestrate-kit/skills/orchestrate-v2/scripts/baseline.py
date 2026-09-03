# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""orchestrate-v2 baseline：發派 executor 前快照 working tree，驗收時比對越界修改。

用法：
  uv run baseline.py snapshot [--repo DIR] [--out FILE.json]
  uv run baseline.py compare --baseline FILE.json --allow PATH... [--allow-new PATH...] [--ignore GLOB...] [--json]

snapshot 記錄 dirty／staged／untracked 檔案的路徑、狀態、working copy sha256、staged blob id 與大小，
完整 patch 另存同名 .patch。非 git 目錄 exit 2 且不寫檔。
compare 產出四類 finding：越界修改（out_of_scope）、新 staged 內容（new_staged）、
未授權的新 untracked（unauthorized_untracked）、baseline 時已 dirty 的檔案內容改變（baseline_dirty_changed，
在 allow 內者標 in_scope 仍列出）。有 finding exit 1，乾淨 exit 0，baseline 讀不到或非 git exit 2。
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


# ---------- git helpers ----------


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip())
    return proc.stdout.decode("utf-8", "surrogateescape")


def repo_root(start: Path) -> Path | None:
    proc = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.strip()).resolve()


def name_status(repo: Path, *extra: str) -> dict[str, str]:
    """回傳 {path: status}；rename 以新路徑為 key，狀態記 R。"""
    out = git(repo, "diff", "--name-status", "--no-ext-diff", "-z", *extra)
    parts = out.split("\0")
    result: dict[str, str] = {}
    i = 0
    while i < len(parts) and parts[i]:
        status = parts[i]
        if status[0] in "RC":
            old, new = parts[i + 1], parts[i + 2]
            result[new] = f"{status[0]}<{old}"
            i += 3
        else:
            result[parts[i + 1]] = status[0]
            i += 2
    return result


def untracked(repo: Path) -> list[str]:
    out = git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    return [p for p in out.split("\0") if p]


def staged_blob(repo: Path, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f":{path}"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() or None


def working_hash(repo: Path, path: str) -> tuple[str | None, int | None]:
    p = repo / path
    if p.is_symlink():
        return f"symlink:{os.readlink(p)}", None
    if not p.is_file():
        return None, None
    h = hashlib.sha256()
    size = 0
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


# ---------- snapshot ----------


def collect(repo: Path) -> dict:
    unstaged = name_status(repo)
    staged = name_status(repo, "--cached")
    others = untracked(repo)
    files: dict[str, dict] = {}
    for path in sorted(set(unstaged) | set(staged) | set(others)):
        wh, size = working_hash(repo, path)
        files[path] = {
            "unstaged": unstaged.get(path),
            "staged": staged.get(path),
            "untracked": path in others,
            "working_sha256": wh,
            "staged_blob": staged_blob(repo, path) if path in staged else None,
            "size": size,
        }
    head = git(repo, "rev-parse", "--verify", "--quiet", "HEAD", check=False).strip() or None
    return {"repo": str(repo), "head": head, "files": files}


def default_out(repo: Path) -> Path:
    digest = hashlib.sha256(str(repo).encode("utf-8")).hexdigest()[:12]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.gettempdir()) / "claude-orchestrate" / digest / f"baseline-{stamp}.json"


def cmd_snapshot(args: argparse.Namespace) -> int:
    repo = repo_root(Path(args.repo))
    if repo is None:
        print(f"not a git repository: {args.repo}", file=sys.stderr)
        return 2
    data = collect(repo)
    data["created_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    out = Path(args.out) if args.out else default_out(repo)
    out.parent.mkdir(parents=True, exist_ok=True)
    patch = git(repo, "diff", "--no-ext-diff", "--binary") + git(repo, "diff", "--cached", "--no-ext-diff", "--binary")
    patch_path = out.with_suffix(".patch")
    patch_path.write_text(patch, encoding="utf-8", errors="surrogateescape")
    data["patch"] = str(patch_path)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"baseline written: {out}")
    print(f"files recorded: {len(data['files'])}")
    return 0


# ---------- compare ----------


def normalize(repo: Path, raw: str) -> str:
    p = Path(raw)
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(repo)
        except ValueError:
            return raw.replace("\\", "/")
    return p.as_posix()


def cmd_compare(args: argparse.Namespace) -> int:
    base_path = Path(args.baseline)
    if not base_path.is_file():
        print(f"baseline not found: {base_path}", file=sys.stderr)
        return 2
    base = json.loads(base_path.read_text(encoding="utf-8"))
    repo = repo_root(Path(base["repo"]))
    if repo is None:
        print(f"not a git repository: {base['repo']}", file=sys.stderr)
        return 2
    allow = {normalize(repo, p) for p in args.allow}
    allow_new = {normalize(repo, p) for p in args.allow_new}
    self_files = {normalize(repo, str(base_path.resolve())), normalize(repo, base.get("patch", ""))}
    ignored = lambda p: any(fnmatch.fnmatch(p, pat) for pat in args.ignore)  # noqa: E731
    before: dict[str, dict] = {p: f for p, f in base["files"].items() if not ignored(p)}
    now = {p: f for p, f in collect(repo)["files"].items() if p not in self_files and not ignored(p)}
    findings: list[dict] = []

    for path, cur in now.items():
        prev = before.get(path)
        # 2. 新 staged 內容：不論是否在 allow 內
        if cur["staged"] and (prev is None or cur["staged_blob"] != prev.get("staged_blob")):
            findings.append({"type": "new_staged", "path": path, "in_scope": path in allow})
        # 3. 未授權的新 untracked
        if cur["untracked"] and prev is None and path not in allow_new:
            findings.append({"type": "unauthorized_untracked", "path": path, "in_scope": False})
        # 4. baseline 時已 dirty／untracked 的檔案內容改變
        if prev is not None and cur["working_sha256"] != prev.get("working_sha256"):
            findings.append({"type": "baseline_dirty_changed", "path": path, "in_scope": path in allow})
        # 1. 越界修改：tracked 檔案有新變更且不在 allow 內
        if (
            not cur["untracked"]
            and path not in allow
            and (prev is None or cur["working_sha256"] != prev.get("working_sha256"))
        ):
            findings.append({"type": "out_of_scope", "path": path, "in_scope": False})

    # baseline 時存在的 dirty 檔案在現況消失（被還原或刪除）也視為內容改變
    for path, prev in before.items():
        if path not in now:
            findings.append({"type": "baseline_dirty_changed", "path": path, "in_scope": path in allow, "note": "no longer dirty"})

    if args.json:
        print(json.dumps({"findings": findings}, ensure_ascii=False, indent=2))
    elif findings:
        for f in findings:
            scope = " (in-scope)" if f.get("in_scope") else ""
            note = f" [{f['note']}]" if f.get("note") else ""
            print(f"{f['type']}: {f['path']}{scope}{note}")
    else:
        print("clean: no findings")
    return 1 if findings else 0


# ---------- cli ----------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("snapshot", help="記錄目前 working tree 狀態")
    s.add_argument("--repo", default=".", help="repo 內任一目錄，預設 cwd")
    s.add_argument("--out", help="manifest 輸出路徑，預設 %%TEMP%%/claude-orchestrate/<repo hash>/baseline-<UTC>.json")
    s.set_defaults(func=cmd_snapshot)

    c = sub.add_parser("compare", help="與 baseline 比對並列出 finding")
    c.add_argument("--baseline", required=True, help="snapshot 產出的 json")
    c.add_argument("--allow", action="append", default=[], help="工單允許修改的檔案，可重複")
    c.add_argument("--allow-new", action="append", default=[], help="工單允許新增的檔案，可重複")
    c.add_argument("--ignore", action="append", default=["*.pyc", "*__pycache__/*", "*.DS_Store"], help="不比對的 glob（建置產物），可重複；預設含 pyc／__pycache__")
    c.add_argument("--json", action="store_true", help="以 JSON 輸出 findings")
    c.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"git error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
