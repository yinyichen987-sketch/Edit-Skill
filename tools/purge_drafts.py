"""按用户要求丢弃旧草稿 —— **同时更新剪映的注册表**。

## 为什么不能只删文件夹

剪映有一份草稿注册表 `<草稿根>/root_meta_info.json`（明文，含 `all_draft_store[]`）。
**只删文件夹而不更新注册表，剪映会报「草稿箱损坏」** —— 本项目已经因此翻过一次车。
（虽然重启剪映通常会让它自己重写注册表恢复一致，但不能指望这个。）

所以本脚本按正确顺序做三件事：
1. 删掉目标草稿文件夹；
2. 从 `all_draft_store[]` 里移除对应条目；
3. 顺手清掉**所有文件夹已不存在**的孤儿条目（这也是最初那次"损坏"的成因）。

只在剪映**未运行**时执行；运行中会让它回存、把删除撤销掉。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
DRAFT_ROOT = (pathlib.Path.home() / "AppData" / "Local" / "JianyingPro" /
              "User Data" / "Projects" / "com.lveditor.draft")

# 要丢弃的（都是本项目早期版本；当前交付的 瓦击杀卡点_H2H 不在其中）
DISCARD = ["瓦集锦_B站_v1", "瓦集锦_B站_v2", "瓦集锦_B站_v3",
           "瓦集锦_B站_v4", "瓦集锦_B站_v5", "瓦操作高光_H2H"]


def jianying_running() -> bool:
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq JianyingPro.exe"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stdout or ""
        return "JianyingPro.exe" in out
    except Exception:
        return False


def main() -> int:
    if jianying_running():
        print("[FAIL] 剪映正在运行 —— 先完全退出，否则它会回存、把删除撤销掉。")
        return 2

    reg = DRAFT_ROOT / "root_meta_info.json"
    data = json.loads(reg.read_text(encoding="utf-8"))
    store = data.get("all_draft_store") or []
    print(f"注册表原有 {len(store)} 条")

    # 1) 删文件夹
    for name in DISCARD:
        d = DRAFT_ROOT / name
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            print(f"  已删文件夹 {name}")

    # 2) 重建注册表：丢掉被删的 + 所有文件夹已不存在的孤儿条目
    kept, dropped = [], []
    for e in store:
        folder = pathlib.Path(e.get("draft_fold_path", "")).name
        if folder in DISCARD or not (DRAFT_ROOT / folder).is_dir():
            dropped.append(folder)
        else:
            kept.append(e)
    data["all_draft_store"] = kept
    if isinstance(data.get("draft_ids"), int):
        data["draft_ids"] = max(1, len(kept))
    reg.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    print(f"  注册表移除 {len(dropped)} 条: {dropped}")
    print(f"  注册表保留 {len(kept)} 条")

    # 3) 一致性自检
    actual = {d.name for d in DRAFT_ROOT.iterdir() if d.is_dir()}
    listed = {pathlib.Path(e.get("draft_fold_path", "")).name for e in kept}
    print(f"  文件夹 {len(actual)} 个 / 注册表 {len(listed)} 条")
    print(f"  注册表有、文件夹缺: {sorted(listed - actual) or '（无）'}")
    print(f"  文件夹有、注册表缺: {sorted(actual - listed) or '（无）'}")
    ok = not (listed - actual)
    print("  [OK] 注册表与文件夹一致" if ok else "  [WARN] 仍有孤儿条目（重启剪映会自愈）")

    print("\n当前保留的草稿:")
    for d in sorted(DRAFT_ROOT.iterdir()):
        if d.is_dir() and (d / "draft_content.json").exists():
            print(f"    {d.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
