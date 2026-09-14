"""Locate the VALORANT kill banner (red plate, bottom-left) and the kill feed (top-right)
by pixel signature, then render fine rulers for visual confirmation.

Kill banner signature (Chinese client): a red-dominant translucent plate near the bottom-left
carrying the 无畏契约 wordmark + a kill-count badge. Measured as red dominance
R - max(G,B) inside the bottom-left search window.

Kill feed signature (top-right): a dark translucent plate with near-white text.
Measured as "bright, low-saturation" pixels inside the top-right search window.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw
import imageio_ffmpeg

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = ROOT / "原始素材"
OUT = ROOT / "projects" / "game-001" / "research" / "_hud"
OUT.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720

# clip 4b0460c4 (a): bottom-effect edges at 4.13 / 4.73 / 9.37 / 14.70 / 16.67
CLIP = SRC / "4b0460c400bbb5320acb6063b4f59358.mp4"
BOTTOM_EDGES = [4.13, 4.73, 9.37, 14.70, 16.67]


def frames(path: pathlib.Path, t0: float, t1: float, fps: int = 30):
    """Yield (t, ndarray) for frames in [t0, t1]."""
    raw = subprocess.run(
        [FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}",
         "-i", str(path), "-vf", f"fps={fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout
    n = len(raw) // (W * H * 3)
    a = np.frombuffer(raw[: n * W * H * 3], dtype=np.uint8).reshape(n, H, W, 3)
    for i in range(n):
        yield t0 + i / fps, a[i]


def bbox(mask, x0, y0):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None, 0
    return ((x0 + int(xs.min()), y0 + int(ys.min()),
             x0 + int(xs.max()), y0 + int(ys.max())), int(mask.sum()))


def sc1080(b):
    return None if b is None else tuple(round(v * 1.5) for v in b)


# ---------- 1. kill banner (red plate, bottom-left) ----------
BX0, BY0, BX1, BY1 = 0, 520, 640, 720
print("=== 底部击杀横幅（红底板）逐帧红色优势 ===")
best = None
for edge in BOTTOM_EDGES:
    for t, fr in frames(CLIP, edge - 0.2, edge + 0.7):
        reg = fr[BY0:BY1, BX0:BX1].astype(np.int16)
        red = reg[:, :, 0] - np.maximum(reg[:, :, 1], reg[:, :, 2])
        mask = red > 28
        n = int(mask.sum())
        if n > 400:
            b, npx = bbox(mask, BX0, BY0)
            if best is None or npx > best[3]:
                best = (t, edge, b, npx)
    if best:
        print(f"  edge {edge:.2f}s -> 最强帧 t={best[0]:.3f}s bbox@720p={best[2]} px={best[3]}"
              f"  -> @1080p {sc1080(best[2])}")
        # per-row extent for the y bounds
        t, e, b, _ = best
        for tt, fr in frames(CLIP, t, t + 0.001):
            reg = fr[BY0:BY1, BX0:BX1].astype(np.int16)
            red = reg[:, :, 0] - np.maximum(reg[:, :, 1], reg[:, :, 2])
            m = red > 28
            rows = [(BY0 + i, int(m[i].sum())) for i in range(m.shape[0]) if m[i].sum() > 5]
            cols = [(BX0 + j, int(m[:, j].sum())) for j in range(m.shape[1]) if m[:, j].sum() > 5]
            if rows:
                print(f"      y 活跃: {rows[0][0]}..{rows[-1][0]} @720p"
                      f"  -> @1080p {round(rows[0][0]*1.5)}..{round(rows[-1][0]*1.5)}")
            if cols:
                print(f"      x 活跃: {cols[0][0]}..{cols[-1][0]} @720p"
                      f"  -> @1080p {round(cols[0][0]*1.5)}..{round(cols[-1][0]*1.5)}")
        break

# ---------- 2. kill feed (bright text, top-right) ----------
TX0, TY0, TX1, TY1 = 900, 0, 1280, 130
print("\n=== 右上角击杀播报（亮字）逐帧 ===")
for edge in [4.60, 6.30, 9.93]:
    hit = None
    for t, fr in frames(CLIP, edge - 0.25, edge + 0.9):
        reg = fr[TY0:TY1, TX0:TX1].astype(np.int16)
        mx = reg.max(axis=2)
        mn = reg.min(axis=2)
        sat = mx - mn
        mask = (mx > 205) & (sat < 42)          # near-white, low saturation
        n = int(mask.sum())
        if n > 60 and (hit is None or n > hit[2]):
            hit = (t, edge, n, mask)
    if hit:
        t, e, n, mask = hit
        b, npx = bbox(mask, TX0, TY0)
        print(f"  edge {e:.2f}s -> t={t:.3f}s bbox@720p={b} px={npx}  -> @1080p {sc1080(b)}")
        rows = [(TY0 + i, int(mask[i].sum())) for i in range(mask.shape[0]) if mask[i].sum() > 2]
        cols = [(TX0 + j, int(mask[:, j].sum())) for j in range(mask.shape[1]) if mask[:, j].sum() > 2]
        if rows:
            print(f"      y: {rows[0][0]}..{rows[-1][0]} @720p -> @1080p"
                  f" {round(rows[0][0]*1.5)}..{round(rows[-1][0]*1.5)}")
        if cols:
            print(f"      x: {cols[0][0]}..{cols[-1][0]} @720p -> @1080p"
                  f" {round(cols[0][0]*1.5)}..{round(cols[-1][0]*1.5)}")

# ---------- 3. fine-ruler renders ----------
def ruler(img, origin, zoom, step=10):
    im = img.resize((img.width * zoom, img.height * zoom), Image.NEAREST).convert("RGB")
    d = ImageDraw.Draw(im)
    ox, oy = origin
    for x in range(0, img.width + 1, step):
        real = ox + x
        if real % 50 == 0:
            d.line([(x * zoom, 0), (x * zoom, 16)], fill=(255, 0, 0), width=1)
            d.text((x * zoom + 1, 2), str(real), fill=(255, 255, 0))
        else:
            d.line([(x * zoom, 0), (x * zoom, 7)], fill=(255, 120, 0), width=1)
    for y in range(0, img.height + 1, step):
        real = oy + y
        if real % 50 == 0:
            d.line([(0, y * zoom), (20, y * zoom)], fill=(0, 255, 0), width=1)
            d.text((1, y * zoom + 1), str(real), fill=(0, 255, 255))
        else:
            d.line([(0, y * zoom), (9, y * zoom)], fill=(0, 180, 255), width=1)
    return im


def grab(path, t):
    p = OUT / f"g_{path.stem[:8]}_{t:.3f}.png"
    if not p.exists():
        subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(path), "-frames:v", "1", "-y", str(p)], capture_output=True)
    return Image.open(p).convert("RGB")


grab(CLIP, 4.70).crop((900, 0, 1280, 110)).resize((380 * 5, 110 * 5)).save(OUT / "fine_tr.png")
ruler(grab(CLIP, 4.70).crop((900, 0, 1160, 110)), (900, 0), 5).save(OUT / "fine_tr_ruler.png")

if best:
    tb = best[0]
    ruler(grab(CLIP, tb).crop((0, 560, 480, 720)), (0, 560), 4).save(OUT / "fine_banner_ruler.png")
    grab(CLIP, tb).crop((0, 560, 480, 720)).resize((480 * 4, 160 * 4)).save(OUT / "fine_banner.png")

print("\nrendered:")
for p in sorted(OUT.glob("fine_*.png")):
    print(f"  {p.name} {Image.open(p).size}")
