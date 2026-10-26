# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""baseline.py 的 stdlib unittest：每案建臨時 git repo。執行：uv run test_baseline.py -v"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("baseline.py")


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def posix_replace(src: Path, dst: Path) -> None:
    """Windows 的 POSIX 語意 rename（FileRenameInfoEx），Rust `std::fs::rename` 用的就是這個；
    `os.replace`（MoveFileExW）連 FILE_SHARE_DELETE 的目的檔都蓋不過，不能當對照。"""
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k32.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = k32.CreateFileW(str(src), 0x00010000, 0x1 | 0x2 | 0x4, None, 3, 0x80, None)  # DELETE 權限
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        name = str(dst).encode("utf-16-le")
        # FILE_RENAME_INFO：Flags(4)＋對齊(4)＋RootDirectory(8)＋FileNameLength(4)＋FileName
        info = (0x1 | 0x2).to_bytes(4, "little") + bytes(4) + bytes(8) + len(name).to_bytes(4, "little") + name + bytes(4)
        buf = ctypes.create_string_buffer(info, len(info))
        if not k32.SetFileInformationByHandle(handle, 22, buf, len(info)):  # FileRenameInfoEx
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        k32.CloseHandle(handle)


class BaselineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name).resolve()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        (self.repo / "b.txt").write_text("b\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")
        self._out = tempfile.TemporaryDirectory()
        self.manifest = Path(self._out.name) / "baseline.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()
        self._out.cleanup()

    def snapshot(self) -> None:
        proc = run("snapshot", "--out", str(self.manifest), cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def compare(self, *extra: str) -> tuple[int, list[dict]]:
        proc = run("compare", "--baseline", str(self.manifest), "--json", *extra, cwd=self.repo)
        findings = json.loads(proc.stdout)["findings"] if proc.stdout.strip() else []
        return proc.returncode, findings

    # 1. 乾淨 repo
    def test_clean_repo(self) -> None:
        self.snapshot()
        code, findings = self.compare()
        self.assertEqual((code, findings), (0, []))

    # 2. allow 內修改
    def test_in_scope_modification(self) -> None:
        self.snapshot()
        (self.repo / "a.txt").write_text("a2\n", encoding="utf-8")
        code, findings = self.compare("--allow", "a.txt")
        self.assertEqual((code, findings), (0, []))

    # 3. allow 外修改
    def test_out_of_scope_modification(self) -> None:
        self.snapshot()
        (self.repo / "b.txt").write_text("b2\n", encoding="utf-8")
        code, findings = self.compare("--allow", "a.txt")
        self.assertEqual(code, 1)
        self.assertEqual([f["type"] for f in findings], ["out_of_scope"])
        self.assertEqual(findings[0]["path"], "b.txt")

    # 4. 使用者原有修改被覆寫（allow 內標 in_scope 仍列出）
    def test_baseline_dirty_overwritten(self) -> None:
        (self.repo / "a.txt").write_text("user edit\n", encoding="utf-8")
        self.snapshot()
        (self.repo / "a.txt").write_text("executor edit\n", encoding="utf-8")
        code, findings = self.compare("--allow", "a.txt")
        self.assertEqual(code, 1)
        self.assertEqual(findings[0]["type"], "baseline_dirty_changed")
        self.assertTrue(findings[0]["in_scope"])

    # 4b. patch 以 LF 寫出，可用來把使用者原有修改還原回去
    def test_patch_applies_after_checkout(self) -> None:
        (self.repo / "a.txt").write_text("user edit\n", encoding="utf-8")
        self.snapshot()
        patch = self.manifest.with_suffix(".patch")
        self.assertNotIn(b"\r\n", patch.read_bytes())
        git(self.repo, "checkout", "--", "a.txt")
        git(self.repo, "apply", str(patch))
        self.assertEqual((self.repo / "a.txt").read_text(encoding="utf-8"), "user edit\n")

    # 5. untracked 有無 allow-new
    def test_untracked_with_and_without_allow_new(self) -> None:
        self.snapshot()
        (self.repo / "new.txt").write_text("n\n", encoding="utf-8")
        code, findings = self.compare()
        self.assertEqual(code, 1)
        self.assertEqual([f["type"] for f in findings], ["unauthorized_untracked"])
        code, findings = self.compare("--allow-new", "new.txt")
        self.assertEqual((code, findings), (0, []))

    # 6. ignored 檔不列
    def test_ignored_file_not_listed(self) -> None:
        self.snapshot()
        (self.repo / "debug.log").write_text("x\n", encoding="utf-8")
        code, findings = self.compare()
        self.assertEqual((code, findings), (0, []))

    # 7. binary 檔
    def test_binary_file(self) -> None:
        (self.repo / "blob.bin").write_bytes(bytes(range(256)) * 4)
        git(self.repo, "add", "blob.bin")
        git(self.repo, "commit", "-q", "-m", "bin")
        self.snapshot()
        (self.repo / "blob.bin").write_bytes(b"\x00\xff" * 100)
        code, findings = self.compare("--allow", "a.txt")
        self.assertEqual(code, 1)
        self.assertEqual(findings[0], {"type": "out_of_scope", "path": "blob.bin", "in_scope": False})
        code, _ = self.compare("--allow", "blob.bin")
        self.assertEqual(code, 0)

    # 8. symlink（無權限則 skip）
    def test_symlink_records_target(self) -> None:
        link = self.repo / "link.txt"
        try:
            os.symlink("a.txt", link)
        except (OSError, NotImplementedError):
            self.skipTest("symlink not permitted on this host")
        self.snapshot()
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["files"]["link.txt"]["working_sha256"], "symlink:a.txt")
        self.assertIsNone(data["files"]["link.txt"]["size"])

    # 9. 非 git 目錄
    def test_non_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as plain:
            out = Path(plain) / "m.json"
            proc = run("snapshot", "--repo", plain, "--out", str(out), cwd=Path(plain))
            self.assertEqual(proc.returncode, 2)
            self.assertFalse(out.exists())

    # 10a. 建置產物（__pycache__）預設不比對
    def test_ignore_build_artifacts(self) -> None:
        (self.repo / "__pycache__").mkdir()
        (self.repo / "__pycache__" / "a.cpython-314.pyc").write_bytes(b"\x00\x01")
        self.snapshot()
        (self.repo / "__pycache__" / "a.cpython-314.pyc").write_bytes(b"\x00\x02")
        (self.repo / "__pycache__" / "b.cpython-314.pyc").write_bytes(b"\x00\x03")
        code, findings = self.compare()
        self.assertEqual((code, findings), (0, []))

    # 10. staged 變更
    def test_staged_change_detected(self) -> None:
        self.snapshot()
        (self.repo / "a.txt").write_text("staged\n", encoding="utf-8")
        git(self.repo, "add", "a.txt")
        code, findings = self.compare("--allow", "a.txt")
        self.assertEqual(code, 1)
        self.assertIn("new_staged", [f["type"] for f in findings])
        self.assertNotIn("out_of_scope", [f["type"] for f in findings])

    # 11. 讀檔期間不妨礙其他程序以 rename 覆寫該檔（Windows；2026-10-01 gbf-cli 進度檔事故）
    @unittest.skipUnless(os.name == "nt", "Windows 的檔案共享模式")
    def test_reading_does_not_block_replace(self) -> None:
        spec = importlib.util.spec_from_file_location("baseline", SCRIPT)
        baseline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(baseline)
        target = self.repo / "record.json"
        target.write_bytes(b"old\n")
        fresh = self.repo / "record.json.tmp"
        fresh.write_bytes(b"new\n")
        with baseline.open_shared(target) as fh:
            posix_replace(fresh, target)
            self.assertEqual(fh.read(), b"old\n")
        self.assertEqual(target.read_bytes(), b"new\n")
        # 對照：Python 預設開檔會擋住同一種 rename
        fresh.write_bytes(b"newer\n")
        with target.open("rb"):
            with self.assertRaises(OSError):
                posix_replace(fresh, target)

    # 12. 單一檔案讀不到時不中止，manifest 記為 unreadable
    @unittest.skipUnless(os.name == "nt", "Windows 的檔案共享模式")
    def test_unreadable_file_does_not_abort(self) -> None:
        import ctypes
        from ctypes import wintypes

        locked = self.repo / "locked.bin"
        locked.write_bytes(b"x")
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = k32.CreateFileW(str(locked), 0x80000000, 0, None, 3, 0x80, None)  # GENERIC_READ，不共享
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        try:
            proc = run("snapshot", "--out", str(self.manifest), cwd=self.repo)
        finally:
            k32.CloseHandle(handle)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["files"]["locked.bin"]["working_sha256"], "unreadable:PermissionError")
        self.assertIsNone(data["files"]["locked.bin"]["size"])
        self.assertIn("locked.bin", proc.stderr)


