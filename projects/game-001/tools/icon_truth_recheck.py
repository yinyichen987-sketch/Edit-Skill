"""把 42 个中心徽记事件的**整段**画成证据图 + 量出「段内到底有没有徽记」（第 12 轮）。

## 为什么需要它

第 11 轮的标注包（`make_icon_review_sheets.py`）对每个事件只画了 `frame-4 … frame+3` 这 8 帧。
人工标注回来以后发现：**有 3 个被判「不是击杀」的事件，其实是「起始帧选错了」** ——
徽记在事件**后面**才出现（`dcc871b1#2` 晚 7 帧、`851622c5#3` 晚 16 帧、`58b8e283#3` 晚 56 帧），
而那 8 格的窗口里根本没有徽记，标注者看不到它，只能照着高亮帧判「这不是徽记」。
⇒ 本工具把**整段**（每 8 帧一格）画出来，并顺带量出「段内有多少帧像徽记」。

## 「像徽记」的判据（必要不充分，**已实测会误收**）

    frac  = 框内「低饱和亮块」占比   ≥ 0.02      # 徽记占框 5%~12%
    bfrac = 框最外 4 圈里亮块占比     ≤ 0.05      # 徽记是**孤立**的，不贴边
    core  = 3x3 腐蚀后的残留占比      ≥ 0.004     # 徽记有**厚度**（细线/地图路线没有）

⚠️ 实测反例：亮地面、武器皮肤、购买阶段界面、地图白色路线 **都能通过**这套判据
（见 `verification/icon-review/README.md` §7）。它只能当「可疑帧」筛选，**不能当判据**。

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/icon_truth_recheck.py --sheets N
    .venv\\Scripts\\python.exe projects/game-001/tools/icon_truth_recheck.py --sheets all

## 输出

    projects/game-001/verification/icon-review/runs/<material>_e<id>.png   整段证据图
    projects/game-001/verification/icon-review/recheck.json                逐事件的量值
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import subprocess
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
REVIEW = ROOT / "projects" / "game-001" / "verification" / "icon-review" / "review.csv"
RUNDIR = REVIEW.parent / "runs"

FPS = 30.0
BOX = (612, 514, 112, 100)     # 与 center_kill_icon.py 一致
BIG = (592, 494, 152, 140)     # 画图时向外扩一圈，能看出框外是什么
BRIGHT, SAT_MAX = 190, 50
TH_FRAC, TH_BFRAC, TH_CORE = 0.02, 0.05, 0.004
STRIDE = 8                     # 证据图取样步长（整段 ~2s → 8~20 格）


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def decode(path, box):
    x, y, w, h = box
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(path),
                          "-vf", f"crop={w}:{h}:{x}:{y}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w, 3)


def badge_like(a):
    """逐帧算 (frac, bfrac, core) —— a 是 (F,h,w,3) uint8。"""
    m = (a.max(3) > BRIGHT) & ((a.max(3).astype(np.int16) - a.min(3)) < SAT_MAX)
    F, h, w = m.shape
    frac = m.reshape(F, -1).mean(1)
    r = 4
    ring = np.concatenate([m[:, :r, :].reshape(F, -1), m[:, -r:, :].reshape(F, -1),
                           m[:, :, :r].reshape(F, -1), m[:, :, -r:].reshape(F, -1)], axis=1)
    bfrac = ring.mean(1)
    core = (m[:, 1:-1, 1:-1] & m[:, :-2, 1:-1] & m[:, 2:, 1:-1]
            & m[:, 1:-1, :-2] & m[:, 1:-1, 2:]).reshape(F, -1).mean(1)
    return frac, bfrac, core


def segments(mask, offset):
    """布尔序列 → [(起帧, 止帧)]（绝对帧号）。"""
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((offset + start, offset + i - 1))
            start = None
    if start is not None:
        out.append((offset + start, offset + len(mask) - 1))
    return out


def sheet(frames, picks, title, dst):
    from PIL import Image, ImageDraw
    H, W = frames.shape[1:3]
    cols = 8
    rows = max(1, -(-len(picks) // cols))
    img = Image.new("RGB", (cols * W, rows * (H + 16)), (0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((2, 2), title, fill=(255, 220, 0))
    for i, f in enumerate(picks):
        r, c = divmod(i, cols)
        img.paste(Image.fromarray(frames[f]), (c * W, r * (H + 16) + 16))
        d.text((c * W + 3, r * (H + 16) + 2), str(f), fill=(0, 255, 0))
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", default="N", choices=["N", "all", "none"],
                    help="给哪些事件画整段证据图（默认只画被判非击杀的 N 行）")
    ap.add_argument("--stride", type=int, default=STRIDE)
    args = ap.parse_args()

    rows = list(csv.DictReader(REVIEW.open("r", encoding="utf-8-sig", newline="")))
    cache, out = {}, []
    for r in rows:
        s = r["material"]
        if s not in cache:
            p = next(SRC.glob(f"{s}*.mp4"))
            cache[s] = (decode(p, BOX), decode(p, BIG))
        small, big = cache[s]
        f0, d = int(r["frame"]), int(r["duration_frames"])
        frac, bfrac, core = badge_like(small)
        like = (frac >= TH_FRAC) & (bfrac <= TH_BFRAC) & (core >= TH_CORE)
        seg = segments(like[f0:f0 + d], f0)
        v = (r["verdict_kill"] or "?").upper()
        # 判据在**起始帧**成立吗？整段里有多少帧像徽记？
        at_start = bool(like[f0]) if f0 < len(like) else None
        out.append({
            "material": s, "event_id": int(r["event_id"]), "verdict_kill": v,
            "frame": f0, "t_s": round(f0 / FPS, 4), "duration_frames": d,
            "peak": float(r["peak"]), "note": (r["note"] or "").strip(),
            "badge_like_frames": int(like[f0:f0 + d].sum()),
            "badge_like_at_start": at_start,
            "badge_like_segments": [{"from": a, "to": b, "len": b - a + 1} for a, b in seg],
        })
        if args.sheets == "all" or (args.sheets == "N" and v == "N"):
            picks = list(range(f0, min(len(big), f0 + d), args.stride))
            title = (f"{s} #{r['event_id']}  verdict={v}  start=f{f0}  dur={d}f  "
                     f"peak={r['peak']}  像徽记 {int(like[f0:f0+d].sum())}/{d} 帧")
            sheet(big, picks, title, RUNDIR / f"{s}_e{r['event_id']}.png")

    dst = REVIEW.parent / "recheck.json"
    dst.write_text(json.dumps({
        "generated_by": "projects/game-001/tools/icon_truth_recheck.py",
        "source": "projects/game-001/verification/icon-review/review.csv（人工标注）",
        "evidence_level": "L1（本机逐帧量 + 整段目视）",
        "predicate": {"bright": BRIGHT, "sat_max": SAT_MAX, "frac_min": TH_FRAC,
                      "border_frac_max": TH_BFRAC, "core_frac_min": TH_CORE,
                      "note": "必要不充分：亮地面/武器皮肤/购买界面/地图路线都能通过"},
        "n_events": len(out), "events": out,
    }, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    print("[OK] %s" % dst.relative_to(ROOT))
    print("%-9s %-3s %-6s %-7s %s" % ("素材", "#", "判", "像徽记", "起始帧就成立？"))
    for e in out:
        flag = "是" if e["badge_like_at_start"] else "**否**"
        print("%-9s %-3d %-6s %3d/%-3d  %s" % (e["material"], e["event_id"],
                                               e["verdict_kill"], e["badge_like_frames"],
                                               e["duration_frames"], flag))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
