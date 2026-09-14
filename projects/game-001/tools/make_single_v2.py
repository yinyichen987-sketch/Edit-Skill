"""单条素材短片 v2：按 skill 知识库的**证据等级**重做。

## 本版相对上一版改了什么（每一条都对应 skill 里的证据）

| 改动 | 依据 | 等级 |
|---|---|---|
| **删掉 `闪白 0.1s` 转场** | `techniques/kill-moment.md` §4 明确列为**「不可用数字」**： 「闪白 0.1 秒」**找不到任何来源** | —— |
| 改用**硬切** | `transitions.md` §1⑧：110s 瓦成片里「**这是唯一贯穿全片的手法**」，>60 灰阶大跳变只有 10 处 | **L1** |
| 切点加 **2 帧黑场** | `transitions.md` §3.3：33ms(1帧) 只够"藏一个切点"，167/667ms 才是"断开"。取 33–67ms 档 | **L1** |
| 击杀叠 **2 帧白闪** | `kill-moment.md` Q5：白闪中位 **50–167ms**，最常见 **33/67/133ms**；且§3 说"**要引用时长优先引用这一档**" | **L1** |
| 白闪做成**素材**而非调亮度 | `kill-moment.md` §1：做法 = **媒体 → 官方素材 → 白场**（是素材） | **L2** |
| 击杀反馈特效换成**瞬间模糊 + 回弹摇摆** | `kill-moment.md` §1 抖动行；`瞬间模糊` 出自曝光击杀特效教程 `BV11hdSYcENH` | **L2** |
| 不再用「交叉闪震」 | 实测该名**不存在**；真名是「**交叉震闪**」且 **VIP** | —— |
| **曲线变速交人工** | `operations.md` §3.4：曲线变速「**❌ 未表达**（只有恒速 speed）」。它是看家手法（闪进 0.1×，L2，4 个教程一致），**不能假装做了** | **L2** |

## 保留的（上一版已验证有效的）
- **零剪切 + 3.0× 变速跳过无击杀空档**（素材 0.30→22.50 连续不断）
- 开场动感放大 / 结尾渐隐（**L4：本项目策略**，不是通用手法，故标注）

## 时间线
| 段 | 素材 | 速度 | 时间线 |
|---|---|---|---|
| s1 | 0.30→8.60 | 1.0× | 0→8.300 |
| s2 | 8.60→19.00 | 3.0× | 8.300→11.767 |
| s3 | 19.00→22.50 | 1.0× | 11.767→15.267 |

击杀（素材时间 → 时间线时间）：1.433→1.133 · 2.100→1.800 · 4.667→4.367 ·
7.333→7.033 · 19.900→12.667 · 20.767→13.534
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
OUT = ROOT / "projects" / "game-001" / "edl" / "single-4c58efb4-v2.json"
SRC = "../../../原始素材/4c58efb455faef8b4795ba6d6538b54b.mp4"
BGM = "../bgm/h2h_style_single.wav"
WHITE = "../assets/white_2f.mp4"      # 2 帧白场（67ms，L1 实测档）
BLACK = "../assets/black_2f.mp4"      # 2 帧黑场（67ms，用于藏切点）
BGM_VOLUME = 0.80
GAME_VOLUME = 0.32

SEGS = [
    (0.30, 8.60, 1.00, "opening_4kills", {"intro": "动感放大", "intro_duration": 0.50}),
    (8.60, 19.00, 3.00, "deadtime_ramp", {"intro": "轻微抖动", "intro_duration": 0.25}),
    (19.00, 22.50, 1.00, "closing_2kills", {"outro": "渐隐", "outro_duration": 0.60}),
]
KILLS = [1.433, 2.100, 4.667, 7.333, 19.900, 20.767]
# 白闪只压在"较大的击杀"上，避免 15 秒里闪 6 次
FLASH_KILLS = {4.667, 7.333, 19.900, 20.767}

FLASH_DUR = 0.0667      # 2 帧 @30fps —— L1 实测白闪档（33/67/133ms）
BLACK_DUR = 0.0667      # 2 帧黑场 —— 藏在 ±(33~600ms) 区间内，用于藏切点

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
    kill_tl: list[tuple[float, bool]] = []
    seams: list[float] = []

    for i, (a, b, sp, role, anim) in enumerate(SEGS, 1):
        dur = (b - a) / sp
        if t > 0:
            seams.append(round(t, 6))
        c = {
            "id": f"s{i}", "track": "main", "source": SRC,
            "source_in": round(a, 6), "start": round(t, 6), "duration": round(dur, 6),
            "role": role, "rule_id": "SINGLE-ADV-02",
            "reason": (f"第 {i} 段：素材 {a:.2f}→{b:.2f}（{b-a:.2f}s），速度 {sp}× ⇒ 时间线 "
                       f"{dur:.3f}s。切点用**硬切**（transitions.md 实测：瓦成片贯穿全片的手法就是硬切，"
                       f">60 灰阶大跳变仅 10 处）；"
                       + ("本段是**变速掠过无击杀空档**，而非剪掉它。" if sp != 1.0 else "常速保留完整击杀过程。")),
            "volume": GAME_VOLUME, "filter": dict(GRADE), "animation": anim,
        }
        if sp != 1.0:
            c["speed"] = sp
        for k in KILLS:
            if a <= k <= b:
                kill_tl.append((round(t + (k - a) / sp, 6), k in FLASH_KILLS))
        clips.append(c)
        t += dur

    total = round(t, 6)

    # ⚠️ 白场/黑场是**素材**（kill-moment.md §1：做法 = 媒体→官方素材→白场），
    #    所以它们是**视频叠加片段**，必须放进 `clips` 并带 `track` 字段。
    #    用自定义键（如 `overlays`）不会报错但会被转换器**静默丢弃**。
    for n, (kt, big) in enumerate([(k, b) for k, b in kill_tl if b], 1):
        if True:
            clips.append({
                "id": f"w{n}", "track": "ovl_white", "source": WHITE,
                "source_in": 0.0,
                "start": max(0.0, round(kt - FLASH_DUR / 2, 6)),
                "duration": FLASH_DUR,
                "role": "flash_white", "rule_id": "SINGLE-ADV-02",
                "reason": (f"击杀反馈：**2 帧白场素材**压在击杀 {kt:.3f}s 上。"
                           f"时长取 2 帧(67ms) —— kill-moment.md Q5 实测白闪中位 50–167ms、"
                           f"最常见 33/67/133ms，且 §3 明确'要引用时长优先引用这一档'。"
                           f"做法用**素材**而非调亮度（§1：官方素材→白场）。"),
                "volume": 0.0,
            })
    for n, st in enumerate(seams, 1):
        clips.append({
            "id": f"b{n}", "track": "ovl_black", "source": BLACK,
            "source_in": 0.0,
            "start": max(0.0, round(st - BLACK_DUR / 2, 6)),
            "duration": BLACK_DUR,
            "role": "hide_cut_black", "rule_id": "SINGLE-ADV-02",
            "reason": (f"藏切点：**2 帧黑场素材**压在变速接缝 {st:.3f}s 上。"
                       f"transitions.md §3.3 实测黑场三档 33/167/667ms，"
                       f"'想要隐形就取 1 帧'；这里取 2 帧(67ms) 仍在藏切点档内。"),
            "volume": 0.0,
        })

    return {
        "version": "1.0", "project": "SINGLE_4c58efb4_V2",
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "style_ref": "single-clip-advanced",
        "target_duration_s": total,
        "tracks": [
            {"type": "video", "name": "main"},
            {"type": "video", "name": "ovl_black"},
            {"type": "video", "name": "ovl_white"},
            {"type": "audio", "name": "bgm"},
        ],
        "clips": clips,
        "texts": [],
        "audio_overlays": [
            {"source": BGM, "track": "bgm", "start": 0.0, "duration": total,
             "volume": BGM_VOLUME, "fade": {"in": 0.0, "out": 0.5}},
        ],
        "effect_tracks": (
            [{"name": "fx_flash", "effects": [
                {"type": "曝光", "start": kt, "duration": 0.07} for kt, _ in kill_tl]}]
            + [{"name": "fx_blur", "effects": [
                {"type": "瞬间模糊", "start": kt, "duration": 0.13}
                for kt, big in kill_tl if big]}]
            + [{"name": "fx_shake", "effects": [
                {"type": "回弹摇摆", "start": kt, "duration": 0.20}
                for kt, big in kill_tl if big]}]
            + [{"name": trk, "effects": [
                {"type": ty, "start": 0.0, "duration": total,
                 "params": _params(ty, pname, val, names)}]}
               for (trk, ty, val, pname, names) in GRADE_LAYERS]
        ),
        "audio": {"voice_priority": "low", "bgm_volume": BGM_VOLUME},
        "qa": {"required": ["duration-valid", "audio-present", "no-black-frame"]},
        "_form_note": (f"**单条素材**短片 v2：4c58efb4，{len(clips)} 段 / 零剪切 / {total:.3f}s。"
                       f"硬切为主；白闪×{sum(1 for _,b in kill_tl if b)}（2帧素材）/ "
                       f"黑场×{len(seams)}（2帧素材）压在接缝上。"),
        "_unsourced_removed": "已移除「闪白 0.1 秒」—— kill-moment.md §4 列为零来源数字。",
        "_manual": ["曲线变速（闪进 0.1×）—— EDL 未表达，见 operations.md §3.4",
                    "切口两侧 2 帧音频交叉淡化（防咔哒声）",
                    "如需动效模糊盖切口，用调整层 + transform keyframe"],
    }


def main() -> int:
    edl = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(c["duration"] for c in edl["clips"])
    nfx = sum(len(t["effects"]) for t in edl["effect_tracks"])
    print("=== 单条素材 v2（按知识库证据等级重做）===")
    print(f"  [OK] {OUT.relative_to(ROOT)}")
    n_ovl = sum(1 for c in edl['clips'] if c['track'].startswith('ovl'))
    print(f"       {len(edl['clips']) - n_ovl} 个主轨段 / 零剪切 / {total:.3f}s")
    print(f"       视频叠加片段 {sum(1 for c in edl['clips'] if c['track'].startswith('ovl'))} 条（白闪 + 黑场，都是素材法）")
    print(f"       特效轨 {len(edl['effect_tracks'])} 条 / {nfx} 个特效")
    print(f"       转场：**已移除**（改用硬切 + 2 帧黑场）")
    print(f"       人工待办：{len(edl['_manual'])} 项（曲线变速 / 音频交叉淡化 / 动效模糊）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