HOOK = Path(__file__).with_name("baseline_hook.py")


class BaselineHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self._dirs = [tempfile.TemporaryDirectory() for _ in range(3)]
        self.repo, self.plain, self.temp = (Path(d.name).resolve() for d in self._dirs)
        git(self.repo, "init", "-q")
        (self.repo / "x.txt").write_text("x\n", encoding="utf-8")  # untracked，manifest 應記 1 個檔

    def tearDown(self) -> None:
        for d in self._dirs:
            d.cleanup()

    def hook(self, stdin: str, *args: str) -> subprocess.CompletedProcess:
        # tempfile 先看 TMPDIR（Git Bash 會帶入），不蓋掉就會寫進真正的 %TEMP%
        env = {**os.environ, "TMPDIR": str(self.temp), "TMP": str(self.temp), "TEMP": str(self.temp), "PYTHONUTF8": "1"}
        return subprocess.run([sys.executable, str(HOOK), *args], input=stdin.encode("utf-8"),
                              capture_output=True, env=env, cwd=self.plain)

    def payload(self, subagent: str, prompt: str, cwd: Path) -> str:
        return json.dumps({"tool_name": "Agent", "tool_use_id": "toolu_T1", "session_id": "s1", "cwd": str(cwd),
                           "tool_input": {"subagent_type": subagent, "prompt": prompt, "description": "d"}},
                          ensure_ascii=False)

    def context(self, proc: subprocess.CompletedProcess) -> str:
        return json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]["additionalContext"]

    def written(self) -> list[Path]:
        return [p for p in self.temp.rglob("*") if p.is_file()]

    def test_hook_plugin_namespaced_executor(self) -> None:
        proc = self.hook(self.payload("orchestrate-kit:opus-lite-executor", f"專案目錄：{self.repo}", self.plain))
        self.assertIn("已自動 snapshot", self.context(proc))
        proc = self.hook(self.payload("orchestrate-kit:opus-lite-explorer", f"專案目錄：{self.repo}", self.plain))
        self.assertEqual(proc.stdout, b"")

    def test_hook_non_executor_silent(self) -> None:
        proc = self.hook(self.payload("opus-lite-explorer", f"專案目錄：{self.repo}", self.repo))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"")
        self.assertEqual(self.written(), [])

    def test_hook_project_line_overrides_cwd(self) -> None:
        proc = self.hook(self.payload("opus-executor", f"工單\n- 專案目錄：{self.repo}\n其他", self.plain))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        ctx = self.context(proc)
        manifests = list(self.temp.glob("claude-orchestrate/*/baseline-*.json"))
        self.assertEqual(len(manifests), 1)
        self.assertIn(str(manifests[0]), ctx)
        self.assertIn("檔案 1 個", ctx)
        data = json.loads(manifests[0].read_text(encoding="utf-8"))
        self.assertEqual(Path(data["repo"]), self.repo)
        rows = [json.loads(l) for l in (self.temp / "claude-orchestrate" / "hook-index.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["tool_use_id"] for r in rows], ["toolu_T1"])
        self.assertEqual(Path(rows[0]["manifest"]), manifests[0])

    def test_hook_backtick_halfwidth_colon(self) -> None:
        proc = self.hook(self.payload("opus-lite-executor", f"專案目錄: `{self.repo}`", self.plain))
        self.assertIn("已自動 snapshot", self.context(proc))

    def test_hook_project_line_with_trailing_note(self) -> None:
        for line in (f"- 專案目錄：{self.repo}（Laravel 13、PHP 8.5）。前一張工單已完成", f"專案目錄：{self.repo} 說明文字"):
            proc = self.hook(self.payload("opus-executor", line, self.plain))
            self.assertIn("已自動 snapshot", self.context(proc), line)

    def test_hook_falls_back_to_cwd(self) -> None:
        proc = self.hook(self.payload("opus-lite-executor", "沒有目錄行", self.repo))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("已自動 snapshot", self.context(proc))
        self.assertEqual(len(list(self.temp.glob("claude-orchestrate/*/baseline-*.json"))), 1)

    def test_hook_non_git(self) -> None:
        proc = self.hook(self.payload("opus-executor", "x", self.plain))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("不是 git repo", self.context(proc))
        self.assertEqual(self.written(), [])

    def test_hook_invalid_json_fail_open(self) -> None:
        proc = self.hook("not json{")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("baseline hook 失敗", self.context(proc))

    def test_hook_dry_run(self) -> None:
        cases = [
            (self.payload("opus-executor", "x", self.repo), "snapshot", "將 snapshot"),
            (self.payload("opus-lite-explorer", "x", self.repo), "skip", "非 executor"),
            (self.payload("opus-executor", "x", self.plain), "skip", "非 git repo"),
        ]
        for stdin, action, reason in cases:
            proc = self.hook(stdin, "--dry-run")
            self.assertEqual(proc.returncode, 0)
            out = json.loads(proc.stdout.decode("utf-8"))
            self.assertEqual((out["action"], out["reason"]), (action, reason))
        self.assertEqual(self.written(), [])

    def test_hook_snapshot_failure_denies(self) -> None:
        blocker = self.temp / "claude-orchestrate"
        blocker.write_text("not a dir", encoding="utf-8")  # manifest 目錄建不起來
        proc = self.hook(self.payload("opus-executor", f"專案目錄：{self.repo}", self.plain))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(b'"permissionDecision": "deny"', proc.stdout)
        reason = json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("baseline hook 失敗：", reason)
        self.assertIn("「baseline manifest：<manifest 路徑>」後重新發派", reason)
        self.assertEqual(self.written(), [blocker])

    def test_hook_given_manifest_skips_snapshot(self) -> None:
        given = self.plain / "given.json"
        given.write_text("{}", encoding="utf-8")
        prompt = f"專案目錄：{self.repo}\n- baseline manifest：{given}\n"
        proc = self.hook(self.payload("opus-executor", prompt, self.plain))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(b"permissionDecision", proc.stdout)
        self.assertEqual(self.context(proc), f"baseline hook：工單已指定 manifest {given}，未另外 snapshot")
        self.assertEqual(self.written(), [])

    def test_hook_placeholder_manifest_line_still_snapshots(self) -> None:
        prompt = f"專案目錄：{self.repo}\n- baseline manifest：（hook 自動 snapshot 後回填）\n"
        proc = self.hook(self.payload("opus-executor", prompt, self.plain))
        self.assertIn("已自動 snapshot", self.context(proc))
        self.assertEqual(len(list(self.temp.glob("claude-orchestrate/*/baseline-*.json"))), 1)

    def test_hook_success_mentions_earliest_manifest(self) -> None:
        proc = self.hook(self.payload("opus-executor", f"專案目錄：{self.repo}", self.plain))
        self.assertIn("同一回合並行派出多張工單時，全部用檔名時間最早的那份", self.context(proc))

    def test_hook_backtick_path_with_space_and_note(self) -> None:
        spaced = self.plain / "My Repo"
        spaced.mkdir()
        git(spaced, "init", "-q")
        (spaced / "y.txt").write_text("y\n", encoding="utf-8")
        for line in (f"專案目錄：`{spaced}` 說明", f"- 專案目錄：`{spaced}`（Laravel）"):
            proc = self.hook(self.payload("opus-executor", line, self.plain))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(f"（repo {spaced}，檔案 1 個）", self.context(proc), line)


if __name__ == "__main__":
    unittest.main()
