# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""check_evidence.py 的 unittest。用法：uv run test_check_evidence.py -v"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_evidence import check_dir  # noqa: E402

SCRIPT = HERE / "check_evidence.py"


class CheckEvidenceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def w(self, name, text, encoding="utf-8"):
        p = self.d / name
        p.write_bytes(text.encode(encoding) if encoding != "utf-16-le-bom" else b"\xff\xfe" + text.encode("utf-16-le"))
        return p

    def by_name(self, r):
        return {f["name"]: f for f in r["files"]}

    def test_exit_forms(self):
        self.w("after-A.txt", "$ a\nexit code: 0\nout\n")
        self.w("after-B.txt", "$ b\nEXIT CODE: 3\n")
        self.w("after-C.txt", "$ c\nEXIT: 0\n")
        self.w("after-D.txt", "$ d\nexit=0\n")
        self.w("after-E.txt", "$ e\nrc=1\n")
        f = self.by_name(check_dir(self.d, [], 8))
        self.assertEqual(f["after-A.txt"]["exit_code"], 0)
        self.assertEqual(f["after-B.txt"]["exit_code"], 3)
        self.assertEqual(f["after-C.txt"]["exit_code"], 0)
        self.assertEqual(f["after-D.txt"]["exit_code"], 0)
        self.assertEqual(f["after-E.txt"]["exit_code"], 1)
        for name in ("after-A.txt", "after-C.txt", "after-D.txt"):
            self.assertEqual(f[name]["flags"], [])
        for name in ("after-B.txt", "after-E.txt"):
            self.assertEqual(f[name]["flags"], ["final_nonzero"])

    def test_exit_with_decoration(self):
        self.w("after-A.txt", "$ a\n--- exit code: 2 ---\n")
        self.w("after-B.txt", "$ b\nexit code: 0  elapsed: 3.2s\n")
        self.w("after-C.txt", "$ c\nexit=1 (rg exit 1 = 0 筆)\n")
        self.w("after-D.txt", "$ d\nexit code: 1.5\n")
        f = self.by_name(check_dir(self.d, [], 8))
        self.assertEqual(f["after-A.txt"]["exit_code"], 2)
        self.assertEqual(f["after-B.txt"]["exit_code"], 0)
        self.assertEqual(f["after-C.txt"]["exit_code"], 1)
        self.assertIn("no_exit_code", f["after-D.txt"]["flags"])

    def test_earlier_nonzero_flagged(self):
        self.w("after-V1.txt", "$ a\nexit code: 0\n$ b\nexit code: 1\n$ c\nexit code: 0\n")
        self.w("after-V2.txt", "$ a\nexit code: 0\n$ b\nexit code: 0\n")
        f = self.by_name(check_dir(self.d, [], 8))
        self.assertEqual(f["after-V1.txt"]["exit_code"], 0)
        self.assertIn("earlier_nonzero", f["after-V1.txt"]["flags"])
        self.assertEqual(f["after-V2.txt"]["flags"], [])

    def test_two_runs_takes_last(self):
        self.w("after-V1.txt", "$ x\nexit code: 1\nfail\n$ x\nexit code: 0\nok\n")
        f = self.by_name(check_dir(self.d, [], 8))["after-V1.txt"]
        self.assertEqual(f["exit_code"], 0)
        self.assertEqual(f["runs"], 2)

    def test_indented_exit_ignored(self):
        self.w("after-V1.txt", "$ x\n    mysql exit code: 0\n")
        f = self.by_name(check_dir(self.d, [], 8))["after-V1.txt"]
        self.assertIsNone(f["exit_code"])
        self.assertIn("no_exit_code", f["flags"])

    def test_no_command(self):
        self.w("after-V1.txt", "exit code: 0\n")
        f = self.by_name(check_dir(self.d, [], 8))["after-V1.txt"]
        self.assertIn("no_command", f["flags"])

    def test_utf16(self):
        self.w("after-V1.txt", "$ uv run 測試\r\nexit code: 0\r\n", "utf-16-le-bom")
        f = self.by_name(check_dir(self.d, [], 8))["after-V1.txt"]
        self.assertEqual(f["command"], "uv run 測試")
        self.assertEqual(f["exit_code"], 0)
        self.assertEqual(f["flags"], [])

    def test_stale(self):
        allow = self.w("allowed.py", "x")
        old = self.w("after-V1.txt", "$ x\nexit code: 0\n")
        new = self.w("after-V2.txt", "$ x\nexit code: 0\n")
        os.utime(allow, (2000, 2000))
        os.utime(old, (1000, 1000))
        os.utime(new, (3000, 3000))
        r = check_dir(self.d, [str(allow), str(self.d / "nope.py")], 8)
        f = self.by_name(r)
        self.assertIn("stale", f["after-V1.txt"]["flags"])
        self.assertNotIn("stale", f["after-V2.txt"]["flags"])
        self.assertEqual(r["missing_allow"], [str(self.d / "nope.py")])

    def test_missing_after(self):
        self.w("before-V2.txt", "$ x\nexit code: 1\n")
        f = self.by_name(check_dir(self.d, [], 8))["before-V2.txt"]
        self.assertIn("missing_after", f["flags"])

    def test_id_and_skipped(self):
        self.w("after-V1.run1-note.txt", "$ x\nexit code: 0\n")
        self.w("notes.md", "hi")
        r = check_dir(self.d, [], 8)
        self.assertEqual(r["files"][0]["id"], "V1")
        self.assertEqual(r["skipped"], ["notes.md"])

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")

    def test_exit_codes(self):
        self.assertEqual(self.run_script("--dir", str(self.d / "missing")).returncode, 2)
        self.w("after-V1.txt", "$ x\nexit code: 0\n")
        p = self.run_script("--dir", str(self.d))
        self.assertEqual(p.returncode, 0)
        self.assertTrue(p.stdout.strip().splitlines()[-1].startswith("files=1 flagged=0"))
        self.w("after-V2.txt", "no command\n")
        self.assertEqual(self.run_script("--dir", str(self.d)).returncode, 1)

    def test_repo_relative_allow_stale(self):
        with tempfile.TemporaryDirectory() as repo:
            src = Path(repo) / "src"
            src.mkdir()
            allow = src / "a.py"
            allow.write_text("x", encoding="utf-8")
            ev = self.w("after-V1.txt", "$ x\nexit code: 0\n")
            os.utime(allow, (2000, 2000))
            os.utime(ev, (1000, 1000))
            r = check_dir(self.d, ["src/a.py"], 8, repo)
            self.assertIn("stale", self.by_name(r)["after-V1.txt"]["flags"])
            self.assertEqual(r["missing_allow"], [])
            p = self.run_script("--dir", str(self.d), "--repo", repo, "--allow", "src/a.py")
            self.assertEqual(p.returncode, 1)
            self.assertIn("stale", p.stdout.splitlines()[0])

    def test_missing_allow_exit_1(self):
        self.w("after-V1.txt", "$ x\nexit code: 0\n")
        r = check_dir(self.d, ["nope.py"], 8, str(self.d))
        self.assertEqual(r["missing_allow"], ["nope.py"])
        p = self.run_script("--dir", str(self.d), "--repo", str(self.d), "--allow", "nope.py")
        self.assertEqual(p.returncode, 1)
        self.assertIn("missing_allow=nope.py", p.stdout.strip().splitlines()[-1])

    def test_expect_missing_evidence(self):
        self.w("after-V1.txt", "$ x\nexit code: 0\n")
        self.w("before-V2.txt", "$ x\nexit code: 1\n")
        r = check_dir(self.d, [], 8, None, ["V1", "V2"])
        self.assertEqual(r["missing_evidence"], ["V2"])
        p = self.run_script("--dir", str(self.d), "--expect", "V1,V2")
        self.assertEqual(p.returncode, 1)
        self.assertIn("missing_evidence=V2", p.stdout.strip().splitlines()[-1])
        p = self.run_script("--dir", str(self.d), "--expect", "V1,V2", "--json")
        self.assertEqual(json.loads(p.stdout)["missing_evidence"], ["V2"])

    def test_expect_satisfied(self):
        self.w("after-V1.txt", "$ x\nexit code: 0\n")
        self.w("after-V2.run2.txt", "$ x\nexit code: 0\n")
        p = self.run_script("--dir", str(self.d), "--expect", "V1,V2")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip().splitlines()[-1], "files=2 flagged=0 skipped=0")

    def test_command_from_last_segment(self):
        self.w("after-V1.txt", "$ required-test\nexit code: 0\nok\n$ unrelated\nexit code: 0\n")
        f = self.by_name(check_dir(self.d, [], 8))["after-V1.txt"]
        self.assertEqual(f["command"], "unrelated")
        p = self.run_script("--dir", str(self.d))
        self.assertIn("  cmd: unrelated", p.stdout.splitlines())

    def test_final_nonzero_after_only(self):
        self.w("after-V1.txt", "$ x\nexit code: 0\n$ x\nexit code: 1\n")
        self.w("before-V1.txt", "$ x\nexit code: 1\n")
        f = self.by_name(check_dir(self.d, [], 8))
        self.assertIn("final_nonzero", f["after-V1.txt"]["flags"])
        self.assertEqual(f["before-V1.txt"]["flags"], [])

    def test_decode_errors(self):
        (self.d / "after-V1.txt").write_bytes("$ x\nexit code: 0\n中文輸出\n".encode("cp950"))
        f = self.by_name(check_dir(self.d, [], 8))["after-V1.txt"]
        self.assertEqual(f["exit_code"], 0)
        self.assertEqual(f["flags"], ["decode_errors"])


if __name__ == "__main__":
    unittest.main()
