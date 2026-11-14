# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""compact_reminder_hook.py 的 unittest。用法：uv run test_compact_reminder_hook.py -v"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "compact_reminder_hook.py"

SKILL_USE = {"type": "assistant", "message": {"role": "assistant", "content": [
    {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "orchestrate-v2"}}]}}
KIT_USE = {"type": "assistant", "message": {"role": "assistant", "content": [
    {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "orchestrate-kit:orchestrate-v2"}}]}}
RISK_USE = {"type": "assistant", "message": {"role": "assistant", "content": [
    {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "risk-grade"}}]}}
SLASH_STR = {"type": "user", "message": {"role": "user", "content":
    "<command-message>orchestrate-v2</command-message>\n<command-name>/orchestrate-v2</command-name>"}}
SLASH_LIST = {"type": "user", "message": {"role": "user", "content": [
    {"type": "text", "text": "<command-name>/orchestrate-v2</command-name>\n<command-args>x</command-args>"}]}}
SLASH_PLUGIN_STR = {"type": "user", "message": {"role": "user", "content":
    "<command-message>orchestrate-kit:orchestrate-v2</command-message>\n"
    "<command-name>/orchestrate-kit:orchestrate-v2</command-name>"}}
SLASH_PLUGIN_LIST = {"type": "user", "message": {"role": "user", "content": [
    {"type": "text", "text": "<command-name>/orchestrate-kit:orchestrate-v2</command-name>\n<command-args>x</command-args>"}]}}
SLASH_PLUGIN_OTHER = {"type": "user", "message": {"role": "user", "content":
    "<command-name>/orchestrate-kit:risk-grade</command-name>\n<command-args>orchestrate-v2</command-args>"}}
PLAIN_USER = {"type": "user", "message": {"role": "user", "content": "請用 orchestrate-v2 處理這個"}}
PLAIN_ASSISTANT = {"type": "assistant", "message": {"role": "assistant", "content": [
    {"type": "text", "text": "我會照 orchestrate-v2 的流程走"}]}}
OTHER = {"type": "user", "message": {"role": "user", "content": "hello"}}


class CompactReminderHookTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def transcript(self, *records, raw_lines=()):
        p = self.d / "t.jsonl"
        lines = list(raw_lines) + [json.dumps(r, ensure_ascii=False) for r in records]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(p)

    def run_hook(self, stdin: bytes | str):
        if isinstance(stdin, str):
            stdin = stdin.encode("utf-8")
        r = subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, timeout=30)
        return r.returncode, r.stdout.decode("utf-8")

    def payload(self, source, path):
        p = {"session_id": "s", "cwd": str(self.d), "hook_event_name": "SessionStart", "source": source}
        if path is not None:
            p["transcript_path"] = path
        return json.dumps(p)

    def assert_reminder(self, source, path):
        code, out = self.run_hook(self.payload(source, path))
        self.assertEqual(code, 0)
        data = json.loads(out)
        hso = data["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SessionStart")
        self.assertIn("委派門檻與路由", hso["additionalContext"])
        self.assertIn("不依壓縮摘要裡的印象執行", hso["additionalContext"])

    def assert_silent(self, stdin):
        code, out = self.run_hook(stdin)
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_compact_skill_tool_use(self):
        self.assert_reminder("compact", self.transcript(OTHER, SKILL_USE, OTHER))

    def test_compact_slash_string(self):
        self.assert_reminder("compact", self.transcript(SLASH_STR))

    def test_compact_slash_block_list(self):
        self.assert_reminder("compact", self.transcript(SLASH_LIST))

    def test_compact_plugin_namespace(self):
        self.assert_reminder("compact", self.transcript(KIT_USE))

    def test_compact_plugin_prefixed_slash_string(self):
        self.assert_reminder("compact", self.transcript(SLASH_PLUGIN_STR))

    def test_compact_plugin_prefixed_slash_block_list(self):
        self.assert_reminder("compact", self.transcript(SLASH_PLUGIN_LIST))

    def test_compact_plugin_prefixed_other_command_silent(self):
        self.assert_silent(self.payload("compact", self.transcript(SLASH_PLUGIN_OTHER)))

    def test_other_sources_silent(self):
        path = self.transcript(SKILL_USE, SLASH_STR)
        for source in ("startup", "resume", "clear"):
            with self.subTest(source=source):
                self.assert_silent(self.payload(source, path))

    def test_compact_no_load(self):
        self.assert_silent(self.payload("compact", self.transcript(OTHER)))

    def test_compact_plain_mention_silent(self):
        self.assert_silent(self.payload("compact", self.transcript(PLAIN_USER, PLAIN_ASSISTANT)))

    def test_compact_other_skill_silent(self):
        self.assert_silent(self.payload("compact", self.transcript(RISK_USE, PLAIN_USER)))

    def test_missing_transcript_file(self):
        self.assert_silent(self.payload("compact", str(self.d / "nope.jsonl")))

    def test_missing_field(self):
        self.assert_silent(self.payload("compact", None))

    def test_stdin_not_json(self):
        self.assert_silent("not json {")

    def test_broken_json_line_silent(self):
        self.assert_silent(self.payload("compact", self.transcript(OTHER, raw_lines=['{"orchestrate-v2": broken'])))

    def test_broken_json_line_then_load(self):
        self.assert_reminder("compact", self.transcript(SKILL_USE, raw_lines=['{"orchestrate-v2": broken']))


if __name__ == "__main__":
    unittest.main(verbosity=2)
