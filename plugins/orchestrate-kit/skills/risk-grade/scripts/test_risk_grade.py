# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pyyaml>=6,<7",
# ]
# ///
"""risk_signals.py 與 risk_ledger.py 的 stdlib unittest。執行：uv run test_risk_grade.py -v"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIGNALS = HERE / "risk_signals.py"
LEDGER = HERE / "risk_ledger.py"

POLICY = """
version: 1
gates:
  - name: auth
    paths: ["**/auth/**"]
    exclude: ["**/*.md"]
  - name: payment
    paths: ["**/pricing/**", "**/refund*"]
safe_changes:
  docs: ["**/*.md", "docs/**"]
  tests: ["tests/**", "**/test_*.py"]
ignore: ["**/__pycache__/**"]
attention_limit_lines: 10
"""


def run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class SignalsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name).resolve()
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude" / "risk-policy.yaml").write_text(POLICY, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def signals(self, *files: str, policy: bool = True) -> dict:
        args = ["--repo", str(self.repo), "--files", *files]
        if not policy:
            (self.repo / ".claude" / "risk-policy.yaml").unlink()
        proc = run(SIGNALS, *args, cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    # 1. gate 命中
    def test_gate_hit(self) -> None:
        out = self.signals("src/auth/login.py", "README.md")
        self.assertEqual(out["mechanical_layer"], "gate")
        self.assertEqual(out["gate_hits"], {"auth": ["src/auth/login.py"]})

    # 2. gate exclude 生效
    def test_gate_exclude(self) -> None:
        out = self.signals("src/auth/README.md")
        self.assertEqual(out["gate_hits"], {})
        self.assertEqual(out["mechanical_layer"], "safe")

    # 3. 全部 safe
    def test_all_safe(self) -> None:
        out = self.signals("docs/a.md", "tests/test_x.py")
        self.assertTrue(out["all_safe"])
        self.assertEqual(out["mechanical_layer"], "safe")

    # 4. 混合 → judgement
    def test_mixed_judgement(self) -> None:
        out = self.signals("docs/a.md", "src/util.py")
        self.assertEqual(out["mechanical_layer"], "judgement")
        self.assertEqual(out["unclassified"], ["src/util.py"])

    # 5. 無檔名目錄的 pattern 匹配根目錄與子目錄
    def test_pattern_without_slash(self) -> None:
        out = self.signals("refund_calc.py", "a/b/refund.ts")
        self.assertEqual(sorted(out["gate_hits"]["payment"]), ["a/b/refund.ts", "refund_calc.py"])

    # 6. 無 policy 用 skill 預設
    def test_default_policy(self) -> None:
        out = self.signals("src/payment/charge.py", policy=False)
        self.assertEqual(out["policy_source"], "skill 預設")
        self.assertIn("payment", out["gate_hits"])

    # 7. --git 取變更並算統計與 formatting-only
    def test_git_mode_and_formatting_only(self) -> None:
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")
        (self.repo / "src" / "a.py").write_text("x  =  1\n\ny = 2\n", encoding="utf-8")
        proc = run(SIGNALS, "--repo", str(self.repo), "--git", cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual([f["path"] for f in out["files"]], ["src/a.py"])
        self.assertTrue(out["diff"]["formatting_only"])
        self.assertEqual(out["mechanical_layer"], "safe")
        self.assertEqual(out["files"][0]["safe"], "formatting")
        (self.repo / "src" / "a.py").write_text("x = 1\n" + "z = 0\n" * 20, encoding="utf-8")
        out = json.loads(run(SIGNALS, "--repo", str(self.repo), "--git", cwd=self.repo).stdout)
        self.assertFalse(out["diff"]["formatting_only"])
        self.assertTrue(out["over_attention_limit"])

    # 7a. --git 遇到非 ASCII 檔名時輸出原檔名並照 policy 分類
    def test_git_mode_non_ascii_path(self) -> None:
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "中文規則.md").write_text("a\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")
        (self.repo / "docs" / "中文規則.md").write_text("a\nb\n", encoding="utf-8")
        proc = run(SIGNALS, "--repo", str(self.repo), "--git", cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual([f["path"] for f in out["files"]], ["docs/中文規則.md"])
        self.assertEqual(out["files"][0]["safe"], "docs")
        self.assertEqual(out["unclassified"], [])

    # 8. --git 在非 git 目錄 exit 2
    def test_git_mode_non_repo(self) -> None:
        proc = run(SIGNALS, "--repo", str(self.repo), "--git", cwd=self.repo)
        self.assertEqual(proc.returncode, 2)

    # 8a. --executor-failed 讓全 safe 的變更也落 gate 層
    def test_executor_failed_is_gate(self) -> None:
        proc = run(SIGNALS, "--repo", str(self.repo), "--files", "docs/a.md", "--executor-failed", cwd=self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["mechanical_layer"], "gate")
        self.assertEqual(out["verdict"], "high")
        self.assertIn("executor_history", out["gate_hits"])
        self.assertFalse(out["all_safe"])
        self.assertEqual(self.signals("docs/a.md")["verdict"], "low")
        self.assertEqual(self.signals("src/x.py")["verdict"], "judgement")

    # 9. ignore 清單命中的檔案不參與分類；全部被忽略時層級為 empty
    def test_ignore_and_empty(self) -> None:
        out = self.signals("__pycache__/a.pyc", "docs/a.md")
        self.assertEqual(out["ignored"], ["__pycache__/a.pyc"])
        self.assertEqual(out["mechanical_layer"], "safe")
        out = self.signals("__pycache__/a.pyc")
        self.assertEqual(out["mechanical_layer"], "empty")
        self.assertFalse(out["all_safe"])


class LedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "sub" / "ledger.jsonl"
        self.repo = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def ledger_cmd(self, *args: str) -> subprocess.CompletedProcess:
        return run(LEDGER, "--ledger", str(self.ledger), *args, cwd=self.repo)

    # 10. record → outcome → summary 四象限
    def test_record_outcome_summary(self) -> None:
        ids = []
        for grade, layer in [("high", "gate"), ("high", "gate"), ("low", "safe"), ("low", "judgement")]:
            proc = self.ledger_cmd("record", "--repo", str(self.repo), "--grade", grade, "--layer", layer, "--gates", "auth", "--reason", "r")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            ids.append(proc.stdout.strip())
        self.assertTrue(all(i.startswith("rg-") for i in ids))
        self.assertEqual(self.ledger_cmd("outcome", "--id", ids[0], "--result", "1 finding", "--findings", "1").returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", ids[1], "--result", "none").returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", ids[3], "--result", "bug found", "--findings", "2").returncode, 0)
        proc = self.ledger_cmd("summary", "--repo", str(self.repo), "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertEqual(rep["counts"], {"high_with_findings": 1, "high_no_findings": 1, "low_with_findings": 1, "low_no_findings": 0, "pending": 1})
        self.assertEqual(rep["over_escalation_candidates"][0]["id"], ids[1])
        self.assertEqual(rep["missed_signal_candidates"][0]["id"], ids[3])

    # 11. 中文等級值正規化
    def test_grade_alias(self) -> None:
        proc = self.ledger_cmd("record", "--repo", str(self.repo), "--grade", "中高", "--layer", "gate", "--reason", "r")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = json.loads(self.ledger.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(row["grade"], "high")
        self.assertEqual(row["gates"], [])

    # 12. outcome 未知 id exit 1
    def test_outcome_unknown_id(self) -> None:
        proc = self.ledger_cmd("outcome", "--id", "rg-none", "--result", "x")
        self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
