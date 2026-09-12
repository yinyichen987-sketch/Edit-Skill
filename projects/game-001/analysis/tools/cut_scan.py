"""全片相邻帧差异扫描 —— 用全量分布判定「瞬时视点跳变」。

为什么重写：
    我之前只按 4fps 抽帧目视，0.25s 的采样间隔**天然会漏掉一帧宽的硬切**。
    要判定「有没有硬切」，必须逐帧比较相邻帧，并看全量分布，而不是抽几帧看。

方法：
    1. 整段解码为灰度、缩放到 320x180，逐帧计算与前一帧的平均绝对差 (MAE)
    2. 汇总全量分布（中位/分位）
    3. 用 MAD 稳健判据找离群点：MAE > median + k*1.4826*MAD
    4. 报告离群点的时间、以及「比中位高多少倍」

同时跑阳性/阴性对照（不靠猜）：
    - 阳性：spike/media/test_film.mp4（已知 2 处硬切，应命中 2 处）
    - 阴性：spike/media/test_a.mp4（已知无切，应 0 误报）
    这一步是关键：如果检测器在阳性对照上 0 命中，那它「没检出切点」毫无意义。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 320, 180
FRAME_BYTES = W * H  # gray8
TMP = "projects/game-001/analysis/raw/_scan_tmp"


def decode_gray(path: str) -> tuple[list[bytes], list[float]]:
    """返回 (帧灰度数据, 各帧 pts_time)。

    注意：**不能**在同一个 ffmpeg 调用里把 rawvideo 写到 stdout 又把 showinfo 写到 stderr。
    视频几十 MB 时 stderr 很快写满管道缓冲，而 ffmpeg 又不读 stderr，导致死锁，
    Python 侧 capture_output 拿到 0 字节。所以这里分两步、且全部落盘，不依赖管道。
    """
    tmp_raw = os.path.join(TMP, "frames.gray")
    os.makedirs(TMP, exist_ok=True)
    # 关键：先删旧文件，避免上一次更大文件的残留字节造成帧错位
    if os.path.exists(tmp_raw):
        os.remove(tmp_raw)

    # 第一遍：只要像素
    r1 = subprocess.run(
        [FF, "-hide_banner", "-nostats", "-v", "error", "-y", "-i", path,
         "-vf", f"scale={W}:{H},format=gray", "-an",
         "-f", "rawvideo", "-pix_fmt", "gray", tmp_raw],
        capture_output=True)
    if r1.returncode != 0:
        print(f"  [decode error] {r1.stderr.decode('utf-8','replace')[:300]}")

    raw = open(tmp_raw, "rb").read() if os.path.exists(tmp_raw) else b""
    # fwrite_packet 输出时会附加统计页脚，字节数通常不是帧大小的整数倍；
    # 只取能整除的整数帧，并**报告**余数，便于发现错位。
    n_frames = len(raw) // FRAME_BYTES
    remainder = len(raw) - n_frames * FRAME_BYTES
    frames = [raw[i * FRAME_BYTES:(i + 1) * FRAME_BYTES] for i in range(n_frames)]
    if remainder:
        print(f"  [note] {os.path.basename(path)}: 尾部余 {remainder} 字节（已丢弃）")

    pts = []
    tmp_meta = os.path.join(TMP, "frames.txt")
    if os.path.exists(tmp_meta):
        os.remove(tmp_meta)
    with open(tmp_meta, "wb") as meta_fh:
        subprocess.run(
            [FF, "-hide_banner", "-nostats", "-v", "error", "-y", "-i", path,
             "-vf", f"scale={W}:{H},format=gray,showinfo", "-an",
             "-f", "null", os.devnull],
            stdout=subprocess.DEVNULL, stderr=meta_fh)
    if os.path.exists(tmp_meta):
        for line in open(tmp_meta, encoding="utf-8", errors="replace"):
            if "pts_time:" in line:
                try:
                    pts.append(float(line.split("pts_time:")[1].split()[0]))
                except (IndexError, ValueError):
                    pass
    return frames, pts


def mae(a: bytes, b: bytes) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    # 逐字节绝对差之和 / 字节数 —— 灰度单通道，不再有通道稀释
    return sum(abs(a[i] - b[i]) for i in range(len(a))) / len(a)


def scan(path: str, label: str, k: float = 8.0, top_n: int = 8) -> dict:
    frames, pts = decode_gray(path)
    if len(frames) < 3:
        return {"label": label, "path": path, "error": f"帧太少 ({len(frames)})"}

    diffs = [mae(frames[i], frames[i + 1]) for i in range(len(frames) - 1)]
    s = sorted(diffs)
    med = s[len(s) // 2]
    mad = sorted(abs(d - med) for d in diffs)[len(diffs) // 2]
    sigma = 1.4826 * mad
    # 全局阈值判据在「纯色底 + 少量变化」的夹具上会退化（MAD=0），
    # 因此阈值只在 sigma 有效时给出，主力判据用下面的 TOP-N 峰值排序。
    thresh = (med + k * sigma) if sigma > 1e-9 else None

    ranked = sorted(range(len(diffs)), key=lambda i: -diffs[i])[:top_n]
    top = []
    for i in ranked:
        t = pts[i + 1] if i + 1 < len(pts) else None
        top.append({
            "frame_index": i + 1,
            "time_s": round(t, 4) if t is not None else None,
            "mae": round(diffs[i], 3),
            "x_median": round(diffs[i] / med, 2) if med > 1e-9 else None,
        })

    outliers = []
    if thresh is not None:
        for i, d in enumerate(diffs):
            if d > thresh:
                t = pts[i + 1] if i + 1 < len(pts) else None
                outliers.append({"frame_index": i + 1,
                                 "time_s": round(t, 4) if t is not None else None,
                                 "mae": round(d, 3)})

    return {
        "label": label, "path": path, "frames": len(frames),
        "mae_median": round(med, 3), "mae_mad": round(mad, 3),
        "mae_p95": round(s[int(len(s) * 0.95)], 3), "mae_max": round(s[-1], 3),
        "threshold": round(thresh, 3) if thresh is not None else None,
        "outlier_count": len(outliers), "outliers": outliers,
        "top_peaks": top,
    }


def main() -> int:
    # Windows 默认控制台为 GBK，中文/符号（⊂ ✓ ✅ → 等）会在打印中途抛
    # UnicodeEncodeError 而退出；崩溃退出码可能与脚本自身的失败码相同，
    # 导致「崩溃」被误读为「检查未通过」。统一改为 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    targets = [
        ("原始素材/4b0460c400bbb5320acb6063b4f59358.mp4", "a_4b0460c4 (CFR)"),
        ("原始素材/6b2eea343eee7595c3c0ede10d21d028.mp4", "b_6b2eea34 (VFR)"),
        ("原始素材/dcc871b1791e7796fadac842593f10f7.mp4", "c_dcc871b1 (VFR)"),
    ]
    controls = [
        ("spike/media/test_film.mp4", "阳性对照 test_film（已知 2 处硬切）"),
        ("spike/media/test_a.mp4", "阴性对照 test_a（已知无切）"),
    ]

    print("=" * 78)
    print("阳性 / 阴性对照（先验证检测器本身是好的）")
    print("=" * 78)
    ctrl_out = []
    for p, lab in controls:
        if not os.path.exists(p):
            print(f"  跳过（不存在）: {p}")
            continue
        r = scan(p, lab, top_n=6)
        ctrl_out.append(r)
        if "error" in r:
            print(f"  {lab}\n     !! {r['error']}（该对照不可用，需换夹具）")
            continue
        print(f"  {lab}")
        print(f"     帧数={r['frames']}  MAE 中位={r['mae_median']}  MAD={r['mae_mad']}  "
              f"max={r['mae_max']}  全局阈值={r['threshold']}  全局离群点={r['outlier_count']}")
        print("     能量最高的相邻帧差（TOP）:")
        for o in r["top_peaks"]:
            t = f"{o['time_s']:.3f}s" if o["time_s"] is not None else "?"
            ratio = f"{o['x_median']}x" if o["x_median"] is not None else "n/a"
            print(f"       frame#{o['frame_index']:>4}  t={t:>9}  MAE={o['mae']:>8}  ({ratio} 中位)")

    print()
    print("=" * 78)
    print("三段原始素材：全片逐帧相邻差异扫描")
    print("=" * 78)
    out = []
    for p, lab in targets:
        r = scan(p, lab, top_n=10)
        out.append(r)
        print(f"\n{lab}")
        if "error" in r:
            print(f"   !! {r['error']}")
            continue
        print(f"   帧数={r['frames']}  MAE 中位={r['mae_median']}  MAD={r['mae_mad']}  "
              f"p95={r['mae_p95']}  max={r['mae_max']}")
        print(f"   全局阈值={r['threshold']}  全局离群点={r['outlier_count']}")
        print("   最强的相邻帧差（TOP，与「claimed 跳变点」比对）:")
        for o in r["top_peaks"]:
            t = f"{o['time_s']:.3f}s" if o["time_s"] is not None else "?"
            ratio = f"{o['x_median']}x" if o["x_median"] is not None else "n/a"
            print(f"       frame#{o['frame_index']:>4}  t={t:>9}  MAE={o['mae']:>8}  ({ratio} 中位)")

    json.dump({"controls": ctrl_out, "clips": out},
              open("projects/game-001/analysis/raw/cut_scan.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n[OK] projects/game-001/analysis/raw/cut_scan.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
