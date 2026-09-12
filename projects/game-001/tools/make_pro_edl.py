"""从基础 EDL 派生出「高级版」EDL —— 加关键帧推拉、字幕动效、描边阴影。

设计意图：基础版是 4 个**完全静止**的镜头 + 5 条**完全静止**的字幕，这是"简陋"的主因。
本脚本只加**不依赖外部素材下载**或**免费档**的效果：

  · 关键帧（scale / brightness）—— 纯数学，零下载风险，是最稳的一档
  · 字幕入场动画（免费档）—— 有下载风险，但可回退
  · 字幕描边/阴影 —— 纯参数

刻意**不加**滤镜与视频特效：它们依赖素材下载（1042/1087 种里只有约 24% 免费），
先把"确定能生效"的一档做出来，再按需试探高风险档。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\make_pro_edl.py
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

# ---------------------------------------------------------------------------
# 视频片段的动效设计（两版共用，因为两版的 clip 时间线相同）
#
# keyframes 用 (属性, 相对片段起点的秒数, 值) 三元组表示。
# 素材内的高光时刻先换算成"相对片段"的偏移：
#   c3 覆盖 b[5.00, 10.60]；B-H1 在 b 5.40 → 偏移 0.40；B-H2 在 b 8.50 → 偏移 3.50
# ---------------------------------------------------------------------------
CLIP_DESIGN = {
    # 钩子：缓慢推近，制造压迫感（"2 HP" 的紧张感靠推镜强化）
    "c1": {
        "keyframes": [("uniform_scale", 0.00, 1.00), ("uniform_scale", 2.05, 1.12)],
    },
    # 过程：反向缓拉，与 c1 的推近形成呼吸感
    "c2": {
        "keyframes": [("uniform_scale", 0.00, 1.10), ("uniform_scale", 4.40, 1.00)],
    },
    # 高潮：先轻微推近，在击杀播报处（偏移 3.50）做一次"冲击脉冲"，再回落
    "c3": {
        "keyframes": [
            ("uniform_scale", 0.00, 1.00),
            ("uniform_scale", 3.30, 1.04),
            ("uniform_scale", 3.50, 1.14),      # 播报瞬间
            ("uniform_scale", 3.90, 1.02),
            ("uniform_scale", 5.60, 1.06),
            ("brightness", 3.30, 0.00),
            ("brightness", 3.50, 0.10),         # 轻微提亮，强化冲击
            ("brightness", 3.90, 0.00),
        ],
    },
    # 收尾：推向「获胜」横幅
    "c4": {
        "keyframes": [("uniform_scale", 0.00, 1.00), ("uniform_scale", 2.95, 1.12)],
    },
}

# ---------------------------------------------------------------------------
# 字幕动效设计（免费档动画；若剪映报"加载失败"可整条删掉 animation 字段）
# 描边加粗 + 阴影 —— 让字从游戏画面里"跳出来"，这是观感差异最直接的一项
# ---------------------------------------------------------------------------
TEXT_DESIGN = {
    "t1": {"animation": {"intro": "放大", "intro_duration": 0.30}, "big": True},
    "t2": {"animation": {"intro": "弹入", "intro_duration": 0.25}},
    "t3": {"animation": {"intro": "弹入", "intro_duration": 0.25}},
    "t4": {"animation": {"intro": "弹入", "intro_duration": 0.25}},
    "t5": {"animation": {"intro": "弹入", "intro_duration": 0.30}, "big": True},
}

BORDER = {"color": (0.0, 0.0, 0.0), "width": 55.0}
SHADOW = {"color": (0.0, 0.0, 0.0), "diffuse": 18.0, "distance": 6.0, "angle": -45.0}


def build(src_name: str, out_name: str) -> None:
    src = EDL_DIR / src_name
    edl = json.loads(src.read_text(encoding="utf-8"))

    for c in edl["clips"]:
        design = CLIP_DESIGN.get(c["id"])
        if not design:
            continue
        c["keyframes"] = [
            {"property": p, "time": t, "value": v} for (p, t, v) in design["keyframes"]
        ]

    for t in edl["texts"]:
        design = TEXT_DESIGN.get(t["id"], {})
        if design.get("animation"):
            t["animation"] = design["animation"]
        t["border"] = dict(BORDER)
        t["shadow"] = dict(SHADOW)
        if design.get("big"):
            t["border"]["width"] = 70.0

    edl["project"] = edl.get("project", out_name) + "_PRO"
    edl["_pro_derived_from"] = src_name
    edl["_pro_note"] = (
        "高级版：在基础版之上加关键帧推拉/冲击脉冲、字幕入场动画与描边阴影。"
        "刻意不含滤镜与视频特效（它们依赖素材下载，风险高）。"
    )
    out = EDL_DIR / out_name
    out.write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")

    n_kf = sum(len(c.get("keyframes") or []) for c in edl["clips"])
    n_an = sum(1 for t in edl["texts"] if t.get("animation"))
    print(f"  {src_name} -> {out_name}   关键帧 {n_kf} 个 / 字幕动效 {n_an} 条 / 描边阴影 {len(edl['texts'])} 条")


def main() -> int:
    print("=== 生成高级版 EDL ===")
    build("ep01.json", "ep01-pro.json")
    build("ep01-vertical.json", "ep01-pro-vertical.json")
    print()
    print("下一步：")
    print("  .venv\\Scripts\\python.exe .dsh\\skills\\jianying-edit\\scripts\\edl_to_draft.py projects\\game-001\\edl\\ep01-pro.json --dry-run")
    print("  .venv\\Scripts\\python.exe .dsh\\skills\\jianying-edit\\scripts\\edl_to_draft.py projects\\game-001\\edl\\ep01-pro.json --draft-root projects\\game-001\\draft-out --name GAME_EP01_LS_PRO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
