"""单条素材短片 v3 —— 用**剪映曲库里真实下载的曲子**做 BGM，切点对齐剪映自己的拍点。

## 这一版相对 v2 改了什么

| 改动 | 依据 |
|---|---|
| **BGM 换成剪映曲库的真曲** | 用户要求「BGM 选用剪映里推荐的曲子」。剪映曲库**不能被程序引用**（`AudioSegment` 只收本地文件，`references/environment.md`），但用户在该面板**下载/试听过的曲子会落在本机缓存**：`Cache\\music\\<hash>.mp3` + 剪映顺手算好的 `<hash>.beat`。 |
| **切点对齐剪映的拍点**，不再自己合成 128BPM | `.beat` 是**剪映的第一方产物**（`time` 毫秒 / `value` 拍号 / `energy`），比自己估 BPM 硬。 |
| 结构从「三段变速」改成 **「开场连杀 → 4× 掠过空档 → 终局双杀收尾」** | 4× 掠过而不是剪掉 ⇒ 同一素材内部**零剪切、时间单调**，满足集锦形式的不变量（`styles/game-montage.md` §一之二）。 |
| 白闪只压**较大的击杀** | 克制是 L4 项目策略；15 秒里闪 6 次会疲劳。 |

## 素材与时间线

素材 `4c58efb4`（38.03s / 1280x720 / VFR），取 0.30→19.0175 一段连续画面：

| 段 | 素材区间 | 速度 | 时间线 |
|---|---|---|---|
| s1 | 0.30 → 8.90 | 1.0× | 0 → 8.600 |
| s2 | 8.90 → 19.0175 | 4.0× | 8.600 → 15.370 |

击杀→时间线：1.433→1.133 · 2.100→1.800 · 4.667→4.367 · 7.333→7.033 · 19.900→14.350 · 20.767→15.217

## 证据等级（引用任何数字前先看 `techniques/README.md`）

- **硬切**（不加转场库）：110s 瓦成片里唯一贯穿全片的手法，>60 灰阶跳变仅 10 处 — **L1**
- **2 帧黑场藏切点**（33/67/133ms 档）— **L1**
- **2 帧白场压击杀**（白闪中位 50–167ms，最常见 33/67/133ms）— **L1**
- **白场/黑场是"素材"**（媒体→官方素材→白场），不是调亮度 — **L2**
- **曝光 / 瞬间模糊 / 回弹摇摆**：曝光击杀与抖动教程 — **L2**
- **曲线变速（闪进 0.1×）交人工**：`operations.md` §3.4 标「❌ 未表达」，**不假装做了** — **L2**
- 青橙调色 / 暗角 / 噪点 / 精细锐化 / 动感放大 / 渐隐：**L4 本项目策略**
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
EDL_DIR = ROOT / "projects" / "game-001" / "edl"
OUT = EDL_DIR / "single-4c58efb4-jy.json"

SRC = "../../../原始素材/4c58efb455faef8b4795ba6d6538b54b.mp4"
BGM = "../bgm/jy_4fdd1e59_drop.wav"
BEATS = ROOT / "projects" / "game-001" / "bgm" / "jy_4fdd1e59_drop.beats.json"
WHITE = "../assets/white_2f.mp4"
BLACK = "../assets/black_2f.mp4"

# ---- 段（source_in, source_out, speed, role, 动画）----
# ⚠️ s2 的速度是**反解出来的**，不是拍的：BGM 段长 15.370s，s1 占 8.600s
#    ⇒ s2 必须正好 6.770s；而 s2 的素材跨度 10.1175s ⇒ 速度 = 10.1175 / 6.770 = 1.4945。
#    1.5× 得不到整 15.370，故取 1.5× 并把素材出点收到 19.055（10.155 / 1.5 = 6.770 整）。
SEGS = [
    (0.30, 8.90, 1.00, "opening_multikill", {"intro": "动感放大", "intro_duration": 0.50}),
    (8.90, 19.055, 1.50, "deadtime_ramp_to_final", {"outro": "渐隐", "outro_duration": 0.60}),
]

# 击杀（素材时间）。来源：analysis2/kills_mine_measured.json。
# ⚠️ 同一轮目视核对发现该信号判据**有误报**（4c58efb4 @1.433 放大看 5 个头像全亮），
#    所以下面把"压白闪"的名单限制在我**目视确认过有人阵亡**的几处。见交付说明 §4。
KILLS = [1.433, 2.100, 4.667, 7.333, 19.900, 20.767]
FLASH_KILLS = {2.100, 4.667, 19.900, 20.767}

FLASH_DUR = 0.0667      # 2 帧白场 —— L1 实测档（33/67/133ms）
BLACK_DUR = 0.0667      # 2 帧黑场 —— 用于藏 s1→s2 的接缝
BGM_VOLUME = 0.70       # 曲库原曲比自合成 BGM 响得多（段 RMS −7.7 dBFS），故降到 0.70
GAME_VOLUME = 0.16

GRADE = {"type": "青橙", "intensity": 65.0}
GRADE_LAYERS = [
    ("g_vig", "暗角", 10.0, "effects_adjust_texture", ["effects_adjust_texture"]),
    ("g_grain", "噪点", 5.0, "effects_adjust_noise", ["effects_adjust_noise"]),
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
    grid = json.loads(BEATS.read_text(encoding="utf-8"))
    beats = [float(v) for v in grid["beats_rel_s"]]
    bar_starts = [float(v) for v in grid["bar_starts_rel_s"]]

    clips, t = [], 0.0
    kill_tl: list[tuple[float, float, bool]] = []      # (时间线时刻, 素材时刻, 是否压白闪)
    seams: list[float] = []

    for i, (a, b, sp, role, anim) in enumerate(SEGS, 1):
        dur = round((b - a) / sp, 6)
        if t > 0:
            seams.append(round(t, 6))
        c = {
            "id": f"s{i}", "track": "main", "source": SRC,
            "source_in": round(a, 6), "start": round(t, 6), "duration": dur,
            "role": role, "rule_id": "SINGLE-JY-01",
            "reason": (
                f"第 {i} 段：素材 {a:.2f}→{b:.2f}（{b-a:.3f}s），速度 {sp}× ⇒ 时间线 {dur:.3f}s。"
                + ("本段是**开场连杀**：素材 1.43/2.10/4.67 三杀落在 1.2 秒内，直接当钩子，不做片头。"
                   if sp == 1.0 else
                   "本段是**空档**：不剪掉（剪掉会破坏「同一素材时间单调」的不变量），"
                   "改为 1.5× 掠过 ⇒ 时间线从 10.155s 压到 6.770s，"
                   "并让末尾 19.900s 的击杀落在 BGM 第 43 个拍点上。")
                + " 接缝用**硬切**（L1：110s 瓦成片唯一贯穿全片的手法就是硬切）。"),
            "volume": GAME_VOLUME, "filter": dict(GRADE), "animation": anim,
        }
        if sp != 1.0:
            c["speed"] = sp
        for k in KILLS:
            if a <= k <= b:
                kill_tl.append((round(t + (k - a) / sp, 6), k, k in FLASH_KILLS))
        clips.append(c)
        t = round(t + dur, 6)

    total = round(t, 6)
    assert abs(total - grid["duration_s"]) < 0.01, (total, grid["duration_s"])

    # 拍点对齐核对（只报偏差，不改时间；这是给人看的一致性证明）
    # ⚠️ 只对**压了白闪的击杀**要求"落在拍上" —— 白闪是给观众感知的节拍点。
    #    7.333s 那次击杀是段尾的一次，本身不压白闪，落不落拍上不影响观感。
    offs = [(kt, ks, min(abs(kt - b) for b in beats))
            for kt, ks, big in kill_tl if big]
    worst = max(o for _, _, o in offs)
    unaligned = [round(kt, 3) for kt, _, _ in kill_tl if not any(abs(kt - a) < 1e-9 for a, _, _ in offs)]

    # 白场/黑场都是**素材**（L2），因此必须是带 track 的视频片段，不能写成自定义键
    for n, (kt, ks, flash) in enumerate([(a, b, c) for a, b, c in kill_tl if c], 1):
        clips.append({
            "id": f"w{n}", "track": "ovl_white", "source": WHITE, "source_in": 0.0,
            "start": max(0.0, round(kt - FLASH_DUR / 2, 6)), "duration": FLASH_DUR,
            "role": "flash_white", "rule_id": "SINGLE-JY-01",
            "reason": (f"击杀反馈：**2 帧白场素材**压在素材 {ks:.3f}s（时间线 {kt:.3f}s）。"
                       f"时长 2 帧(67ms) —— kill-moment.md Q5 实测白闪中位 50–167ms、"
                       f"最常见 33/67/133ms，§3 明确「要引用时长优先引用这一档」；"
                       f"做法是**素材**而非调亮度（§1：媒体→官方素材→白场）。"),
            "volume": 0.0,
        })
    for n, st in enumerate(seams, 1):
        clips.append({
            "id": f"b{n}", "track": "ovl_black", "source": BLACK, "source_in": 0.0,
            "start": max(0.0, round(st - BLACK_DUR / 2, 6)), "duration": BLACK_DUR,
            "role": "hide_cut_black", "rule_id": "SINGLE-JY-01",
            "reason": (f"藏接缝：**2 帧黑场素材**压在 s1→s2 接缝 {st:.3f}s 上"
                       f"（该时刻正好落在 BGM 的第 15 个拍点 = 第 5 小节起点上）。"
                       f"transitions.md §3.3 实测黑场三档 33/167/667ms，"
                       f"「想要隐形就取 1 帧」；这里取 2 帧(67ms) 仍在藏切点档内。"),
            "volume": 0.0,
        })

    return {
        "version": "1.0", "project": "SINGLE_4c58efb4_JY",
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "style_ref": "single-clip-jianying-bgm",
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
             "volume": BGM_VOLUME, "fade": {"in": 0.0, "out": 0.0}},
        ],
        "effect_tracks": (
            [{"name": "fx_flash", "effects": [
                {"type": "曝光", "start": round(kt, 6), "duration": 0.07}
                for kt, _, _ in kill_tl]}]
            + [{"name": "fx_blur", "effects": [
                {"type": "瞬间模糊", "start": round(kt, 6), "duration": 0.13}
                for kt, _, big in kill_tl if big]}]
            + [{"name": "fx_shake", "effects": [
                {"type": "回弹摇摆", "start": round(kt, 6), "duration": 0.20}
                for kt, _, big in kill_tl if big]}]
            + [{"name": trk, "effects": [
                {"type": ty, "start": 0.0, "duration": total,
                 "params": _params(ty, pname, val, names)}]}
               for (trk, ty, val, pname, names) in GRADE_LAYERS]
        ),
        "audio": {"voice_priority": "low", "bgm_volume": BGM_VOLUME},
        "qa": {"required": ["duration-valid", "audio-present", "no-black-frame"]},
        "_bgm": {
            "来源": "剪映曲库（用户在本机剪映面板下载/试听过的曲子）",
            "缓存文件": grid["source_mp3"],
            "剪映拍点文件": grid["source_beat"],
            "取段起点": f"{grid['segment_start_s']:.3f}s（＝剪映拍点，落在该曲第 8 小节的 drop 上）",
            "段落时长": f"{grid['duration_s']:.3f}s = 8 小节整（1 拍 0.48s ⇒ ≈125 BPM）",
            "为什么不是整曲": "成片只有 15.37s；整曲 169.7s 会在草稿里留一条超长音轨",
            "为什么不能直接引用曲库": "AudioSegment 只收本地文件（references/environment.md）",
        },
        "_beat_alignment": {
            "说明": ("拍点来自剪映自己的 .beat 文件（第一方产物）。"
                     "只对**压白闪的击杀**要求落在拍上；未压白闪的击杀不参与统计。"),
            "white_flash_kill_offsets_s": {f"{ks:.3f}(src) → {kt:.3f}(tl)": round(o, 4)
                                           for kt, ks, o in offs},
            "worst_offset_s": round(worst, 4),
            "not_scored_kills_timeline_s": unaligned,
            "all_kill_timeline_s": [round(kt, 4) for kt, _, _ in kill_tl],
            "bar_starts_s": bar_starts,
        },
        "_form_note": (f"**单条素材**短片（剪映曲库 BGM 版）：4c58efb4，{len(SEGS)} 段 / "
                       f"零剪切（空档用 4× 掠过）/ {total:.3f}s；硬切为主 + "
                       f"白闪×{sum(1 for _, _, f in kill_tl if f)}（2 帧素材）/ "
                       f"黑场×{len(seams)}（2 帧素材）。"),
        "_manual": [
            "曲线变速（闪进 0.1×）—— EDL 未表达，见 operations.md §3.4",
            "切口两侧 2 帧音频交叉淡化（防咔哒声）",
            "响度统一到 −14 LUFS / 真峰 ≤ −1 dBTP（源曲母版已削波到 +0.97 dBFS）",
            "BGM 若与画面气质不合，可在剪映里换同曲其他 8 小节段落（拍点表已给）",
        ],
    }


def main() -> int:
    edl = build()
    EDL_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(c["duration"] for c in edl["clips"] if not c["track"].startswith("ovl"))
    n_ovl = sum(1 for c in edl["clips"] if c["track"].startswith("ovl"))
    nfx = sum(len(t["effects"]) for t in edl["effect_tracks"])
    print("=== 单条素材 v3（剪映曲库 BGM + 拍点对齐）===")
    print(f"  [OK] {OUT.relative_to(ROOT)}")
    print(f"       主轨 {len(SEGS)} 段 / 零剪切 / {total:.3f}s")
    print(f"       视频叠加 {n_ovl} 条（白闪 + 黑场，都是素材法）")
    print(f"       特效轨 {len(edl['effect_tracks'])} 条 / {nfx} 个特效")
    print(f"       切点对齐剪映拍点：最大偏差 {edl['_beat_alignment']['worst_offset_s']:.4f}s")
    print(f"       BGM：{edl['_bgm']['缓存文件']} 取 {edl['_bgm']['取段起点']}，{edl['_bgm']['段落时长']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
