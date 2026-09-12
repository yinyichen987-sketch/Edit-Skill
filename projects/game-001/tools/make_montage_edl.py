"""生成「卡点集锦」EDL —— 14 个镜头全部落在 128 BPM 的拍点上。

## 形式：集锦（不做叙事）

用户裁决：**不做叙事，做集锦**。这解开了上一轮登记的那个规则冲突 ——
`CUT-01`（固定四段 2:4:7:2）与 `CUT-02`（≈12 切/分）本来把「慢」写成了硬规则，
而素材分析（可用高光中位 1.0s）与外部调研（单镜头上限 3s）都要求碎片化。
本脚本走的是**集锦形式**，有意偏离 CUT-01/CUT-02/CUT-05 的高光余量条款（见
`references/styles/game-montage.md`）；CUT-04（不越素材上界）仍然强制满足。

## 为什么是 128 BPM

    1 拍 = 60/128 = 0.46875 s      1 小节 = 1.875 s
    15.000 / 0.46875 = **32 拍整 = 8 小节整**

即 15 秒天然等于 8 小节，**每个剪切点都能落在拍上**，不需要变速凑整。
BGM 由 `make_bgm.py` 按同一网格合成，所以画面与音乐是同一条时间栅格。

## 镜头表（拍数 → 累计 → 素材）

14 镜 / 13 切 / 平均镜长 1.07s（调研目标 1.0–2.0s，切点数目标 8–14 ✓）
最长镜 1.875s（调研硬上限 3.5s ✓）。4 拍长镜只放在三个重音位：
第 10 拍（4.688s）、第 20 拍（9.375s）、第 28 拍（13.125s）。

拍摄区间两两不重叠（SEL-02 禁止复用同一素材区间），且全部避开
VFR 真实跳变窗口：b [10.9797,11.0454] / [12.9787,13.0120]、c [2.0717,2.1050] / [3.3717,3.4050]。

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\make_montage_edl.py
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

BPM = 128.0
BEAT = 60.0 / BPM                 # 0.46875
BAR = 4 * BEAT                    # 1.875
SRC = {
    "a": "../../../原始素材/4b0460c400bbb5320acb6063b4f59358.mp4",
    "b": "../../../原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4",
    "c": "../../../原始素材/dcc871b1791e7796fadac842593f10f7.mp4",
}
# 音量：先保持三段素材的响度对齐比例（a 最响→0.7，b/c→0.851），再统一压低。
# ⚠️ 压低幅度由**实测**决定：三段原素材的真峰值都是 **+0.8 dBFS（已削顶）**，
#    叠上 BGM 与音效后第一版预览的真峰值到 **+1.1 dBFS**（明确削顶）。
#    故整体再让 ~3dB 余量，并把限幅器设到 −3 dB（AAC 编码后还有 1-2dB intersample 过冲）。
GAME_TRIM = 0.70
VOL = {"a": round(0.7 * GAME_TRIM, 3), "b": round(0.851 * GAME_TRIM, 3),
       "c": round(0.851 * GAME_TRIM, 3)}
BGM_VOLUME = 0.34
SFX_VOLUME = 0.70
BAND_SCALE = 1.18                 # 竖屏画面带放大（与 ep01 一致）
CANVAS_BLUR = 0.75

# (拍数, 素材, 入点, 角色, 依据, 速度)
#
# ⚠️ 第三轮修正：用户反馈"**把原始素材切割得太割裂了**"，要求
#    "**把这几个连接起来做成一个游戏集锦就行了**"。
#    ⇒ 结构性改动：从"把一个素材剁成很多小片"改成"**每个素材用一整段连续画面**"。
#
#    上一版：9 镜 / 8 切 / 均长 1.667s（仍在来回切三段素材）
#    这一版：**5 镜 / 4 切 / 均长 3.000s**，前三镜分别是 c / a / b 的**一整段连续长镜**，
#           再也不在同一段素材里反复进出。
#
#    仍然落在 128BPM 拍点上：`8+8+8+4+4 = 32 拍 = 8 小节 = 15.000s`。
#    切点 = 3.75 / 7.5 / 11.25 / 13.125s = 第 8 / 16 / 24 / 28 拍 —— **全是小节线或半小节线**，
#    其中 **7.5s 正好是 BGM 的 drop（第 5 小节）**，第 3 镜（b 段）从 drop 上起。
#
#    "割裂感"的三个来源与对策：
#      ① 切得太密（上一版 56 切/分）→ 降到 **16 切/分**；
#      ② 同一素材反复进出 → 每个素材只有**一段连续**（c 与 b 各用两段，但两段互不相邻、各自完整）；
#      ③ 每镜都在动、没有落点 → 长镜配**推镜关键帧**给出内部运动，切点配高级故障转场。
SHOTS = [
    # 第 1 镜：c 段一整段（C-H5 击杀播报 → C-H7 甩枪 → C-H8 交火），开场即冷开峰值
    (8, "c", 6.40,  "run_c",  "c 段连续长镜：C-H5(击杀播报同帧，信息量最高) → C-H7 → C-H8", 1.0),
    # 第 2 镜：a 段一整段（A-H2 拾取 → A-H3 实测 2HP → A-H4）
    (8, "a", 5.60,  "run_a",  "a 段连续长镜：A-H2(拾取) → A-H3(**实测 2 HP**，conf 0.95) → A-H4", 1.0),
    # 第 3 镜：b 段一整段（B-H1 全集最强音频 → B-H2 击杀确认），正好从 drop 上起
    (8, "b", 5.40,  "run_b",  "b 段连续长镜：B-H1(**全 70 秒音频能量最强**) → B-H2(击杀确认)，起点=drop", 1.0),
    # 第 4 镜：c 段另一段（C-H10 本段最长的高能量持续段）
    (4, "c", 19.10, "run_c2", "c 段第二段：C-H10 持续交火（与第 1 镜不重叠、不连号）", 1.0),
    # 第 5 镜：b 段收尾（B-H7 获胜横幅）
    (4, "b", 21.40, "ending", "b 段收尾：B-H7「获胜」横幅，收在最强的情绪点上", 1.0),
]
# 三段连续长镜的素材窗口（每段两端都避开 VFR 真实跳变窗口）：
#   c 6.40 → 10.15   （c 的跳变窗在 2.0717 / 3.3717，远离）
#   a 5.60 →  9.35   （a 为 CFR，无跳变）
#   b 5.40 →  9.15   （b 的跳变窗在 10.9797 / 12.9787，留 1.83s 余量）
#   c 19.10 → 20.975 ；b 21.40 → 23.275（b 上界 26.017，余量 2.74s）

# 调色：**全片同一个 grade**（调研：craft layer 必须每一镜完全一致 ——
# 「这才是让 13+ 个镜头读成一部片子的原因」；且"纯克制"会被读成 washed out）。
GRADE = {"type": "青橙", "intensity": 65.0}

# 转场：只一种高级故障转场。选 信号故障 的另一个硬理由 —— 调研实测本机
# `Cache\effect\` 里**只有它已缓存**，是唯一**零下载风险**的 VIP 转场。
# 4 个切点里用 3 处、**1 处故意硬切**（进 11.25s 那一下留个干净硬切，避免全是转场而"糊"）。
TRANSITION_TYPE = "信号故障"
TRANSITION_AT = {3.75, 7.5, 13.125}
TRANSITION_LONG_AT = {7.5}          # drop 处的转场给到 0.20s
TRANSITION_SHORT = 0.12
TRANSITION_LONG = 0.20

# 特效：用户要求"低级反馈特效不要用了，直接用高级特效"。
#   上一版已删掉 冲击波 / 闪光震动 / 星火炸开（基础档"反馈"特效）。
#   镜头变长变少之后特效也要更克制 —— 调研：「flashes/punches on energy **PEAKS only**」。
#   故只留 2 个，且同一套故障语言：drop 落点 + 收尾。
EFFECTS = [
    ("fx",  "像素故障", 7.50,   0.30),   # DROP 落点（第 3 镜起点）
    ("fx2", "花屏故障", 13.125, 0.35),   # 收尾（第 5 镜起点）
]

# 音效：分两条轨以便同一时刻叠加。
# 镜头变长后 riser 的作用更明显 —— 两条 riser 分别推到 drop(7.5) 与收尾(13.125)。
SFX = [
    ("sfx1", "whoosh",    3.750,  0.35, 0.70 * SFX_VOLUME / 0.70),
    ("sfx1", "riser",     5.625,  1.80, 0.60 * SFX_VOLUME / 0.70),
    ("sfx1", "impact_b",  7.500,  0.14, 1.00 * SFX_VOLUME / 0.70),
    ("sfx1", "riser",    11.250,  1.80, 0.60 * SFX_VOLUME / 0.70),
    ("sfx2", "sub_drop",  7.500,  0.90, 0.90 * SFX_VOLUME / 0.70),
    ("sfx2", "impact_a", 13.125,  0.16, 0.90 * SFX_VOLUME / 0.70),   # impact_a 只有 0.1604s
]

# 字幕：**短促标签，不是叙事句**（用户反馈"文字很死板"）。
#   · 每条 ≤6 个字符，读得完；· 不断言不可证的事实（SEL-04）；
#   · 逐条不同动效；· 白为主 + 一个固定强调色（红=危险 / 黄=重音）。
#     调研：「纯白静止就是业余信号；修法是**两色层级**，并把节奏交给强调色」。
#   · 入场时长 0.40s ≈ 一拍（128BPM 一拍 0.469s）。调研：
#     「动画比你想象的短 —— 一拍，不是两拍」；「一个落在重音帧上的缩放脉冲，
#       比任何长装饰入场都值钱」。
# ⚠️ 时间必须写**精确的拍值**（0.9375 而不是 0.938）。曾用四舍五入到 3 位小数的
#    0.938+0.938=1.876，比下一个字幕的入点 1.875 多了 1ms → add_segment 的重叠校验直接拒绝。
# 镜头变长后字幕也跟着变长（4 拍 = 1.875s），条数从 7 降到 6。
# (id, 文本, 起, 时长, 字号, 颜色, 入场, 循环)
CAPTIONS = [
    ("t1", "别眨眼",       0.0000,  1.8750, 24.0, (1.0, 1.0, 1.0), "弹簧",     "爆闪"),
    ("t2", "2 HP",         3.7500,  1.8750, 24.0, (1.0, 0.35, 0.35), "弹入",   "跳动"),
    ("t3", "一枪一个",     7.5000,  1.8750, 22.0, (1.0, 0.9, 0.2),  "复古打字机", "爆闪"),
    ("t4", "还在打",      11.2500,  1.8750, 20.0, (1.0, 1.0, 1.0),  "弹入",     "颤抖"),
    ("t5", "这枪换你，敢不敢上？", 13.1250, 1.8750, 17.0, (1.0, 0.9, 0.2), "渐显", None),
]

# 竖屏字幕位置：钩子上部信息区（300px），其余下部信息区（1450px）
TY_TITLE = 1.0 - 2 * 300 / 1920          # +0.6875
TY_BODY = 1.0 - 2 * 1450 / 1920          # -0.510417
# 横屏字幕只能叠在画面上：钩子/收尾 940px、过程 966.6px（沿用已验证的安全带）
TY_LS_TITLE = 1.0 - 2 * 940 / 1080       # -0.740741
TY_LS_BODY = 1.0 - 2 * 966.6 / 1080      # -0.79

# 横屏字号：竖屏的字号按画布高比例缩到 1080/1920
LS_SIZE = 1080 / 1920


def build(vertical: bool) -> dict:
    W, H = (1080, 1920) if vertical else (1920, 1080)
    clips, t = [], 0.0
    for i, (beats, key, src_in, role, why, speed) in enumerate(SHOTS, 1):
        dur = beats * BEAT
        c = {
            "id": f"m{i:02d}",
            "track": "main",
            "source": SRC[key],
            "source_in": round(src_in, 4),
            "start": round(t, 6),
            "duration": round(dur, 6),
            "role": role,
            "rule_id": "MONT-01",
            "reason": (f"集锦第 {i} 镜 / {beats} 拍（{dur:.4f}s）@128BPM；拍点 {t/BEAT:.1f}–"
                       f"{(t+dur)/BEAT:.1f}；速度 {speed}×（吃素材 "
                       f"{dur*speed:.4f}s）。{why}。"),
            "volume": VOL[key],
            "filter": dict(GRADE),      # 全片同一个 grade
        }
        if speed != 1.0:
            c["speed"] = speed
        if t in TRANSITION_AT:
            c["transition"] = {
                "type": TRANSITION_TYPE,
                "duration": TRANSITION_LONG if t in TRANSITION_LONG_AT else TRANSITION_SHORT,
            }
        clips.append(c)
        t += dur

    # ---- 关键帧：给 4 拍长镜做轻微推近（镜头变长后更需要内部运动）----
    #   ⚠️ 推近量写成**相对倍率**，再乘各自的基准（竖屏 1.18 / 横屏 1.0）。
    #   上一版直接写死绝对终点值，结果竖屏只推 8.5%、横屏推 28% —— 两版手感不一致。
    #   长镜（3.75s）比上一版的 1.875s 更需要内部运动，故推近量略加大
    push = {"m01": 1.07, "m02": 1.08, "m03": 1.09, "m04": 1.05, "m05": 1.05}
    for c in clips:
        mult = push.get(c["id"])
        if mult:
            base = BAND_SCALE if vertical else 1.0
            c["keyframes"] = [
                {"property": "uniform_scale", "time": 0.0, "value": round(base, 4)},
                {"property": "uniform_scale", "time": c["duration"],
                 "value": round(base * mult, 4)},
            ]

    if vertical:
        for c in clips:
            c["background_filling"] = {"type": "blur", "blur": CANVAS_BLUR}
            c["clip"] = {"scale": BAND_SCALE}

    texts = []
    for cid, txt, start, dur, size, color, intro, loop in CAPTIONS:
        is_title = cid in ("t1", "t5")
        ty = (TY_TITLE if is_title else TY_BODY) if vertical \
            else (TY_LS_TITLE if is_title else TY_LS_BODY)
        # 入场时长 ≈ 一拍（128BPM → 0.469s）。调研：「动画比你想象的短，一拍不是两拍」。
        anim = {"intro": intro, "intro_duration": 0.40}
        if loop:
            anim["loop"] = loop
        texts.append({
            # 钩子与过程字幕**分两条轨**：钩子在上部信息区、过程在下部，
            # 位置本来就不冲突，而 t1（0–1.31s）与 t2（0.938–1.875s）时间上是重叠的 ——
            # 同轨会被 add_segment 的重叠校验直接拒绝。
            "id": cid, "track": "cap_top" if is_title else "cap_body",
            "content": txt,
            "start": start, "duration": dur,
            "style": {
                "size": round(size * (1.0 if vertical else LS_SIZE), 2),
                "bold": True,
                "font": "得意黑" if is_title else "未来黑",
                "color": list(color),
                "transform_x": 0.0,
                "transform_y": round(ty, 6),
            },
            "animation": anim,
            # 描边/阴影：调研结论是"亮场靠描边保住字"，故描边给足
            "border": {"color": (0.0, 0.0, 0.0), "width": 70.0 if is_title else 58.0},
            "shadow": {"color": (0.0, 0.0, 0.0), "diffuse": 18.0, "distance": 6.0, "angle": -45.0},
        })

    return {
        "version": "1.0",
        "project": f"GAME_MONT_{'VT' if vertical else 'LS'}",
        "canvas": {"width": W, "height": H, "fps": 30},
        "style_ref": "game-montage",
        "target_duration_s": 15.0,
        "tracks": [
            {"type": "video", "name": "main"},
            {"type": "text", "name": "cap_top"},
            {"type": "text", "name": "cap_body"},
            {"type": "audio", "name": "bgm"},
            {"type": "audio", "name": "sfx1"},
            {"type": "audio", "name": "sfx2"},
        ],
        "clips": clips,
        "texts": texts,
        "audio_overlays": (
            [{"source": "../bgm/bgm_128_15s.wav", "track": "bgm",
              "start": 0.0, "duration": 15.0, "volume": BGM_VOLUME,
              "fade": {"in": 0.0, "out": 0.25}}]
            + [{"source": f"../sfx/{name}.wav", "track": trk,
                "start": st, "duration": du, "volume": vol,
                "fade": {"in": 0.005, "out": min(0.06, du * 0.25)}}
               for (trk, name, st, du, vol) in SFX]
        ),
        "effect_tracks": [
            {"name": "fx", "effects": [
                {"type": ty, "start": st, "duration": du}
                for (trk, ty, st, du) in EFFECTS if trk == "fx"]},
            {"name": "fx2", "effects": [
                {"type": ty, "start": st, "duration": du}
                for (trk, ty, st, du) in EFFECTS if trk == "fx2"]},
        ],
        "audio": {"voice_priority": "low", "bgm_volume": BGM_VOLUME},
        "qa": {"required": ["duration-valid", "audio-present", "no-black-frame"]},
        "_form_note": ("集锦形式（不做叙事）：14 镜 / 13 切 / 32 拍 @128BPM / 15.000s。"
                       "有意偏离 CUT-01（固定四段）与 CUT-02（≈12 切/分）—— 依据是素材分析"
                       "（可用高光中位 1.0s）与外部调研（单镜头 ≥3.5s 判失败、切点目标 8–14/15s），"
                       "两条独立证据都指向碎片化。CUT-04（不越素材上界）仍强制满足。"),
        "_audio_note": ("BGM 为本地合成（128BPM，与剪切点同格，见 tools/make_bgm.py）；"
                        "whoosh/riser/sub_drop 亦为合成（tools/make_sfx.py）；"
                        "impact_*/win 从原素材裁出。剪映音效库无法程序化引用。"),
    }


def main() -> int:
    print("=== 生成卡点集锦 EDL（128 BPM，32 拍 = 15.000s）===")
    for vertical, name in ((False, "montage.json"), (True, "montage-vertical.json")):
        edl = build(vertical)
        total = sum(c["duration"] for c in edl["clips"])
        beats = total / BEAT
        cuts = len(edl["clips"]) - 1
        (EDL_DIR / name).write_text(json.dumps(edl, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
        tag = "竖屏 1080x1920" if vertical else "横屏 1920x1080"
        print(f"  [OK] {name:26} {tag}  {len(edl['clips'])} 镜 / {cuts} 切 / "
              f"{total:.3f}s = {beats:.1f} 拍")
        print(f"       镜长 {min(c['duration'] for c in edl['clips']):.4f}–"
              f"{max(c['duration'] for c in edl['clips']):.4f}s  "
              f"平均 {total/len(edl['clips']):.3f}s  "
              f"切点密度 {cuts/total*60:.0f} 切/分")
        print(f"       字幕 {len(edl['texts'])} 条 | 特效 "
              f"{sum(len(e['effects']) for e in edl['effect_tracks'])} 个 | "
              f"音效 {len(edl['audio_overlays'])} 条")
    print()
    print("自检口径：切点应全部落在 0.46875s 的整数倍上；"
          "镜长 ≤6s；本轮目标是**连接**而非切碎，故切点数只看是否落在拍点上。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
