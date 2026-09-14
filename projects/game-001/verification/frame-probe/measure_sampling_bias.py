"""抽帧偏差测量器 —— 测「按时间抽帧」的工具是否有**系统性偏差**。

问题
----
很多工具（含 ffmpeg 的 `fps` / `select` 滤镜、以及各种"每 N 秒取一帧"的脚本）会声称
「输出第 k 帧 = 源时间 k/R 秒」。**这个声称需要验证，不能假设。**

本项目实测反例：`-vf fps=4` 在**三段素材上都**存在约 **+0.105s 的单边系统偏差**
（fps=4 第 k 帧的内容实际取自源 PTS ≈ k/4 + 0.105s）。它与 CFR/VFR **无关**，
所以"只看时间码对不对"是发现不了的——必须比**内容**。

方法（核心：逐像素匹配求真实来源）
----------------------------------
1. **基准**：用 `-fps_mode passthrough` 解码源视频，得到帧序与容器一一对应的源帧序列，
   同时用 `showinfo` 取每帧的真实 `pts_time`。
   > 必须 passthrough。默认解码会对 VFR 素材**补帧**（本项目实测 `6b2eea34` 780→781、
   > `dcc871b1` 750→751），补入帧插在中段，使其后帧号整体偏移一帧。
2. **待测**：用待测滤镜（如 `fps=4`）抽出输出帧。
3. **匹配**：对每个输出帧，在"标称源帧号 ± 窗口"内逐帧算平均绝对差（MAD），取最小者为它的真实来源。
4. **判定**：
   - 所有匹配的 MAD **必须为 0**（或极小）→ 说明映射**无歧义**，结果可信；
   - 源帧号**必须严格递增** → 否则说明匹配发生了别名（把不同输出帧匹配到同一源帧）。
   这两条不成立时，测出的偏差数不可信，必须换参数重测。
5. **偏差** = `pts_time(匹配到的源帧) - 标称时间 k/R`。

自带自测（--selftest）
----------------------
对三段素材跑 `fps=4`，断言上面第 4 步的两条不变量成立，
并复现本项目已记录的结论（三段偏差**同号且量级一致**）。
不变量不成立即判 FAIL——**没有不变量的测量只是数字，不是证据**。

用法
----
    .venv/Scripts/python.exe measure_sampling_bias.py --selftest
    .venv/Scripts/python.exe measure_sampling_bias.py --input <video> --fps 4
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import imageio_ffmpeg
import imageio.v3 as iio

REPO_ROOT = Path(__file__).resolve().parents[4]
DOWN = 4          # 匹配用降采样倍数（灰度）
WINDOW = 14       # 在标称源帧号两侧搜索的帧数
SRC_FPS = 30.0


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def dump_pts(path: str) -> list[float]:
    """用 showinfo 取每帧真实 pts_time（秒），顺序即解码序。"""
    cmd = [ffmpeg_exe(), "-hide_banner", "-nostats", "-i", path,
           "-vf", "showinfo", "-an", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    return [float(b) for _, b in
            re.findall(r"n:\s*(\d+)\s+pts:\s*-?\d+\s+pts_time:(-?[\d.]+)", r.stderr)]


def decode_gray(path: str, step: int = DOWN, output_params=None) -> np.ndarray:
    """解码为降采样灰度帧。output_params 默认用 passthrough 保证帧序精确。"""
    if output_params is None:
        output_params = ["-fps_mode", "passthrough"]
    gen = imageio_ffmpeg.read_frames(path, pix_fmt="rgb24",
                                     output_params=list(output_params))
    meta = next(gen)
    w, h = meta["size"]
    nb = w * h * 3
    out = []
    for chunk in gen:
        a = np.frombuffer(chunk[:nb], dtype=np.uint8).reshape(h, w, 3)
        out.append(a[::step, ::step].mean(axis=2).astype(np.float32))
    if not out:
        raise RuntimeError(f"解码不到帧: {path}")
    return np.stack(out)


def extract_with_filter(path: str, vf: str, tmpdir: Path,
                        step: int = DOWN) -> np.ndarray:
    """用待测滤镜抽帧，返回降采样灰度帧。

    每次调用都在**本次运行专属的子目录**里写 PNG，而不是复用 `tmpdir` 本身。
    原因（实测踩到）：若上一次运行被中断（例如宿主命令管道被截断导致 ffmpeg 被 kill），
    `tmpdir` 里会留下**写了一半的 PNG**；下一次运行读到它就会以
    `OSError: unrecognized data stream contents when reading image file` 崩溃——
    而这个报错完全看不出真正原因是"上一轮的残留"。
    **工具不能因为上一次被中断而变得不可信。**
    """
    import shutil
    import uuid
    run_dir = tmpdir / f"run_{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                        "-i", path, "-vf", vf, str(run_dir / "o_%05d.png")], check=True)
        files = sorted(run_dir.glob("o_*.png"))
        if not files:
            raise RuntimeError(f"滤镜 {vf!r} 没有输出帧")
        out = []
        for f in files:
            try:
                out.append(iio.imread(str(f))[::step, ::step].mean(axis=2).astype(np.float32))
            except Exception as exc:
                raise RuntimeError(
                    f"读取抽出的帧失败: {f.name}（{exc}）。"
                    f"常见原因是该文件被写了一半——检查是否有被中断的上一轮残留。") from exc
        return np.stack(out)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def measure(path: str, vf: str, nominal_fps: float, tmpdir: Path) -> dict:
    src_pts = dump_pts(path)
    S = decode_gray(path)
    if len(src_pts) != len(S):
        raise RuntimeError(
            f"基准解码帧序不可信: showinfo {len(src_pts)} vs 解码 {len(S)}（需 passthrough）")
    F = extract_with_filter(path, vf, tmpdir)

    rows = []
    for k, fr in enumerate(F):
        tgt = k / nominal_fps
        c = int(round(tgt * SRC_FPS))
        lo, hi = max(0, c - WINDOW), min(len(S), c + WINDOW + 1)
        mad, idx = min(((float(np.abs(S[j] - fr).mean()), j) for j in range(lo, hi)))
        rows.append({"k": k, "nominal_s": round(tgt, 6), "src_index": idx,
                     "src_pts_s": round(src_pts[idx], 6),
                     "bias_s": round(src_pts[idx] - tgt, 6),
                     "match_mad": round(mad, 4)})

    mad_max = max(r["match_mad"] for r in rows)
    idxs = [r["src_index"] for r in rows]
    strictly_increasing = all(b > a for a, b in zip(idxs, idxs[1:]))
    biases = np.array([r["bias_s"] for r in rows])

    return {
        "input": str(path),
        "filter": vf,
        "nominal_fps": nominal_fps,
        "source_frames": len(S),
        "output_frames": len(F),
        "invariants": {
            # 这两条不成立时，偏差数字不可信
            "mapping_is_exact": bool(mad_max < 1e-6),
            "max_match_mad": mad_max,
            "source_index_strictly_increasing": strictly_increasing,
        },
        "bias": {
            "min_s": float(biases.min()), "max_s": float(biases.max()),
            "mean_s": float(biases.mean()), "median_s": float(np.median(biases)),
            "all_same_sign": bool((biases > 0).all() or (biases < 0).all()),
            "is_systematic": bool(abs(biases.mean()) > 0.02 and
                                  (biases.max() - biases.min()) < 0.05),
        },
        "rows": rows,
    }


def selftest(repo_root: Path) -> bool:
    tmp = Path(__file__).resolve().parent / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    clips = sorted(glob.glob(str(repo_root / "原始素材" / "*.mp4")))
    print("=" * 74)
    print("抽帧偏差自测：-vf fps=4，逐像素匹配求真实来源")
    print("=" * 74)
    ok = True
    means = []
    for c in clips:
        r = measure(c, "fps=4", 4.0, tmp)
        inv = r["invariants"]
        b = r["bias"]
        good = inv["mapping_is_exact"] and inv["source_index_strictly_increasing"]
        ok = ok and good
        means.append(b["mean_s"])
        print(f"  {os.path.basename(c)[:14]}… 输出 {r['output_frames']:4d} 帧  "
              f"匹配 MAD max={inv['max_match_mad']:.4f} "
              f"严格递增={inv['source_index_strictly_increasing']}  "
              f"偏差 min={b['min_s']:+.4f} max={b['max_s']:+.4f} mean={b['mean_s']:+.4f}"
              f"  同号={b['all_same_sign']}")
        if not good:
            print("     [FAIL] 不变量不成立，本次偏差数字不可信")
    # 结论断言：三段同号且量级一致（本项目已记录的事实）
    same_sign = all(m > 0 for m in means) or all(m < 0 for m in means)
    consistent = (max(means) - min(means)) < 0.03
    if not (same_sign and consistent):
        print(f"  [FAIL] 三段偏差不同号或不一致: {means}")
        ok = False
    else:
        print(f"\n  [PASS] 三段偏差同号且一致（均值 {np.mean(means):+.4f}s）"
              f" → 这是 **系统性偏差**，不是随机抖动")
        print("         与 CFR/VFR 无关：CFR 的 a 段同样偏，且量级相同。")

    (tmp / "last-run.json").write_text(
        json.dumps({"clip_means_s": means}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    for f in tmp.glob("o_*.png"):
        f.unlink()
    return ok


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="抽帧偏差测量器")
    ap.add_argument("--input")
    ap.add_argument("--filter", default="fps=4")
    ap.add_argument("--fps", type=float, default=4.0, help="该滤镜的标称输出帧率")
    ap.add_argument("--json-out")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return 0 if selftest(REPO_ROOT) else 1

    if not args.input:
        ap.error("需要 --input（或用 --selftest）")
    tmp = Path(__file__).resolve().parent / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    r = measure(args.input, args.filter, args.fps, tmp)
    b, inv = r["bias"], r["invariants"]
    print(f"输入: {r['input']}")
    print(f"滤镜: {r['filter']}  标称 {r['nominal_fps']}fps  "
          f"源 {r['source_frames']} 帧 → 输出 {r['output_frames']} 帧")
    print(f"不变量: 映射精确={inv['mapping_is_exact']} (MAD max={inv['max_match_mad']})  "
          f"源帧号严格递增={inv['source_index_strictly_increasing']}")
    print(f"偏差: min={b['min_s']:+.4f}s max={b['max_s']:+.4f}s "
          f"mean={b['mean_s']:+.4f}s 同号={b['all_same_sign']} 系统性={b['is_systematic']}")
    if not (inv["mapping_is_exact"] and inv["source_index_strictly_increasing"]):
        print("[WARN] 不变量不成立，上述偏差不可信（需调窗口或降采样倍数重测）")
    for f in tmp.glob("o_*.png"):
        f.unlink()
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print(f"明细已写入: {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
