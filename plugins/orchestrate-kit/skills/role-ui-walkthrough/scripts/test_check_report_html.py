# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""check_report_html.py 的 unittest。用法：uv run test_check_report_html.py -v"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_report_html import check  # noqa: E402

SCRIPT = HERE / "check_report_html.py"
IMG = '<img src="{src}" width="390" height="844" alt="畫面" loading="lazy">'
PAGE = '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>手冊</title></head><body>{body}</body></html>'


class CheckReportHtmlTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        (self.d / "manual.assets").mkdir()
        (self.d / "manual.assets" / "host-01-003.png").write_bytes(b"png")
        (self.d / "report.html").write_text(PAGE.format(body='<article id="D1" data-id="ghost"></article>'), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def page(self, body, name="manual.html", wrap=True):
        p = self.d / name
        p.write_text(PAGE.format(body=body) if wrap else body, encoding="utf-8")
        return p

    def test_valid_page_passes(self):
        body = ('<section id="step-1">' + IMG.format(src="manual.assets/host-01-003.png")
                + '<a href="#step-1">回到步驟</a><a href="report.html#D1">D1</a>'
                + '<a href="http://site.test/host">系統</a></section>')
        summary, problems = check(self.page(body), ids=["step-1"], require_hrefs=["report.html#D1"], min_img=1)
        self.assertEqual(problems, [])
        self.assertIn("img=1", summary)

    def test_missing_targets_and_anchors(self):
        body = ('<img src="manual.assets/none.png" width="1" height="1" alt="" loading="lazy">'
                '<a href="#nowhere">x</a><a href="report.html#Z9">x</a><a href="report.html#ghost">x</a>'
                '<a href="gone.html">x</a>')
        _, problems = check(self.page(body), ids=["step-2"], require_hrefs=["report.html#D1"], min_img=2)
        self.assertEqual(problems, [
            "圖片不存在：manual.assets/none.png",
            "頁內連結沒有對應的 id：#nowhere",
            "連結的錨點在目標檔不存在：report.html#Z9",
            "連結的錨點在目標檔不存在：report.html#ghost",
            "連結目標不存在：gone.html",
            "缺少 id：step-2",
            "缺少連結：report.html#D1",
            "圖片數量 1 少於要求的 2",
        ])

    def test_external_resources(self):
        body = ('<script src="https://cdn.test/a.js"></script><link rel="stylesheet" href="a.css">'
                '<style>@import "b.css"; .x{background:url(https://cdn.test/b.png)}</style>'
                '<img src="//cdn.test/c.png" width="1" height="1" alt="" loading="lazy">')
        _, problems = check(self.page(body))
        self.assertEqual(problems, [
            "外部圖片：//cdn.test/c.png",
            "有外部 script（<script src>）",
            "有外部樣式表（<link rel=stylesheet>）",
            "有 @import",
            "CSS 內有外部 url()",
        ])

    def test_img_attrs_and_switch(self):
        body = '<img src="manual.assets/host-01-003.png" data-width="9" alt="畫面">'
        page = self.page(body)
        _, problems = check(page)
        self.assertEqual(problems, ["圖片缺少屬性 width,height,loading：manual.assets/host-01-003.png"])
        self.assertEqual(check(page, img_attrs=False)[1], [])

    def test_forbid_reference_and_file(self):
        (self.d / "manual.assets" / "host-01-055.png").write_bytes(b"png")
        body = IMG.format(src="manual.assets/host-01-055.png") + IMG.format(src="manual.assets/host-01-003.png")
        _, problems = check(self.page(body), forbid=["host-01-055"])
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("引用了禁用的檔案（host-01-055）"))
        self.assertTrue(problems[1].startswith("素材目錄內有禁用的檔案（host-01-055）"))
        self.assertEqual(check(self.page(IMG.format(src="manual.assets/host-01-003.png")), forbid=["host-01-099"])[1], [])

    def test_fragment_and_asset_base(self):
        sub = self.d / "parts"
        sub.mkdir()
        frag = sub / "cards.html"
        frag.write_text('<article id="A1">' + IMG.format(src="manual.assets/host-01-003.png")
                        + '<a href="#B2">另一張卡</a></article>', encoding="utf-8")
        self.assertEqual(check(frag, fragment=True, asset_base=self.d)[1], [])
        _, problems = check(frag, asset_base=self.d)
        self.assertEqual(problems, [
            "頁內連結沒有對應的 id：#B2", "缺少 <html lang=...>", "缺少 <meta charset>", "缺少 <title>",
        ])

    def test_cli_exit_codes(self):
        good = self.page('<p id="a">ok</p>')

        def run(*argv):
            return subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, encoding="utf-8")

        ok = run(str(good), "--ids", "a")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertTrue(ok.stdout.rstrip().endswith("OK"))
        bad = run(str(good), "--ids", "a,b")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("FAIL 缺少 id：b", bad.stdout)
        self.assertEqual(run(str(self.d / "none.html")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
