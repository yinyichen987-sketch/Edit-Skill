"""把中心徽记事件渲染成**人工标注用**的证据图 + 打勾表（第 11 轮）。

## 给人看什么

每个事件一张「证据块」，两行：

- **第一行**：整帧（缩到 426×240）三张 —— `t−0.5s / t / t+0.5s`，
  并在徽记位置画一个矩形 ⇒ 用来看**当时在不在交火、画面里有没有敌人**；
- **第二行**：徽记区（`x600..760, y495..625`）**逐帧 8 张** —— `f−4 … f+3`
  ⇒ 用来看**徽记到底从哪一帧开始出现**（标注「真实击杀帧偏移」时要的就是这个）。

每块左上角有标题：`#序号  t=…s  frame=N  段长=Nf  peak=…  HC/short`。

## 打勾表

`icon-review/review.csv` 每个事件一行（含**非高置信**的那些，`high_conf=0`），
空白列留给人填（列义见 `icon-review/README.md`）。
**这个 CSV 用 UTF-8 BOM + LF**：BOM 是「Excel 双击不乱码」的关键；
**不能用 CRLF** —— 本机 git 的 **system 级** `core.autocrlf=true`（本仓库用 local 覆盖成 false），
而 `git am` 在 autocrlf=true 的仓库里会把 CRLF **归一化成 LF**，于是「交付包打出来的 tree」
和「我的 tree」不一致。第 11 轮实测：`review.csv` 1824 字节(CRLF=43) → am 后 1781 字节(CRLF=0)。

## 用法

    .venv\\Scripts\\python.exe projects/game-001/tools/make_icon_review_sheets.py all
    .venv\\Scripts\\python.exe projects/game-001/tools/make_icon_review_sheets.py all --all-events
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
ICON_DIR = ROOT / "projects" / "game-001" / "verification" / "icon-scan"
OUTDIR = ROOT / "projects" / "game-001" / "verification" / "icon-review"

FPS = 30.0
ICON_BOX = (612, 514, 112, 100)      # 徽记判据框（与 center_kill_icon.py 保持一致）
VIEW_BOX = (600, 495, 160, 130)      # 给人看的、略大的框（w/h 必须偶数）
FULL = (426, 240)                    # 整帧缩放后尺寸（3 张拼起来 ≈1280 宽）
STRIP_BEFORE, STRIP_AFTER = 4, 3     # 徽记区逐帧：f-4 … f+3
CANVAS_W = 1280
ROW1_H = FULL[1]
ROW2_H = VIEW_BOX[3]
TITLE_H = 20
BLOCK_H = TITLE_H + ROW1_H + ROW2_H + 6
PER_PAGE = 5

CSV_COLUMNS = ["material", "event_id", "t_s", "frame", "duration_frames", "peak", "high_conf",
               "page", "verdict_kill", "verdict_mine", "kill_frame_offset", "note"]


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def grab(path, t0, n, crop=None, scale=None):
    """抓 n 帧（从 t0 起）。返回 list[np.ndarray(h,w,3)]。"""
    vf = []
    if crop:
        vf.append(f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}")
    if scale:
        vf.append(f"scale={scale[0]}:{scale[1]}")
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-ss", "%.4f" % max(0.0, t0),
                          "-i", str(path), "-frames:v", str(n), "-vf", ",".join(vf),
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    w, h = scale if scale else (crop[2], crop[3])
    a = np.frombuffer(raw, dtype=np.uint8)
    k = a.size // (w * h * 3)
    return [a[i * w * h * 3:(i + 1) * w * h * 3].reshape(h, w, 3) for i in range(k)]


def block(path, ev, n_frames, tag):
    f = int(ev["frame"])
    t = f / FPS
    canvas = Image.new("RGB", (CANVAS_W, BLOCK_H), (18, 18, 18))
    d = ImageDraw.Draw(canvas)
    d.text((4, 4), "#%d  t=%.3fs  frame=%d  段长=%df  peak=%.3f  %s" % (
        ev["event_id"], t, f, ev["duration_frames"], ev["peak"], tag), fill=(255, 225, 120))

    # 第一行：整帧 ×3（t-0.5 / t / t+0.5）
    lo = max(0, f - 15)
    span = min(n_frames - lo, 31)
    full = grab(path, lo / FPS, span, scale=FULL)
    picks = [p for p in (0, 15, 30) if p < len(full)]
    sx, sy = FULL[0] / 1280.0, FULL[1] / 720.0
    for i, p in enumerate(picks):
        img = Image.fromarray(full[p])
        x = i * FULL[0]
        canvas.paste(img, (x, TITLE_H))
        bx, by, bw, bh = ICON_BOX
        d.rectangle([x + bx * sx, TITLE_H + by * sy,
                     x + (bx + bw) * sx, TITLE_H + (by + bh) * sy], outline=(255, 60, 60))
        d.text((x + 4, TITLE_H + 4), "f%d  %+.2fs" % (lo + p, (lo + p - f) / FPS),
               fill=(120, 255, 160))

    # 第二行：徽记区逐帧（f-4 … f+3）
    start = max(0, f - STRIP_BEFORE)
    n = STRIP_BEFORE + STRIP_AFTER + 1
    strip = grab(path, start / FPS, n, crop=VIEW_BOX)
    y = TITLE_H + ROW1_H + 6
    for i, img in enumerate(strip):
        x = i * VIEW_BOX[2]
        canvas.paste(Image.fromarray(img), (x, y))
        d.text((x + 4, y + 4), "f%d (%+d)" % (start + i, start + i - f), fill=(120, 255, 160))
    return canvas


def analyse(short, use_all=False):
    js = ICON_DIR / f"{short}.json"
    if not js.exists():
        print(f"[FAIL] 缺 {js.relative_to(ROOT)} —— 先跑 center_kill_icon.py")
        return []
    data = json.loads(js.read_text(encoding="utf-8"))
    n_frames = data["n_frames"]
    events = data["events_raw"] if use_all else data["events"]
    hc = {e["frame"] for e in data["events"]}
    p = next(SRC.glob(f"{short}*.mp4"), None)
    if p is None:
        print(f"[FAIL] 没有素材 {short}*.mp4")
        return []
    rows = []
    pages = [events[i:i + PER_PAGE] for i in range(0, len(events), PER_PAGE)]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for pi, page in enumerate(pages, 1):
        canvas = Image.new("RGB", (CANVAS_W, BLOCK_H * len(page) + 24), (18, 18, 18))
        ImageDraw.Draw(canvas).text((4, 4), "%s  page %d/%d" % (p.name, pi, len(pages)),
                                    fill=(255, 255, 255))
        for k, ev in enumerate(page):
            ev = dict(ev, event_id=events.index(ev) + 1)
            canvas.paste(block(p, ev, n_frames, "HC" if ev["frame"] in hc else "short"),
                         (0, 24 + k * BLOCK_H))
            rows.append({"material": short, "event_id": ev["event_id"], "t_s": ev["t_s"],
                         "frame": ev["frame"], "duration_frames": ev["duration_frames"],
                         "peak": ev["peak"], "high_conf": int(ev["frame"] in hc),
                         "page": pi, "verdict_kill": "", "verdict_mine": "",
                         "kill_frame_offset": "", "note": ""})
        dst = OUTDIR / f"{short}_p{pi}.png"
        canvas.save(dst)
        print("[OK] %s  (%d 个事件)" % (dst.relative_to(ROOT), len(page)))
    return rows


def write_csv(rows):
    dst = OUTDIR / "review.csv"
    # ⚠️ 重跑**不能覆盖人工已填的列**：先读回旧的，按 (material, event_id) 把标注列搬过来。
    # （只跑单条素材时也会写这个文件，不合并就会把别的素材的标注清掉。）
    keep = {}
    if dst.exists():
        with dst.open("r", encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                keep[(r.get("material"), r.get("event_id"))] = r
    merged = 0
    for r in rows:
        old = keep.get((r["material"], str(r["event_id"])))
        if not old:
            continue
        for col in ("verdict_kill", "verdict_mine", "kill_frame_offset", "note"):
            if old.get(col):
                r[col] = old[col]
                merged += 1
    # 只跑单条素材时，**旧的其它素材的行也要留下**（这个表只增不减）
    have = {(r["material"], str(r["event_id"])) for r in rows}
    extra = [old for key, old in keep.items() if key not in have]
    extra.sort(key=lambda r: (r.get("material", ""), int(r.get("event_id") or 0)))
    rows = rows + extra
    with dst.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("[OK] %s  (%d 行，其中 %d 行是旧表保留的；沿用 %d 个已填单元格；"
          "UTF-8 BOM + LF，给 Excel 用)"
          % (dst.relative_to(ROOT), len(rows), len(extra), merged))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("short", help="素材短 id 或 all")
    ap.add_argument("--all-events", action="store_true",
                    help="连非高置信（<1s）的段一起渲染（默认只渲染高置信事件）")
    args = ap.parse_args()
    shorts = ([q.name[:8] for q in sorted(SRC.glob("*.mp4"))] if args.short == "all"
              else [args.short])
    rows = []
    for s in shorts:
        rows += analyse(s, use_all=args.all_events)
    write_csv(rows)
    print("\n下一步：打开 icon-review/*.png 看图，把结论填进 icon-review/review.csv"
          "（列义见 icon-review/README.md）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
