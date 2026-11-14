# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""orchestrate-v2 驗收指令執行器：執行一條驗收指令，把結果附加到工單證據檔，終端只印末段。

用法：
  uv run run_evidence.py --dir <證據檔目錄> --id <驗收編號> --when before|after|op [--cwd <目錄>] [--tail N] -- <argv...>
  uv run run_evidence.py --dir … --id … --when … --sh '<bash 指令字串>'
  uv run run_evidence.py --dir … --id … --when … --pwsh '<pwsh 指令字串>'

檔名：before → before-<id>.txt；after → after-<id>.txt；op → after-op.txt（--id 可省略）。目錄不存在時建立。
每次執行在檔尾附加一段（段與段之間空一行，既有內容不動），UTF-8 無 BOM、LF：
  $ <指令原文>          argv 模式為 shlex.join（各參數經 POSIX shell 引號處理後以空白相接）；--sh／--pwsh 為該字串原樣；
                        指令含換行時，換行寫成字面的 \n 兩個字元，標頭固定佔一行
  exit code: <n>
  elapsed: <秒，小數一位>s
  <stdout 與 stderr 合併的完整輸出>
產出的證據檔可直接交給同目錄 check_evidence.py 檢查。

輸出處理：
- 解碼先試 UTF-8，失敗改用系統 ANSI code page（Windows）或 locale 編碼，仍失敗才以替換字元解碼。
- 移除 ANSI 色碼（CSI 序列）；換行一律依 str.splitlines() 切行後以 LF 寫入（CRLF、單獨 CR 都變成 LF）。
- 輸出本文某一行若會被 check_evidence.py 的 CMD_RE 或 EXIT_RE 命中（例：被測程式自己印出
  "exit code: 0"、"rc=0"、"$ foo"），寫入證據檔時在該行行首加一個空白，
  讓 check_evidence.py 只認得本腳本寫的標頭。終端輸出不加空白。

終端輸出：輸出最後 N 行（預設 40；0 表示不印），再加一行
  [run_evidence] exit code: <n> | elapsed: <秒>s | <證據檔路徑>
結束碼＝被執行指令的 exit code。指令無法啟動（找不到執行檔或 shell、參數錯誤）時
stderr 印原因、結束碼 2、不寫入任何段。

執行細節：stdin 接空裝置；不做逾時處理。argv 模式在 Windows 以 shutil.which 解析第一個參數（可執行 .cmd shim）；
第一個參數是含目錄成分的相對路徑（例 .\\pwsh.exe、./vendor/bin/pest）時，以 --cwd 為基準解析。
Windows 解析到 .cmd／.bat 時參數會經 cmd.exe 解析：含 cmd 特殊字元或空白的參數加雙引號；
含 " % 或換行的參數無法原樣傳遞，stderr 提示改用 --sh／--pwsh、結束碼 2、不寫入任何段。
--sh 的 bash：環境變數 RUN_EVIDENCE_BASH → Windows 由 `git --exec-path` 往上找 Git for Windows 的 bin/bash.exe
（不退回 PATH 的 bash，避免跑到 System32 的 WSL bash）→ 非 Windows 用 shutil.which("bash")。
--pwsh：pwsh -NoProfile -NonInteractive -Command <字串>。
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

IS_WIN = os.name == "nt"
# 與 check_evidence.py 的 CMD_RE／EXIT_RE 相同，兩邊要一起改
CMD_RE = re.compile(r"^(?:\$ |command:|cmd:)(.*)$", re.IGNORECASE)
EXIT_RE = re.compile(r"^(?:-+\s*)?(?:exit code|exit|rc)\s*[:=]\s*(-?\d+)(?![\w.])", re.IGNORECASE)
CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def fail(msg: str) -> int:
    print(f"run_evidence: {msg}", file=sys.stderr)
    return 2


