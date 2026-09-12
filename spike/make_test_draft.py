"""兼容性验证 spike —— 写路径。

目的：为剪映 11.4.2 生成一个最小可用草稿，验证 pyJianYingDraft 0.3.0
能否让新版剪映正常识别并打开。

用法：
    .venv\\Scripts\\python.exe spike\\make_test_draft.py
"""
import os
import sys
import traceback

import pyJianYingDraft as d

DRAFT_ROOT = r"C:\Users\18930\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft"
HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(HERE, "media")
DRAFT_NAME = "DSH_SPIKE_TEST"

WIDTH, HEIGHT, FPS = 1080, 1920, 30


def main() -> int:
    print("=" * 60)
    print("写路径验证：为剪映 11.4.2 生成最小草稿")
    print("=" * 60)

    if not os.path.isdir(DRAFT_ROOT):
        print(f"[FAIL] 草稿根目录不存在: {DRAFT_ROOT}")
        return 1

    for f in ("test_a.mp4", "test_b.mp4"):
        p = os.path.join(MEDIA, f)
        if not os.path.exists(p):
            print(f"[FAIL] 缺少测试素材: {p}")
            return 1

    folder = d.DraftFolder(DRAFT_ROOT)
    print(f"草稿根目录: {DRAFT_ROOT}")
    print(f"现有草稿 ({len(folder.list_drafts())} 个): {folder.list_drafts()}")

    # ---- 1. 创建草稿 ----
    script = folder.create_draft(DRAFT_NAME, WIDTH, HEIGHT, fps=FPS, allow_replace=True)
    print(f"[OK] 草稿已创建: {DRAFT_NAME}  ({WIDTH}x{HEIGHT} @{FPS}fps)")

    # ---- 2. 建轨道 ----
    script.append_tracks([
        d.TrackSpec(d.TrackType.video, "main"),
        d.TrackSpec(d.TrackType.text, "caption"),
    ])
    print("[OK] 已创建轨道: main(video), caption(text)")

    # ---- 3. 视频片段 + 转场 ----
    seg_a = d.VideoSegment(os.path.join(MEDIA, "test_a.mp4"), d.trange("0s", "3s"))
    seg_b = d.VideoSegment(os.path.join(MEDIA, "test_b.mp4"), d.trange("3s", "3s"))
    print(f"[OK] 视频片段: test_a 0-3s, test_b 3-6s")

    try:
        seg_a.add_transition(d.TransitionType.信号故障)
        print("[OK] 转场: 信号故障 (加在前一片段上)")
    except Exception as e:
        print(f"[WARN] 转场添加失败（非致命）: {type(e).__name__}: {e}")

    script.add_segment(seg_a, "main").add_segment(seg_b, "main")
    print("[OK] 视频片段已入轨")

    # ---- 4. 字幕 ----
    caption = d.TextSegment(
        "DSH SPIKE 测试字幕",
        d.trange("0s", "3s"),
        clip_settings=d.ClipSettings(transform_y=-0.8),
    )
    script.add_segment(caption, "caption")
    print("[OK] 字幕已入轨")

    # ---- 5. 保存 ----
    out = script.save()
    print(f"[OK] 草稿已保存: {out}")

    # ---- 6. 落盘校验 ----
    draft_dir = os.path.join(DRAFT_ROOT, DRAFT_NAME)
    print("-" * 60)
    print(f"落盘目录: {draft_dir}")
    if os.path.isdir(draft_dir):
        for name in sorted(os.listdir(draft_dir)):
            full = os.path.join(draft_dir, name)
            if os.path.isfile(full):
                print(f"  {os.path.getsize(full):>10,}  {name}")
            else:
                print(f"  {'<dir>':>10}  {name}/")

        content = os.path.join(draft_dir, "draft_content.json")
        if os.path.exists(content):
            raw = open(content, "rb").read(48)
            readable = all(32 <= b < 127 for b in raw)
            head = raw.decode("ascii", "replace")
            print(f"\ndraft_content.json 前 48 字节: {head}")
            print(f"形态: {'明文 JSON' if raw.lstrip()[:1] == b'{' else '非明文（加密或二进制）'}")
    else:
        print("[FAIL] 草稿目录未生成")
        return 1

    print("=" * 60)
    print("写路径脚本执行完毕 —— 请在剪映里打开该草稿做人工确认")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("[EXCEPTION] 生成草稿时抛出异常：")
        traceback.print_exc()
        sys.exit(2)
