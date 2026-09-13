# -*- coding: utf-8 -*-
"""Extract evenly-spaced frames from downloaded tutorial videos."""
import os, subprocess, sys, glob, json
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
VIDS = os.path.join(HERE, "vids")
FRAMES = os.path.join(HERE, "frames")
os.makedirs(FRAMES, exist_ok=True)

FFMPEG = r"C:\Users\18930\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def probe_dur(p):
    r = subprocess.run([FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error",
                        "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def extract(path, every=2.0, width=1280):
    bv = os.path.splitext(os.path.basename(path))[0]
    outdir = os.path.join(FRAMES, bv)
    os.makedirs(outdir, exist_ok=True)
    if glob.glob(os.path.join(outdir, "*.jpg")):
        return outdir, len(glob.glob(os.path.join(outdir, "*.jpg")))
    dur = probe_dur(path)
    fps = 1.0 / every
    cmd = [FFMPEG, "-y", "-v", "error", "-i", path,
           "-vf", "fps=%s,scale=%d:-1" % (fps, width),
           "-q:v", "3", os.path.join(outdir, "f_%04d.jpg")]
    subprocess.run(cmd, capture_output=True, text=True)
    return outdir, len(glob.glob(os.path.join(outdir, "*.jpg")))


if __name__ == "__main__":
    every = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    for p in sorted(glob.glob(os.path.join(VIDS, "*.mp4"))):
        d, n = extract(p, every)
        print("%-14s dur=%6.1fs frames=%d  %s" % (os.path.basename(p), probe_dur(p), n, d))
    print("FFMPEG:", FFMPEG)
