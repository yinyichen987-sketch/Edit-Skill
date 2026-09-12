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


def build(src_name: str, out_name: str, vertical: bool = False) -> None:
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
    if vertical:
        apply_vertical_framing(edl)
        edl["_framing_note"] = (
            f"竖屏构图修正：canvas_blur 背景填充（blur={CANVAS_BLUR}）+ 画面带放大 "
            f"{BAND_SCALE}x。依据：实测 scale=1.0 = contain，横屏素材直落竖屏画布会留 "
            "2/3 黑边（剪映封面实测 1080x608 画面带 + 上下各 656px 黑）。"
        )
    out = EDL_DIR / out_name
    out.write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")

    n_kf = sum(len(c.get("keyframes") or []) for c in edl["clips"])
    n_an = sum(1 for t in edl["texts"] if t.get("animation"))
    print(f"  {src_name} -> {out_name}   关键帧 {n_kf} 个 / 字幕动效 {n_an} 条 / 描边阴影 {len(edl['texts'])} 条")


def build_hit(src_name: str, out_name: str, vertical: bool = False) -> None:
    """在高级版之上再加「打击重音」：独立特效轨 + 从原素材裁出的音效。

    设计依据（来自专项调研，含来源分级）：
      · **片段特效会作用于整段** → 0.1–0.3s 的打击特效必须走**独立特效轨**
      · 打击点选在「声—画—字」三点对齐处：0.30s(A-H3 高光) / 2.35s(A-H4) /
        9.95s(B-H2 击杀播报，也是字幕 t4 声称的时刻) / 12.05s(获胜横幅)
      · **剪映音效库无法程序化引用**（AudioSegment 只收本地文件）→ 音效由 ffmpeg
        从**原素材**裁出（枪声即 impact，零版权风险）
    """
    src = EDL_DIR / src_name
    edl = json.loads(src.read_text(encoding="utf-8"))

    # ---- 方案A：独立特效轨 ----
    # 注意：同一条轨道上 pyJianYingDraft 用 add_segment 落素材，会做重叠校验，
    # 同一时刻的两个特效不能放同轨 → 9.95s 的「冲击波+闪白」拆到两条轨。
    edl["effect_tracks"] = [
        {
            "name": "fx",
            "effects": [
                {"type": "冲击波",   "start": 0.30,  "duration": 0.20},   # A-H3 高光起点
                {"type": "闪光震动", "start": 2.35,  "duration": 0.15},   # A-H4 起点 = 字幕 t2 入点
                {"type": "冲击波",   "start": 9.95,  "duration": 0.25},   # B-H2 击杀播报
                {"type": "星火炸开", "start": 12.05, "duration": 0.30},   # 获胜横幅
            ],
        },
        {
            "name": "fx2",
            "effects": [
                {"type": "闪白",     "start": 9.95,  "duration": 0.10},   # 与冲击波叠加
            ],
        },
    ]

    # ---- 方案A：音效（从原素材裁出，路径相对 EDL 文件所在目录）----
    edl["audio_overlays"] = [
        {"source": "../sfx/impact_a.wav", "start": 0.30,  "duration": 0.14,
         "volume": 0.90, "fade": {"in": 0.005, "out": 0.04}},
        {"source": "../sfx/impact_b.wav", "start": 9.95,  "duration": 0.14,
         "volume": 1.00, "fade": {"in": 0.005, "out": 0.04}},
        {"source": "../sfx/win.wav",      "start": 12.05, "duration": 0.40,
         "volume": 0.80, "fade": {"in": 0.010, "out": 0.10}},
    ]

    # ---- 方案B：精细运镜（缓动缺失 → 用位移分配假装缓动：进得快、回得慢）----
    hit_kf = {
        "c1": [("uniform_scale", 0.00, 1.00), ("uniform_scale", 0.90, 1.06), ("uniform_scale", 2.05, 1.02)],
        "c2": [("uniform_scale", 0.00, 1.10), ("uniform_scale", 4.40, 1.00)],
        # 让 9.95s 的冲击波打在"画面正在推近"的运动上（静止画面上的特效会像贴纸）
        "c3": [("uniform_scale", 0.00, 1.00), ("uniform_scale", 3.50, 1.05),
               ("uniform_scale", 3.62, 1.14), ("uniform_scale", 4.02, 1.02),
               ("uniform_scale", 5.60, 1.06)],
        "c4": [("uniform_scale", 0.00, 1.00), ("uniform_scale", 2.95, 1.12)],
    }
    for c in edl["clips"]:
        kf = hit_kf.get(c["id"])
        if kf:
            c["keyframes"] = [{"property": p, "time": t, "value": v} for (p, t, v) in kf]

    # ---- 方案B：字幕节奏（克制——15s 里不要两条大字都在跳）----
    hit_text = {
        "t1": {"intro": "弹入", "intro_duration": 0.30, "loop": "跳动"},   # 先入场、后循环
        "t2": {"intro": "弹入", "intro_duration": 0.25},
        "t3": {"intro": "弹入", "intro_duration": 0.25},
        "t4": {"intro": "向上滑动", "intro_duration": 0.25},               # 高潮字幕反而要克制
        "t5": {"intro": "渐显", "intro_duration": 0.35},                   # 收尾要"稳"
    }
    for t in edl["texts"]:
        d2 = hit_text.get(t["id"])
        if d2:
            t["animation"] = d2
        t["border"] = {"color": (0.0, 0.0, 0.0), "width": 70.0 if t["id"] in ("t1", "t5") else 55.0}
        t["shadow"] = {"color": (0.0, 0.0, 0.0), "diffuse": 18.0, "distance": 6.0, "angle": -45.0}

    edl["project"] = edl.get("project", out_name) + "_HIT"
    edl["_hit_derived_from"] = src_name
    edl["_hit_note"] = (
        "打击感版：独立特效轨（冲击波/闪光震动/闪白/星火炸开）+ 从原素材裁出的音效 impact + "
        "精细运镜与字幕节奏。不含滤镜（1052 个里仅 250 个非 VIP 且游戏感滤镜全是 VIP）与蒙版"
        "（剪映 11.4 静默失效）。"
    )
    if vertical:
        apply_vertical_framing(edl)
        edl["_framing_note"] = (
            f"竖屏构图修正：canvas_blur 背景填充（blur={CANVAS_BLUR}）+ 画面带放大 "
            f"{BAND_SCALE}x。依据：实测 scale=1.0 = contain，横屏素材直落竖屏画布会留 "
            "2/3 黑边（剪映封面实测 1080x608 画面带 + 上下各 656px 黑）。"
        )
    out = EDL_DIR / out_name
    out.write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")

    n_eff = sum(len(e["effects"]) for e in edl["effect_tracks"])
    n_kf = sum(len(c.get("keyframes") or []) for c in edl["clips"])
    print(f"  {src_name} -> {out_name}   特效 {n_eff} 个 / 音效 {len(edl['audio_overlays'])} 个 / "
          f"关键帧 {n_kf} 个 / 字幕动效 {sum(1 for t in edl['texts'] if t.get('animation'))} 条")


