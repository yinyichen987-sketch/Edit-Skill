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
# 音量：先保持三段素材的响度对齐比例（a 最响→0.7，b/c→0.851），再统一缩放。
# ⚠️ 缩放系数经过两次修正：
#   ① 第一版 0.88 时预览真峰值到 **+1.1 dBFS（削顶）** —— 因为三段原素材真峰值本来就是
#      **+0.8 dBFS**，再叠 BGM 与音效就爆了，故压到 0.70；
#   ② 但**用户参考成片实测响度是 −10.1 / −8.3 LUFS**，而 0.70 时我们只有 −15.4 LUFS，
#      比参考**轻了 5–7 dB**。故回提到 0.90，把落点拉到 −12 LUFS 附近（限幅器兜住峰值）。
GAME_TRIM = 0.90
VOL = {"a": round(0.7 * GAME_TRIM, 3), "b": round(0.851 * GAME_TRIM, 3),
       "c": round(0.851 * GAME_TRIM, 3)}
BGM_VOLUME = 0.46
SFX_VOLUME = 0.70
BAND_SCALE = 1.18                 # 竖屏画面带放大（与 ep01 一致）
CANVAS_BLUR = 0.75

# (拍数, 素材, 入点, 角色, 依据, 速度)
#
# 用户对"集锦"的定义（最终版）：**每个原始素材各取一整段连续画面，保持它自身的先后顺序，
# 再把这几段串起来** —— 不是在同一段素材里反复进出。
#
# ⚠️ 第四轮修正（本轮）。前三版的问题：
#    第 1 版 15 镜 / 均长 1.00s（56 切/分）→ 第 2 版 9 镜 / 1.667s（32）→ 第 3 版 5 镜 / 3.0s（16）。
#    用户参考成片实测是 **镜头 11–31 秒、2.8–4.8 切/分**（见 research/reference-films-notes.md）。
#    本版：**3 镜 / 2 切 / 均长 5.000s / 8 切每分**，每段素材**只出现一次**、各是一整段连续画面。
#
#    仍然落在 128BPM 拍点上：`16+8+8 = 32 拍 = 8 小节 = 15.000s`。
#    切点 = **7.5s 与 11.25s** —— 其中 **7.5s 正是 BGM 的 drop（第 5 小节）**，
#    也就是说第一镜恰好把前 4 小节走完、在 drop 上切开，第二/三镜各占 2 小节。
#
#    三个素材的顺序 —— **用户已确认**（"每条素材内部不被打乱即可，三段可以按叙事重排"）。
#    故约束只在**每段素材内部**（必须完整连续、时序不乱），素材之间可重排。本稿选：
#      c 段（击杀播报冷开 → 持续交火）→ a 段（拾取 → **实测 2 HP**）→ b 段（**「获胜」横幅**）
#    从动作 → 悬念 → 结果 —— 因为 b 段含「获胜」横幅，是三者里唯一能当"结果"的素材。
#    形式定义见 .dsh/skills/jianying-edit/references/styles/game-montage.md
SHOTS = [
    # 第 1 镜：c 段一整段 7.5s（C-H5 击杀播报同帧 → C-H7 甩枪 → C-H8 交火 → C-H9 前）
    (16, "c", 6.40,  "run_c", "c 段连续长镜 7.5s：C-H5(击杀播报同帧) → C-H7 → C-H8；开场即冷开峰值", 1.0),
    # 第 2 镜：a 段一整段 3.75s（A-H2 拾取 → A-H3 实测 2HP → A-H4）
    (8,  "a", 5.60,  "run_a", "a 段连续长镜 3.75s：A-H2(拾取) → A-H3(**实测 2 HP**，conf 0.95) → A-H4", 1.0),
    # 第 3 镜：b 段一整段 3.75s（B-H7「获胜」横幅，收在最强的情绪点上）
    (8,  "b", 20.86, "run_b", "b 段连续长镜 3.75s：B-H7「**获胜**」横幅；出点 24.61 距 b 上界 26.017 余 1.41s", 1.0),
]
# 各段的素材窗口（两端都避开 VFR 真实跳变窗口，且留足 CUT-04 余量）：
#   c 6.40 → 13.90  （c 跳变窗在 2.0717 / 3.3717，远离；c 上界 25.012）
#   a 5.60 →  9.35  （a 为 CFR 无跳变；a 上界 18.984）
#   b 20.86 → 24.61 （b 跳变窗在 10.9797 / 12.9787，远离；b 上界 26.017，余量 1.407s）
# 三段互不重叠（SEL-02），且每段素材只出现一次。

# 调色：**全片同一个 grade**（调研：craft layer 必须每一镜完全一致 ——
# 「这才是让 13+ 个镜头读成一部片子的原因」；且"纯克制"会被读成 washed out）。
GRADE = {"type": "青橙", "intensity": 65.0}

# 转场：只一种高级故障转场。选 信号故障 的硬理由 —— 调研实测本机
# `Cache\effect\` 里**只有它已缓存**，是唯一**零下载风险**的 VIP 转场。
# 只有 2 个切点，都给转场；drop 那一下给到 0.20s。
TRANSITION_TYPE = "信号故障"
TRANSITION_AT = {7.5, 11.25}
TRANSITION_LONG_AT = {7.5}
TRANSITION_SHORT = 0.12
TRANSITION_LONG = 0.20

