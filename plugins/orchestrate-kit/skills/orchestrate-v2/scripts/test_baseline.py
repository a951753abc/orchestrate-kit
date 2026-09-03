# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""baseline.py 的 stdlib unittest：每案建臨時 git repo。執行：uv run test_baseline.py -v"""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
