"""按实测口径重标定字幕字号，并换上真实的抖音向字体。

## 为什么必须改：原字号小了约 3 倍

`format-spec.md` 把「钩子=72px / 过程=56px」当作设计字号写进 EDL 的 `style.size`
（钩子 6.0、过程 5.0），但**剪映的 `size` 不是像素**，换算关系此前被登记为「已声明缺口」（§13）。

本轮把它测出来了 —— 用的是**剪映自己渲染的草稿封面**（不是猜、不是抄文档）：

`DSH_SPIKE_TEST` 草稿用的是 pyJianYingDraft 的**默认字号 8.0**，文案 `DSH SPIKE 测试字幕`
（8 个拉丁大写 + 2 空格 + 4 汉字）。对剪映回存的 `draft_cover.jpg`（1080x1920）做像素测量：

| 量 | 实测 | 由 em 反推 |
|---|---|---|
| 文字 ink 高度 | **43 px** | 汉字近满格 ≈ 0.97 em → em ≈ 44.4 |
| 文字总宽度 | **456 px** | 0.72·8 + 0.26·2 + 1.0·4 = 10.28 em → em ≈ 44.4 |

两个独立量**同时收敛到 em ≈ 44.4px**，故：

```
em_px ≈ 5.55 × size          （1080x1920 画布）
```

**同时被证伪的假设**：`px = size/100 × 画布高`（会得 8.0 → 153.6px）。若成立，
该字符串需要约 1470px 宽，而画面只有 1080px —— **物理上放不下**，故该假设排除。
（此假设由调研提出，本测量否定之。）

**结论**：原 `size=5.0/6.0` 实际只有 **≈28/33px**，占画布高 1.5–1.7%；
而竖屏短视频字幕的目标字高是画布高的 **6–7%（115–134px）**。**原设计小了约 3–4 倍**
——这是「画面太简陋」在文字侧的真正成因。

## 改法

字号按**目标 em ≈ 90–130px** 反推，并**逐条按字数校核不超画布宽**
（`宽度 ≈ (拉丁×0.72 + 汉字/全角标点×1.0) × em ≤ 0.92 × 画布宽`）。

字体：原稿没指定字体 → 落到剪映默认字体。改为**非 VIP** 的真实字体
（`is_vip=False` 已逐个核对）：钩子/收尾用 **得意黑**（抖音向标题向），
过程字幕用 **未来黑**（干净黑体，长句更耐读）。依据是调研结论：
「标题用展示体、正文用黑体」是电竞向的通行分工。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\apply_caption_recalibration.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[3]
EDL_DIR = ROOT / "projects" / "game-001" / "edl"

EM_PER_SIZE = 5.55          # 实测：em_px ≈ 5.55 × size
MAX_WIDTH_FRACTION = 0.92   # 单行最宽不超过画布宽的 92%

# 逐条设计：目标字号 + 字体。字号已按字数校核过不超宽（见文件末尾自检）。
DESIGN = {
    # ---- 竖屏 1080x1920：目标 em 90-130px ----
    "ep01-vertical.json": {
        "title_font": "得意黑",
        "body_font": "未来黑",
        "sizes": {"t1": 24.0, "t2": 17.0, "t3": 20.0, "t4": 18.0, "t5": 17.0},
        "note": ("竖屏字幕重标定：em≈5.55×size（剪映封面实测）。t1/t5 用得意黑（标题向），"
                 "t2-t4 用未来黑（正文耐读）。字号按目标字高 94-133px 反推，"
                 "并逐条校核单行不超画布宽 92%。"),
    },
    # ---- 横屏 1920x1080：字幕只能叠在游戏画面上，目标字高 4.5-5.5% 画布高 ≈ 49-59px ----
    "ep01.json": {
        "title_font": "得意黑",
        "body_font": "未来黑",
        "sizes": {"t1": 12.0, "t2": 9.0, "t3": 10.0, "t4": 9.0, "t5": 9.0},
        "note": ("横屏字幕重标定：目标字高取画布高的 4.5-5.5%（≈49-66px）。"
                 "横屏没有信息区可放字，字幕叠在画面上，故比竖屏小一档。"),
    },
}


def width_em(text: str) -> float:
    """按字宽模型估行宽（单位：em）。拉丁大写 0.72、空格 0.26、汉字与全角标点 1.0。"""
    total = 0.0
    for ch in text:
        if ch == " ":
            total += 0.26
        elif ord(ch) < 128:
            total += 0.72
        else:
            total += 1.0
    return total


def main() -> int:
    rc = 0
    for fname, cfg in DESIGN.items():
        path = EDL_DIR / fname
        edl = json.loads(path.read_text(encoding="utf-8"))
        W = int(edl["canvas"]["width"])
        budget = MAX_WIDTH_FRACTION * W

        print(f"=== {fname}  画布 {W}x{int(edl['canvas']['height'])}  单行宽度上限 {budget:.0f}px ===")
        for t in edl["texts"]:
            tid = t["id"]
            size = cfg["sizes"][tid]
            em = EM_PER_SIZE * size
            is_title = tid in ("t1", "t5")
            font = cfg["title_font"] if is_title else cfg["body_font"]
            w = width_em(t["content"]) * em
            ok = w <= budget
            if not ok:
                rc = 1
            t["style"]["size"] = size
            t["style"]["font"] = font
            # 位置不动：字号变大后字框变高，必须复核是否仍在安全带内
            print(f"  {tid} size={size:>5}  em={em:6.1f}px  行宽={w:6.0f}px  "
                  f"{'OK ' if ok else '超宽!'}  字体={font}  {t['content']!r}")

        edl["_caption_note"] = cfg["note"]
        path.write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> 已写回 {path.name}\n")

    if rc:
        print("[FAIL] 有字幕行超出画布宽上限，需要缩字号或拆行。")
    else:
        print("[OK] 全部字幕行宽在预算内。")
        print("     下一步：复核字框是否仍在各画布的安全带内（运行 check_caption_pixels.py）")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