def find_bash() -> str | None:
    env = os.environ.get("RUN_EVIDENCE_BASH")
    if env:
        return env
    if not IS_WIN:
        return shutil.which("bash")
    try:
        p = subprocess.run(["git", "--exec-path"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except OSError:
        return None
    if p.returncode != 0 or not p.stdout.strip():
        return None
    for d in Path(p.stdout.strip()).parents:
        cand = d / "bin" / "bash.exe"
        if cand.is_file():
            return str(cand)
    return None


def decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    if IS_WIN:
        import ctypes
        enc = f"cp{ctypes.windll.kernel32.GetACP()}"
    else:
        import locale
        enc = getattr(locale, "getencoding", lambda: locale.getpreferredencoding(False))()
    try:
        return data.decode(enc)
    except (UnicodeDecodeError, LookupError):
        return data.decode("utf-8", errors="replace")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd_argv: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, cmd_argv = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description="執行驗收指令並附加到工單證據檔")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--id")
    ap.add_argument("--when", required=True, choices=["before", "after", "op"])
    ap.add_argument("--cwd")
    ap.add_argument("--tail", type=int, default=40)
    ap.add_argument("--sh")
    ap.add_argument("--pwsh")
    a = ap.parse_args(argv)

    if sum([bool(cmd_argv), a.sh is not None, a.pwsh is not None]) != 1:
        return fail("必須恰好指定一種指令：-- <argv...>、--sh 或 --pwsh")
    if a.when == "op":
        name = "after-op.txt"
    elif not a.id:
        return fail("--when before／after 需要 --id")
    elif re.search(r"[\\/]", a.id):
        return fail(f"--id 不可含路徑分隔字元：{a.id}")
    else:
        name = f"{a.when}-{a.id}.txt"

    if cmd_argv:
        shown = shlex.join(cmd_argv)
        exe = cmd_argv[0]
        if a.cwd and os.path.dirname(exe) and not os.path.isabs(exe):
            exe = os.path.normpath(os.path.join(os.path.abspath(a.cwd), exe))
        if IS_WIN:
            exe = shutil.which(exe)
        if exe is None:
            return fail(f"找不到執行檔：{cmd_argv[0]}")
        run = [exe, *cmd_argv[1:]]
        if IS_WIN and Path(exe).suffix.lower() in (".cmd", ".bat"):
            # 批次檔的命令列由 cmd.exe 解析：雙引號內的 & | < > ^ ( ) , ; = 與空白是字面，
            # 但 % 照樣展開環境變數，" 會切換引號狀態，換行會結束指令，這三類無法原樣傳遞
            bad = next((x for x in run if set(x) & set('"%\r\n\0')), None)
            if bad is not None:
                return fail(f"{exe} 是批次檔，參數經 cmd.exe 解析，含 \" % 或換行的參數無法原樣傳遞："
                            f"{bad!r}；請改用 --sh 或 --pwsh")
            run = " ".join([f'"{exe}"'] + [x if re.fullmatch(r"[\w@+:./\\-]+", x)
                                            else '"' + re.sub(r"(\\+)$", r"\1\1", x) + '"' for x in run[1:]])
    elif a.sh is not None:
        shown = a.sh
        bash = find_bash()
        if bash is None:
            return fail("找不到 bash（可設環境變數 RUN_EVIDENCE_BASH）")
        run = [bash, "-c", a.sh]
    else:
        shown = a.pwsh
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            return fail("找不到 pwsh")
        run = [pwsh, "-NoProfile", "-NonInteractive", "-Command", a.pwsh]

    t0 = time.perf_counter()
    try:
        p = subprocess.run(run, cwd=a.cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        return fail(f"無法啟動指令：{e}")
    elapsed = time.perf_counter() - t0
    rc = p.returncode

    shown = "\\n".join(shown.splitlines())  # 標頭固定一行，exit code 才會在第 2 行
    lines = CSI_RE.sub("", decode(p.stdout)).splitlines()
    body = [" " + ln if CMD_RE.match(ln) or EXIT_RE.match(ln) else ln for ln in lines]
    seg = f"$ {shown}\nexit code: {rc}\nelapsed: {elapsed:.1f}s\n" + "".join(ln + "\n" for ln in body)

    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / name
    if path.is_file() and path.stat().st_size > 0:
        with path.open("rb") as f:
            f.seek(-1, os.SEEK_END)
            seg = ("\n" if f.read(1) == b"\n" else "\n\n") + seg
    with path.open("ab") as f:
        f.write(seg.encode("utf-8", errors="replace"))

    if a.tail > 0:
        for ln in lines[-a.tail:]:
            print(ln)
    print(f"[run_evidence] exit code: {rc} | elapsed: {elapsed:.1f}s | {path}")
    return rc


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
