"""给 tools/ 下所有脚本加上 stdout/stderr 的 UTF-8 reconfigure。

为什么必须做：
    Windows 默认控制台是 GBK。本项目的脚本大量打印中文与符号（⊂ ✓ ✅ → 等），
    默认编码下会在**打印中途**抛 UnicodeEncodeError 而退出。
    更危险的是：崩溃的退出码往往与脚本自身的"失败"退出码相同
    （例如 audit_verify_dir.py 用 exit=1 表示审计不通过），
    于是**崩溃与"审计失败"无法区分** —— 一个不能完整运行的门禁比没有门禁更危险。

用法：python patch_stdout_encoding.py          # 原地修改 tools/*.py
      python patch_stdout_encoding.py --check   # 只检查，不修改
"""
from __future__ import annotations

import os
import re
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
SNIPPET = (
    "    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛\n"
    "    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，\n"
    "    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。\n"
    "    try:\n"
    "        sys.stdout.reconfigure(encoding=\"utf-8\", errors=\"replace\")\n"
    "        sys.stderr.reconfigure(encoding=\"utf-8\", errors=\"replace\")\n"
    "    except (AttributeError, ValueError):\n"
    "        pass\n"
)
MAIN_RE = re.compile(r"^(def main\([^)]*\)[^:]*:\n)", re.M)


def patch(text: str) -> tuple[str, bool]:
    if "reconfigure(encoding=" in text:
        return text, False
    if "import sys" not in text:
        return text, False
    m = MAIN_RE.search(text)
    if not m:
        return text, False
    insert_at = m.end()
    return text[:insert_at] + SNIPPET + text[insert_at:], True


def main() -> int:
    check_only = "--check" in sys.argv
    changed, skipped, already = [], [], []
    for name in sorted(os.listdir(TOOLS)):
        if not name.endswith(".py") or name == os.path.basename(__file__):
            continue
        path = os.path.join(TOOLS, name)
        text = open(path, encoding="utf-8").read()
        if "reconfigure(encoding=" in text:
            already.append(name)
            continue
        new, did = patch(text)
        if not did:
            skipped.append(name)
            continue
        if not check_only:
            open(path, "w", encoding="utf-8", newline="\n").write(new)
        changed.append(name)

    print(f"已具备 reconfigure: {len(already)} -> {already}")
    print(f"{'需修改' if check_only else '已修改'}: {len(changed)} -> {changed}")
    print(f"无法自动处理（缺少 import sys 或无 main）: {len(skipped)} -> {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
