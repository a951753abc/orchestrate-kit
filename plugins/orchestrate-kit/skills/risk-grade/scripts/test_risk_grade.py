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

    # 6b. 點開頭路徑保留開頭的點，只去掉 ./ 前綴
    def test_dot_prefixed_paths(self) -> None:
        out = self.signals(".github/workflows/ci.yml", "./.gitlab-ci.yml", ".env.example",
                           ".claude/risk-policy.yaml", policy=False)
        self.assertEqual(out["gate_hits"], {
            "infra_ci": [".github/workflows/ci.yml", ".gitlab-ci.yml"],
            "secrets": [".env.example"],
            "approval_governance": [".claude/risk-policy.yaml"],
        })

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

    def commit_then_change(self, path: str) -> None:
        """建立 git repo、提交 path 的初版後再改它。"""
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("a = 1\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")
        target.write_text("a = 1\nb = 2\n", encoding="utf-8")

    def ledger_path(self) -> Path:
        """repo 之外的暫存 ledger 路徑（放在 repo 內會變成 untracked 變更）。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name) / "sub" / "ledger.jsonl"

    def record(self, ledger: Path, *extra: str) -> subprocess.CompletedProcess:
        return run(SIGNALS, "--repo", str(self.repo), "--git", "--record", "--source", "t", "--ledger", str(ledger), *extra, cwd=self.repo)

    def ledger_rows(self, ledger: Path) -> list[dict]:
        return [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 9a. --record：verdict low 時記一筆 safe 層並輸出 ledger_id；沒帶 --record 時輸出沒有 ledger_id 鍵
    def test_record_low(self) -> None:
        self.commit_then_change("docs/a.md")
        ledger = self.ledger_path()
        plain = json.loads(run(SIGNALS, "--repo", str(self.repo), "--git", cwd=self.repo).stdout)
        self.assertNotIn("ledger_id", plain)
        proc = self.record(ledger)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["verdict"], "low")
        rows = self.ledger_rows(ledger)
        self.assertEqual(len(rows), 1)
        self.assertEqual(out["ledger_id"], rows[0]["id"])
        self.assertTrue(rows[0]["id"].startswith("rg-"))
        self.assertEqual(
            {k: rows[0][k] for k in ("type", "repo", "grade", "layer", "gates", "reason", "source", "files_count")},
            {"type": "grade", "repo": str(self.repo), "grade": "low", "layer": "safe", "gates": [],
             "reason": "全部 safe-change", "source": "t", "files_count": 1},
        )

    # 9b. --record：verdict high 時記一筆 gate 層，gates 與理由帶命中的 gate 名
    def test_record_high(self) -> None:
        self.commit_then_change("src/auth/login.py")
        ledger = self.ledger_path()
        proc = self.record(ledger)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["verdict"], "high")
        rows = self.ledger_rows(ledger)
        self.assertEqual(len(rows), 1)
        self.assertEqual(out["ledger_id"], rows[0]["id"])
        self.assertEqual((rows[0]["grade"], rows[0]["layer"], rows[0]["gates"]), ("high", "gate", ["auth"]))
        self.assertEqual(rows[0]["reason"], "命中 gate：auth")

    # 9c. --record：verdict judgement 時不記 ledger，ledger_id 為 null
    def test_record_judgement_not_recorded(self) -> None:
        self.commit_then_change("src/x.py")
        ledger = self.ledger_path()
        proc = self.record(ledger)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["verdict"], "judgement")
        self.assertIsNone(out["ledger_id"])
        self.assertFalse(ledger.exists())

    # 9d. --record 只能與 --git 併用：與 --files 併用 exit 2 且不記 ledger
    def test_record_requires_git(self) -> None:
        ledger = self.ledger_path()
        proc = run(SIGNALS, "--repo", str(self.repo), "--files", "docs/a.md", "--record", "--ledger", str(ledger), cwd=self.repo)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(ledger.exists())

    # 9e. --record：ledger 寫不進去時 exit 2，不輸出 JSON
    def test_record_ledger_failure(self) -> None:
        self.commit_then_change("docs/a.md")
        ledger = self.ledger_path()
        ledger.parent.write_text("x", encoding="utf-8")  # 上層是檔案，ledger 無法建立
        proc = self.record(ledger)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertIn("ledger error", proc.stderr)


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

    def record(self, grade: str = "high") -> str:
        proc = self.ledger_cmd("record", "--repo", str(self.repo), "--grade", grade, "--layer", "gate", "--reason", "r")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def last_row(self) -> dict:
        return json.loads(self.ledger.read_text(encoding="utf-8").splitlines()[-1])

    def line_count(self) -> int:
        return len(self.ledger.read_text(encoding="utf-8").splitlines())

    # 13. 結構化 outcome 寫入 dispositions，省略 --findings 時推得 fixed＋deferred
    def test_outcome_dispositions_written(self) -> None:
        rid = self.record()
        proc = self.ledger_cmd("outcome", "--id", rid, "--result", "r", "--fixed", "3", "--deferred", "1",
                               "--rejected", "2", "--category", "logic=2", "--category", "test_gap=1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = self.last_row()
        self.assertEqual(row["dispositions"], {"fixed": 3, "deferred": 1, "rejected": 2, "categories": {"logic": 2, "test_gap": 1}})
        self.assertEqual(row["findings"], 4)

    # 14. 只給部分結構化參數：其餘記 0、類別 {}；有給 --findings 時照用
    def test_outcome_partial_dispositions(self) -> None:
        rid = self.record()
        self.assertEqual(self.ledger_cmd("outcome", "--id", rid, "--result", "r", "--deferred", "1", "--findings", "1").returncode, 0)
        row = self.last_row()
        self.assertEqual(row["dispositions"], {"fixed": 0, "deferred": 1, "rejected": 0, "categories": {}})
        self.assertEqual(row["findings"], 1)
        self.assertEqual(self.ledger_cmd("outcome", "--id", rid, "--result", "r", "--fixed", "2").returncode, 0)
        self.assertEqual(self.last_row()["findings"], 2)

    # 15. 沒給結構化參數時不出現 dispositions 鍵
    def test_outcome_legacy_shape(self) -> None:
        rid = self.record()
        self.assertEqual(self.ledger_cmd("outcome", "--id", rid, "--result", "r").returncode, 0)
        self.assertEqual(sorted(self.last_row()), ["at", "findings", "id", "result", "type"])
        self.assertEqual(self.last_row()["findings"], 0)

    # 16. 不合法的結構化參數 exit 2，ledger 行數不變
    def test_outcome_invalid_dispositions(self) -> None:
        rid = self.record()
        before = self.line_count()
        cases = [
            ["--fixed", "2", "--category", "logic=1"],          # 加總不符
            ["--fixed", "1", "--category", "style=1"],          # 未知類別
            ["--category", "logic=1"],                          # 有 category 沒 fixed
            ["--fixed", "-1"],                                  # 負數
            ["--rejected", "-2"],
            ["--fixed", "1", "--category", "logic"],            # 格式錯誤
            ["--fixed", "1", "--category", "logic=x"],
        ]
        for extra in cases:
            proc = self.ledger_cmd("outcome", "--id", rid, "--result", "r", *extra)
            self.assertEqual(proc.returncode, 2, extra)
            self.assertNotEqual(proc.stderr.strip(), "", extra)
            self.assertEqual(self.line_count(), before, extra)

    # 17. 新舊 outcome 混合、同一 id 回填兩次以最後一筆為準
    def test_summary_dispositions_mixed(self) -> None:
        a, b, c, d = self.record("high"), self.record("high"), self.record("low"), self.record("low")
        self.record("low")  # pending
        self.assertEqual(self.ledger_cmd("outcome", "--id", a, "--result", "old", "--findings", "1").returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", b, "--result", "first", "--fixed", "5", "--category", "doc=5").returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", b, "--result", "last", "--rejected", "2").returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", c, "--result", "s", "--fixed", "2", "--deferred", "1",
                                         "--category", "logic=1", "--category", "security_data=1").returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", d, "--result", "s", "--fixed", "1", "--rejected", "1",
                                         "--category", "logic=1").returncode, 0)
        proc = self.ledger_cmd("summary", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rep = json.loads(proc.stdout)
        self.assertEqual(rep["dispositions"], {"structured": 3, "legacy": 1, "merged": 0, "fixed": 3, "deferred": 1, "rejected": 3,
                                               "categories": {"logic": 2, "security_data": 1}})
        self.assertEqual(rep["counts"], {"high_with_findings": 1, "high_no_findings": 1, "low_with_findings": 2, "low_no_findings": 0, "pending": 1})
        self.assertEqual(rep["over_escalation_candidates"][0]["id"], b)
        text = self.ledger_cmd("summary")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("fixed=3 deferred=1 rejected=3", text.stdout)

    def record_in(self, repo: Path, grade: str) -> str:
        proc = self.ledger_cmd("record", "--repo", str(repo), "--grade", grade, "--layer", "gate", "--reason", "r")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def summary_json(self, *extra: str) -> dict:
        proc = self.ledger_cmd("summary", "--json", *extra)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    # 18. --merged-into 寫入列的鍵與值
    def test_outcome_merged_row(self) -> None:
        host, m = self.record(), self.record()
        proc = self.ledger_cmd("outcome", "--id", m, "--result", "merged review", "--merged-into", host)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = self.last_row()
        self.assertEqual(sorted(row), ["at", "findings", "id", "merged_into", "result", "type"])
        self.assertEqual((row["type"], row["id"], row["result"], row["findings"], row["merged_into"]),
                         ("outcome", m, "merged review", 0, host))

    # 19. 目標有 findings → merged 中高筆算 high_with_findings、不在過度升級候選；merged 計數不重複加總
    def test_summary_merged_target_with_findings(self) -> None:
        host, m1, m2 = self.record(), self.record(), self.record()
        self.assertEqual(self.ledger_cmd("outcome", "--id", host, "--result", "r", "--fixed", "2", "--deferred", "1",
                                         "--rejected", "1", "--category", "logic=2").returncode, 0)
        for m in (m1, m2):
            self.assertEqual(self.ledger_cmd("outcome", "--id", m, "--result", "r", "--merged-into", host).returncode, 0)
        rep = self.summary_json()
        self.assertEqual(rep["counts"], {"high_with_findings": 3, "high_no_findings": 0, "low_with_findings": 0, "low_no_findings": 0, "pending": 0})
        self.assertEqual(rep["over_escalation_candidates"], [])
        self.assertEqual(rep["dispositions"], {"structured": 1, "legacy": 0, "merged": 2, "fixed": 2, "deferred": 1, "rejected": 1,
                                               "categories": {"logic": 2}})
        text = self.ledger_cmd("summary")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn("合併 2 筆", text.stdout)

    # 20. 目標 findings 為 0 → high_no_findings；目標沒有 outcome、目標也是 merged → pending
    def test_summary_merged_target_states(self) -> None:
        zero_host, m_zero = self.record(), self.record()
        empty_host, m_empty = self.record(), self.record()
        chain_host, m_chain = self.record(), self.record()
        self.assertEqual(self.ledger_cmd("outcome", "--id", zero_host, "--result", "r", "--findings", "0").returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", m_zero, "--result", "r", "--merged-into", zero_host).returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", m_empty, "--result", "r", "--merged-into", empty_host).returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", zero_host, "--result", "r2", "--findings", "0").returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", chain_host, "--result", "r", "--merged-into", zero_host).returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", m_chain, "--result", "r", "--merged-into", chain_host).returncode, 0)
        rep = self.summary_json()
        self.assertEqual(rep["counts"], {"high_with_findings": 0, "high_no_findings": 3, "low_with_findings": 0, "low_no_findings": 0, "pending": 3})
        self.assertEqual(sorted(c["id"] for c in rep["over_escalation_candidates"]), sorted([zero_host, m_zero, chain_host]))
        self.assertEqual(rep["dispositions"]["merged"], 4)

    # 21. --repo 過濾掉目標所在 repo 時仍依目標結果分類
    def test_summary_merged_target_other_repo(self) -> None:
        other = self.repo / "other"
        other.mkdir()
        host = self.record_in(other, "high")
        m = self.record_in(self.repo, "high")
        self.assertEqual(self.ledger_cmd("outcome", "--id", host, "--result", "r", "--findings", "3").returncode, 0)
        self.assertEqual(self.ledger_cmd("outcome", "--id", m, "--result", "r", "--merged-into", host).returncode, 0)
        rep = self.summary_json("--repo", str(self.repo))
        self.assertEqual(rep["total"], 1)
        self.assertEqual(rep["counts"], {"high_with_findings": 1, "high_no_findings": 0, "low_with_findings": 0, "low_no_findings": 0, "pending": 0})
        self.assertEqual(rep["dispositions"], {"structured": 0, "legacy": 0, "merged": 1, "fixed": 0, "deferred": 0, "rejected": 0, "categories": {}})

    # 22. --merged-into 不合法：併用 exit 2、指向自己 exit 2、目標不存在 exit 1；ledger 行數不變
    def test_outcome_merged_invalid(self) -> None:
        host, m = self.record(), self.record()
        before = self.line_count()
        cases = [
            (["--merged-into", host, "--fixed", "1"], 2),
            (["--merged-into", host, "--findings", "0"], 2),
            (["--merged-into", host, "--deferred", "1"], 2),
            (["--merged-into", host, "--rejected", "1"], 2),
            (["--merged-into", host, "--fixed", "1", "--category", "logic=1"], 2),
            (["--merged-into", m], 2),
            (["--merged-into", "rg-none"], 1),
        ]
        for extra, code in cases:
            proc = self.ledger_cmd("outcome", "--id", m, "--result", "r", *extra)
            self.assertEqual(proc.returncode, code, extra)
            self.assertNotEqual(proc.stderr.strip(), "", extra)
            self.assertEqual(self.line_count(), before, extra)


if __name__ == "__main__":
    unittest.main()
