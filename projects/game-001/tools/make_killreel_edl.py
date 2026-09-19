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

输出：`projects/game-001/edl/<name>.json`（默认名 `killreel.json`）
      `projects/game-001/edl/<name>.plan.json`（取段台账，供交付说明引用）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

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


def fs(t: float) -> str:
    return f"{t:.6f}".rstrip("0").rstrip(".")


def load_kills(short: str) -> tuple[list[float], str]:
    """返回 (击杀秒列表, 来源标记)。只取人工判为「我击杀」的；无真值则退回高置信段。

    时刻取 `frame_true`（= 检测帧 + 人工给的 `kill_frame_offset`，即人看着画面判的**真实击杀帧**，
    见 `icon_truth_from_review.py` 的字段表）。没有整数 offset 的行退回 `t_s`。
    """
    tf = V / "icon-review" / "truth.json"
    if tf.exists():
        truth = json.loads(tf.read_text(encoding="utf-8"))["events"]
        rows = [e for e in truth if e["material"] == short]
        if rows:
            def t_of(e) -> float:
                f = e["frame_true"] if e.get("frame_true") is not None else e["frame"]
                return round(f / FPS, 4)
            mine = sorted(t_of(e) for e in rows if e["verdict_mine"] == "Y")
            rejected = [e["t_s"] for e in rows if e["verdict_mine"] != "Y"]
            return mine, ("truth.json（人工判「我击杀」，时刻取人工校正帧 frame_true）"
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
    ap.add_argument("--materials", required=True, help="逗号分隔的素材短 id，顺序即成片顺序")
    ap.add_argument("--name", default="killreel", help="草稿名 / EDL 文件名")
    ap.add_argument("--dry-run", action="store_true", help="只打印取段台账，不写文件")
    args = ap.parse_args()
    shorts = [s.strip() for s in args.materials.split(",") if s.strip()]

    clips, plan, texts = [], [], []
    t_us = 0                       # 时间轴游标：**整数微秒**，避免各自取整造成 1µs 重叠
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
        plan.append({"material": s, "file": f.name, "duration_s": round(dur, 4),
                     "kills_s": kills, "kill_source": ksrc,
                     "n_blocks": len(keeps), "kept_s": round(kept, 4),
                     "kept_ratio": round(kept / dur, 3),
                     "blocks": [{"in_frame": a, "out_frame": b,
                                 "in": round(a / FPS, 6), "out": round(b / FPS, 6),
                                 "dur": round((b - a) / FPS, 6),
                                 "kills_inside": [k for k in kills
                                                  if a / FPS - 1e-9 <= k <= b / FPS + 1e-9]}
                                for a, b in keeps],
                     "cuts": cuts})
        for j, (a, b) in enumerate(keeps, 1):
            a_s, b_s = a / FPS, b / FPS
            inside = [k for k in kills if a_s - 1e-9 <= k <= b_s + 1e-9]
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
                "volume": 1.0,
            })
            t_us += b_us - a_us

    if t_us <= 0 or any(c["duration"] < MIN_CLIP for c in clips):
        raise SystemExit("[FAIL] 有片段短于 MIN_CLIP 或总时长为 0（P0：不出亚秒片段）")

    edl = {
        "version": "1.0",
        "project": args.name,
        "canvas": {"width": CANVAS[0], "height": CANVAS[1], "fps": FPS},
        "style_ref": "game-valorant",
        "target_duration_s": round(t_us / 1e6, 3),
        "tracks": [{"type": "video", "name": "main"}],
        "clips": clips,
        "texts": texts,
        "audio": {"voice_priority": "high", "bgm_volume": 0.0},
        "qa": {"required": ["duration-valid", "no-black-frame", "audio-present"]},
    }
    print(f"素材 {len(shorts)} 条 → 片段 {len(clips)} 个，成片 {t_us / 1e6:.3f}s")
    for p in plan:
        print("  %-9s %6.3fs  我击杀 %d 次 → 保留 %6.3fs（%.0f%%）%d 段  [%s]" % (
            p["material"], p["duration_s"], len(p["kills_s"]), p["kept_s"],
            100 * p["kept_ratio"], p["n_blocks"], p["kill_source"]))
        for b in p["blocks"]:
            print("      [%7.3f, %7.3f] %5.2fs  含击杀 %s" % (
                b["in"], b["out"], b["dur"], b["kills_inside"]))
    if args.dry_run:
        print("[dry-run] 未写文件")
        return 0
    EDL_DIR.mkdir(parents=True, exist_ok=True)
    dst = EDL_DIR / f"{args.name if args.name != 'killreel' else 'killreel'}.json"
    dst.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (EDL_DIR / f"{dst.stem}.plan.json").write_text(
        json.dumps({"name": args.name, "params": {"gap_s": GAP, "pre_s": PRE, "post_s": POST,
                                                  "min_cut_s": MIN_CUT, "snap_s": SNAP},
                    "total_duration_s": round(t_us / 1e6, 3), "materials": plan},
                   ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("[OK] %s" % dst.relative_to(ROOT))
    print("[OK] %s" % (EDL_DIR / f"{dst.stem}.plan.json").relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
