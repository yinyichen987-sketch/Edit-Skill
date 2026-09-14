"""Contact sheets around detected freeze / flash events, to verify by eye what they are."""
from __future__ import annotations

import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw
import imageio_ffmpeg

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[3]
VID = ROOT / "参考视频"
OUT = ROOT / "projects" / "game-001" / "research" / "_hud"
OUT.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()


def sheet(stem: str, t0: float, span: float, n: int, name: str, fps=30.0, cw=480):
    p = VID / f"{stem}.mp4"
    imgs = []
    for k in range(n):
        t = t0 + k * span / max(n - 1, 1)
        f = OUT / f"cs_{stem}_{t:.2f}.png"
        if not f.exists():
            subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                            "-i", str(p), "-frames:v", "1", "-y", str(f)], capture_output=True)
        im = Image.open(f).convert("RGB")
        ch = int(im.height * cw / im.width)
        im = im.resize((cw, ch))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 118, 20], fill=(0, 0, 0))
        d.text((4, 5), f"{t:.2f}s f{int(t*fps)}", fill=(255, 255, 0))
        imgs.append(im)
    ch = max(i.height for i in imgs)
    cols = 3
    rows = (len(imgs) + cols - 1) // cols
    S = Image.new("RGB", (cols * cw, rows * ch), (20, 20, 20))
    for i, im in enumerate(imgs):
        S.paste(im, ((i % cols) * cw, (i // cols) * ch))
    S.save(OUT / name)
    print(f"  {name}  {S.size}  t={t0:.2f}..{t0+span:.2f}s")


print("contact sheets:")
# freeze cluster in BV1U1kJBrEd7 (40.3万) around 7.97-13.77
sheet("BV1U1kJBrEd7", 7.85, 0.75, 6, "sheet_freeze_40w.png")
# flash + black in BV19m3uzhECJ (57.7万) around 6.9-7.3
sheet("BV19m3uzhECJ", 6.85, 0.55, 6, "sheet_flash_57w.png")
# freeze burst in BV1mbPsz5EeK (42.2万) around 33.95-35.6
sheet("BV1mbPsz5EeK", 34.00, 1.00, 6, "sheet_freeze_42w.png", fps=26.42)
# flash in BV11c6GBrEPm at 34.6
sheet("BV11c6GBrEPm", 34.50, 0.40, 6, "sheet_flash_vct.png", fps=29.97)
