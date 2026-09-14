"""单条素材短片：只剪 `4c58efb4`，把剪映的进阶技巧真正用起来。

## 用户指示
> "我们先从单一的视频剪辑开始吧，你现在仅仅对原始素材里
>  `4c58efb455faef8b4795ba6d6538b54b` 的进行剪辑……
>  这一次你可以学习有没有**开头，结尾动画，转场动画还有击杀突出反馈**之类的技巧。
>  你现在要学会**全面会用剪映的进阶技巧**。"

## 素材分析（`4c58efb4`，38.03s）
自身击杀：**1.433 · 2.100 · 4.667 · 7.333**（前 8 秒 **4 连杀**）……
**19.900 · 20.767**（运动量峰值区，2 连杀）。
中间 8.6→19.0 是**无击杀空档**（10.4s）。

## 结构：**一条连续素材、零剪切**，用「变速」跳过空档
这是本轮最关键的取舍：用户要"不减断、保连贯"，而空档又必须处理。
**变速就是答案** —— 不切，把空档**加速 3 倍**冲过去：

| 段 | 素材 | 速度 | 时间线 | 内容 |
|---|---|---|---|---|
| s1 | 0.30→8.60 | 1.0× | 0→8.30s | **4 连杀** |
| s2 | 8.60→19.00 | **3.0×** | 8.30→11.77s | 空档加速（视觉上像"快进掠过"） |
| s3 | 19.00→22.50 | 1.0× | 11.77→15.27s | **2 连杀** |

**素材从头到尾连续**（0.30→22.50，无跳跃），整片 15.27s。

## 用上的剪映进阶技巧（此前十几版一个都没用）
1. **开场动画** `IntroType.动感放大`（s1）
2. **结尾动画** `OutroType.渐隐`（s3）
3. **转场动画** `TransitionType.闪白`（两个变速接缝，短促）
4. **击杀突出反馈**：
   - 每次击杀叠 `曝光`（0.07s，白闪）
   - 较大的击杀再叠 `震动`（0.15s）
   —— 两者分轨，避免同轨重叠
5. **变速**（3.0× 掠过空档，全片零剪切）
6. 全片统一调色（青橙 + 暗角/噪点/锐化三层）

## BGM
《STYLE》(Hearts2Hearts) 取 15.3s 高能量段 —— 127BPM、当前热门、基调契合。
（本轮联网搜索被限流，未能再筛新曲，沿用已下载的这首。）
"""
from __future__ import annotations

import json
import pathlib
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "projects" / "game-001" / "edl" / "single-4c58efb4.json"
SHORT = "4c58efb4"
SRC = "../../../原始素材/4c58efb455faef8b4795ba6d6538b54b.mp4"
BGM = "../bgm/h2h_style_single.wav"
BGM_VOLUME = 0.80
GAME_VOLUME = 0.32

# (素材入点, 出点, 速度, 角色, 动画)
SEGS = [
    (0.30, 8.60, 1.00, "opening_4kills",
     {"intro": "动感放大", "intro_duration": 0.50}),
    (8.60, 19.00, 3.00, "deadtime_ramp",
     {"intro": "轻微抖动", "intro_duration": 0.25}),
    (19.00, 22.50, 1.00, "closing_2kills",
     {"outro": "渐隐", "outro_duration": 0.60}),
]
# 自身击杀（素材时间）
KILLS = [1.433, 2.100, 4.667, 7.333, 19.900, 20.767]
# 较大的击杀（叠震动）：前 4 连杀里的 2 个 + 收尾 2 个
SHAKE_KILLS = {4.667, 7.333, 19.900, 20.767}

TRANSITION = "闪白"
TRANSITION_DUR = 0.10

GRADE = {"type": "青橙", "intensity": 65.0}
GRADE_LAYERS = [
    ("g_vig",   "暗角",     10.0, "effects_adjust_texture", ["effects_adjust_texture"]),
    ("g_grain", "噪点",      5.0, "effects_adjust_noise",   ["effects_adjust_noise"]),
    ("g_sharp", "精细锐化", 10.0, "effects_adjust_sharpen",
     ["effects_adjust_blur", "effects_adjust_sharpen", "effects_adjust_size",
      "effects_adjust_range", "effects_adjust_filter"]),
]


