"""「击杀集锦」粗剪 EDL —— 击杀源换成**中心徽记**（第 14 轮集成测试）。

## 为什么换击杀源

| 源 | 覆盖谁 | 事件语义 | 人工真值 |
|---|---|---|---|
| 右上角播报（第 10 轮，`feed_scan.py`） | **场上任何人** | 只覆盖「一批播报里的第一次击杀」，且旧条目过期上移会**二次触发** | 无 |
| **中心徽记**（第 11 轮，`center_kill_icon.py`） | 疑似**只有自己** | 击杀瞬间出现、约 2s | **34/42 = 81.0%**（第 12 轮玩家本人标注） |

⇒ 做「**我的**击杀集锦」，徽记是更直接的源。本工具**只信人工判为「我击杀」的事件**
（`verification/icon-review/truth.json`，`verdict_mine == "Y"`）；没有真值的素材才退回
高置信段（`icon-scan/<short>.json` 的 `events`），并在输出里标 `kill_source`。

## 取段策略：「排除法」（沿用 `build_by_exclusion.py` 的项目策略，L4）

用户原话：**「我们不做选择，我们做排除，把原始素材里是否有过长的无击杀的画面删除去除」**。

- 整条素材**默认全留**；只删「无击杀持续时间 > `GAP` 秒」的区间；
- 删除时两侧分别留 `POST`（给上一杀收尾）/ `PRE`（给下一杀前摇）；
- 可删部分不足 `MIN_CUT` 秒 ⇒ **不切这一刀**（避免为一两帧画面切口子）；
- 一条素材的保留片段**按时间顺序连在一起**，不与其他素材交错（`GAP` 越大越接近「原片直出」）。

## 切点吸附（"不要切在动作中间"的可计算版本）

删除边界吸附到 `±SNAP` 秒内**运动量最低**的一帧（`analysis2/motion.json`，逐帧帧间差）。
吸附后仍保证「上一杀之后至少留 `POST_MIN` 秒、下一杀之前至少留 `PRE` 秒」。

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/make_killreel_edl.py --materials 7f0d8287,b61cc53d,9526869d --name 击杀集锦_A01_徽记源
    .venv\\Scripts\\python.exe projects/game-001/tools/make_killreel_edl.py --materials ... --dry-run

## 选片：从「素材池」到一条 N 秒（第 16 轮新增）

    --order-by {input,kills,density}   成片顺序（每杀占用片长升序 = density，用得多）
    --target-seconds 30                按上面的顺序**整条素材地**累加，直到累计 ≥ 30s

这条规则是**可复算的**，不要用「手敲一串 --materials」代替它 ——
池子、顺序、目标都写进 `plan.json` 的 `pool_materials` / `selected_materials` / `dropped_materials`。
注意：跨过目标的那条素材是**整条**进来的 ⇒ 实际时长会比目标高出一截（见 `spec/击杀集锦_B01…`）。

## 音频层（第 17 轮新增，`--audio` 打开）

    --audio                     叠加音频层：BGM + 每杀一个 impact + 切入前 whoosh（并压低游戏原声）
    --bgm <path>                BGM 文件（默认 projects/game-001/bgm/bgm_128_18bars.wav）
    --bgm-volume 0.7            BGM 音量
    --voice-volume 0.45         游戏原声音量（1.0 = 原样）
    --impact-volume / --whoosh-volume
    --whoosh {all,material,none} whoosh 落点：all=每个切点前；material=只在换素材的接缝前

依据 `references/techniques/audio.md`（都是既有记录，不是本轮新编的）：

| 约定 | 来源 |
|---|---|
| **impact 落在击杀帧、whoosh 落在切入前** | `audio.md` §3（L4） |
| **BGM 服从剪辑**：先定镜头长度 → 生成曲子 → 裁到成片长度 + 末 0.25s 淡出 | `audio.md` §1（L4） |
| **剪映音效库不能被程序引用** ⇒ 音效自带 wav 走 `audio_overlays` | `audio.md` §4（L2） |
| **没有可脚本化的动态 ducking** ⇒ 用静态音量压低游戏原声 | 转换器只支持固定 `volume`（本轮实测） |

`--audio` **关闭时输出与之前逐字节相同**（回归对照见交付说明）。

## 视觉转场（第 19 轮新增）

    --transition 闪白            在切点挂转场（`类型[:时长秒]`，如 `闪白:0.5`）；默认不加
    --transition-scope {all,material,none}
                                加在哪：all=每个切点；material=只在换素材的接缝（默认）

EDL 语义取自 `references/edl-schema.md`「转场语义」：`transition` 写在片段上
= **「进入本片段」的转场**，所以从第 2 个片段开始挂。转场名必须是剪映 `TransitionType`
枚举里的，写错 `edl_to_draft.py` 会拦下。

⚠️ **预览与剪映在转场上不等价**：预览用「白色叠加层 + alpha 包络」近似，**不改任何时长**；
剪映的转场会**占用前后片段的时间**，成片可能比 EDL 目标短 ⇒ 导出后要复量时长。

输出：`projects/game-001/edl/<name>.json`（默认名 `killreel.json`）
      `projects/game-001/edl/<name>.plan.json`（取段台账，供交付说明引用）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import wave

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
V = ROOT / "projects" / "game-001" / "verification"
A2 = ROOT / "projects" / "game-001" / "analysis2"
EDL_DIR = ROOT / "projects" / "game-001" / "edl"

FPS = 30.0
CANVAS = (1920, 1080)          # 横屏主版（B站）；竖屏包装是另一件事，见交付说明「还缺什么」

# --- 排除法参数（与 build_by_exclusion.py 同一套，L4 项目策略）---
GAP = 3.0          # 无击杀超过这么多秒 = 「过长」，删
PRE = 0.6          # 删除区间的右端留出（给下一杀前摇）
POST = 1.5         # 删除区间的左端留出（给上一杀收尾）
MIN_CUT = 1.5      # 真正能删掉的部分不足这么多秒 ⇒ 不值得切，保留
SNAP = 0.35        # 切点在 ±该秒数内寻找「动作间隙」（运动量局部极小）
POST_MIN = 1.0     # 吸附后「上一杀之后」的硬下限（不许把击杀收尾切掉）
PRE_MIN = 0.4      # 吸附后「下一杀之前」的硬下限
MIN_CLIP = 0.5     # 任一片段短于此值 ⇒ P0 违规（不出亚秒片段）

# --- 音频层参数（第 17 轮；依据 references/techniques/audio.md）---
BGM_DEFAULT = ROOT / "projects" / "game-001" / "bgm" / "bgm_128_18bars.wav"
SFX_DIR = ROOT / "projects" / "game-001" / "sfx"
IMPACT_SFX = ("impact_a.wav", "impact_b.wav")   # 从原素材裁下来的枪声（make_sfx 的产出）
WHOOSH_SFX = "whoosh.wav"
BGM_BARS = 18          # make_bgm.py 的小节数：18 × 1.875s = 33.750s（≥ B01 的 32.167s）
BGM_DROP_BAR = 9       # drop 落第 9 小节 = 15.000s（成片中点；这是判断，不是量出来的）
BGM_VOLUME = 0.7
VOICE_VOLUME = 0.45    # 游戏原声压低（静态 ducking）
IMPACT_VOLUME = 1.0
WHOOSH_VOLUME = 0.8
BGM_FADE_OUT = 0.25


def fs(t: float) -> str:
    return f"{t:.6f}".rstrip("0").rstrip(".")


def wav_dur(p: pathlib.Path) -> float:
    """读 wav 的真实时长 —— 不硬编码音效长度（长度会随 make_sfx.py 改动）。"""
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def rel_to_edl(p: pathlib.Path) -> str:
    """EDL 里的相对路径基准 = EDL 文件所在目录（edl_to_draft.build.resolve 的约定）。"""
    return "../" + p.relative_to(EDL_DIR.parent).as_posix()


def load_kills(short: str) -> tuple[list[float], str]:
    """返回 (击杀秒列表, 来源标记)。只取人工判为「我击杀」的；无真值则退回高置信段。

    时刻取 `frame_true_note`（= 检测帧 + 人工给的 `kill_frame_offset` + 从备注推出的偏移）。
    为什么**不用** `frame_true`：`frame_true` 不含备注偏移，而 `review.csv` 里有 5 行
    （全都是我击杀）把 offset 写成 `?`、只在备注里写「0.5 秒才看到击杀」
    ⇒ 用 `frame_true` 会让这 5 次的时刻**早 15 帧（0.5s）**（第 15 轮用逐帧图发现的）。
    """
    tf = V / "icon-review" / "truth.json"
    if tf.exists():
        truth = json.loads(tf.read_text(encoding="utf-8"))["events"]
        rows = [e for e in truth if e["material"] == short]
        if rows:
            def t_of(e) -> float:
                f = e.get("frame_true_note")
                if f is None:
                    f = e["frame_true"] if e.get("frame_true") is not None else e["frame"]
                return round(f / FPS, 4)
            mine = sorted(t_of(e) for e in rows if e["verdict_mine"] == "Y")
            rejected = [e["t_s"] for e in rows if e["verdict_mine"] != "Y"]
            return mine, ("truth.json（人工判「我击杀」，时刻取人工校正帧 frame_true_note）"
                          + (f"，已排除 {len(rejected)} 处误报：{rejected}" if rejected else "，无误报"))
    d = json.loads((V / "icon-scan" / f"{short}.json").read_text(encoding="utf-8"))
    return sorted(e["t_s"] for e in d["events"]), "icon-scan 高置信段（**无人工真值**）"


def motion_of(short: str) -> list[float] | None:
    p = A2 / "motion.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8")).get(short, {}).get("motion")


def snap(t: float, motion, lo: float, hi: float) -> tuple[float, float]:
    """在 [lo, hi] ∩ [t−SNAP, t+SNAP] 内找运动量最小的一帧，返回 (新时刻, 原时刻)。"""
    if not motion:
        return (round(t * FPS), round(t * FPS)), t
    f0 = max(int(round((t - SNAP) * FPS)), int(round(lo * FPS)), 0)
    f1 = min(int(round((t + SNAP) * FPS)), int(round(hi * FPS)), len(motion) - 1)
    if f1 <= f0:
        return (round(t * FPS), round(t * FPS)), t
    i = min(range(f0, f1 + 1), key=lambda k: motion[k])
    return (i, i), t


def us(f: int) -> int:
    """帧号 → 整数微秒。时间轴全程用**整数微秒**累加，避免各自取整造成 1µs 重叠。"""
    return round(f * 1_000_000 / FPS)


def blocks_of(kills: list[float], dur: float, motion):
    """排除法 + 切点吸附 ⇒ [(起始帧, 结束帧)]（整数帧，30fps 网格）。"""
    bounds = [0.0] + list(kills) + [dur]
    keeps, cuts = [], []           # keeps 一律用**帧号**：全程整数帧，不混秒（第 14 轮的坑）
    cur_f = 0
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        gap = hi - lo
        gs = lo + (POST if lo > 0 else 0.0)
        ge = hi - (PRE if hi < dur else 0.0)
        if gap > GAP and (ge - gs) > MIN_CUT:
            (gs_f, _), _ = snap(gs, motion, lo + POST_MIN, gs + SNAP)
            (ge_f, _), _ = snap(ge, motion, ge - SNAP, hi - PRE_MIN)
            if ge_f - gs_f <= 0:
                continue
            # 片头裁掉时 gs==0 ⇒ 「上一段」是空的：只把游标推过去，不要留 0 长片段
            if gs_f - cur_f > 0:
                keeps.append((cur_f, gs_f))
                cuts.append({"t": round(gs_f / FPS, 6), "from": gs, "why": "上一杀收尾后切出"})
            else:
                cuts.append({"t": 0.0, "from": 0.0, "why": "片头无击杀段整段删除（无上一杀）"})
            cur_f = ge_f
            cuts.append({"t": round(ge_f / FPS, 6), "from": ge, "why": "下一杀前摇前切入"})
    dur_f = round(dur * FPS)
    keeps.append((cur_f, dur_f))
    out = []
    for af, bf in keeps:
        bf = min(bf, dur_f)            # 末尾片段不许越出素材总帧数
        af = min(af, bf)
        if bf - af >= round(MIN_CLIP * FPS):
            out.append((af, bf))
        elif bf - af > 0 and out:      # 非空但太短的尾巴并进上一段（宁多留，P0 不出亚秒片段）
            out[-1] = (out[-1][0], bf)
        # bf == af（片尾整段被删掉）⇒ 什么都不做，别把刚删掉的画面接回来
    return out, cuts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", required=True, help="逗号分隔的素材短 id（这是**素材池**）")
    ap.add_argument("--name", default="killreel", help="草稿名 / EDL 文件名")
    ap.add_argument("--order-by", default="input", choices=("input", "kills", "density"),
                    help="成片顺序：input=按 --materials 给的原顺序；kills=按我击杀数降序；"
                         "density=按「每杀占用片长」升序（越大越省时长，说明击杀越密）")
    ap.add_argument("--target-seconds", type=float, default=None,
                    help="目标时长：按上面的顺序**整条素材地**累加，直到累计 ≥ 这个值"
                         "（跨过它的那条**算进来**）；不给就全用")
    ap.add_argument("--audio", action="store_true",
                    help="叠加音频层：BGM + 每杀一个 impact + 切入前 whoosh，并把游戏原声压到 --voice-volume")
    ap.add_argument("--bgm", default=None, help=f"BGM 文件（默认 {BGM_DEFAULT.name}）")
    ap.add_argument("--bgm-volume", type=float, default=BGM_VOLUME)
    ap.add_argument("--voice-volume", type=float, default=VOICE_VOLUME,
                    help="游戏原声音量（1.0 = 原样；剪映没有可脚本化的动态 ducking，所以这里是静态压低）")
    ap.add_argument("--impact-volume", type=float, default=IMPACT_VOLUME)
    ap.add_argument("--whoosh-volume", type=float, default=WHOOSH_VOLUME)
    ap.add_argument("--whoosh", default="all", choices=("all", "material", "none"),
                    help="whoosh 落点：all=每个切点前（默认）；material=只在换素材的接缝前；none=不放")
    ap.add_argument("--transition", default=None,
                    help="在切点挂转场，`类型[:时长秒]`，如 `闪白` 或 `闪白:0.5`；默认不加")
    ap.add_argument("--transition-scope", default="material",
                    choices=("all", "material", "none"),
                    help="转场加在哪：all=每个切点；material=只在换素材的接缝（默认）；none=不加")
    ap.add_argument("--dry-run", action="store_true", help="只打印取段台账，不写文件")
    args = ap.parse_args()
    shorts = [s.strip() for s in args.materials.split(",") if s.strip()]

    # ---- 第一遍：逐素材算保留片段（每条素材独立 ⇒ 成片顺序可以随便换）----
    pool = []
    for s in shorts:
        f = next(SRC.glob(f"{s}*.mp4"), None)
        if f is None:
            raise SystemExit(f"[FAIL] 没有素材 {s}*.mp4")
        kills, ksrc = load_kills(s)
        if not kills:
            raise SystemExit(f"[FAIL] {s} 没有可用的击杀时刻")
        motion = motion_of(s)
        dur = (len(motion) / FPS if motion
               else json.loads((V / "icon-scan" / f"{s}.json").read_text(encoding="utf-8"))["n_frames"] / FPS)
        keeps, cuts = blocks_of(kills, dur, motion)
        kept = sum(b - a for a, b in keeps) / FPS
        pool.append({"material": s, "file": f, "duration_s": round(dur, 4),
                     "kills_s": kills, "kill_source": ksrc,
                     "n_blocks": len(keeps), "kept_s": round(kept, 4),
                     "kept_ratio": round(kept / dur, 3),
                     "blocks": [{"in_frame": a, "out_frame": b,
                                 "in": round(a / FPS, 6), "out": round(b / FPS, 6),
                                 "dur": round((b - a) / FPS, 6),
                                 "kills_inside": [k for k in kills
                                                  if a / FPS - 1e-9 <= k <= b / FPS + 1e-9]}
                                for a, b in keeps],
                     "cuts": cuts, "keeps": keeps})

    # ---- 选片与排序：让「从池子里挑哪几条素材」变成可复算的规则，而不是手敲的顺序 ----
    ordered = list(pool)
    if args.order_by == "density":
        ordered.sort(key=lambda p: p["kept_s"] / max(1, len(p["kills_s"])))
    elif args.order_by == "kills":
        ordered.sort(key=lambda p: -len(p["kills_s"]))
    selected, dropped, acc = [], [], 0.0
    for p in ordered:
        if args.target_seconds is not None and acc >= args.target_seconds:
            dropped.append(p["material"])
            continue
        selected.append(p)
        acc += p["kept_s"]

    # ---- 第二遍：按成片顺序拼片段（时间轴游标 = **整数微秒**，避免各自取整造成 1µs 重叠）----
    clips, texts = [], []
    kill_tl: list[float] = []      # 每次击杀在成片时间轴上的位置（音频层用）
    t_us = 0
    voice_vol = args.voice_volume if args.audio else 1.0
    for p in selected:
        s, f = p["material"], p["file"]
        for j, (a, b) in enumerate(p["keeps"], 1):
            a_s, b_s = a / FPS, b / FPS
            inside = [k for k in p["kills_s"] if a_s - 1e-9 <= k <= b_s + 1e-9]
            a_us, b_us = us(a), us(b)
            clips.append({
                "id": f"{s}-{j:02d}", "track": "main",
                "source": f"../../../原始素材/{f.name}",
                "source_in": a_us / 1e6, "start": t_us / 1e6,
                "duration": (b_us - a_us) / 1e6, "role": "body",
                "rule_id": "REEL-EXCLUDE-01",
                "reason": (f"排除法：{s} 保留 [{a_s:.3f}, {b_s:.3f}]（{b_s - a_s:.2f}s），"
                           f"含 {len(inside)} 次我击杀 {['%.3f' % k for k in inside]}；"
                           f"无击杀段 > {GAP}s 才删，删除处两侧留 POST {POST}s / PRE {PRE}s，"
                           f"切点已吸附到 ±{SNAP}s 内运动量最小帧，落点对齐 30fps 整数帧"),
                "confidence": 0.81,
                "volume": voice_vol,
            })
            for k in inside:
                kill_tl.append(t_us / 1e6 + (k - a_s))
            t_us += b_us - a_us

    if t_us <= 0 or any(c["duration"] < MIN_CLIP for c in clips):
        raise SystemExit("[FAIL] 有片段短于 MIN_CLIP 或总时长为 0（P0：不出亚秒片段）")

    # ---- 视觉转场（第 19 轮）----
    # EDL 语义（references/edl-schema.md「转场语义」）：transition 写在片段上
    #   = 「**进入本片段**的转场」⇒ 从第 2 个片段开始挂；挂在第 1 个片段上无效（执行层会忽略）。
    # ⚠️ 转场名必须是剪映 TransitionType 枚举里的，写错 edl_to_draft.py 会拦下。
    # ⚠️ 转场**不改变 EDL 里任何片段的时长**（改时长是执行层/剪映的事）。
    n_trans = 0
    trans_scope = args.transition_scope if args.transition else "none"
    if args.transition:
        tname, _, tdur = args.transition.partition(":")
        trans_spec = {"type": tname}
        if tdur:
            trans_spec["duration"] = float(tdur)
        for i, c in enumerate(clips[1:], 1):
            if trans_scope == "material" and c["source"] == clips[i - 1]["source"]:
                continue
            c["transition"] = dict(trans_spec)
            n_trans += 1

    # ---- 音频层（第 17 轮）----
    # 依据 references/techniques/audio.md 的既有约定（不是本轮新编的）：
    #   · impact 落在**击杀帧**、whoosh 落在**切入前**  （audio.md §3，L4）
    #   · BGM 服从剪辑：先定镜头长度 → 生成曲子 → 裁到成片长度 + 末 0.25s 淡出（§1，L4）
    #   · 剪映音效库不能被程序引用 ⇒ 自带 wav 走 audio_overlays（§4，L2）
    #   · 剪映没有可脚本化的动态 ducking ⇒ 用**静态音量**压低游戏原声
    audio_overlays: list[dict] = []
    audio_note = None
    total_s = t_us / 1e6
    if args.audio:
        bgm_path = pathlib.Path(args.bgm) if args.bgm else BGM_DEFAULT
        if not bgm_path.exists():
            raise SystemExit(
                f"[FAIL] 找不到 BGM：{bgm_path}\n"
                "       先跑：.venv/Scripts/python.exe projects/game-001/tools/make_bgm.py "
                f"{BGM_BARS} {BGM_DROP_BAR}")
        audio_overlays.append({
            "source": rel_to_edl(bgm_path), "track": "bgm", "start": 0.0,
            "duration": round(total_s, 6), "volume": args.bgm_volume,
            "fade": {"in": 0.0, "out": round(min(BGM_FADE_OUT, total_s), 6)},
        })
        impact_files = [SFX_DIR / n for n in IMPACT_SFX if (SFX_DIR / n).exists()]
        if not impact_files:
            raise SystemExit(f"[FAIL] {SFX_DIR} 下没有 impact_*.wav（先跑 make_sfx.py）")
        n_impact = 0
        for i, t in enumerate(kill_tl):
            dur = min(wav_dur(impact_files[0]), total_s - t)
            if dur < 0.02:
                continue
            audio_overlays.append({
                "source": rel_to_edl(impact_files[i % len(impact_files)]),
                "track": "sfx_impact", "start": round(t, 6),
                "duration": round(dur, 6), "volume": args.impact_volume,
            })
            n_impact += 1
        whoosh_path = SFX_DIR / WHOOSH_SFX
        if not whoosh_path.exists():
            raise SystemExit(f"[FAIL] 找不到 {whoosh_path}（先跑 make_sfx.py）")
        whoosh_dur = wav_dur(whoosh_path)
        cut_tl = [c["start"] for c in clips[1:]]
        if args.whoosh == "material":
            cut_tl = [c["start"] for i, c in enumerate(clips[1:], 1)
                      if c["source"] != clips[i - 1]["source"]]
        elif args.whoosh == "none":
            cut_tl = []
        n_whoosh = 0
        for t in cut_tl:
            start = max(0.0, t - whoosh_dur)          # whoosh 的**尾**落在切点上 = 「切入前」
            dur = min(whoosh_dur, t - start)
            if dur < 0.02:
                continue
            audio_overlays.append({
                "source": rel_to_edl(whoosh_path),
                "track": "sfx_whoosh", "start": round(start, 6),
                "duration": round(dur, 6), "volume": args.whoosh_volume,
            })
            n_whoosh += 1
        audio_note = {
            "bgm": bgm_path.relative_to(ROOT).as_posix(),
            "bgm_volume": args.bgm_volume,
            "voice_volume": args.voice_volume,
            "impact_volume": args.impact_volume,
            "whoosh_volume": args.whoosh_volume,
            "whoosh_mode": args.whoosh,
            "n_impact": n_impact,
            "n_whoosh": n_whoosh,
            "kill_timeline_s": [round(t, 6) for t in kill_tl],
            "cut_timeline_s": [round(t, 6) for t in cut_tl],
            "rules": "impact 落击杀帧、whoosh 落切入前（audio.md §3，L4）；"
                     "BGM 服从剪辑、裁到成片长度 + 末 0.25s 淡出（§1，L4）；"
                     "动态 ducking 不可脚本化 ⇒ 静态压低游戏原声",
        }
        print("音频层：BGM %s（音量 %s） + impact×%d（落击杀帧）+ whoosh×%d（落切入前）；游戏原声 1.0 → %s"
              % (bgm_path.name, args.bgm_volume, n_impact, n_whoosh, args.voice_volume))

    tracks = [{"type": "video", "name": "main"}]
    audio = {"voice_priority": "high", "bgm_volume": 0.0}
    if args.audio:
        tracks += [{"type": "audio", "name": "bgm"},
                   {"type": "audio", "name": "sfx_impact"},
                   {"type": "audio", "name": "sfx_whoosh"}]
        audio = {"voice_priority": "high", "bgm_volume": args.bgm_volume}

    edl = {
        "version": "1.0",
        "project": args.name,
        "canvas": {"width": CANVAS[0], "height": CANVAS[1], "fps": FPS},
        "style_ref": "game-valorant",
        "target_duration_s": round(t_us / 1e6, 3),
        "tracks": tracks,
        "clips": clips,
        "texts": texts,
        "audio": audio,
        "qa": {"required": ["duration-valid", "no-black-frame", "audio-present"]},
    }
    if audio_overlays:
        edl["audio_overlays"] = audio_overlays
        edl["_audio"] = {
            "依据": "references/techniques/audio.md（§1 BGM 服从剪辑 / §3 音效对位 / §4 音效库不可程序引用）",
            "对位": "impact 落在击杀帧；whoosh 的尾落在切点上（＝切入前）",
            "游戏原声": f"静态压低到 {args.voice_volume}（剪映没有可脚本化的动态 ducking）",
            "响度": "草稿不做响度归一化 —— −14 LUFS / ≤ −1 dBTP 仍须人工（见交付说明）",
        }
        # 与先例单素材 BGM 版同一套「人工清单」：EDL 表达不了的，写下来别假装做了
        edl["_manual"] = [
            "响度统一到 ≈ −14 LUFS、真峰 ≤ −1 dBTP —— 草稿里**没有**限幅器，这一步必须人工",
            "各切点两侧 2 帧音频交叉淡化（防咔哒声）—— EDL 未表达",
            "BGM 若与画面气质不合可在剪映里换曲：EDL 不关心 BGM 内容，只按时间码摆位置",
        ]
    if n_trans:
        edl.setdefault("_manual", []).append(
            f"转场 ×{n_trans} 处（{args.transition}）在剪映里会**占用前后片段的时间** ⇒ "
            "成片时长可能比 EDL 的目标短；预览用的是 alpha 叠加、**不改时长** —— "
            "两者不完全等价，导出后要复量时长")
    print(f"素材 {len(shorts)} 条 → 片段 {len(clips)} 个，成片 {t_us / 1e6:.3f}s")
    print("素材池 %d 条 → 选中 %d 条、丢弃 %d 条；顺序 = %s，目标 = %s" % (
        len(pool), len(selected), len(dropped), args.order_by,
        "无（全用）" if args.target_seconds is None else "%.1fs" % args.target_seconds))
    if dropped:
        print("  丢弃（已满足目标）：%s" % ", ".join(dropped))
    for p in selected:
        print("  %-9s %6.3fs  我击杀 %d 次 → 保留 %6.3fs（%.0f%%）%d 段  [%s]" % (
            p["material"], p["duration_s"], len(p["kills_s"]), p["kept_s"],
            100 * p["kept_ratio"], p["n_blocks"], p["kill_source"]))
        for b in p["blocks"]:
            print("      [%7.3f, %7.3f] %5.2fs  含击杀 %s" % (
                b["in"], b["out"], b["dur"], b["kills_inside"]))
    if n_trans:
        print("视觉转场：%s × %d 处（范围 %s）" % (args.transition, n_trans, trans_scope))
    if args.dry_run:
        print("[dry-run] 未写文件")
        return 0
    EDL_DIR.mkdir(parents=True, exist_ok=True)
    dst = EDL_DIR / f"{args.name if args.name != 'killreel' else 'killreel'}.json"
    dst.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (EDL_DIR / f"{dst.stem}.plan.json").write_text(
        json.dumps({"name": args.name, "params": {"gap_s": GAP, "pre_s": PRE, "post_s": POST,
                                                  "min_cut_s": MIN_CUT, "snap_s": SNAP,
                                                  "order_by": args.order_by,
                                                  "target_seconds": args.target_seconds,
                                                  "transition": args.transition,
                                                  "transition_scope": trans_scope},
                    **({"audio_layer": audio_note} if audio_note else {}),
                    "pool_materials": [p["material"] for p in pool],
                    "selected_materials": [p["material"] for p in selected],
                    "dropped_materials": dropped,
                    "total_duration_s": round(t_us / 1e6, 3),
                    # file 在内存里是 Path（要拿 .name 拼 EDL 的 source），写盘时转成字符串
                    "materials": [{**{k: v for k, v in p.items() if k not in ("keeps", "file")},
                                   "file": p["file"].name} for p in selected]},
                   ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("[OK] %s" % dst.relative_to(ROOT))
    print("[OK] %s" % (EDL_DIR / f"{dst.stem}.plan.json").relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
