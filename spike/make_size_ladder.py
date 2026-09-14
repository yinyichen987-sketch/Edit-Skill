"""字号标定阶梯草稿 —— 用**一帧**把剪映的 `size → px` 换算钉死。

## 为什么需要它

本轮从剪映自渲染的 `DSH_SPIKE_TEST` 封面反推出 `em_px ≈ 5.55 × size`
（size=8.0 时 ink 高 43px 与总宽 456px 两个独立量同时收敛到 em≈44.4px）。
据此把本集字幕从 size 5.0/6.0 提到 17–24（原值实际只有 ≈28–33px，太小）。

**但该常数只来自一个字号点。** 本脚本用**一次人工打开**换来一次多点标定：
同一条草稿里放 4 个不同字号的同款文案，剪映打开后会渲染出 `draft_cover.jpg`，
从这一张图就能同时量出 4 个字号的实际 em，从而：

  1. 验证 `em ∝ size` 是否线性；
  2. 反算精确常数（替换当前的 5.55）；
  3. 顺带验证**指定字体（得意黑）是否真的被加载**（若回退系统字体，字宽会变）。

用法：
    .venv\\Scripts\\python.exe spike\\make_size_ladder.py
然后在剪映里打开草稿 `DSH_SIZE_LADDER`（打开即可，不必导出），再运行：
    .venv\\Scripts\\python.exe spike\\measure_size_ladder.py
"""
import os
import sys
import traceback

import pyJianYingDraft as d

DRAFT_ROOT = os.path.join(os.environ["LOCALAPPDATA"], "JianyingPro", "User Data",
                          "Projects", "com.lveditor.draft")
DRAFT_NAME = "DSH_SIZE_LADDER"
WIDTH, HEIGHT, FPS = 1080, 1920, 30
FONT_NAME = "得意黑"

# (字号, 中心距顶 px)。间距 480px，最大 em≈144px，不会互相压到。
LADDER = [(8.0, 240), (14.0, 720), (20.0, 1200), (26.0, 1680)]
SAMPLE = "测试字 AB"


def y_to_transform_y(center_px: float, H: int = HEIGHT) -> float:
    """中心距顶 px → transform_y（单位：半个画布高，上移为正）。"""
    return 1.0 - 2.0 * center_px / H


def main() -> int:
    print("=" * 64)
    print(f"字号标定阶梯：{len(LADDER)} 档  {WIDTH}x{HEIGHT}  字体={FONT_NAME}")
    print("=" * 64)
    if not os.path.isdir(DRAFT_ROOT):
        print(f"[FAIL] 草稿根目录不存在: {DRAFT_ROOT}")
        return 2

    font = getattr(d.FontType, FONT_NAME, None)
    if font is None:
        print(f"[FAIL] FontType 里没有 {FONT_NAME}")
        return 2
    print(f"[OK] 字体 {FONT_NAME}: resource_id={font.value.resource_id} "
          f"is_vip={font.value.is_vip}")

    folder = d.DraftFolder(DRAFT_ROOT)
    script = folder.create_draft(DRAFT_NAME, WIDTH, HEIGHT, fps=FPS, allow_replace=True)

    # 每一档单独一条轨：4 条文案都要在第 0 帧同时可见（一张封面量完 4 档），
    # 但同一轨上时间区间重叠会被 add_segment 的重叠校验直接拒绝 —— 和特效轨同一个坑。
    for i in range(len(LADDER)):
        script.append_track(d.TrackSpec(d.TrackType.text, f"ladder{i}"))

    for i, (size, center_px) in enumerate(LADDER):
        ty = y_to_transform_y(center_px)
        seg = d.TextSegment(
            SAMPLE,
            d.trange("0s", "3s"),
            font=font,
            style=d.TextStyle(size=size, bold=True),
            clip_settings=d.ClipSettings(transform_y=ty),
            border=d.TextBorder(color=(0.0, 0.0, 0.0), width=40.0),
        )
        script.add_segment(seg, f"ladder{i}")
        print(f"  size={size:>5}  中心={center_px:>5}px  transform_y={ty:+.4f}  轨=ladder{i}")

    script.save()
    print(f"[OK] 草稿已保存到: {os.path.join(DRAFT_ROOT, DRAFT_NAME)}")
    print("-" * 64)
    print("下一步（人工，只需一次）：")
    print(f"  1. 在剪映里打开草稿「{DRAFT_NAME}」（打开即可）")
    print("  2. 关掉或切走，让剪映把 draft_cover.jpg 写出来")
    print("  3. 运行 spike\\measure_size_ladder.py 反算精确常数")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("[EXCEPTION] 生成标定草稿时抛出异常：")
        traceback.print_exc()
        sys.exit(2)
