# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""操作測試產出的 HTML 靜態檢查（現況表、操作手冊、裁決報告或其片段）。只讀檔。

用法：
  uv run check_report_html.py <html 檔> [--ids id1,id2,...] [--require-hrefs href1,href2,...]
      [--min-img N] [--forbid <片段> ...] [--fragment] [--asset-base <目錄>] [--no-img-attrs]

檢查項目：
  1. 圖片與本機連結（img src、a href 的相對路徑）指到的檔案存在。
  2. 錨點對得上：頁內連結 #id 在本檔有對應的 id；連到其他本機 HTML 的 #id 在那個檔有對應的 id。
  3. 沒有外部資源：<script src>、<link rel=stylesheet>、@import、外部圖片、CSS 內的外部 url()。
     （<a href="http://..."> 這類文字連結允許。）
  4. --ids 列出的每個 id 存在；--require-hrefs 列出的每個 href 至少出現一次（逗號分隔，照字面比對）。
  5. 圖片數量不少於 --min-img。
  6. 每個 <img> 有 width、height、alt、loading（--no-img-attrs 可關閉）。
  7. --forbid：圖片或連結的路徑不得含這個片段，素材基準目錄底下也不得有檔名含這個片段的檔案
     （用於隔離清單上的截圖；可重複）。
  8. 非片段檔要有 <html lang=...>、<meta charset>、<title>。
--fragment：檔案是待組裝的片段，略過第 8 項與頁內錨點。--asset-base：相對路徑的基準目錄，預設為 html 檔所在目錄。
輸出：一行摘要，之後每個問題一行 FAIL；全部通過印 OK。
結束碼：全部通過 0；有問題 1；html 檔不存在 2。可 import：check(path, ...) 回傳 (摘要, 問題清單)。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.I)
SRC_RE = re.compile(r"\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
HREF_RE = re.compile(r"<a\b[^>]*?\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I)
ID_RE = re.compile(r"(?<![\w-])id\s*=\s*[\"']([^\"']+)[\"']")
EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.I)
IMG_ATTRS = ("width", "height", "alt", "loading")


def split_list(value: str) -> list[str]:
    return [item for item in value.split(",") if item]


def ids_of(text: str) -> set[str]:
    return set(ID_RE.findall(text))


def check(path, ids=(), require_hrefs=(), min_img=0, forbid=(), fragment=False, asset_base=None, img_attrs=True):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    base = Path(asset_base) if asset_base else path.parent
    problems: list[str] = []

    img_tags = IMG_TAG_RE.findall(text)
    srcs = [m.group(1) for tag in img_tags if (m := SRC_RE.search(tag))]
    hrefs = HREF_RE.findall(text)
    own_ids = ids_of(text)
    other_ids: dict[Path, set[str]] = {}

    for src in srcs:
        if src.startswith("data:"):
            continue
        if EXTERNAL_RE.match(src):
            problems.append(f"外部圖片：{src}")
        elif not (base / unquote(src.split("#")[0].split("?")[0])).is_file():
            problems.append(f"圖片不存在：{src}")

    for href in hrefs:
        if href.startswith("#"):
            target = unquote(href[1:])
            if target and target not in own_ids and not fragment:
                problems.append(f"頁內連結沒有對應的 id：{href}")
            continue
        if EXTERNAL_RE.match(href):
            continue
        file_part, _, anchor = href.partition("#")
        target_file = base / unquote(file_part.split("?")[0])
        if not target_file.is_file():
            problems.append(f"連結目標不存在：{href}")
            continue
        if anchor and target_file.suffix.lower() in (".html", ".htm"):
            if target_file not in other_ids:
                other_ids[target_file] = ids_of(target_file.read_text(encoding="utf-8"))
            if unquote(anchor) not in other_ids[target_file]:
                problems.append(f"連結的錨點在目標檔不存在：{href}")

    if re.search(r"<script\b[^>]*\bsrc\s*=", text, re.I):
        problems.append("有外部 script（<script src>）")
    if re.search(r"<link\b[^>]*rel\s*=\s*[\"']?stylesheet", text, re.I):
        problems.append("有外部樣式表（<link rel=stylesheet>）")
    if re.search(r"@import\b", text):
        problems.append("有 @import")
    if re.search(r"url\(\s*[\"']?(?:https?:)?//", text, re.I):
        problems.append("CSS 內有外部 url()")

    for want in ids:
        if want not in own_ids:
            problems.append(f"缺少 id：{want}")
    for want in require_hrefs:
        if want not in hrefs:
            problems.append(f"缺少連結：{want}")
    if len(img_tags) < min_img:
        problems.append(f"圖片數量 {len(img_tags)} 少於要求的 {min_img}")

    if img_attrs:
        for tag in img_tags:
            missing = [a for a in IMG_ATTRS if not re.search(rf"(?<![\w-]){a}\s*=", tag, re.I)]
            if missing:
                src = SRC_RE.search(tag)
                problems.append(f"圖片缺少屬性 {','.join(missing)}：{src.group(1) if src else tag[:60]}")

    for piece in forbid:
        for ref in srcs + hrefs:
            if piece in unquote(ref):
                problems.append(f"引用了禁用的檔案（{piece}）：{ref}")
        if base.is_dir():
            for found in base.rglob("*"):
                if found.is_file() and piece in found.name:
                    problems.append(f"素材目錄內有禁用的檔案（{piece}）：{found}")

    if not fragment:
        if not re.search(r"<html\b[^>]*\blang\s*=\s*[\"'][^\"']+[\"']", text, re.I):
            problems.append("缺少 <html lang=...>")
        if not re.search(r"<meta\b[^>]*charset", text, re.I):
            problems.append("缺少 <meta charset>")
        if not re.search(r"<title>[^<]+</title>", text, re.I):
            problems.append("缺少 <title>")

    summary = f"{path.name}: img={len(img_tags)} href={len(hrefs)} ids={len(own_ids)} bytes={len(text.encode('utf-8'))}"
    return summary, problems


def main() -> int:
    parser = argparse.ArgumentParser(description="操作測試產出的 HTML 靜態檢查")
    parser.add_argument("html")
    parser.add_argument("--ids", default="")
    parser.add_argument("--require-hrefs", default="")
    parser.add_argument("--min-img", type=int, default=0)
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument("--fragment", action="store_true")
    parser.add_argument("--asset-base", default="")
    parser.add_argument("--no-img-attrs", action="store_true")
    args = parser.parse_args()

    if not Path(args.html).is_file():
        print(f"檔案不存在：{args.html}", file=sys.stderr)
        return 2

    summary, problems = check(
        args.html,
        ids=split_list(args.ids),
        require_hrefs=split_list(args.require_hrefs),
        min_img=args.min_img,
        forbid=args.forbid,
        fragment=args.fragment,
        asset_base=args.asset_base or None,
        img_attrs=not args.no_img_attrs,
    )
    print(summary)
    for problem in problems:
        print("FAIL", problem)
    if problems:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
