"""兼容性验证 spike —— 读路径。

目的：验证能否解析剪映 11.4.2 已加密的 draft_content.json。
这是「用你已有的草稿反推剪辑风格」这条路的前提。

用法：
    .venv\\Scripts\\python.exe spike\\read_existing_draft.py
"""
import os
import sys
import traceback

from pyJianYingDraft import draft_content_loader as loader

DRAFT_ROOT = r"C:\Users\18930\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft"
SKIP = {".recycle_bin"}


def probe(path: str) -> None:
    if not os.path.exists(path):
        print(f"    跳过（不存在）")
        return

    size = os.path.getsize(path)
    raw = open(path, "rb").read(32)
    is_plain = raw.lstrip()[:1] == b"{"
    print(f"    大小 {size:,} 字节 | 前 24 字节: {raw[:24].decode('ascii', 'replace')}")
    print(f"    形态: {'明文 JSON' if is_plain else '加密/二进制'}")

    try:
        data = loader.load_draft_content(path)
        print(f"    [OK] 解析成功，顶层键 {len(data)} 个")
        if isinstance(data, dict):
            for k in list(data.keys())[:18]:
                v = data[k]
                n = f" len={len(v)}" if isinstance(v, (list, dict, str)) else ""
                print(f"         - {k}: {type(v).__name__}{n}")
    except Exception as e:
        print(f"    [FAIL] {type(e).__name__}: {e}")
        if isinstance(e, loader.DraftContentLoadFailed):
            print("    -> 需外部 fallback_loader 才能读取（库未内置该版本解密）")


def main() -> int:
    print("=" * 68)
    print("读路径验证：解析剪映 11.4.2 草稿")
    print("=" * 68)

    if not os.path.isdir(DRAFT_ROOT):
        print(f"[FAIL] 草稿根目录不存在: {DRAFT_ROOT}")
        return 1

    names = sorted(
        n for n in os.listdir(DRAFT_ROOT)
        if os.path.isdir(os.path.join(DRAFT_ROOT, n)) and n not in SKIP
    )
    print(f"共 {len(names)} 个草稿目录\n")

    for name in names:
        base = os.path.join(DRAFT_ROOT, name)
        files = sum(1 for _ in os.scandir(base))
        print(f"[{name}]  目录内 {files} 个条目")
        probe(os.path.join(base, "draft_content.json"))
        probe(os.path.join(base, "draft_meta_info.json"))
        print()

    print("=" * 68)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("[EXCEPTION]")
        traceback.print_exc()
        sys.exit(2)
