"""从剪映自渲染的标定封面里反算 `size → px` 常数。

前置：先跑 `spike/make_size_ladder.py`，再在剪映里**打开一次**该草稿
（打开后剪映会写 `draft_cover.jpg` 到草稿目录）。

本脚本读那张封面，按已知的 4 个落点分行测量文字 ink 高度与宽度，
反算每档的 em 与 `em / size`，给出：
  · 线性性检验（4 个比值是否一致）
  · 精确常数（应替换 `edl_to_draft` / `check_caption_pixels` / `render_preview` 里的 5.55）
  · 字体是否真被加载的旁证（与"得意黑"期望字宽比对，回退系统字体时会明显不同）

用法：
    .venv\\Scripts\\python.exe spike\\measure_size_ladder.py
"""
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

DRAFT_ROOT = Path(os.environ["LOCALAPPDATA"]) / "JianyingPro" / "User Data" / \
    "Projects" / "com.lveditor.draft"
DRAFT_NAME = "DSH_SIZE_LADDER"
LADDER = [(8.0, 240), (14.0, 720), (20.0, 1200), (26.0, 1680)]
SAMPLE = "测试字 AB"
WINDOW = 200          # 在每个落点上下各取多少 px 作为搜索窗
EM_ASSUMED = 5.29     # 当前在用的常数，仅用于打印对比


def main() -> int:
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        print("[FAIL] 需要 Pillow 与 numpy")
        return 2

    cover = DRAFT_ROOT / DRAFT_NAME / "draft_cover.jpg"
    if not cover.exists():
        print(f"[FAIL] 还没找到剪映渲染的封面: {cover}")
        print("       请先在剪映里打开一次该草稿（打开即可，不必导出）。")
        return 2

    a = np.asarray(Image.open(cover).convert("RGB"), dtype=np.int16)
    H, W = a.shape[:2]
    print(f"封面: {W}x{H}   {cover}")
    # 白字（深色描边之外的核心像素）
    near_white = (a.min(axis=2) > 215) & ((a.max(axis=2) - a.min(axis=2)) < 30)
    print(f"{'字号':>6} {'落点':>6} {'ink高':>7} {'ink宽':>7} {'推算em':>8} {'em/size':>9}")
    print("-" * 54)
    ratios = []
    for size, center in LADDER:
        lo, hi = max(0, center - WINDOW), min(H, center + WINDOW)
        band = near_white[lo:hi]
        rows = band.sum(axis=1)
        ys = [i for i, c in enumerate(rows) if c > 3]
        if not ys:
            print(f"{size:>6.1f} {center:>6} {'—':>7} {'—':>7}   未检出文字")
            continue
        cols = band[min(ys):max(ys) + 1].sum(axis=0)
        xs = [i for i, c in enumerate(cols) if c > 0]
        ink_h = max(ys) - min(ys) + 1
        ink_w = (max(xs) - min(xs) + 1) if xs else 0
        # 文案 = 3 汉字(≈1.0em) + 1 空格(≈0.26em) + 2 拉丁大写(≈0.72em) = 4.70em
        em_from_w = ink_w / 4.70 if ink_w else 0.0
        em_from_h = ink_h / 0.97           # 汉字近满格
        em = (em_from_w + em_from_h) / 2 if em_from_w else em_from_h
        ratios.append(em / size)
        print(f"{size:>6.1f} {center:>6} {ink_h:>7} {ink_w:>7} {em:>8.1f} {em/size:>9.2f}")

    print("-" * 54)
    if len(ratios) >= 2:
        spread = max(ratios) - min(ratios)
        print(f"em/size 比值: {['%.2f' % r for r in ratios]}")
        print(f"极差 = {spread:.2f}  ->  " +
              ("线性成立" if spread < 0.35 else "**线性可疑，需查字号语义**"))
        mean = sum(ratios) / len(ratios)
        print(f"实测常数 ≈ {mean:.2f}（当前在用 {EM_ASSUMED}，"
              f"偏差 {abs(mean-EM_ASSUMED)/EM_ASSUMED*100:.0f}%）")
        if abs(mean - EM_ASSUMED) / EM_ASSUMED > 0.20:
            print("  ⚠️ 偏差 >20%：应把新常数写回 edl_to_draft / check_caption_pixels / render_preview")
    else:
        print("检出档位不足，无法线性性检验")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