# ---------------------------------------------------------------------------
# 竖屏构图修正（VT 专属，且是本次最大的一处画面改善）
#
# 【实测事实】剪映里 clip.scale=1.0 表示 **contain（等比装进画布）**。
#   证据：1280x720 素材放进 1080x1920 画布、scale=1.0 时，剪映自己渲染的草稿封面
#   里画面带实测为 1080x608，上下各 656px 纯黑；contain 理论值 1080x607.5，吻合。
#   即：横屏素材直接丢进竖屏画布 → **整整 2/3 的屏幕是黑边**。这是「画面太简陋」的
#   最大单一成因，与特效/关键帧无关 —— 特效再多也补不回 2/3 的黑屏。
#
# 【修法】两层：
#   1. background_filling = canvas_blur —— 用素材自身的放大模糊版填满画布，
#      黑边消失，这是抖音横屏游戏素材最常见的处理，且**零信息损失**。
#   2. 把画面带适度放大（BAND_SCALE），让主体更"顶"。
#
# 【为什么不直接铺满全屏】16:9 → 9:16 要铺满必须裁掉约 68% 的宽度，VALORANT 的
#   小地图（左上）与击杀播报（右上）都在边缘，裁掉就等于毁掉关键信息与证据链。
#   所以这里选择"放大 + 模糊填充"，而不是"裁满"。
# ---------------------------------------------------------------------------
BAND_SCALE = 1.18          # 画面带放大倍数；1.18 → 显示约 1274x717，保留约 85% 宽度
# canvas_blur 的模糊强度只有四档合法值：0.0625(弱) / 0.375(中) / 0.75(强) / 1.0(最强)。
# 这来自 pyJianYingDraft 的 add_background_filling 文档，**不是任意 0-1 连续值**，
# 写别的值剪映不一定认，所以固定用 0.75。
CANVAS_BLUR = 0.75