def _params(effect: str, target: str, value: float, names) -> list:
    from pyJianYingDraft import VideoSceneEffectType
    meta = getattr(VideoSceneEffectType, effect).value
    pmeta = {p.name: p for p in (getattr(meta, "params", None) or [])}
    out = []
    for n in names:
        p = pmeta.get(n)
        if p is None:
            out.append(None)
        elif n == target:
            out.append(value)
        else:
            lo, hi, dv = float(p.min_value), float(p.max_value), float(p.default_value)
            out.append(round((dv - lo) / (hi - lo) * 100.0, 3) if hi > lo else 0.0)
    return out


def build() -> dict:
    clips, t = [], 0.0
    kill_tl: list[float] = []
    for i, (a, b, sp, role, anim) in enumerate(SEGS, 1):
        src_len, dur = b - a, (b - a) / sp
        c = {
            "id": f"s{i}",
            "track": "main",
            "source": SRC,
            "source_in": round(a, 6),
            "start": round(t, 6),
            "duration": round(dur, 6),
            "role": role,
            "rule_id": "SINGLE-ADV-01",
            "reason": (f"第 {i} 段：素材 {a:.2f}→{b:.2f}（{src_len:.2f}s），"
                       f"速度 {sp}× ⇒ 时间线 {dur:.3f}s。"
                       + ("**零剪切跳过无击杀空档**，而不是把它剪掉 —— 保连贯。" if sp != 1.0
                          else "常速，保留完整击杀过程。")),
            "volume": GAME_VOLUME,
            "filter": dict(GRADE),
            "animation": anim,
        }
        if sp != 1.0:
            c["speed"] = sp
        if t > 0:
            c["transition"] = {"type": TRANSITION, "duration": TRANSITION_DUR}
        # 把该段覆盖的击杀映射到时间线
        for k in KILLS:
            if a <= k <= b:
                kill_tl.append((round(t + (k - a) / sp, 6), k in SHAKE_KILLS))
        clips.append(c)
        t += dur

    total = round(t, 6)

    return {
        "version": "1.0",
        "project": "SINGLE_4c58efb4",
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "style_ref": "single-clip-advanced",
        "target_duration_s": total,
        "tracks": [
            {"type": "video", "name": "main"},
            {"type": "audio", "name": "bgm"},
        ],
        "clips": clips,
        "texts": [],
        "audio_overlays": [
            {"source": BGM, "track": "bgm", "start": 0.0, "duration": total,
             "volume": BGM_VOLUME, "fade": {"in": 0.0, "out": 0.5}},
        ],
        "effect_tracks": (
            # 击杀反馈：白闪（每次击杀）
            [{"name": "fx_flash", "effects": [
                {"type": "曝光", "start": kt, "duration": 0.07} for kt, _ in kill_tl]}]
            # 击杀反馈：震动（较大的击杀）
            + [{"name": "fx_shake", "effects": [
                {"type": "震动", "start": kt, "duration": 0.15} for kt, big in kill_tl if big]}]
            # 全片调色三层
            + [{"name": trk, "effects": [
                {"type": ty, "start": 0.0, "duration": total,
                 "params": _params(ty, pname, val, names)}]}
               for (trk, ty, val, pname, names) in GRADE_LAYERS]
        ),
        "audio": {"voice_priority": "low", "bgm_volume": BGM_VOLUME},
        "qa": {"required": ["duration-valid", "audio-present", "no-black-frame"]},
        "_form_note": (f"**单条素材**短片：{SHORT}，{len(clips)} 段 / 零剪切 / {total:.3f}s。"
                       f"用 3.0× 变速跳过无击杀空档，而非剪掉它。"),
        "_advanced_note": ("剪映进阶技巧：开场动画 动感放大 / 结尾动画 渐隐 / "
                           "转场 闪白 ×2 / 击杀反馈 曝光 ×%d + 震动 ×%d / 变速 3.0×"
                           % (len(kill_tl), sum(1 for _, b in kill_tl if b))),
    }


def main() -> int:
    edl = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
    clips = edl["clips"]
    total = sum(c["duration"] for c in clips)
    nfx = sum(len(t["effects"]) for t in edl["effect_tracks"])
    print("=== 单条素材短片（剪映进阶技巧版）===")
    print(f"  [OK] {OUT.relative_to(ROOT)}")
    print(f"       {len(clips)} 段 / 零剪切 / {total:.3f}s")
    print(f"       开场动画 动感放大 ｜ 结尾动画 渐隐 ｜ 转场 闪白 ×2")
    print(f"       击杀反馈特效 {nfx} 个（曝光 + 震动，分轨）｜ 调色三层")
    print(f"       BGM {BGM_VOLUME} ｜ 游戏原声 {GAME_VOLUME} ｜ 字幕 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
