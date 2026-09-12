"""audit_verify_dir.py 的负向测试：验证双向断言真的会失败。

为什么需要这个文件：
    「审计通过」这件事本身也需要被验证。一个永远返回 0 的审计脚本，
    和一个真的在检查的审计脚本，对外表现完全一样。
    所以这里故意制造两类问题，确认审计会 exit=1：
        1. 漏披露 —— 从披露清单里删掉一条真实存在的异常
        2. 幽灵披露 —— 往清单里塞一条实际不存在的异常
    `audit_verify_dir.py --selftest` 做的是同样的事（内存内注入）；
    本文件做的是**在真实文件副本上改文本**，覆盖面更接近真实误操作。

只改副本，不改动任何交付物。
用法：python test_audit_verify_dir.py    退出码 0=两个方向都能检出
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(TOOLS, "audit_verify_dir.py")
CLEANUP = os.path.dirname(TOOLS)  # projects/game-001/analysis


def find_python() -> str:
    """优先用仓库 venv，拿不到就退回当前解释器。"""
    for cand in (os.path.join(CLEANUP, "..", "..", "..", ".venv", "Scripts", "python.exe"),
                 os.path.join(".venv", "Scripts", "python.exe")):
        cand = os.path.abspath(cand)
        if os.path.exists(cand):
            return cand
    return sys.executable


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    src_text = open(SRC, encoding="utf-8").read()
    py = find_python()
    tmp = os.path.join(CLEANUP, "raw", "_negtest")
    os.makedirs(tmp, exist_ok=True)

    victim = '{"id": "A-H5", "interval": [11.60, 12.20], "pk": 11.25, "offset": -0.35},'
    if victim not in src_text:
        print("!! 找不到目标条目 A-H5，测试无效（清单可能已改）")
        return 2

    cases = {
        "漏披露（清单删掉 A-H5）": src_text.replace(victim, ""),
        "幽灵披露（清单塞入不存在项）": src_text.replace(
            '"pk_outside_interval": [',
            '"pk_outside_interval": [\n        '
            '{"id": "GH-H00", "interval": [9.0, 9.5], "pk": 8.0, "offset": -1.0},',
            1),
    }

    all_ok = True
    for name, text in cases.items():
        path = os.path.join(tmp, "case.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        r = subprocess.run([py, path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        triggered = r.returncode == 1
        all_ok &= triggered
        print(f"  {name:26} exit={r.returncode}  {'✅ 已触发' if triggered else '❌ 未触发'}")

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("NEGATIVE TEST", "PASS：漏披露与幽灵披露两个方向都能被检出" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
