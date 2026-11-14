# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""audit_agent_tools.py 的 unittest。用法：uv run test_audit_agent_tools.py -v"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_agent_tools import audit  # noqa: E402

SCRIPT = HERE / "audit_agent_tools.py"
RUN = "C:/tmp/out/walk/host-01"
RUN_CODE = "mcp__playwright__browser_run_code_unsafe"


def shot_code(step: str, action: str = "await page.mouse.click(10, 20);") -> str:
    return f"async (page) => {{ {action} await page.screenshot({{ path: '{RUN}/shots/{step}.png' }}); return page.url(); }}"


class AuditTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "agent.jsonl"
        self.n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, uses, repeat_last=False):
        lines = []
        for name, inp in uses:
            self.n += 1
            lines.append(json.dumps({"message": {"content": [
                {"type": "tool_use", "id": f"t{self.n}", "name": name, "input": inp}]}}, ensure_ascii=False))
        if repeat_last:
            lines.append(lines[-1])
        self.path.write_text("\n".join(lines) + "\nnot json\n", encoding="utf-8")

    def kinds(self, result):
        return [(v["kind"], v["step"]) for v in result["violations"]]

    def test_clean_run_passes(self):
        self.write([
            ("ToolSearch", {"query": f"select:{RUN_CODE},mcp__playwright__browser_handle_dialog"}),
            (RUN_CODE, {"code": shot_code("001")}),
            ("Read", {"file_path": "C:\\tmp\\out\\walk\\host-01\\shots\\001.png"}),
            (RUN_CODE, {"code": shot_code("002", "await page.keyboard.press('Control+A');")}),
            ("Write", {"file_path": f"{RUN}/log/steps-001-010.md"}),
            ("mcp__playwright__browser_file_upload", {"paths": [f"{RUN}/album/photo.jpg"]}),
        ], repeat_last=True)
        result = audit(self.path, RUN)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["steps"], {"count": 2, "first": "001", "last": "002"})
        self.assertEqual(result["tool_counts"]["mcp__playwright__browser_file_upload"], 1)

    def test_each_violation_kind(self):
        self.write([
            (RUN_CODE, {"code": shot_code("003")}),
            ("Bash", {"command": "ls"}),
            ("Read", {"file_path": f"{RUN}/log/steps-001-010.md"}),
            ("Read", {"file_path": "D:/project/app/Models/User.php"}),
            ("Write", {"file_path": f"{RUN}/shots/notes.md"}),
            (RUN_CODE, {"code": shot_code("004", "await page.locator('#a').click();")}),
            (RUN_CODE, {"code": shot_code("005"), "filename": "x.js"}),
            (RUN_CODE, {"code": shot_code("006", "await page.goto('http://other.test/admin');")}),
            ("mcp__playwright__browser_file_upload", {"paths": ["C:/Users/me/secret.pdf"]}),
            ("ToolSearch", {"query": "select:mcp__playwright__browser_snapshot"}),
            ("ToolSearch", {"query": "playwright click"}),
        ])
        result = audit(self.path, RUN, allow_goto=["http://site.test/"])
        self.assertEqual(self.kinds(result), [
            ("tool", "003+"), ("read", "003+"), ("read", "003+"), ("write", "003+"),
            ("code", "004"), ("code", "005"), ("goto", "006"),
            ("upload", "006+"), ("toolsearch", "006+"), ("toolsearch", "006+"),
        ])
        self.assertFalse(result["ok"])

    def test_goto_allowed_prefix_and_extra_tool_and_upload_dir(self):
        self.write([
            (RUN_CODE, {"code": shot_code("001", "await page.goto('http://site.test/');")}),
            ("mcp__playwright__browser_file_upload", {"paths": ["C:/tmp/out/walk/shared/cert.png"]}),
            ("mcp__playwright__browser_press_key", {"key": "Enter"}),
        ])
        result = audit(self.path, RUN, allow_goto=["http://site.test/"],
                       upload_dirs=["C:/tmp/out/walk/shared"], extra_tools=["mcp__playwright__browser_press_key"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["goto_urls"], {"http://site.test/": 1})

    def test_clipboard_keys_fail_without_other_violations(self):
        self.write([
            (RUN_CODE, {"code": shot_code("053", "await page.keyboard.press('Control+V');")}),
            (RUN_CODE, {"code": shot_code("054", "await page.keyboard.press('Meta+c');")}),
        ])
        result = audit(self.path, RUN)
        self.assertEqual(result["violations"], [])
        self.assertEqual([c["step"] for c in result["clipboard"]], ["053", "054"])
        self.assertFalse(result["ok"])

    def test_cli_exit_codes_and_no_code_leak(self):
        self.write([(RUN_CODE, {"code": shot_code("001", "const secret = 'do-not-print'; await page.evaluate(() => 1);")})])
        proc = subprocess.run([sys.executable, str(SCRIPT), "--transcript", str(self.path), "--run-dir", RUN],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("forbidden: evaluate", proc.stdout)
        self.assertNotIn("do-not-print", proc.stdout)
        self.assertTrue(proc.stdout.rstrip().endswith("FAIL"))
        missing = subprocess.run([sys.executable, str(SCRIPT), "--transcript", str(self.path) + ".none", "--run-dir", RUN],
                                 capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
