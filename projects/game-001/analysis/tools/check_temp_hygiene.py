"""检查 tools/ 下的脚本是否会遗留中间产物，并可选清理。

动机（真实欠账）：
    fps_offset_selfconsistent.py 每段源帧导一张 PNG，我在 raw/ 下留下
    **2386 个文件 / 285MB** 未清理。这是卫生问题：临时产物不该留在交付树里。

    ⚠️ 归因更正：我曾把 creative-reviewer 的 frame-probe 崩溃归因于这些残留 PNG。
    **该归因是错的**（已由它用实验排除，我也独立核对过）：它的工具只 glob 自己运行
    专属子目录下的 `o_*.png`（measure_sampling_bias.py:107），从不扫 raw/；
    真因是它自己 `_tmp` 里一个被中断、写了一半的 PNG。
    本脚本存在的理由是**卫生本身**，与那次崩溃无因果关系。

用法：
    python check_temp_hygiene.py            # 只报告
    python check_temp_hygiene.py --clean    # 报告并清理可安全删除的临时目录
"""
from __future__ import annotations

import os
import re
import shutil
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(TOOLS)
RAW = os.path.join(ANALYSIS, "raw")

# 约定：脚本的临时目录一律以 _ 开头，且位于 raw/ 下
TMP_PATTERNS = ("_self", "_scan_tmp", "_final", "_diag", "_fpschk", "_probe",
                "_mae_tmp", "_paired", "_mtest", "_fmt", "_negtest")
WRITE_RE = re.compile(r'os\.path\.join\(\s*(?:TMP|tmp|RAW)[^)]*\)|f"\{TMP\}|f"\{tmp\}')
CLEAN_RE = re.compile(r"rmtree|shutil\.rmtree")


def main() -> int:
    clean = "--clean" in sys.argv
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    print("=" * 74)
    print("1) 脚本侧的临时目录定义与清理逻辑")
    print("=" * 74)
    offenders = []
    for name in sorted(os.listdir(TOOLS)):
        if not name.endswith(".py"):
            continue
        text = open(os.path.join(TOOLS, name), encoding="utf-8").read()
        m = re.search(r'^(TMP[^\n]*=.*)$', text, re.M)
        writes_tmp = bool(m)
        cleans = bool(CLEAN_RE.search(text))
        if writes_tmp and not cleans:
            offenders.append(name)
        if writes_tmp:
            print(f"  {name:34} 定义 TMP={'是' if writes_tmp else '否'}  "
                  f"清理={'有' if cleans else '!! 无'}")
    if not offenders:
        print("  （没有'定义 TMP 但不清理'的脚本）")
    else:
        print(f"\n  !! 定义 TMP 但无清理逻辑: {offenders}")

    print()
    print("=" * 74)
    print("2) 树内是否残留临时目录")
    print("=" * 74)
    found = []
    for entry in sorted(os.listdir(RAW)):
        if entry.startswith("_") or entry in TMP_PATTERNS:
            found.append(entry)
    if not found:
        print("  raw/ 下无临时残留 ✅")
    for entry in found:
        p = os.path.join(RAW, entry)
        if os.path.isdir(p):
            n = sum(len(f) for _, _, f in os.walk(p))
            sz = sum(os.path.getsize(os.path.join(r, f))
                     for r, _, fs in os.walk(p) for f in fs)
            print(f"  {entry:16} 目录  {n} 个文件  {sz / 1e6:.1f} MB")
        else:
            print(f"  {entry:16} 文件  {os.path.getsize(p) / 1e6:.1f} MB")

    # 项目内其它位置的 PNG 污染（检测器常 glob png）
    print()
    print("=" * 74)
    print("3) 项目树内 PNG 分布（glob PNG 的检测器会看到这些）")
    print("=" * 74)
    proj = os.path.join(os.path.dirname(ANALYSIS), "")
    total = 0
    for r, _, fs in os.walk(proj):
        pngs = [f for f in fs if f.lower().endswith(".png")]
        if pngs:
            rel = os.path.relpath(r, proj)
            print(f"  {rel:52} {len(pngs)}")
            total += len(pngs)
    print(f"  合计 {total} 张")

    if clean and found:
        print()
        print("=" * 74)
        print("清理")
        print("=" * 74)
        for entry in found:
            p = os.path.join(RAW, entry)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
            print(f"  已删除 {entry}")

    return 1 if offenders else 0


if __name__ == "__main__":
    raise SystemExit(main())
