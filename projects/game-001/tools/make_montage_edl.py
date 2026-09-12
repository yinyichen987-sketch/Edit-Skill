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
# ⚠️ 第五轮（本轮）：用户取消了时长限制，并要求**先只做面向 B站 的横屏版**。
#    参考成片实测 37.2s / 43.5s（见 research/reference-films-notes.md），
#    故不再压到 15s，长度让素材决定。
#
# 集锦定义（用户确认）：
#   ① **每段原始素材各取一整段连续画面**，内部时序与素材自身一致（不打乱、不跳着取）；
#   ② **不要切割太碎**；
#   ③ 素材之间**可以按叙事重排**（约束只在素材内部）。
#   形式定义见 .dsh/skills/jianying-edit/references/styles/game-montage.md
#
# 本版结构：**4 镜 / 3 切 / 30.000s / 6 切每分**，b 段出现两次（5.4s 段与 13.5s 段，
# 各自完整、保持先后），因为它的高光被一处真实视点跳变（10.9797s）隔开、无法并成一段。
#
#   小节对照（128BPM，1 小节 = 1.875s，共 16 小节 = 30.000s）：
#     m1 c  0.000– 7.500（4 小节）
#     m2 a  7.500–15.000（4 小节）
#     m3 b 15.000–18.750（2 小节）  ← **起点 15.000s 正是 BGM 的 drop（第 9 小节）**
#     m4 b 18.750–30.000（6 小节）
SHOTS = [
    # 每个"镜"是 **(素材, 入点, [(拍数, 速度), …], 角色, 依据)** —— 一个镜可由**若干变速子段**组成。
    # 本轮从教学文里学到的核心手法（来源 https://diantuoyi.com/article/8990.html
    # 「三、素材类型 1：游戏录屏」）：**击杀瞬间放慢到 0.7×、前后保持快放，形成节奏反差**。
    #
    # ⚠️ 变速子段**不是"切割"**：只要相邻子段在**时间线与素材上都首尾相接**，画面就是连续的
    #    （同一场景、推进速度不同而已），因此不违反用户"不要切割太碎"的要求。
    #    素材消耗 = 时间线长度 × 速度 ⇒ source_in 必须**按子段消耗量累加**。
    #
    # ⚠️⚠️ **本轮改成"阶梯式"变速（用户反馈"击杀变速太生硬"）**：
    #   上一版是 0.70× → 1.15× **一步跳完**（相邻差 0.45，一个帧内速度涨 64%），
    #   肉眼就是"咯噔"一下。现在把一次大跳**拆成两三次小跳**：
    #     a 段 1.00 → **0.78** → 1.10（相邻差 0.22 / 0.32）
    #     b 段 0.95 → **0.78**（相邻差 0.17）
    #   调研口径是"相邻倍数差 ≤0.5"，现在最大 0.32，留了余量。
    #   **真正的治本是剪映的「曲线变速」与「智能补帧/光流法」** —— 但这两个
    #   pyJianYingDraft **都写不了**：`Speed.export_json()` 把 `curve_speed` 硬编码为
    #   `None`（库源码 `segment.py:93`），补帧也没有任何可写字段。
    #   故这两项**列进导出清单交人工一键开启**，不假装做进去了。
    #
    # 第 1 镜：c 段一整段 7.5s，常速（冷开峰值，不加速以免第一印象发飘）
    ("c", 3.55, [(16, 1.00)], "run_c",
     "c 段连续长镜 7.5s：C-H5(击杀播报同帧，信息量最高) → C-H7 → C-H8；开场即冷开峰值"),
    # 第 2 镜：a 段 7.5s —— 阶梯 1.00× → **0.78×**（压住 2 HP）→ 1.10× 提回
    ("a", 5.20, [(2, 1.00), (5, 0.78), (9, 1.10)], "run_a",
     "a 段 7.5s：A-H2(拾取) → **A-H3 实测 2 HP 处降到 0.78×** → A-H4 → A-H5(两条击杀播报，1.10× 提回)"),
    # 第 3 镜：b 段第一段 3.75s —— 阶梯 0.95× → **0.78×**（压住 B-H2 击杀确认 8.5s）
    ("b", 5.40, [(3, 0.95), (5, 0.78)], "run_b1",
     "b 段第一段 3.75s：B-H1(**全 70 秒音频能量最强**) → **B-H2 击杀确认处降到 0.78×**"),
    # 第 4 镜：b 段第二段 11.25s，常速（收尾「获胜」，不需要速度反差）
    ("b", 13.50, [(24, 1.00)], "run_b2",
     "b 段第二段 11.25s：B-H5(爆能器已部署横幅) → B-H7(**「获胜」横幅**)"),
]
# 拍数合计 = 16 +（2+5+9）+（3+5）+ 24 = **64 拍 = 16 小节 = 30.000s**（128BPM，1 小节 = 1.875s）。
# ⚠️ 单位是**拍**不是小节：曾把 4/4/2/6（小节数）误填进去，总长只剩 7.5s。改完必须复核总长。
#
# 素材窗口（按"时间线 × 速度"逐段累加，两端都避开 VFR 真实跳变窗口）：
#   c  3.550 → 11.050  （跳变窗 [3.3717,3.4050] 距入点 0.145s；上界 25.012）
#   a  5.200 → 12.606  （2×1.00 + 5×0.78 + 9×1.10 = 15.8 拍素材；a 为 CFR；上界 18.984）
#   b  5.400 →  8.564  （3×0.95 + 5×0.78 = 6.75 拍素材；距 10.9797 跳变窗 2.42s）
#   b 13.500 → 24.750  （上界 26.017，余量 1.267s）
# 四段互不重叠（SEL-02）。