# 特效：用户要求"低级反馈特效不要用了，直接用高级特效"。
#   镜头只有 3 个、切点只有 2 个 ⇒ 特效也只留 2 个，且都在切点上（= 能量峰值）。
#   调研：「flashes/punches on energy **PEAKS only**」。
EFFECTS = [
    ("fx",  "像素故障", 7.50,  0.30),   # DROP 落点（第 2 镜起点）
    ("fx2", "花屏故障", 11.25, 0.35),   # 第 3 镜起点（「获胜」前）
]

# 音效：两条轨以便同一时刻叠加。
# 一条 riser 推到 7.5s 的 drop；drop 处 sub_drop 与 impact 同时响；11.25s 切点配 whoosh+impact+win。
SFX = [
    ("sfx1", "riser",    5.625,  1.80, 0.65 * SFX_VOLUME / 0.70),
    ("sfx1", "impact_b", 7.500,  0.14, 1.00 * SFX_VOLUME / 0.70),
    ("sfx1", "whoosh",  11.250,  0.35, 0.75 * SFX_VOLUME / 0.70),
    ("sfx2", "sub_drop", 7.500,  0.90, 0.95 * SFX_VOLUME / 0.70),
    ("sfx2", "impact_a",11.250,  0.16, 0.90 * SFX_VOLUME / 0.70),   # impact_a 只有 0.1604s
    ("sfx2", "win",     11.520,  0.45, 0.80 * SFX_VOLUME / 0.70),
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
#
# 镜头变成 3 个长镜之后，字幕也跟着变成 **4 条**、而且**时间上互不重叠**：
# 横屏的字幕现在统一放在上部 210px（对齐参考成片），同位置的字幕不能同时出现，
# 所以横屏这几条必须**首尾相接而不是叠着**（竖屏钩子在上、过程在下，本来可以叠）。
# (id, 文本, 起, 时长, 字号, 颜色, 入场, 循环)
CAPTIONS = [
    ("t1", "别眨眼",       0.0000,  1.2000, 24.0, (1.0, 1.0, 1.0), "弹簧",     "爆闪"),
    ("t2", "一枪一个",     1.2000,  2.4000, 22.0, (1.0, 0.9, 0.2),  "复古打字机", "爆闪"),
    ("t3", "2 HP",         8.2000,  2.0000, 24.0, (1.0, 0.35, 0.35), "弹入",   "跳动"),
    ("t4", "这枪换你，敢不敢上？", 11.4000, 3.2000, 17.0, (1.0, 0.9, 0.2), "渐显", None),
]

# 字幕位置。**横屏一版按用户参考成片（`瓦参考素材/`）实测重定**：
#   两份模板的标签都在**上部居中**，实测字框中心约 **y≈200px / 画布高 1080 = 18.5%**，
#   形态是**白粗字 + 半透明底板**（底板让字在亮画面上也读得清）。
#   ⇒ 横屏放弃原先的"底部安全带（900–1080）"。那条规则本是为避开准星；
#     200px 远高于画面中心 540px，同样不压准星，而且与参考成片一致。
TY_TITLE = 1.0 - 2 * 300 / 1920          # +0.6875   竖屏钩子：上部信息区 300px
TY_BODY = 1.0 - 2 * 1450 / 1920          # -0.510417 竖屏过程：下部信息区 1450px
TY_LS_ALL = 1.0 - 2 * 210 / 1080         # +0.611111 横屏：统一上部居中（对齐参考成片）

# 参考成片的标签底板（半透明深色）。参考成片画面偏亮，白字必须有底才稳。
CAPTION_BG = {"color": "#00000073", "style": 1, "round_radius": 0.08}

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
    #   3 个长镜（7.5 / 3.75 / 3.75s）都需要内部运动；第一镜最长故推得最多
    push = {"m01": 1.10, "m02": 1.08, "m03": 1.07}
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
        is_title = cid in ("t1", "t4")
        # 竖屏：钩子在上部 300px、过程在下部 1450px（信息区）
        # 横屏：**统一放上部 210px**（对齐参考成片实测的标签位置）
        ty = (TY_TITLE if is_title else TY_BODY) if vertical else TY_LS_ALL
        # 入场时长 ≈ 一拍（128BPM → 0.469s）。调研：「动画比你想象的短，一拍不是两拍」。
        anim = {"intro": intro, "intro_duration": 0.40}
        if loop:
            anim["loop"] = loop
        texts.append({
            # 两条轨：竖屏时钩子在上、过程在下，位置不冲突但**时间重叠**，
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
            # 底板：**照参考成片**（它的标签是"白粗字 + 半透明底板"）。
            # 横屏尤其需要 —— 标签直接压在亮画面上，没有底板白字会糊。
            "background": dict(CAPTION_BG),
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
          "镜长 ≤8s；本轮目标是**每段素材一整段连续**，故切点数只看是否落在拍点上。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