def apply_vertical_framing(edl: dict, band_scale: float = BAND_SCALE,
                           blur: float = CANVAS_BLUR) -> None:
    """给竖屏 EDL 的所有视频片段补上模糊背景填充与画面带放大。

    ⚠️ **关键：缩放关键帧的值必须一起乘 band_scale。**
    `clip.scale` 与 `KeyframeProperty.scale_x/scale_y` 控制的是**同一个量**（都是绝对缩放
    比例，库里两者都注为"1.0 为不缩放"）。所以一旦片段带缩放关键帧，**关键帧的值会取代
    `clip.scale`** —— 只把 `clip.scale` 设成 1.18 而关键帧仍写 1.00，剪映里就会在关键帧
    区间被拉回 1.0，**构图修正被悄悄吃掉**（而在只看 JSON 的检查里完全看不出来）。
    因此这里把关键帧里的缩放值也一并放大，两处保持一致。

    另外 `uniform_scale` 保持库导出的形态不动：EDL 里用 `uniform_scale` 属性写关键帧时，
    库会把它落成 `property_type: KFTypeScaleX` 而 `uniform_scale.on` 仍为 true ——
    这是库的设计（on=true 表示等比，X 轴关键帧同时作用于两轴），不是缺陷。
    """
    scale_props = {"scale_x", "scale_y", "uniform_scale"}
    for c in edl.get("clips") or []:
        if c.get("track") == "audio":
            continue
        c["background_filling"] = {"type": "blur", "blur": blur}
        c["clip"] = {**({"scale": band_scale} if band_scale != 1.0 else {}),
                     **(c.get("clip") or {})}
        if band_scale != 1.0:
            for kf in c.get("keyframes") or []:
                if kf.get("property") in scale_props:
                    kf["value"] = round(float(kf["value"]) * band_scale, 6)


def main() -> int:
    print("=== 生成高级版 EDL ===")
    build("ep01.json", "ep01-pro.json")
    build("ep01-vertical.json", "ep01-pro-vertical.json", vertical=True)
    print()
    print("=== 生成打击感版 EDL（方案A 特效+音效 / 方案B 精细运镜）===")
    build_hit("ep01.json", "ep01-hit.json")
    build_hit("ep01-vertical.json", "ep01-hit-vertical.json", vertical=True)
    print()
    print("下一步：")
    print("  .venv\\Scripts\\python.exe .dsh\\skills\\jianying-edit\\scripts\\edl_to_draft.py projects\\game-001\\edl\\ep01-hit.json --dry-run")
    print("  .venv\\Scripts\\python.exe .dsh\\skills\\jianying-edit\\scripts\\edl_to_draft.py projects\\game-001\\edl\\ep01-hit.json --draft-root projects\\game-001\\draft-out --name GAME_EP01_LS_HIT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