# 推镜倍率（按**镜号**，不是片段号）：整镜从 1.0 推到该倍率，子段按时间线占比插值。
#   第 4 镜最长（11.25s）故推得最多；有变速反差的两镜推得少一些，避免和变速抢戏。
SHOT_PUSH = {1: 1.09, 2: 1.07, 3: 1.05, 4: 1.11}

# 调色：**全片同一个 grade**（调研：craft layer 必须每一镜完全一致 ——
# 「这才是让 13+ 个镜头读成一部片子的原因」；且"纯克制"会被读成 washed out）。
#   滤镜给出色调基调；下面三层的**颗粒/暗角/锐化**来自教学文的调色公式
#   （来源 https://diantuoyi.com/article/8990.html 「技巧 2：色调统一成游戏内质感」：
#    颗粒 5% + 暗角 10% + 锐化 8%）。文章里的「对比度 +15 / 阴影 -10 / 色调 +5」属**调节**面板，
#   而 pyJianYingDraft **不写调节**（materials.adjusts 等数组它从不写），故这三档
#   列进导出清单让人工在剪映里补 —— 不要假装已经做进去了。
GRADE = {"type": "青橙", "intensity": 65.0}
# (轨名, 特效名, 目标强度 0-100, **目标参数名**, 需要输出的参数名列表)
GRADE_LAYERS = [
    ("g_vig",   "暗角",     10.0, "effects_adjust_texture",
     ["effects_adjust_texture"]),                                   # 暗角 10%
    ("g_grain", "噪点",      5.0, "effects_adjust_noise",
     ["effects_adjust_noise"]),                                     # 颗粒 5%
    ("g_sharp", "精细锐化", 10.0, "effects_adjust_sharpen",
     ["effects_adjust_blur", "effects_adjust_sharpen", "effects_adjust_size",
      "effects_adjust_range", "effects_adjust_filter"]),            # 锐化 10%
]

# 转场：只一种高级故障转场。选 信号故障 的硬理由 —— 调研实测本机
# `Cache\effect\` 里**只有它已缓存**，是唯一**零下载风险**的 VIP 转场。
# **只在场景切换处**（7.5 / 15.0 / 18.75）；变速子段的交界处（9.375 / 16.875）**必须是硬切** ——
# 那是同一场景内的速度变化，加转场反而会把它切成两段。
TRANSITION_TYPE = "信号故障"
TRANSITION_AT = {7.5, 15.0, 18.75}
TRANSITION_LONG_AT = {15.0}
TRANSITION_SHORT = 0.12
TRANSITION_LONG = 0.20

# 特效：用户要求"低级反馈特效不用了，直接用高级特效"。
#   只在**场景切换 / 能量峰值**上，且同一套故障语言。调研：「flashes/punches on energy PEAKS only」。
EFFECTS = [
    ("fx",  "幻彩故障",  7.50, 0.25, None),   # 第 2 镜起点
    ("fx",  "像素故障", 15.00, 0.35, None),   # DROP 落点（第 3 镜起点）
    ("fx2", "花屏故障", 18.75, 0.30, None),   # 第 4 镜起点
]

