"""成片分析器 —— 从已剪好的成片反推剪辑结构。

用途：
    在没有草稿可读（剪映 11.x 草稿加密）的前提下，用成片本身反推
    切点位置、镜头时长分布、节奏特征和音频响度，作为风格归纳的输入。

用法：
    python analyze_film.py <成片路径> [-o 输出.json] [--json-only]

设计说明：
    ffmpeg 的 scdet 场景分以亮度差为主，等亮度换色（如深蓝->深红）得分很低
    （实测 5.47 vs 23.05）。因此这里用 threshold=0 全量采样所有帧的场景分，
    再用自适应峰值检测判定切点，而不是依赖固定阈值。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys

try:
    import imageio_ffmpeg
except ImportError:  # pragma: no cover
    imageio_ffmpeg = None

try:
    from pymediainfo import MediaInfo
except ImportError:  # pragma: no cover
    MediaInfo = None


# ---------------------------------------------------------------- ffmpeg

def ffmpeg_exe() -> str:
    if imageio_ffmpeg is not None:
        return imageio_ffmpeg.get_ffmpeg_exe()
    raise RuntimeError("未找到 ffmpeg：请先 pip install imageio-ffmpeg")


def run_ffmpeg(args: list[str]) -> str:
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostats", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return (proc.stdout or "") + (proc.stderr or "")


# ---------------------------------------------------------------- 媒体信息

def probe_media(path: str) -> dict:
    info: dict = {
        "duration": None, "width": None, "height": None, "fps": None,
        "video_codec": None, "has_audio": False, "audio_codec": None,
        "audio_sample_rate": None, "audio_channels": None,
    }
    if MediaInfo is None:
        return info

    mi = MediaInfo.parse(path)
    for track in mi.tracks:
        if track.track_type == "Video" and info["width"] is None:
            info["width"] = track.width
            info["height"] = track.height
            info["video_codec"] = track.format
            if track.duration:
                info["duration"] = round(float(track.duration) / 1000.0, 3)
            if track.frame_rate:
                info["fps"] = round(float(track.frame_rate), 3)
        elif track.track_type == "Audio" and not info["has_audio"]:
            info["has_audio"] = True
            info["audio_codec"] = track.format
            info["audio_sample_rate"] = track.sampling_rate
            info["audio_channels"] = track.channel_s

    if info["duration"] is None:
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", run_ffmpeg(["-i", path]))
        if m:
            h, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
            info["duration"] = round(h * 3600 + mm * 60 + ss, 3)

    if info["width"] and info["height"]:
        from math import gcd
        g = gcd(info["width"], info["height"])
        info["aspect_ratio"] = f"{info['width'] // g}:{info['height'] // g}"
        info["orientation"] = ("portrait" if info["height"] > info["width"]
                               else "landscape" if info["width"] > info["height"] else "square")
    return info


# ---------------------------------------------------------------- 切点检测

SCORE_RE = re.compile(r"lavfi\.scd\.score:\s*([\d.]+).*?lavfi\.scd\.time:\s*([\d.]+)")


def scene_scores(path: str) -> list[tuple[float, float]]:
    """返回 [(time, score)]，覆盖所有被 scdet 记录的帧。"""
    out = run_ffmpeg(["-i", path, "-vf", "scdet=threshold=0", "-f", "null", "-"])
    pairs = []
    for line in out.splitlines():
        m = SCORE_RE.search(line)
        if m:
            pairs.append((float(m.group(2)), float(m.group(1))))
    pairs.sort(key=lambda x: x[0])
    return pairs


def detect_cuts(scores: list[tuple[float, float]], min_gap: float = 0.25,
                peak_ratio: float = 1.0) -> list[dict]:
    """自适应峰值检测。

    不依赖固定阈值：以场景分的中位数为噪声基线，取显著高于基线的局部极大值。
    这样对「等亮度换色」这类低分切点也能召回。
    """
    if not scores:
        return []

    vals = [s for _, s in scores]
    baseline = statistics.median(vals) if vals else 0.0
    spread = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    # 阈值 = max(中位数 + 1 倍标准差, 3.0)，并保证不低于全局最大值的一定比例
    top = max(vals)
    threshold = max(baseline + spread, 3.0, top * 0.15 * peak_ratio)

    cuts: list[dict] = []
    for i, (t, s) in enumerate(scores):
        if s < threshold:
            continue
        prev_s = scores[i - 1][1] if i > 0 else 0.0
        next_s = scores[i + 1][1] if i + 1 < len(scores) else 0.0
        if s < prev_s or s < next_s:
            continue  # 非局部极大值
        if cuts and t - cuts[-1]["time"] < min_gap:
            if s > cuts[-1]["score"]:
                cuts[-1] = {"time": round(t, 3), "score": round(s, 2)}
            continue
        cuts.append({"time": round(t, 3), "score": round(s, 2)})

    return cuts


def build_shots(cuts: list[dict], duration: float | None) -> list[dict]:
    if duration is None:
        if not cuts:
            return []
        duration = cuts[-1]["time"]
    bounds = [0.0] + [c["time"] for c in cuts] + [duration]
    shots = []
    for i in range(len(bounds) - 1):
        start, end = bounds[i], bounds[i + 1]
        if end - start <= 0.01:
            continue
        shots.append({
            "index": len(shots),
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "cut_score": cuts[i - 1]["score"] if i > 0 else None,
        })
    return shots


# ---------------------------------------------------------------- 节奏

def analyze_pacing(shots: list[dict], duration: float | None) -> dict:
    if not shots:
        return {"shot_count": 0}
    durs = [s["duration"] for s in shots]
    total = duration or sum(durs)
    hist = {"<1s": 0, "1-2s": 0, "2-3s": 0, "3-5s": 0, "5-10s": 0, ">=10s": 0}
    for d in durs:
        if d < 1: hist["<1s"] += 1
        elif d < 2: hist["1-2s"] += 1
        elif d < 3: hist["2-3s"] += 1
        elif d < 5: hist["3-5s"] += 1
        elif d < 10: hist["5-10s"] += 1
        else: hist[">=10s"] += 1
    return {
        "shot_count": len(shots),
        "cut_count": len(shots) - 1,
        "total_duration": round(total, 3),
        "avg_shot_duration": round(statistics.mean(durs), 3),
        "median_shot_duration": round(statistics.median(durs), 3),
        "min_shot_duration": round(min(durs), 3),
        "max_shot_duration": round(max(durs), 3),
        "stdev_shot_duration": round(statistics.pstdev(durs), 3) if len(durs) > 1 else 0.0,
        "cuts_per_minute": round((len(shots) - 1) / total * 60, 2) if total else None,
        "duration_histogram": hist,
    }


# ---------------------------------------------------------------- 音频

def analyze_audio(path: str, has_audio: bool) -> dict:
    if not has_audio:
        return {"has_audio": False}
    out = run_ffmpeg(["-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"])
    result: dict = {"has_audio": True}

    # ebur128 在 Summary 之前会逐帧打印进度行，其中同样含 "I: … LUFS" 与 "LRA: …"，
    # 但早期帧因样本不足会报 -70.0（静音下限）/ 0.0。若直接对整段输出 re.search，
    # 抓到的是第一行进度数据而不是摘要，会得到 -70.0 这种自相矛盾的假值
    # （实测同一文件：真值 -12.9 LUFS，误报 -70.0）。因此只解析 Summary 段。
    summary = out.rsplit("Summary:", 1)[-1] if "Summary:" in out else out

    m = re.search(r"I:\s*(-?[\d.]+)\s*LUFS", summary)
    if m:
        result["integrated_loudness_lufs"] = float(m.group(1))
    m = re.search(r"Peak:\s*(-?[\d.]+)\s*dBFS", summary)
    if m:
        result["true_peak_dbfs"] = float(m.group(1))
    m = re.search(r"LRA:\s*(-?[\d.]+)\s*LU", summary)
    if m:
        result["loudness_range_lu"] = float(m.group(1))
    return result


# ---------------------------------------------------------------- main

def analyze(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    media = probe_media(path)
    scores = scene_scores(path)
    cuts = detect_cuts(scores)
    shots = build_shots(cuts, media.get("duration"))
    pacing = analyze_pacing(shots, media.get("duration"))
    audio = analyze_audio(path, bool(media.get("has_audio")))

    return {
        "source": os.path.abspath(path),
        "media": media,
        "shots": shots,
        "pacing": pacing,
        "candidate_cuts": cuts,
        "audio": audio,
        "analysis_meta": {
            "scene_score_samples": len(scores),
            "detector": "ffmpeg scdet(threshold=0) + adaptive peak detection",
            "note": "scdet 以亮度差为主，等亮度换色得分偏低；已用自适应基线补偿",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="从成片反推剪辑结构")
    ap.add_argument("video", help="成片路径")
    ap.add_argument("-o", "--output", help="输出 JSON 路径（默认打印到标准输出）")
    ap.add_argument("--summary", action="store_true", help="额外打印人类可读摘要")
    args = ap.parse_args()

    try:
        result = analyze(args.video)
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"[OK] 已写入 {args.output}")
    else:
        print(text)

    if args.summary:
        m, p = result["media"], result["pacing"]
        print("\n" + "=" * 56)
        print(f"成片: {os.path.basename(result['source'])}")
        print(f"时长 {m.get('duration')}s | {m.get('width')}x{m.get('height')} "
              f"({m.get('aspect_ratio')}, {m.get('orientation')}) | {m.get('fps')}fps")
        print(f"镜头 {p.get('shot_count')} 个 | 平均 {p.get('avg_shot_duration')}s | "
              f"中位 {p.get('median_shot_duration')}s | 每分钟 {p.get('cuts_per_minute')} 切")
        print(f"时长分布: {p.get('duration_histogram')}")
        a = result["audio"]
        if a.get("has_audio"):
            print(f"响度 {a.get('integrated_loudness_lufs')} LUFS | 峰值 {a.get('true_peak_dbfs')} dBFS")
        print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
