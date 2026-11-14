# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""run_evidence.py 的 unittest。用法：uv run test_run_evidence.py -v

以 subprocess 執行 run_evidence.py，只對證據檔內容、終端輸出、exit code 與 check_evidence.check_dir() 的結果斷言。
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_evidence import check_dir  # noqa: E402

SCRIPT = HERE / "run_evidence.py"
PY = sys.executable


def acp() -> str | None:
    if os.name != "nt":
        return None
    import ctypes
    return f"cp{ctypes.windll.kernel32.GetACP()}"


class RunEvidenceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_ev(self, *args, when="after", vid="V1", env=None):
        head = ["--dir", str(self.d), "--when", when] + (["--id", vid] if vid else [])
        return subprocess.run([PY, str(SCRIPT), *head, *args], capture_output=True, text=True, encoding="utf-8", env=env)

    def lines(self, name):
        return (self.d / name).read_bytes().decode("utf-8").split("\n")

    def by_name(self):
        return {f["name"]: f for f in check_dir(self.d, [], 8)["files"]}

    def test_01_success_format(self):
        p = self.run_ev("--", PY, "-c", "print('hello')")
        self.assertEqual(p.returncode, 0, p.stderr)
        ln = self.lines("after-V1.txt")
        self.assertTrue(ln[0].startswith("$ ") and ln[0].endswith(" -c 'print('\"'\"'hello'\"'\"')'"), ln[0])
        self.assertEqual(shlex.split(ln[0][2:]), [PY, "-c", "print('hello')"])
        self.assertEqual(ln[1], "exit code: 0")
        self.assertRegex(ln[2], r"^elapsed: \d+\.\ds$")
        self.assertEqual(ln[3], "hello")
        f = self.by_name()["after-V1.txt"]
        self.assertEqual(f["flags"], [])
        self.assertEqual(f["exit_code"], 0)
        self.assertEqual(shlex.split(f["command"]), [PY, "-c", "print('hello')"])

    def test_02_failure_exit_3(self):
        code = "import sys; sys.exit(3)"
        p = self.run_ev("--", PY, "-c", code, when="after", vid="V2")
        self.assertEqual(p.returncode, 3)
        p = self.run_ev("--", PY, "-c", code, when="before", vid="V3")
        self.assertEqual(p.returncode, 3)
        f = self.by_name()
        self.assertEqual(f["after-V2.txt"]["flags"], ["final_nonzero"])
        self.assertEqual(f["before-V3.txt"]["exit_code"], 3)
        self.assertNotIn("final_nonzero", f["before-V3.txt"]["flags"])

    def test_03_two_runs_append(self):
        self.run_ev("--", PY, "-c", "print('one')")
        first = (self.d / "after-V1.txt").read_bytes()
        p = self.run_ev("--", PY, "-c", "import sys; print('two'); sys.exit(4)")
        self.assertEqual(p.returncode, 4)
        both = (self.d / "after-V1.txt").read_bytes()
        self.assertTrue(both.startswith(first))
        self.assertTrue(both[len(first):].startswith(b"\n$ "))
        f = self.by_name()["after-V1.txt"]
        self.assertEqual(f["runs"], 2)
        self.assertEqual(f["exit_codes"], [0, 4])

    def test_04_tail(self):
        p = self.run_ev("--tail", "5", "--", PY, "-c", "for i in range(1, 101): print(f'line{i}')")
        self.assertEqual(p.returncode, 0)
        out = p.stdout.splitlines()
        self.assertIn("line100", out)
        self.assertIn("line96", out)
        self.assertNotIn("line95", out)
        self.assertNotIn("line1", out)
        self.assertTrue(out[-1].startswith("[run_evidence] exit code: 0 | elapsed: "))
        self.assertEqual(len(out), 6)
        ln = self.lines("after-V1.txt")
        self.assertEqual(ln[3], "line1")
        self.assertEqual(ln[102], "line100")
        self.assertEqual(ln[3:103], [f"line{i}" for i in range(1, 101)])

    def test_05_fake_headers_escaped(self):
        code = "import sys; print('exit code: 0'); print('rc=0'); print('$ fake'); sys.exit(5)"
        p = self.run_ev("--", PY, "-c", code)
        self.assertEqual(p.returncode, 5)
        f = self.by_name()["after-V1.txt"]
        self.assertEqual(f["exit_code"], 5)
        self.assertEqual(f["runs"], 1)
        self.assertEqual(shlex.split(f["command"]), [PY, "-c", code])
        self.assertEqual(self.lines("after-V1.txt")[3:6], [" exit code: 0", " rc=0", " $ fake"])
        self.assertIn("exit code: 0", p.stdout.splitlines())

    def test_06_non_utf8_bytes(self):
        code = "import sys; sys.stdout.buffer.write(bytes([0xA4, 0xA4, 0x0A]))"
        p = self.run_ev("--", PY, "-c", code)
        self.assertEqual(p.returncode, 0)
        text = (self.d / "after-V1.txt").read_bytes().decode("utf-8")  # 不是合法 UTF-8 會丟例外
        if acp() == "cp950":
            self.assertEqual(text.split("\n")[3], "中")
            self.assertNotIn("�", text)
            self.assertEqual(self.by_name()["after-V1.txt"]["flags"], [])
        else:
            print(f"\n[test_06] 略過「中」斷言：系統 ANSI code page 為 {acp()}，不是 cp950", file=sys.stderr)

    def test_07_ansi_stripped(self):
        p = self.run_ev("--", PY, "-c", "e = chr(27); print(e + '[31mred' + e + '[0m done')")
        self.assertEqual(p.returncode, 0)
        text = (self.d / "after-V1.txt").read_text(encoding="utf-8")
        self.assertNotIn("\x1b", text)
        self.assertEqual(text.split("\n")[3], "red done")
        self.assertNotIn("\x1b", p.stdout)
        self.assertIn("red done", p.stdout.splitlines())

    def test_08_when_op(self):
        p = self.run_ev("--", PY, "-c", "print('op')", when="op", vid=None)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(sorted(x.name for x in self.d.iterdir()), ["after-op.txt"])
        f = self.by_name()["after-op.txt"]
        self.assertEqual(f["flags"], [])
        self.assertEqual(f["exit_code"], 0)

    def test_09_missing_executable(self):
        ev = self.d / "ev"
        p = subprocess.run(
            [PY, str(SCRIPT), "--dir", str(ev), "--id", "V1", "--when", "after", "--", "no-such-exe-run-evidence-xyz"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 2)
        self.assertNotEqual(p.stderr.strip(), "")
        self.assertFalse(ev.exists())

    def test_10_sh(self):
        p = self.run_ev("--sh", "echo a | tr a b")
        if p.returncode == 2 and "找不到 bash" in p.stderr:
            self.skipTest(f"找不到 bash：{p.stderr.strip()}")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.splitlines()[0], "b")
        ln = self.lines("after-V1.txt")
        self.assertEqual(ln[0], "$ echo a | tr a b")
        self.assertEqual(ln[3], "b")

    def test_11_pwsh(self):
        if shutil.which("pwsh") is None:
            self.skipTest("找不到 pwsh")
        p = self.run_ev("--pwsh", "Write-Output 'pwsh-ok'")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("pwsh-ok", p.stdout.splitlines())
        ln = self.lines("after-V1.txt")
        self.assertEqual(ln[0], "$ Write-Output 'pwsh-ok'")
        self.assertEqual(ln[3], "pwsh-ok")

    def test_12_elapsed(self):
        self.run_ev("--", PY, "-c", "import time; time.sleep(0.3)")
        ln = self.lines("after-V1.txt")
        m = re.fullmatch(r"elapsed: (.+)s", ln[2])
        self.assertIsNotNone(m)
        self.assertGreaterEqual(float(m.group(1)), 0.2)

    def test_13_multiline_command_header_is_one_line(self):
        p = self.run_ev("--sh", "echo first\nrc=0; echo second; exit 4")
        if p.returncode == 2 and "找不到 bash" in p.stderr:
            self.skipTest(f"找不到 bash：{p.stderr.strip()}")
        self.assertEqual(p.returncode, 4, p.stderr)
        ln = self.lines("after-V1.txt")
        self.assertEqual(ln[0], "$ echo first\\nrc=0; echo second; exit 4")
        self.assertEqual(ln[1], "exit code: 4")
        self.assertEqual(ln[3:5], ["first", "second"])
        f = check_dir(self.d)["files"][0]
        self.assertEqual((f["exit_code"], f["runs"]), (4, 1))

    def test_14_argv_header_keeps_arg_boundaries(self):
        p = self.run_ev("--", PY, "-c", "print('hello world')")
        self.assertEqual(p.returncode, 0, p.stderr)
        ln = self.lines("after-V1.txt")
        self.assertTrue(ln[0].endswith(" -c 'print('\"'\"'hello world'\"'\"')'"), ln[0])
        self.assertEqual(shlex.split(ln[0][2:]), [PY, "-c", "print('hello world')"])
        self.assertEqual(ln[3], "hello world")

    def test_15_batch_file_args_not_shell_syntax(self):
        if os.name != "nt":
            self.skipTest("F6 只發生在 Windows 的 .cmd／.bat（參數經 cmd.exe 解析）；此平台不執行")
        fx = self.d / "fx"
        fx.mkdir()
        (fx / "echoargs.cmd").write_bytes(b"@echo off\r\necho ARG1=[%1] ARG2=[%2]\r\n")
        env = dict(os.environ, PATH=str(fx) + os.pathsep + os.environ.get("PATH", ""))
        cases = [
            ("foo|bar", {"ARG1=[foo|bar] ARG2=[plain]", 'ARG1=["foo|bar"] ARG2=[plain]'}),
            ("a%PATH%b", {"ARG1=[a%PATH%b] ARG2=[plain]", 'ARG1=["a%PATH%b"] ARG2=[plain]'}),
            ('x"&echo INJECTED&"y', set()),  # 沒有可接受的原樣輸出，只能拒絕
        ]
        for i, (arg, ok) in enumerate(cases):
            with self.subTest(arg=arg):
                vid = f"F6{i}"
                p = self.run_ev("--", "echoargs", arg, "plain", vid=vid, env=env)
                out = p.stdout + p.stderr
                self.assertNotIn("不是內部或外部命令", out)
                self.assertNotIn("is not recognized", out)
                self.assertFalse(any(x.strip() == "INJECTED" for x in p.stdout.splitlines()), p.stdout)
                if ok and p.returncode == 0:
                    self.assertTrue(set(p.stdout.splitlines()) & ok, p.stdout)
                else:
                    self.assertEqual(p.returncode, 2, out)
                    self.assertIn("--sh", p.stderr)
                    self.assertIn("--pwsh", p.stderr)
                    self.assertFalse((self.d / f"after-{vid}.txt").exists())

    def test_16_relative_exe_resolved_against_cwd(self):
        fx = self.d / "fx"
        tools = fx / "tools"
        tools.mkdir(parents=True)
        if os.name == "nt":
            (tools / "hello.cmd").write_bytes(b"@echo cwd-ok\r\n")
        else:
            h = tools / "hello"
            h.write_bytes(b"#!/bin/sh\necho cwd-ok\n")
            h.chmod(0o755)
        p = self.run_ev("--cwd", str(fx), "--", os.path.join(".", "tools", "hello"))
        self.assertNotIn("找不到執行檔", p.stderr)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("cwd-ok", p.stdout.splitlines())
        self.assertEqual(self.lines("after-V1.txt")[3], "cwd-ok")


if __name__ == "__main__":
    unittest.main()
