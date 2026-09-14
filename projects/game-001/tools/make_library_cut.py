"""**全新**生成一版剪辑：从原始素材库取材，落实 skill 知识库里的实证结论。

> 用户："你现在从**原始素材库**里运用这些库里面的知识**重新给我生成一个新的剪辑**，
>  **不要从之前的草稿上改**。"

⇒ 本脚本**不读任何既有 EDL**，依据全部来自：
- 素材本体（`原始素材/`）
- 知识库的**手法与实测时长**（`references/techniques/`）
- **实测标定**的击杀列表（`analysis2/kills_mine_measured.json`）

## 落实了哪几条知识（逐条带等级）

| 决策 | 依据 | 等级 |
|---|---|---|
| 用**实测标定**的击杀列表 | `kill-extraction.md`：旧带 `y600~720` 只截到横幅下缘 14px，装的是技能栏/弹匣，**任何 HUD 变化都会误触发**；修正带 `y520~620` 能剔除已确证的误报（4b0460c4 @16.733） | **L1** |
| **硬切**为主，不加转场库 | 110s 瓦成片「硬切是唯一贯穿全片的手法」，>60 灰阶大跳变仅 10 处 | **L1** |
| 接缝压 **2 帧黑场素材** | 黑场三档 33/167/667ms，「想要隐形就取 1 帧」 | **L1** |
| 击杀压 **2 帧白场素材** | 白闪中位 50–167ms，最常见 33/67/133ms；§3「要引用时长优先引用这一档」 | **L1** |
| 反馈特效 `曝光` / `瞬间模糊` / `回弹摇摆` | 出自曝光击杀与抖动教程 | **L2** |
| 只对**较大击杀**加白闪与模糊 | 避免 15 秒闪 6 次；克制是 L4 项目策略 | **L4** |
| **曲线变速交人工** | `operations.md` §3.4：曲线变速「❌ 未表达」 | **L2** |

## 结构：每段素材**零剪切**，内部用变速压掉无击杀空档
这是把用户"不要切碎 / 不要空画面"两条要求**同时**满足的唯一办法：
- 空档**不剪掉**（所以没有跳切，不需要藏）；
- 空档**加速 3.5× 掠过**（所以不拖沓）。

每条素材 = **一个连续段**（`source_in` 单调、无跳跃），段与段之间硬切 + 2 帧黑场。
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
KILLS_MEASURED = ROOT / "projects/game-001/analysis2/kills_mine_measured.json"
OUT = ROOT / "projects" / "game-001" / "edl" / "library-fresh-01.json"
BGM = "../bgm/h2h_style_lib.wav"
WHITE = "../assets/white_2f.mp4"
BLACK = "../assets/black_2f.mp4"

# ---- 工程参数（L4：本项目策略，不是通用手法）----
PRE = 0.6          # 击杀前留白（≈击杀播报滞后于开火 0.2–0.5s，L3/L4）
POST = 1.5         # 击杀后留白
GAP = 3.0          # 击杀间隔 > 此值 ⇒ 视为"空档"，用变速掠过（而不剪掉）
RAMP = 3.5         # 空档加速倍率
MIN_KILLS = 4      # 进入成片的素材至少要有这么多次自身击杀
TAIL_BIG = 0.8     # 什么样的击杀算"较大"（其后有 >=TAIL_BIG 秒的收尾）——这里用简化判据

BGM_VOLUME = 0.80
GAME_VOLUME = 0.32
FLASH_DUR = 0.0667     # 2 帧白场
BLACK_DUR = 0.0667     # 2 帧黑场
CLOSER = "6b2eea34"    # 含「获胜」横幅，固定收尾

GRADE = {"type": "青橙", "intensity": 65.0}
GRADE_LAYERS = [
    ("g_vig",   "暗角",     10.0, "effects_adjust_texture", ["effects_adjust_texture"]),
    ("g_grain", "噪点",      5.0, "effects_adjust_noise",   ["effects_adjust_noise"]),
    ("g_sharp", "精细锐化", 10.0, "effects_adjust_sharpen",
     ["effects_adjust_blur", "effects_adjust_sharpen", "effects_adjust_size",
      "effects_adjust_range", "effects_adjust_filter"]),
]
ANIM_FIRST = {"intro": "动感放大", "intro_duration": 0.50}
ANIM_LAST = {"outro": "渐隐", "outro_duration": 0.60}


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


def kill_windows(ks: list[float]) -> list[tuple[float, float]]:
    """把击杀序列切成若干"活跃窗口"：相邻击杀间隔 <= GAP 的归为一组。"""
    groups = [[ks[0]]]
    for a, b in zip(ks, ks[1:]):
        groups[-1].append(b) if (b - a) <= GAP else groups.append([b])
    return [(g[0], g[-1]) for g in groups]


def main() -> int:
    km = json.loads(KILLS_MEASURED.read_text(encoding="utf-8"))
    paths = {p.stem[:8]: p.name for p in (ROOT / "原始素材").glob("*.mp4")}

    # 素材真实时长 —— 窗口右端必须钳制在它之内，否则下游会报
    # 「source_in + duration 超出 video 流可用时长」。
    from pymediainfo import MediaInfo

    def clip_dur(name: str) -> float:
        for tr in MediaInfo.parse(str(ROOT / "原始素材" / name)).tracks:
            if tr.track_type == "Video":
                return tr.duration / 1000.0
        return 0.0

    DUR = {s_: clip_dur(r_["file"]) for s_, r_ in km.items()}

    # 选材：自身击杀数 >= MIN_KILLS；按击杀数递增排（一杀→多杀），收尾固定
    picks = [(s, r) for s, r in km.items() if len(r["mine"]) >= MIN_KILLS]
    picks.sort(key=lambda kv: (kv[0] == CLOSER, len(kv[1]["mine"]), kv[0]))
    if not picks:
        print("[FAIL] 没有素材满足 MIN_KILLS")
        return 1

    clips: list[dict] = []
    overlays: list[dict] = []
    kill_tl: list[tuple[float, bool]] = []
    seams: list[float] = []
    t_us = 0          # ★ 时间线一律用**整数微秒**累加，避免各自 round 后差几微秒
    seg_no = 0

    for bi, (short, r) in enumerate(picks, 1):
        ks = sorted(r["mine"])
        wins = kill_windows(ks)
        lo = max(0.0, wins[0][0] - PRE)
        hi = min(DUR.get(short, 1e9), wins[-1][1] + POST)   # ★ 不许越过素材末尾
        # 逐窗口生成：活跃段 1.0×，窗口之间的空档 RAMP×
        # 每个连杀窗口的**最后一次**击杀 = 该条素材的高潮，只有它拿全套反馈
        climax = {w[1] for w in wins}
        parts: list[tuple[float, float, float]] = []   # (入点, 出点, 速度)
        prev_end = lo
        for a, b in wins:
            a2, b2 = max(lo, a - PRE), min(hi, b + POST)
            if a2 > prev_end + 0.05:
                parts.append((prev_end, a2, RAMP))     # 空档：加速掠过
            parts.append((a2, b2, 1.0))
            prev_end = b2
        if hi > prev_end + 0.05:
            parts.append((prev_end, hi, RAMP))

        if bi > 1:
            seams.append(round(t_us / 1e6, 6))
        for pi, (a, b, sp) in enumerate(parts, 1):
            seg_no += 1
            dur = (b - a) / sp
            dur_us = int(round(dur * 1e6))
            anim = ANIM_FIRST if (bi == 1 and pi == 1) else (
                ANIM_LAST if (bi == len(picks) and pi == len(parts)) else None)
            c = {
                "id": f"c{bi:02d}p{pi}", "track": "main",
                "source": f"../../../原始素材/{paths[short]}",
                "source_in": round(a, 6),
                "start": round(t_us / 1e6, 6),
                "duration": round(dur_us / 1e6, 6),
                "role": f"{short}_part{pi}", "rule_id": "LIB-FRESH-01",
                "reason": (f"素材 {short} 第 {bi} 条（自身击杀 {len(ks)} 次）；本段 "
                           f"素材 {a:.2f}→{b:.2f}（{b-a:.2f}s）速度 {sp}× ⇒ 时间线 {dur:.3f}s。"
                           + ("**空档用变速掠过而非剪掉** —— 保住连续性、又不拖沓。" if sp != 1.0
                              else "击杀活跃段，常速保留完整过程（击杀播报滞后开火 0.2–0.5s，故留前摇）。")),
                "volume": GAME_VOLUME, "filter": dict(GRADE),
            }
            if sp != 1.0:
                c["speed"] = sp
            if anim:
                c["animation"] = anim
            clips.append(c)
            for k in ks:
                if a <= k <= b:
                    kill_tl.append((round(t_us / 1e6 + (k - a) / sp, 6), k in climax))
            t_us += dur_us

    total = round(t_us / 1e6, 6)

    # 2 帧白场：压在击杀上（L1 实测档）
    for n, (kt, big) in enumerate([(k, b) for k, b in kill_tl if b], 1):
        overlays.append({"id": f"w{n}", "track": "ovl_white", "source": WHITE,
                         "source_in": 0.0, "start": max(0.0, round(kt - FLASH_DUR / 2, 6)),
                         "duration": FLASH_DUR, "role": "flash_white",
                         "rule_id": "LIB-FRESH-01",
                         "reason": ("击杀反馈：2 帧白场**素材**压在击杀上。"
                                    "kill-moment.md Q5 实测白闪 50–167ms、最常见 33/67/133ms；"
                                    "§1 做法为官方素材→白场。"),
                         "volume": 0.0})
    # 2 帧黑场：压在素材接缝上藏切点
    for n, st in enumerate(seams, 1):
        overlays.append({"id": f"b{n}", "track": "ovl_black", "source": BLACK,
                         "source_in": 0.0, "start": max(0.0, round(st - BLACK_DUR / 2, 6)),
                         "duration": BLACK_DUR, "role": "hide_cut_black",
                         "rule_id": "LIB-FRESH-01",
                         "reason": ("藏切点：2 帧黑场**素材**压在换素材接缝上。"
                                    "transitions.md §3.3 实测黑场 33/167/667ms，"
                                    "取「隐形」那一档（1–2 帧）。"),
                         "volume": 0.0})

    edl = {
        "version": "1.0", "project": "LIBRARY_FRESH_01",
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "style_ref": "game-montage",
        "target_duration_s": total,
        "tracks": [
            {"type": "video", "name": "main"},
            {"type": "video", "name": "ovl_black"},
            {"type": "video", "name": "ovl_white"},
            {"type": "audio", "name": "bgm"},
        ],
        "clips": clips + overlays,
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
        "_form_note": (f"**全新**库收割版：{len(picks)} 条素材 / {len(clips)} 个主轨段 / "
                       f"零素材内剪辑 / {total:.3f}s。空档用 {RAMP}× 变速掠过。"),
        "_kill_source": "analysis2/kills_mine_measured.json（实测标定，见 references/kill-extraction.md）",
        "_manual": ["曲线变速（闪进 0.1×）—— EDL 未表达，operations.md §3.4",
                    "切口两侧 2 帧音频交叉淡化（防咔哒声）",
                    "如需动效模糊盖切口 → 调整层 + transform keyframe"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")

    n_main = len(clips)
    print("=== 全新库收割版（applied skill knowledge）===")
    print(f"  [OK] {OUT.relative_to(ROOT)}")
    print(f"       素材 {len(picks)} 条: {', '.join(s for s, _ in picks)}")
    print(f"       主轨 {n_main} 段 / 叠加 {len(overlays)} 条 / 总长 {total:.3f}s")
    print(f"       素材内剪辑：**零**（每条素材 kick 连续，空档用 {RAMP}× 掠过）")
    print(f"       击杀反馈 {len(kill_tl)} 处（曝光+瞬间模糊+回弹摇摆）｜白闪 {len(overlays)-len(seams)} ｜黑场 {len(seams)}")
    print(f"       转场：**0 条硬切**（L1：瓦成片贯穿全片的手法）")
    print(f"       BGM 需 >= {total:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
