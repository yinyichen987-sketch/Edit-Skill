"""校验 EDL 的「不割裂」性质：**每段原始素材内部必须单调递增**。

## 为什么需要这个脚本

用户对"集锦"的定义是：
> **每个原始素材先后一致，不要把片段切割太碎。**

但实测的六条高播放参考成片，节奏是 **20–38 切/分、中位镜长 0.97–2.67s**
（`research/bili-highview-analysis.md`）—— 也就是**快切**。
而本项目早期版本为了"不切碎"，做成了 12 切/分、均长 4.4s，慢了 2–3 倍。

两者曾经看似互斥。**自洽的解法是把"不割裂"重新定义成一条可计算的约束**：

> **不割裂 = 同一段素材在时间轴上只朝素材时间增大的方向走，绝不回头。**

只要满足它，就不存在"在同一段素材里反复进出"的割裂感，
同时又允许把每段素材切成许多短镜去做快切。
**这条判据是本脚本唯一的职责** —— 它是"快"与"不碎"能同时成立的那个不变量。

## 用法

    .venv\\Scripts\\python.exe tools\\verify_shot_order.py projects/game-001/edl/montage.json

退出码 0 = 全部单调；1 = 有回跳（有割裂）。

## ⚠️ 叠加轨（`ovl_*`）不参与这条判据（第 6 轮修正）

白闪/黑场是**同一份素材被反复压在不同时刻**（`white_2f.mp4` 用 N 次，`source_in` 都是 0），
它们**天然"回跳"**，但它们不是"切点"，而是**叠加在切点上的效果素材**。
把它们混进"每段素材内部单调"里会得出**假 FAIL**：

    ✗ white_2f: 0.000@15.37s < 0.000@15.44s   ← 两条白闪，本来就该在多个时刻出现

而且它们还会污染节奏统计（镜长中位数被 0.0667s 的白闪拉到 0.067s、
总长按"各片段时长求和"算成 15.57s，比真实时长多出叠加轨的长度）。

⇒ 本脚本现在**只统计主轨**（`track` 不以 `ovl_` 开头的视频片段），
并且总长用 `max(start + duration)` 而不是求和（允许片段重叠）。
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = pathlib.Path(sys.argv[1])
    if not path.is_absolute():
        path = pathlib.Path(__file__).resolve().parents[1] / path
    edl = json.loads(path.read_text(encoding="utf-8"))
    all_clips = edl["clips"]
    # 叠加轨（白闪/黑场素材）不是切点，见文件头说明
    clips = [c for c in all_clips if not str(c.get("track", "")).startswith("ovl_")]
    skipped = len(all_clips) - len(clips)

    per_source: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for c in clips:
        per_source[c["source"]].append(
            (float(c["source_in"]), float(c["start"]), c.get("id", "?")))
    timeline = max(float(c["start"]) + float(c["duration"]) for c in clips)

    print(f"=== {path.name} ===")
    print(f"  主轨片段 {len(clips)} 个 / 总长 {timeline:.4f}s / "
          f"{len(clips) - 1} 切 / {(len(clips) - 1) / timeline * 60:.1f} 切每分")
    if skipped:
        print(f"  （已跳过 {skipped} 个叠加轨片段：白闪/黑场是效果素材，不是切点）")

    bad = 0
    print("\n=== 各段素材内部顺序（必须严格递增）===")
    for src, entries in per_source.items():
        name = pathlib.Path(src).stem[:10]
        seq = [f"{si:.3f}@{tl:.2f}s" for si, tl, _ in entries]
        ok = all(entries[i][0] < entries[i + 1][0] for i in range(len(entries) - 1))
        if not ok:
            bad += 1
            bad_at = [i for i in range(len(entries) - 1)
                      if entries[i][0] >= entries[i + 1][0]]
            print(f"  ✗ {name}: {' < '.join(seq)}")
            for i in bad_at:
                print(f"      ↳ 第 {i + 1}→{i + 2} 次出现回跳："
                      f"{entries[i][0]:.3f} → {entries[i + 1][0]:.3f}"
                      f"（时间轴 {entries[i][1]:.2f}s → {entries[i + 1][1]:.2f}s）")
        else:
            print(f"  ✓ {name}: {' < '.join(seq)}")

    durs = sorted(float(c["duration"]) for c in clips)
    med = durs[len(durs) // 2]
    print(f"\n=== 节奏 ===\n  镜长中位数 {med:.4f}s（参考区间 0.97–2.67s）")
    print(f"  切点密度 {(len(clips) - 1) / timeline * 60:.1f} 切每分（参考区间 20–38）")

    if bad:
        print(f"\n[FAIL] {bad} 段素材存在回跳 —— 这就是用户说的「割裂」。")
        return 1
    print("\n[OK] 所有素材内部单调递增：快切，但不割裂。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
