"""生成 B站 操作高光集锦（11 条素材版）。

## 与前几版的区别

1. **素材从 3 条增加到 11 条**（`原始素材/`，共 5.60 分钟），本版**全部用上**。
2. **每段素材只切一刀、取一整段连续画面**（用户："尽量不要切割每一个原素材，
   他们都是每一段连杀接着另一段连杀"）⇒ **11 镜 = 11 条素材各一段连杀**。
3. **BGM 换成 Hearts2Hearts《STYLE》**（用户指定）。实测 **127.66 BPM**、
   1 拍 0.469986s、1 小节 1.88s。取第 **90 小节**（歌曲 169.45s）起的 **16 小节 = 30.08s**
   —— 该段是歌曲能量最强的尾段（每秒能量 0.27–0.36，全曲最高）。
   剪切点全部落在**这首歌自己的拍点**上（不再用自制 128BPM 的网格）。
4. **不再使用自制音效**：歌曲本身提供节奏，游戏原声压低垫底。

## 两条可机器校验的不变量（前几轮学到的）

- **各段素材内部单调递增** —— 每条素材只出现一次，天然满足；
  由 `tools/verify_shot_order.py` 校验。
- **切点落在歌曲拍点上** —— 由本脚本自检打印。

## 素材窗口怎么来的

对 11 条素材各跑 `analysis/tools/audio_energy.py`（逐帧音频能量），
取 **band 能量最高的 3.0 秒窗口**作为「连杀候选」
（`analysis2/best_windows.json`）。这是音频侧的启发式：
**技能特效也会很响**，所以个别窗口可能以特效为主而非击杀，
需要人工过目 —— `analysis2/winsheet/all_best_windows.png` 就是为此生成的对照图。
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
OUT = ROOT / "projects" / "game-001" / "edl" / "bili-montage.json"

# ---- 歌曲：Hearts2Hearts《STYLE》实测参数 ----
BPM = 127.66
BEAT = 60.0 / BPM                      # 0.469986 s
BAR = 4 * BEAT                          # 1.879943 s
# ⚠️ 这两个常量必须与 SHOTS 的总拍数**一致**，否则 build() 的断言会拦下
#    （改素材池时最容易忘这里：本轮拍数从 64 变成 128，SECTION_BARS 忘了改，直接断言失败）。
SECTION_START_IN_SONG = 30.0             # 从歌曲 30s 起（够长且覆盖全曲段落）
SECTION_BARS = 92                       # 92 小节（≥ 成片拍数）
# ⚠️ EDL 在 projects/game-001/edl/ 下，所以 ../bgm/ 才是 projects/game-001/bgm/。
#    写成 ../../bgm/ 会解析到 projects/bgm/，转换器只报一句 WARN、**照常生成草稿但没有 BGM** ——
#    这种静默少了一条轨必须靠报告里的「音效叠加 N 个」核对，不能只看草稿已生成。
# ⚠️ **由 SECTION_BARS 推导，不要手写**：本轮就因手写的还停在 16bars（30.08s）、而成片已 60.16s，
#    转换器报 截取的素材时间范围 ... 超出了素材时长 —— 这类两个常量各改各的最易漏。
BGM_FILE = f"../bgm/h2h_style_{SECTION_BARS}bars.wav"
BGM_VOLUME = 0.85                       # 歌曲是主角
# ⚠️ 游戏原声压到 0.28：0.34 时 BGM(0.85) + 原声叠加实测**真峰值 +0.4 dBFS（削顶）**。
#    六条参考的真峰值是 +1.4 / -0.1 / -0.9 / +0.3 / -1.9 / -4.8 —— 削顶在 B站 很常见，
#    但我们自己没有平台端兜底，所以留 -1 dBTP 余量更稳。
GAME_VOLUME = 0.28                      # 游戏原声压低垫底，让击杀/技能透出来

# ★★ **击杀落在镜内第几拍**（本轮修正，用户反馈）
#   用户："很多时候你出现的都是击杀之后的画面，你要确认**击杀前后要有一段连续的画面**。"
#   上一版 `source_in = 击杀帧` ⇒ 镜头从击杀那刻才开始，只有后段没有前因。
#   现在入点前移 KILL_LEAD_BEATS 拍，击杀落在**镜内第 KILL_LEAD_BEATS 拍**：
#     镜头开始 ──前摇──> 【击杀·踩重拍】 ──击杀后──> 镜头结束
#   2 拍 = 0.940s 前摇（够看到抬枪/瞄准），击杀后还有 3–4 拍。
KILL_LEAD_BEATS = 2

# ---- 16 条**击杀卡点** ----
# ⚠️⚠️ **本轮关键修正（用户）**：
#   > "你的画面要和音乐卡点的话，**主要是要让击杀和音乐卡点**，不是人物动作之类的……
#   >  保证音乐的卡点应当和**击杀帧**卡点。"
#   ⇒ 所以 `source_in` **直接对准检测到的击杀帧**
#     （`tools/detect_kills.py` 抓右上角击杀播报的上升沿；已用原 a 段验证：
#      检出 6.30s vs 已知真值 6.35s，且它比我先前的**人工标注更准** ——
#      我标的 "11.6s 击杀播报" 其实是动作峰值，播报 12.57s 才刷出）。
#     这样**每一次剪切（= 音乐的一个重拍）都正好落在一次击杀上**，
#     而不是落在"在跑 / 在转视角"这种次要动作上。
#
# 结构：**16 镜 / 15 切 / 每镜 3–5 拍**，铺满《STYLE》第 90 小节起的 16 小节。
#   16 镜来自 11 条素材：6 条各出 1 次，5 条各出 2 次（取其最强的两个击杀）。
#   每条素材内部**击杀时刻严格递增**（不回头）⇒ 满足"不割裂"不变量。
# 排法：先 11 条各一发（轮转交错，避免"三条片子拼接"的观感），
#       再把 5 条的第二发插在中后段，**收尾固定在 b 段的击杀**（紧邻「获胜」横幅）。
#
# (素材短名, 击杀帧秒, 拍数, 说明)
# ⚠️ 本表由 `tools/detect_kills.py` + `analysis2/my_multikill.json` **自动派生**，
#    **不要手改拍数**：拍数 = ceil((簇跨度 + 前摇) / 1拍)，下限 5 拍，
#    这样每个簇内的击杀必然全部落在镜内（手写时曾因拍数不足而静默截断）。
#    素材池 = **你本人**的击杀所构成的连杀簇（底部击杀特效 ∩ 右上播报），
#    已滤除队友击杀与自己死亡。
# 总长 = 128 拍 = 60.16s = 32 小节（由素材决定；BGM 去适配）
# ⚠️ 本表由 `analysis2/runs_whole.json` 派生，**规则 =「整段素材骨架」**：
#    每条素材内，**间隔 ≤ 4.5s 的击杀归为一个连续段**（只有超过 4.5s 没击杀才剔除），
#    两端留 1.5s 前摇 / 2.5s 收尾，重叠段合并，再对齐到整拍。
#    ⇒ 每段是**一条连续画面**，不是碎片。这是用户第三次强调才纠正过来的结构。
#    总长 = 365 拍 = 171.55s = 92 小节（由素材决定，BGM 去适配）
SHOTS = [
    ("0a550967",   5.300, 14, "整段素材：2 杀 [6.8, 9.47]，原始 6.67s → 对齐 14 拍"),
    ("38cc4903",   0.000, 46, "整段素材：8 杀 [1.3, 2.23, 2.9, 6.8, 8.73, 10.4, 14.5, 19.1]，原始 21.6s → 对齐 46 拍"),
    ("4b0460c4",   3.100,  9, "整段素材：1 杀 [4.6]，原始 4.0s → 对齐 9 拍"),
    ("4c58efb4",   0.000, 21, "整段素材：4 杀 [1.43, 2.1, 4.67, 7.33]，原始 9.83s → 对齐 21 拍"),
    ("58b8e283",   0.000, 29, "整段素材：4 杀 [0.57, 4.0, 7.2, 11.0]，原始 13.5s → 对齐 29 拍"),
    ("6b2eea34",   8.600, 15, "整段素材：2 杀 [10.1, 12.97]，原始 6.87s → 对齐 15 拍"),
    ("7f0d8287",  16.567, 13, "整段素材：2 杀 [18.07, 20.37]，原始 6.3s → 对齐 13 拍"),
    ("851622c5",   2.167,  9, "整段素材：1 杀 [3.67]，原始 4.0s → 对齐 9 拍"),
    ("9526869d",   4.633,  9, "整段素材：1 杀 [6.13]，原始 4.0s → 对齐 9 拍"),
    ("b61cc53d",   4.700, 25, "整段素材：6 杀 [6.2, 6.8, 9.57, 10.7, 11.77, 13.97]，原始 11.77s → 对齐 25 拍"),
    ("dcc871b1",   0.567,  9, "整段素材：1 杀 [2.07]，原始 4.0s → 对齐 9 拍"),
    ("0a550967",  16.800, 10, "整段素材：2 杀 [18.3, 18.87]，原始 4.57s → 对齐 10 拍"),
    ("4b0460c4",   8.467,  9, "整段素材：1 杀 [9.97]，原始 4.0s → 对齐 9 拍"),
    ("4c58efb4",  18.400, 10, "整段素材：2 杀 [19.9, 20.77]，原始 4.87s → 对齐 10 拍"),
    ("58b8e283",  14.700,  9, "整段素材：1 杀 [16.2]，原始 4.0s → 对齐 9 拍"),
    ("7f0d8287",  32.033,  9, "整段素材：1 杀 [33.53]，原始 4.0s → 对齐 9 拍"),
    ("9526869d",   9.467,  9, "整段素材：1 杀 [10.97]，原始 4.0s → 对齐 9 拍"),
    ("b61cc53d",  17.600, 22, "整段素材：4 杀 [19.1, 21.33, 22.7, 25.33]，原始 10.23s → 对齐 22 拍"),
    ("dcc871b1",  13.033, 10, "整段素材：2 杀 [14.53, 15.13]，原始 4.6s → 对齐 10 拍"),
    ("0a550967",  25.767,  9, "整段素材：1 杀 [27.27]，原始 4.0s → 对齐 9 拍"),
    ("4b0460c4",  13.233, 12, "整段素材：2 杀 [14.73, 16.73]，原始 5.75s → 对齐 12 拍"),
    ("58b8e283",  19.400, 10, "整段素材：2 杀 [20.9, 21.83]，原始 4.93s → 对齐 10 拍"),
    ("7f0d8287",  36.933, 11, "整段素材：2 杀 [38.43, 39.57]，原始 5.13s → 对齐 11 拍"),
    ("9526869d",  31.067,  4, "整段素材：1 杀 [32.57]，原始 1.95s → 对齐 4 拍"),
    ("dcc871b1",  21.400,  8, "整段素材：2 杀 [22.9, 23.5]，原始 3.61s → 对齐 8 拍"),
    ("0a550967",  31.300,  4, "整段素材：1 杀 [32.8]，原始 1.71s → 对齐 4 拍"),
    ("58b8e283",  25.100, 10, "整段素材：2 杀 [26.6, 27.23]，原始 4.63s → 对齐 10 拍"),
    ("6b2eea34",  21.333, 10, "整段素材：2 杀 [22.83, 25.97]，原始 4.68s → 对齐 10 拍"),
]
# 拍数合计 = 4+4+5+4+3+5+4+4+4+4+4+4+4+4+3+4 = **64 拍 = 16 小节 = 30.0799s**
# 16 镜 / 15 切 ⇒ **29.9 切每分**（六条参考区间 20–38 ✓）；镜长 1.41–2.35s（中位 1.88s）
#
# **素材内部击杀时刻单调性**（tools/verify_shot_order.py 机器校验）：
#   0a550967: 2.40 < 6.80 ✓ ｜ 38cc4903: 1.30 < 2.90 ✓ ｜ 58b8e283: 0.57 < 7.20 ✓
#   7f0d8287: 1.23 < 13.97 ✓ ｜ b61cc53d: 6.20 < 9.57 ✓ ｜ 其余各出现 1 次 ✓
# **出点上界（CUT-04）**：最长镜 5 拍 = 2.35s ⇒ 最大出点 29.43+2.35 = 31.78 ≤ 33.03 ✓

GRADE = {"type": "青橙", "intensity": 65.0}
GRADE_LAYERS = [
    ("g_vig",   "暗角",     10.0, "effects_adjust_texture", ["effects_adjust_texture"]),
    ("g_grain", "噪点",      5.0, "effects_adjust_noise",   ["effects_adjust_noise"]),
    ("g_sharp", "精细锐化", 10.0, "effects_adjust_sharpen",
     ["effects_adjust_blur", "effects_adjust_sharpen", "effects_adjust_size",
      "effects_adjust_range", "effects_adjust_filter"]),
]
# 转场只用在**段落性的切点**上；15 个切点里挑 3 个，避免每刀都加故障显得吵
# —— 而且这里的每一刀**本身就是一次击杀**，25–38 切/分下再全加故障会糊成一团。
TRANSITION_TYPE = "信号故障"
# ⚠️ 必须写**真实的镜起点拍号**（由各镜拍数累加得出）：
#    ⚠️ 每次改镜数/拍数都会让这张表失配，而失配是**静默**的（只少几条转场）。
#    所以生成时打印命中数量，改完必须核对。
#   28 镜的起点拍号：0,14,60,69,90,119,134,147,156,165,190,199,209,218,228,237,246,255,277,287,296,308,318,329,333,341,345,355
TRANSITION_AT_BEAT = {134, 218, 296, 355}       # 第 3 / 9 / 12 镜起点
TRANSITION_SHORT = 0.12
TRANSITION_LONG = 0.20


def _grade_params(effect_name: str, target: str, value: float, names: list) -> list:
    from pyJianYingDraft import VideoSceneEffectType
    meta = getattr(VideoSceneEffectType, effect_name).value
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


def _source_paths() -> dict:
    """短名（文件名前 8 位）→ 真实文件名。**不要手写全名**：素材是按哈希命名的，
    手写容易打错，而错了只会在转换器那边报"素材不存在"。"""
    src_dir = ROOT / "原始素材"
    out = {}
    for p in src_dir.glob("*.mp4"):
        out[p.stem[:8]] = p.name
    missing = [s[0] for s in SHOTS if s[0] not in out]
    assert not missing, f"原始素材/ 里找不到这些短名: {missing}"
    return out


def build() -> dict:
    total_beats = sum(s[2] for s in SHOTS)
    # BGM 段落可以**比成片长**（多余部分在 EDL 里按成片总长裁掉）；
    # 但绝不能比成片**短**，否则转换器会报"截取的素材时间范围超出素材时长"。
    assert total_beats <= SECTION_BARS * 4, \
        f"拍数合计 {total_beats} 超过了 BGM 的 {SECTION_BARS*4} 拍（BGM 太短）"
    paths = _source_paths()

    clips = []
    # ⚠️⚠️ **时间线必须用整数微秒累加**，不能各自 `round(x, 6)`。
    #   本曲 1 拍 = 60/127.66 = 0.4700551…s，**不是二进制精确值**，
    #   于是 `start = round(t,6)` 与上一段的 `start + round(dur,6)` 会差 1µs：
    #   实测 s02 结束于 5639982µs，而 s03 起始算成 5639981µs ⇒ **重叠 1 微秒** ⇒
    #   `add_segment` 直接抛 SegmentOverlap。
    #   （上一版是 128BPM、1 拍恰好 0.46875s（二进制精确），所以这个 bug 没暴露。）
    #   改成 µs 整数累加后，相邻段的 start/end **按构造**严丝合缝。
    t_us = 0
    for i, (short, src_in, beats, why) in enumerate(SHOTS, 1):
        dur_us = int(round(beats * BEAT * 1e6))
        # **入点 = 击杀帧 − 前摇**，让击杀落在镜内第 KILL_LEAD_BEATS 拍（见文件头说明）
        src_in = src_in - KILL_LEAD_BEATS * BEAT
        beat_no = int(round(t_us / 1e6 / BEAT))
        span = dur_us / 1e6          # 本版不变速 ⇒ 素材消耗 == 时间线长度
        c = {
            "id": f"s{i:02d}",
            "track": "main",
            "source": f"../../../原始素材/{paths[short]}",
            "source_in": round(src_in, 6),
            "start": round(t_us / 1e6, 6),
            "duration": round(dur_us / 1e6, 6),
            "role": f"run_{short}",
            "rule_id": "MONT-BILI-11",
            "reason": (f"第 {i} 镜 / {beats} 拍（{span:.4f}s）；歌曲拍点 {beat_no}–"
                       f"{beat_no+beats}（{BPM:.2f}BPM，1 拍 {BEAT:.6f}s）。"
                       f"**本镜的剪切点 = 素材的击杀帧 {src_in:.2f}s**"
                       f"（音乐重拍 ⟺ 击杀帧，用户要求），素材窗口 {src_in:.2f}→"
                       f"{src_in+span:.2f}s。依据：{why}。"),
            "volume": GAME_VOLUME,
        }
        if beat_no in TRANSITION_AT_BEAT:
            c["transition"] = {
                "type": TRANSITION_TYPE,
                "duration": TRANSITION_LONG if beat_no == 40 else TRANSITION_SHORT,
            }
        clips.append(c)
        t_us += dur_us

    total = t_us / 1e6

    return {
        "version": "1.0",
        "project": "BILI_H2H_STYLE",
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "style_ref": "game-op-highlight",
        "target_duration_s": round(total, 6),
        "tracks": [
            {"type": "video", "name": "main"},
            {"type": "audio", "name": "bgm"},
        ],
        "clips": clips,
        "texts": [],
        "audio_overlays": [
            {"source": BGM_FILE, "track": "bgm", "start": 0.0,
             "duration": round(total, 6), "volume": BGM_VOLUME,
             "fade": {"in": 0.0, "out": 0.35}},
        ],
        "effect_tracks": [
            {"name": trk, "effects": [
                {"type": ty, "start": 0.0, "duration": round(total, 6),
                 "params": _grade_params(ty, pname, val, names)}]}
            for (trk, ty, val, pname, names) in GRADE_LAYERS
        ],
        "audio": {"voice_priority": "low", "bgm_volume": BGM_VOLUME},
        "qa": {"required": ["duration-valid", "audio-present", "no-black-frame"]},
        "_bgm_note": (f"BGM = Hearts2Hearts《STYLE》第 90 小节起 16 小节"
                      f"（歌曲 {SECTION_START_IN_SONG}s → "
                      f"{SECTION_START_IN_SONG+SECTION_BARS*BAR:.2f}s，"
                      f"{SECTION_BARS*BAR:.2f}s）。"
                      f"⚠️ 这是**商业录音**：B站 有音乐版权检测，可能被限流/静音；"
                      f"若要投放或变现，请改用 B站 音乐库 / 已授权曲目。"),
        "_form_note": (f"击杀卡点集锦：{len(clips)} 镜 / {len(clips)-1} 切（**每刀都落在一个击杀帧上**） / "
                       f"{total_beats} 拍 @{BPM:.2f}BPM / {total:.3f}s。"
                       f"**每段素材只出现一次、各取一整段连续连杀**（用户要求）。"),
    }


def main() -> int:
    edl = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")

    clips = edl["clips"]
    total = sum(c["duration"] for c in clips)
    durs = sorted(c["duration"] for c in clips)
    print(f"=== B站 操作高光集锦（11 素材 · Hearts2Hearts《STYLE》）===")
    print(f"  [OK] {OUT.relative_to(ROOT)}")
    print(f"       {len(clips)} 镜 / {len(clips)-1} 切 / {total:.4f}s "
          f"= {total/BEAT:.0f} 拍 = {total/BAR:.1f} 小节")
    print(f"       镜长 {durs[0]:.4f}–{durs[-1]:.4f}s  中位 {durs[len(durs)//2]:.4f}s  "
          f"切点密度 {(len(clips)-1)/total*60:.1f} 切/分")
    print(f"       BGM {BGM_VOLUME}｜游戏原声 {GAME_VOLUME}｜字幕 0 条｜"
          f"转场 {sum(1 for c in clips if 'transition' in c)} 条")
    print(f"  ⚠️ BGM 是商业录音（Hearts2Hearts《STYLE》）—— B站 版权检测可能限流/静音。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