# 音效：两条轨以便同一时刻叠加。
# 一条长 riser 从第 7 小节推到 drop（15.000s）；drop 处 sub_drop + impact 同时响；
# 18.750s 切点配 whoosh + impact，随后 win 音落在「获胜」横幅上。
SFX = [
    ("sfx1", "riser",    11.250, 1.80, 0.65 * SFX_VOLUME / 0.70),   # 推到 15.000 的 drop
    ("sfx1", "impact_b", 15.000, 0.14, 1.00 * SFX_VOLUME / 0.70),
    ("sfx1", "whoosh",   18.750, 0.35, 0.75 * SFX_VOLUME / 0.70),
    ("sfx2", "sub_drop", 15.000, 0.90, 0.95 * SFX_VOLUME / 0.70),
    ("sfx2", "impact_a", 18.750, 0.16, 0.90 * SFX_VOLUME / 0.70),   # impact_a 只有 0.1604s
    ("sfx2", "win",      25.800, 0.45, 0.85 * SFX_VOLUME / 0.70),   # 「获胜」横幅出现处
    ("sfx2", "whoosh",    7.500, 0.35, 0.70 * SFX_VOLUME / 0.70),
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
# 时长放宽到 30s 之后字幕 **7 条**，而且**时间上互不重叠**：
# 横屏字幕统一放在上部 210px（对齐参考成片），同位置的字幕不能同时出现，
# 所以必须**首尾相接而不是叠着**。
#
# 本轮从教学文学到两条新的排版手法（来源 https://diantuoyi.com/article/8990.html
# 「技巧 3：文字排版贴游戏 UI」）：
#   ① **数据类文字（"2 KILLS"）放画面右上角，用游戏内计分板样式（黑底白字）**；
#   ② 技能/事件名紧跟对应镜头出现。
#   故 t4 从居中的"播报两连"改成**右上角计分板式 `2 KILLS`**（`place="right"`）——
#   它对应 a 段 A-H5 画面里**真的同时刷出两条击杀播报**（可证，符合 SEL-04）。
#
# ⚠️⚠️ **本轮（用户要求）把所有文字全部删除** —— 包括右上角那个计分板式 `2 KILLS`。
#    用户原话："把所有的文字解说部分先删除"。**"所有"就按字面执行**，
#    所以连数据条一起去掉，片子只靠**画面 + BGM + 音效**说话。
#    （若用户的本意只是"去掉解说句、保留数据条"，把 t4 那一行单独加回来即可。）
#
# 删字幕后需要**同时**做两件事，否则会留下空轨：
#   ① `CAPTIONS = []`；② EDL 的 `tracks` 里不再声明 cap_top / cap_body（见 build()）。
#
# 保留这段格式说明，方便随时恢复：
#   (id, 文本, 起, 时长, 字号, 颜色, 入场, 循环, 位置)
#   place="right" → 计分板式数据条贴右上（transform_x 取负）
CAPTIONS: list = []

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


def _fx_tracks(effects: list) -> list:
    """把 (轨名, 特效名, 起, 时长, 参数) 按轨名分组。参数为 None 时交给库用默认值。"""
    out: dict = {}
    for trk, ty, st, du, params in effects:
        out.setdefault(trk, []).append(
            {k: v for k, v in (("type", ty), ("start", st), ("duration", du),
                               ("params", params)) if v is not None})
    return [{"name": k, "effects": v} for k, v in out.items()]


def _grade_params(effect_name: str, target_name: str, value: float,
                  param_names: list) -> list:
    """调色层参数：把目标强度（0–100）写进**指定那一个**参数，其余按默认值补齐。

    库的 `parse_params` 语义：传入数字是 **0–100**，映射到 `min + (max-min)*v/100`；
    传 `None` 会被写成**默认值**（不是 100）。故这里显式给出每个参数的值：
    目标参数用 `value`，其余按"默认值折回 0–100 刻度"。
    （**必须显式给值**：曾想靠 `None` 走默认，但库对 `None` 的处理是写默认值、
      结果是"看起来设了、其实等于没调"。）
    """
    from pyJianYingDraft import VideoSceneEffectType
    meta = getattr(VideoSceneEffectType, effect_name).value
    pmeta = {p.name: p for p in (getattr(meta, "params", None) or [])}
    out = []
    for n in param_names:
        p = pmeta.get(n)
        if p is None:
            out.append(None)
            continue
        if n == target_name:
            out.append(value)
            continue
        lo, hi, dv = float(p.min_value), float(p.max_value), float(p.default_value)
        out.append(round((dv - lo) / (hi - lo) * 100.0, 3) if hi > lo else 0.0)
    return out


def build(vertical: bool) -> dict:
    W, H = (1080, 1920) if vertical else (1920, 1080)
    clips, t = [], 0.0
    # 一个"镜"可含若干**变速子段**。子段之间**素材首尾相接**（source_in 按 时间线×速度 累加），
    # 所以画面连续、只是推进速度不同 —— 这是"变速"而不是"切割"。
    seg_no = 0
    for shot_i, (key, src_in, parts, role, why) in enumerate(SHOTS, 1):
        cursor = float(src_in)              # 该镜的素材游标
        total_beats = sum(b for b, _ in parts)
        # 推镜：整镜给一个总倍率，子段按**时间线占比**插值，避免子段交界处缩放跳变
        push_total = SHOT_PUSH.get(shot_i, 1.0)
        base = BAND_SCALE if vertical else 1.0
        elapsed = 0.0
        for part_i, (beats, speed) in enumerate(parts, 1):
            dur = beats * BEAT
            src_used = dur * speed       # ★ 素材消耗 = 时间线长度 × 速度
            seg_no += 1
            c = {
                "id": f"m{seg_no:02d}",
                "track": "main",
                "source": SRC[key],
                "source_in": round(cursor, 6),
                "start": round(t, 6),
                "duration": round(dur, 6),
                "role": role,
                "rule_id": "MONT-01",
                "reason": (f"第 {shot_i} 镜第 {part_i}/{len(parts)} 段 / {beats} 拍（{dur:.4f}s）"
                           f"@128BPM；时间线 {t/BEAT:.0f}–{(t+dur)/BEAT:.0f} 拍；"
                           f"速度 {speed}×（吃素材 {src_used:.4f}s，素材 {cursor:.3f}→"
                           f"{cursor+src_used:.3f}）。{why}"),
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
            # 推镜关键帧：按整镜时间线占比插值 → 子段交界处数值连续
            if push_total != 1.0:
                f0, f1 = elapsed / (total_beats * BEAT), (elapsed + dur) / (total_beats * BEAT)
                c["keyframes"] = [
                    {"property": "uniform_scale", "time": 0.0,
                     "value": round(base * (1 + (push_total - 1) * f0), 5)},
                    {"property": "uniform_scale", "time": round(dur, 6),
                     "value": round(base * (1 + (push_total - 1) * f1), 5)},
                ]
            clips.append(c)
            cursor += src_used
            elapsed += dur
            t += dur

    # ---- 推镜已在上面的子段循环里按"整镜时间线占比"插值写入（避免交界处缩放跳变）----
    if vertical:
        for c in clips:
            c["background_filling"] = {"type": "blur", "blur": CANVAS_BLUR}
            c["clip"] = {"scale": BAND_SCALE}

    texts = []
    for cid, txt, start, dur, size, color, intro, loop, place in CAPTIONS:
        is_title = cid in ("t1", "t7")
        # 竖屏：钩子在上部 300px、过程在下部 1450px（信息区）
        # 横屏：**统一放上部 210px**（对齐参考成片实测的标签位置）
        ty = (TY_TITLE if is_title else TY_BODY) if vertical else TY_LS_ALL
        # place="right" → 计分板式数据条，贴右上（但仍在上部 210px 那条带里，
        # 避开游戏自身在右上角的击杀播报；transform_x 正方向为**左**，故取负值往右）
        tx = 0.0
        if place == "right":
            tx = 1.0 - 2 * (1600 / 1920)          # ≈ -0.667 → 中心约在 x=1600
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
                "transform_x": round(tx, 6),
                "transform_y": round(ty, 6),
            },
            "animation": anim,
            # 描边/阴影：调研结论是"亮场靠描边保住字"，故描边给足
            "border": {"color": (0.0, 0.0, 0.0), "width": 70.0 if is_title else 58.0},
            "shadow": {"color": (0.0, 0.0, 0.0), "diffuse": 18.0, "distance": 6.0, "angle": -45.0},
            # 底板：**照参考成片**（它的标签是"白粗字 + 半透明底板"）。
            # 横屏尤其需要 —— 标签直接压在亮画面上，没有底板白字会糊。
            # place="right" 时用**更实的黑底**，贴教学文里"计分板 = 黑底白字"的样子。
            "background": ({**CAPTION_BG, "color": "#000000B3"} if place == "right"
                           else dict(CAPTION_BG)),
        })

    return {
        "version": "1.0",
        "project": f"GAME_MONT_{'VT' if vertical else 'LS'}",
        "canvas": {"width": W, "height": H, "fps": 30},
        "style_ref": "game-montage",
        # ⚠️ **从片段实算**，不写死。曾写死 15.0，取消时长限制后没跟着改，
        #    于是 EDL 里躺着一个和实际（30.0s）矛盾的旧值 —— 这类"元数据与实际不一致"
        #    最容易在排查"为什么还是 15 秒"时把人带偏。
        "target_duration_s": round(sum(c["duration"] for c in clips), 6),
        "tracks": (
            [{"type": "video", "name": "main"}]
            # 字幕轨**只在真的有字幕时才声明** —— 删掉全部文字后若仍留下空轨，
            # 剪映里会多出两条看不见的空轨（也让门禁无处判定）
            + ([{"type": "text", "name": "cap_top"},
                {"type": "text", "name": "cap_body"}] if texts else [])
            + [{"type": "audio", "name": "bgm"},
               {"type": "audio", "name": "sfx1"},
               {"type": "audio", "name": "sfx2"}]
        ),
        "clips": clips,
        "texts": texts,
        "audio_overlays": (
            [{"source": "../bgm/bgm_128_16bars.wav", "track": "bgm",
              "start": 0.0, "duration": 30.0, "volume": BGM_VOLUME,
              "fade": {"in": 0.0, "out": 0.25}}]
            + [{"source": f"../sfx/{name}.wav", "track": trk,
                "start": st, "duration": du, "volume": vol,
                "fade": {"in": 0.005, "out": min(0.06, du * 0.25)}}
               for (trk, name, st, du, vol) in SFX]
        ),
        "effect_tracks": (
            _fx_tracks(EFFECTS)
            # 全片调色层：三条轨各一个覆盖 0→总长的特效（同轨会与命中特效重叠而被拒）
            + [{"name": trk, "effects": [
                {"type": ty, "start": 0.0,
                 "duration": round(sum(c["duration"] for c in clips), 6),
                 "params": _grade_params(ty, pname, val, names)}]}
               for (trk, ty, val, pname, names) in GRADE_LAYERS]
        ),
        "audio": {"voice_priority": "low", "bgm_volume": BGM_VOLUME},
        "qa": {"required": ["duration-valid", "audio-present", "no-black-frame"]},
        "_form_note": (
            f"集锦形式（不做叙事）：{len(clips)} 镜 / {len(clips)-1} 切 / "
            f"{sum(c['duration'] for c in clips)/BEAT:.0f} 拍 @128BPM / "
            f"{sum(c['duration'] for c in clips):.3f}s。"
            "每段原始素材各取**一整段连续画面**（用户确认的集锦定义），"
            "有意偏离叙事型的 CUT-01（固定四段）与 CUT-02（≈12 切/分）。"
            "CUT-04（不越素材上界）与 CUT-05（避开 VFR 跳变窗）仍强制满足。"),
        "_audio_note": ("BGM 为本地合成（128BPM，与剪切点同格，见 tools/make_bgm.py）；"
                        "whoosh/riser/sub_drop 亦为合成（tools/make_sfx.py）；"
                        "impact_*/win 从原素材裁出。剪映音效库无法程序化引用。"),
    }


def main() -> int:
    print("=== 生成 B站横屏集锦 EDL（128 BPM，64 拍 = 16 小节 = 30.000s）===")
    # 用户："先只做面向B站的视频" ⇒ 只出横屏。竖屏能力仍在 build(vertical=True) 里保留。
    for vertical, name in ((False, "montage.json"),):
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
          "镜长 ≤12s；本轮目标是**每段素材一整段连续**，故切点数只看是否落在拍点上。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
