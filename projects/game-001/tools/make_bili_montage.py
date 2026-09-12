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
SECTION_START_IN_SONG = 169.45          # 第 90 小节（歌曲时间）
SECTION_BARS = 16                       # 16 小节
# ⚠️ EDL 在 projects/game-001/edl/ 下，所以 ../bgm/ 才是 projects/game-001/bgm/。
#    写成 ../../bgm/ 会解析到 projects/bgm/，转换器只报一句 WARN、**照常生成草稿但没有 BGM** ——
#    这种静默少了一条轨必须靠报告里的「音效叠加 N 个」核对，不能只看草稿已生成。
BGM_FILE = "../bgm/h2h_style_16bars.wav"
BGM_VOLUME = 0.85                       # 歌曲是主角
# ⚠️ 游戏原声压到 0.28：0.34 时 BGM(0.85) + 原声叠加实测**真峰值 +0.4 dBFS（削顶）**。
#    六条参考的真峰值是 +1.4 / -0.1 / -0.9 / +0.3 / -1.9 / -4.8 —— 削顶在 B站 很常见，
#    但我们自己没有平台端兜底，所以留 -1 dBTP 余量更稳。
GAME_VOLUME = 0.28                      # 游戏原声压低垫底，让击杀/技能透出来

# ---- 11 条素材：短名 → (源文件, 连杀窗口入点, 拍数, 依据) ----
# 按"能量从高到低 + 末镜收在「获胜」"排出一条弧线。
# 拍数合计必须等于 SECTION_BARS × 4 = 64 拍。
SHOTS = [
    ("851622c5", 29.50,  6, "band −3.58dB（全集最响）；绿色技能特效 + 交火"),
    ("4c58efb4", 11.00,  6, "band −4.70dB；交火 + 击杀"),
    ("b61cc53d", 24.00,  5, "band −5.17dB；检视 + 遭遇"),
    ("0a550967", 27.00,  6, "band −5.18dB；右上角连续击杀播报"),
    ("58b8e283", 10.50,  6, "band −5.87dB；运动模糊下的高强度动作"),
    ("9526869d", 14.50,  5, "band −6.02dB；技能 + 击杀"),
    ("7f0d8287", 37.25,  6, "band −6.08dB；击杀播报 + 技能"),
    ("4b0460c4",  4.50,  6, "band −6.82dB；原 a 段，双通道高强度"),
    ("38cc4903",  0.50,  6, "band −8.11dB；开场爆发"),
    ("dcc871b1", 19.00,  6, "band −8.13dB；原 c 段，A 点交火"),
    ("6b2eea34", 21.50,  6, "band −7.44dB；原 b 段，**「获胜」横幅**收尾"),
]

GRADE = {"type": "青橙", "intensity": 65.0}
GRADE_LAYERS = [
    ("g_vig",   "暗角",     10.0, "effects_adjust_texture", ["effects_adjust_texture"]),
    ("g_grain", "噪点",      5.0, "effects_adjust_noise",   ["effects_adjust_noise"]),
    ("g_sharp", "精细锐化", 10.0, "effects_adjust_sharpen",
     ["effects_adjust_blur", "effects_adjust_sharpen", "effects_adjust_size",
      "effects_adjust_range", "effects_adjust_filter"]),
]
# 转场只用在**段落性的切点**上；11 个切点里挑 3 个，避免每刀都加故障显得吵。
TRANSITION_TYPE = "信号故障"
# ⚠️ 这里必须写**真实的镜起点拍号**（由各镜拍数累加得出：0,6,12,17,23,29,34,40,46,52,58）。
#    曾写成 {18,40,58}，18 不对应任何镜起点 ⇒ 那一条被静默忽略（只落了 2 条转场）。
TRANSITION_AT_BEAT = {12, 40, 58}       # 第 3 / 8 / 11 镜起点
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
    assert total_beats == SECTION_BARS * 4, \
        f"拍数合计 {total_beats} ≠ {SECTION_BARS*4}（必须正好铺满所选歌曲段落）"
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
                       f"{beat_no+beats}（{BPM:.2f}BPM，1 拍 {BEAT:.6f}s）；"
                       f"素材 {src_in:.2f}→{src_in+span:.2f}s。"
                       f"**每段素材只切一刀、取一整段连杀**。依据：{why}。"),
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
        "_form_note": (f"操作高光集锦：{len(clips)} 镜 / {len(clips)-1} 切 / "
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
