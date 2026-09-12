"""生成「**整段素材块**」结构的集锦。

## 这一版的结构（用户第三次澄清后才定下来）

> "**不要把一个素材的击杀切分之后和别的素材混起来**，
>  保证比如一个素材哪怕剪辑了也是**要连在一起**，
>  因为要符合**从一杀到多杀**的过程。我现在**不强求你卡点**了。"

⇒ 三条硬要求：

1. **同一素材的所有片段必须连在一起**，中间**不得插入别的素材**；
2. 素材内部按**时间顺序**（= 一杀 → 二杀 → 多杀 的过程）；
3. **不卡点** —— 不为对齐拍点去裁画面，**连续性优先**。

之前几版我做的是「轮转交错」（a¹ c¹ b¹ a² c² …），那一开始是为了避免
"三条片子拼接"的观感；但用户要的恰恰相反 —— **素材必须成块**。

## 块内怎么剪
每条素材内，**间隔 ≤ 4.5s 的击杀归为一个连续段**（只有超过 4.5s 没有任何击杀才剔除），
两端留 1.5s 前摇 / 2.5s 收尾，重叠段合并。
⇒ 段与段之间是"长时间没击杀"的空档，属于**该剔除**的部分；
     段内是连续画面，段与段在时间轴上紧挨着放（都来自同一素材、且在素材里就是升序）。

## 块顺序
按**击倒数递增**排（1 杀 → 3 → 4 → 5 → 6 → 8 → 9 → 10 杀），
让全片本身就是"从一杀到多杀"的过程；**收尾固定为含「获胜」横幅的那条素材**。

## 长度
用户："长度没有限制，只要不超过 BGM 最长长度"。
BGM =《STYLE》35.0 → 204.2s（169.2s，在歌曲淡出 205s 之前）。
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
BLOCKS = ROOT / "projects/game-001/analysis2/source_blocks.json"
OUT = ROOT / "projects/game-001/edl/bili-montage.json"
BGM = "../bgm/h2h_style_blocks.wav"
BGM_VOLUME = 0.80        # 比上一版降一点：商业母带 −0.1dBFS + 游戏原声容易冲到 0
GAME_VOLUME = 0.30

GRADE = {"type": "青橙", "intensity": 65.0}
GRADE_LAYERS = [
    ("g_vig",   "暗角",     10.0, "effects_adjust_texture", ["effects_adjust_texture"]),
    ("g_grain", "噪点",      5.0, "effects_adjust_noise",   ["effects_adjust_noise"]),
    ("g_sharp", "精细锐化", 10.0, "effects_adjust_sharpen",
     ["effects_adjust_blur", "effects_adjust_sharpen", "effects_adjust_size",
      "effects_adjust_range", "effects_adjust_filter"]),
]
TRANSITION_TYPE = "信号故障"
TRANSITION_DUR = 0.12     # 每个**块边界**（换素材）放一个，标明"换片源"

COMPACT = {"g_vig": (1,), "g_grain": (1,)}
PARAM_ORDER = {"g_sharp": ("effects_adjust_blur", "effects_adjust_sharpen",
                           "effects_adjust_size", "effects_adjust_range",
                           "effects_adjust_filter")}


def _source_paths() -> dict:
    out = {}
    for p in (ROOT / "原始素材").glob("*.mp4"):
        out[p.stem[:8]] = p.name
    return out


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
    blocks = json.loads(BLOCKS.read_text(encoding="utf-8"))
    paths = _source_paths()

    # 块顺序：击倒数递增；含「获胜」的那条（6b2eea34）固定收尾
    CLOSER = "6b2eea34"
    blocks.sort(key=lambda b: (b["short"] == CLOSER, b["n_kills"], b["short"]))

    clips = []
    t_us = 0
    for bi, b in enumerate(blocks, 1):
        short = b["short"]
        for si, (a, e) in enumerate(b["segs"], 1):
            dur_us = int(round((e - a) * 1e6))
            if dur_us <= 0:
                continue
            # ⚠️ 只有**块的第一个段**才在换素材的接缝上：i>1 or si>1 是错的
            #    （那样几乎每段都为真，27 段全打了转场）。正确条件是 si == 1。
            first = (si == 1)
            clips.append({
                "id": f"b{bi:02d}s{si}",
                "track": "main",
                "source": f"../../../原始素材/{paths[short]}",
                "source_in": round(a, 6),
                "start": round(t_us / 1e6, 6),
                "duration": round(dur_us / 1e6, 6),
                "role": f"block_{short}",
                "rule_id": "MONT-BLOCK",
                "reason": (f"第 {bi} 块（素材 {short}，自身击杀 {b['n_kills']} 个）第 {si}/{len(b['segs'])} 段；"
                           f"素材 {a:.2f}→{e:.2f}s（{dur_us/1e6:.2f}s）。"
                           f"**同素材段落必须连在一起、按时序排列**（用户要求：符合从一杀到多杀的过程）；"
                           f"只剔除了 >4.5s 无击杀的空档；**不卡点**，连续性优先。"),
                "volume": GAME_VOLUME,
                # 每个**块边界**（换素材）放一个转场，块内的段间是"剔除空档"的接缝，也放一个
                "transition": ({"type": TRANSITION_TYPE, "duration": TRANSITION_DUR}
                               if first else None),
            })
            # 段之间的接缝（同一素材内被剔除空档处）不加转场：那是同一素材的连续推进
            if not first:
                clips[-1].pop("transition", None)
            t_us += dur_us

    total = t_us / 1e6
    for c in clips:
        if c.get("transition") is None:
            c.pop("transition", None)

    return {
        "version": "1.0",
        "project": "BILI_BLOCKS_H2H",
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "style_ref": "game-block-highlight",
        "target_duration_s": round(total, 6),
        "tracks": [
            {"type": "video", "name": "main"},
            {"type": "audio", "name": "bgm"},
        ],
        "clips": clips,
        "texts": [],
        "audio_overlays": [
            {"source": BGM, "track": "bgm", "start": 0.0,
             "duration": round(total, 6), "volume": BGM_VOLUME,
             "fade": {"in": 0.0, "out": 0.6}},
        ],
        "effect_tracks": [
            {"name": trk, "effects": [
                {"type": ty, "start": 0.0, "duration": round(total, 6),
                 "params": _params(ty, pname, val, names)}]}
            for (trk, ty, val, pname, names) in GRADE_LAYERS
        ],
        "audio": {"voice_priority": "low", "bgm_volume": BGM_VOLUME},
        "qa": {"required": ["duration-valid", "audio-present", "no-black-frame"]},
        "_form_note": (f"**整段素材块**结构：{len(blocks)} 块（一条素材一块，块内不插别的素材）/ "
                       f"{len(clips)} 段 / {total:.2f}s。块内按素材时序 ⇒ 呈现「一杀→多杀」。"
                       f"**不卡点**（用户明确不再要求），连续性优先。"),
        "_bgm_note": "BGM = Hearts2Hearts《STYLE》35.0→204.2s。⚠️ 商业录音，B站 版权检测可能限流/静音。",
    }


def main() -> int:
    edl = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
    clips = edl["clips"]
    total = sum(c["duration"] for c in clips)
    durs = sorted(c["duration"] for c in clips)
    from collections import Counter
    nb = len(Counter(c["role"] for c in clips))
    print("=== B站 击杀集锦（整段素材块 · Hearts2Hearts《STYLE》）===")
    print(f"  [OK] {OUT.relative_to(ROOT)}")
    print(f"       {nb} 块 / {len(clips)} 段 / {total:.2f}s")
    print(f"       段长 {durs[0]:.2f}–{durs[-1]:.2f}s  中位 {durs[len(durs)//2]:.2f}s")
    print(f"       切点 {len(clips)-1} → {(len(clips)-1)/total*60:.1f} 切每分（块内空档接缝不计转场）")
    print(f"       BGM {BGM_VOLUME}｜游戏原声 {GAME_VOLUME}｜字幕 0｜转场 {sum(1 for c in clips if c.get('transition'))} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
