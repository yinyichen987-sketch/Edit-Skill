"""剪映草稿换行归一化器（CRLF -> LF）。

pyJianYingDraft 在 Windows 上写出的 draft_content.json / draft_meta_info.json 是 CRLF，
而本仓库要求文本文件不带 CRLF（core.autocrlf=false）——
所以每份新草稿出完都要过一遍这个脚本，**母本与剪映目录两份都要过**。

用法：
    python lf_normalize.py <草稿目录> [<草稿目录> ...]

说明：
    - 只处理目录下的 *.json；每个文件 replace(b"\r\n", b"\n") 后回写。
    - 回写后立刻 json.loads 自检，解析失败就报错（退出码 1）。
    - 已经是 LF 的文件内容不变（仍会重写一次，字节相同）。
"""
from __future__ import annotations

import json
import pathlib
import sys


def normalize(draft_dir: pathlib.Path) -> bool:
    if not draft_dir.is_dir():
        print(f"[FAIL] 不是目录: {draft_dir}")
        return False
    files = sorted(p for p in draft_dir.glob("*.json") if p.is_file())
    if not files:
        print(f"[FAIL] 目录里没有 *.json: {draft_dir}")
        return False
    ok = True
    for path in files:
        raw = path.read_bytes()
        before = raw.count(b"\r\n")
        new = raw.replace(b"\r\n", b"\n")
        if new != raw:
            path.write_bytes(new)
        after = path.read_bytes().count(b"\r\n")
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - 自检失败要原样报出来
            print(f"[FAIL] {path.name}: 归一化后 JSON 解析失败: {exc}")
            ok = False
            continue
        print(f"  {path.name}: CRLF {before} -> {after}，{len(raw)} -> {len(new)} 字节")
    print(f"[{'OK' if ok else 'FAIL'}] {draft_dir}")
    return ok


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ok = True
    for arg in sys.argv[1:]:
        ok = normalize(pathlib.Path(arg)) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
