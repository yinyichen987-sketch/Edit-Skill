"""按 EDL 用 ffmpeg 渲染预览成片（不需要剪映）。

用途：剪映 7+ 无法自动导出，草稿只能人工打开导出。本脚本用 ffmpeg 按 EDL 的
时间码/音量/字幕落点渲染一版 **预览**，让人在打开剪映之前就能看到剪辑结果。

与剪映成片的差异（渲染前请知悉）：
  - 字幕字体用系统字体近似（剪映内部字体无法从 EDL 还原）
  - 转场「闪白」用 ffmpeg 的白色 fade 近似（剪映的转场实现有自己的曲线）
  - 剪映的 size→px 换算无公开来源，此处按规格的设计字号（56/72px）渲染
  - 这是**预览**，不是发行成片；正式导出仍须在剪映里人工完成

用法：
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\render_preview.py ep01
    .venv\\Scripts\\python.exe projects\\game-001\\tools\\render_preview.py ep01-vertical
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[3]
EDL_DIR = ROOT / "projects" / "game-001" / "edl"
OUT_DIR = ROOT / "projects" / "game-001" / "preview"
WORK = OUT_DIR / "_work"

FONT_PATH = r"C:\Windows\Fonts\msyhbd.ttc"      # 微软雅黑 Bold
FONT_PATH_FALLBACK = r"C:\Windows\Fonts\msyh.ttc"

# 字号映射：EDL 的 style.size（剪映内部值）→ 规格 §4.2 的设计像素
SIZE_PX = {6.0: 72, 5.0: 56}


def ff() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args: list[str], desc: str) -> None:
    proc = subprocess.run([ff(), "-hide_banner", "-loglevel", "error", *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"[FAIL] {desc}\n{(proc.stderr or '').strip()[-800:]}")
        raise SystemExit(1)
    print(f"  [OK] {desc}")


def px_from_y(y: float, H: int) -> float:
    """transform_y（半个画布高，上移为正）→ 中心距顶像素。"""
    return (1.0 - y) / 2.0 * H


def piecewise(keys: list[tuple[float, float]], var: str = "t") -> str:
    """把 [(时刻秒, 值)] 关键帧编成 ffmpeg 分段线性表达式。

    ffmpeg 里逗号是参数分隔符，表达式内的逗号必须转义成 `\\,`。
    """
    if not keys:
        return "1"
    if len(keys) == 1:
        return f"{keys[0][1]}"
    expr = f"{keys[-1][1]}"
    for (t0, v0), (t1, v1) in zip(reversed(keys[:-1]), reversed(keys[1:])):
        span = (t1 - t0) or 1e-6
        seg = f"{v0}+({v1}-{v0})*({var}-{t0})/{span}"
        expr = f"if(lt({var}\\,{t1})\\,{seg}\\,{expr})"
    return expr


def kf_series(item: dict, prop: str) -> list[tuple[float, float]]:
    """取出某属性的关键帧序列（相对片段起点的秒 → 值）。"""
    out = [(float(k["time"]), float(k["value"]))
           for k in (item.get("keyframes") or []) if k.get("property") == prop]
    return sorted(out)


def probe_dims(path: Path) -> tuple[int, int] | None:
    """读素材像素尺寸（pymediainfo，与 edl_to_draft 用的是同一套依赖）。"""
    try:
        from pymediainfo import MediaInfo
    except ImportError:
        return None
    for t in MediaInfo.parse(str(path)).tracks:
        if t.track_type == "Video" and t.width and t.height:
            return int(t.width), int(t.height)
    return None


def contain_size(sw: int, sh: int, W: int, H: int) -> tuple[int, int]:
    """剪映 scale=1.0 的 displayed 尺寸 —— contain（等比装进画布）。

    实测依据：1280x720 放进 1080x1920、scale=1.0 时剪映渲染出的画面带是 1080x608，
    与 contain 理论值 1080x607.5 吻合（见 draft 封面实测）。
    """
    if sw / sh >= W / H:
        return W, max(2, round(W * sh / sw))
    return max(2, round(H * sw / sh)), H


def make_caption_png(text: str, size_px: int, W: int, H: int, center_px: float, out: Path) -> None:
    """渲染一条字幕为透明 PNG（白字 + 黑描边），水平居中，中心位于 center_px。"""
    font = ImageFont.truetype(FONT_PATH if os.path.exists(FONT_PATH) else FONT_PATH_FALLBACK, size_px)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = d.textbbox((0, 0), text, font=font, stroke_width=max(2, size_px // 18))
    tw, th = box[2] - box[0], box[3] - box[1]
    x = (W - tw) / 2 - box[0]
    y = center_px - th / 2 - box[1]
    d.text((x, y), text, font=font, fill=(255, 255, 255, 255),
           stroke_width=max(2, size_px // 18), stroke_fill=(0, 0, 0, 255))
    img.save(out)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: render_preview.py <edl 名，如 ep01 或 ep01-vertical>")
        return 2
    name = sys.argv[1]
    edl_path = EDL_DIR / f"{name}.json"
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    W = int(edl["canvas"]["width"]); H = int(edl["canvas"]["height"]); FPS = int(edl["canvas"].get("fps", 30))
    base = edl_path.parent

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    print(f"=== 渲染预览: {name}  {W}x{H} @{FPS} ===")

    # ---- 1. 逐片段裁剪 + 音量 + 关键帧动效 ----
    seg_files = []
    for i, c in enumerate(edl["clips"]):
        src = Path(c["source"]) if os.path.isabs(c["source"]) else (base / c["source"]).resolve()
        out = WORK / f"seg{i}.mp4"

        clip_cfg = c.get("clip") or {}
        band_scale = float(clip_cfg.get("scale", clip_cfg.get("scale_y", 1.0)))
        bf = c.get("background_filling") or {}
        blur_bg = bf.get("type") == "blur"

        # 关键帧推拉（uniform_scale / scale_x）→ 先裁再放大，等价于「画面变大」
        sc = kf_series(c, "uniform_scale") or kf_series(c, "scale_x")
        # 关键帧亮度 → eq（需 eval=frame 才逐帧求值）
        br = kf_series(c, "brightness")

        base_f = [f"scale={W}:{H}:force_original_aspect_ratio=decrease",
                  "setsar=1", f"fps={FPS}"]

        if blur_bg:
            # 竖屏构图：画面带 + 素材自身的模糊放大版填满画布（消灭 2/3 黑边）
            dims = probe_dims(src)
            sw, sh = dims if dims else (1280, 720)
            bw, bh = contain_size(sw, sh, W, H)
            band_w, band_h = max(2, round(bw * band_scale)), max(2, round(bh * band_scale))
            sigma = max(6.0, 8.0 + float(bf.get("blur", 0.75)) * 28.0)
            fg = [f"scale={band_w}:{band_h}:flags=bicubic"]
            if sc:
                z = piecewise(sc)
                fg = [f"crop=w='{bw}/({z})':h='{bh}/({z})':x='(iw-ow)/2':y='(ih-oh)/2'",
                      f"scale={band_w}:{band_h}:flags=bicubic"]
            fc = (
                f"[0:v]{','.join(base_f)}[base];"
                f"[base]split=2[fgsrc][bgsrc];"
                f"[bgsrc]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},gblur=sigma={sigma:.1f}[bg];"
                f"[fgsrc]{','.join(fg)}[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2[ov]"
            )
            if br:
                fc += f";[ov]eq=brightness='{piecewise(br)}':eval=frame[vout]"
                last = "vout"
            else:
                last = "ov"
            run(["-y", "-ss", f"{c.get('source_in', 0)}", "-t", f"{c['duration']}", "-i", str(src),
                 "-filter_complex", fc, "-map", f"[{last}]",
                 "-af", f"volume={c.get('volume', 1.0)}",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)],
                f"clip {c['id']}  {src.name}  in={c.get('source_in',0)}  dur={c['duration']}  "
                f"竖屏构图 画面带{band_w}x{band_h}({band_scale}x) + 模糊底 sigma={sigma:.0f}"
                + (f"  推拉关键帧{len(sc)}个" if sc else "")
                + (f"  亮度关键帧{len(br)}个" if br else ""))
            seg_files.append(out)
            continue

        vf = base_f + [f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"]
        if sc:
            z = piecewise(sc)
            vf.append(f"crop=w='iw/({z})':h='ih/({z})':x='(iw-ow)/2':y='(ih-oh)/2'")
            vf.append(f"scale={W}:{H}:flags=bicubic")
        if br:
            vf.append(f"eq=brightness='{piecewise(br)}':eval=frame")

        run(["-y", "-ss", f"{c.get('source_in', 0)}", "-t", f"{c['duration']}", "-i", str(src),
             "-vf", ",".join(vf),
             "-af", f"volume={c.get('volume', 1.0)}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)],
            f"clip {c['id']}  {src.name}  in={c.get('source_in',0)}  dur={c['duration']}  vol={c.get('volume',1.0)}"
            + (f"  推拉关键帧{len(sc)}个" if sc else "") + (f"  亮度关键帧{len(br)}个" if br else ""))
        seg_files.append(out)

    # ---- 2. 拼接（零间隙，与 EDL 的 start 递进一致）----
    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in seg_files), encoding="utf-8")
    joined = WORK / "joined.mp4"
    run(["-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)], "拼接 4 片段")

    # ---- 3. 转场：闪白 ----
    # 实现要点（踩过的坑）：不能用 video 层的 `fade=t=in:st=X` 来做局部白闪——
    # `fade=in` 会把 X **之前**的所有帧都置为"淡入起始态"（即纯白），
    # 多段叠加后整片变白（实测 flashed.mp4 只剩 1.3 KB 的纯白）。
    # 正确做法：另起一个 **白色叠加层**，只对它的 **alpha** 做 in/out 包络，再 overlay。
    total = sum(float(c["duration"]) for c in edl["clips"])
    cur = joined
    trans = [c for c in edl["clips"] if c.get("transition")]
    if trans:
        args = ["-y", "-i", str(joined)]
        chain, prev, inp = [], "0:v", 1
        for c in trans:
            T = float(c["start"])
            d = float(c["transition"].get("duration", 0.13))
            args += ["-f", "lavfi", "-i", f"color=white:s={W}x{H}:d={total}:r={FPS}"]
            chain.append(
                f"[{inp}:v]format=rgba,"
                f"fade=t=in:st={max(0.0, T - d/2):.3f}:d={d/2:.3f}:alpha=1,"
                f"fade=t=out:st={T:.3f}:d={d/2:.3f}:alpha=1[w{inp}]")
            chain.append(f"[{prev}][w{inp}]overlay=0:0:format=auto[v{inp}]")
            prev = f"v{inp}"
            inp += 1
        flashed = WORK / "flashed.mp4"
        args += ["-filter_complex", ";".join(chain), "-map", f"[{prev}]", "-map", "0:a?",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "copy", str(flashed)]
        run(args, f"转场闪白 ×{len(trans)}（白色叠加层 + alpha 包络）")
        cur = flashed
    # ---- 4. 字幕叠加 ----
    cap_inputs, cap_filters, cap_meta = [], [], []
    for t in edl["texts"]:
        size_px = SIZE_PX.get(float(t.get("style", {}).get("size", 5.0)), 56)
        center = px_from_y(float(t["style"]["transform_y"]), H)
        png = WORK / f"cap_{t['id']}.png"
        make_caption_png(t["content"], size_px, W, H, center, png)
        cap_meta.append((t, png, size_px, center))

    args = ["-y", "-i", str(cur)]
    for _, png, _, _ in cap_meta:
        args += ["-i", str(png)]
    chain = []
    prev = "0:v"
    for idx, (t, png, size_px, center) in enumerate(cap_meta):
        st, en = float(t["start"]), float(t["start"]) + float(t["duration"])
        lab = f"v{idx}"
        chain.append(f"[{prev}][{idx+1}:v]overlay=0:0:enable='between(t,{st:.3f},{en:.3f})'[{lab}]")
        prev = lab
    fc = ";".join(chain)
    out_file = OUT_DIR / f"{name}_preview.mp4"
    args += ["-filter_complex", fc, "-map", f"[{prev}]", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_file)]
    run(args, f"叠加 {len(cap_meta)} 条字幕")

    # ---- 5. 校验 ----
    probe = subprocess.run([ff(), "-hide_banner", "-i", str(out_file)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    import re
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", (probe.stderr or ""))
    dur = (int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))) if m else 0.0
    print()
    print("=" * 60)
    print(f"输出: {out_file}")
    print(f"  分辨率 {W}x{H}  时长 {dur:.2f}s  大小 {out_file.stat().st_size/1024/1024:.1f} MB")
    print(f"  字幕 {len(cap_meta)} 条 | 转场 {len(edl['clips'])-1} 处（闪白近似）")
    print("  ⚠️ 这是 ffmpeg 预览，不是剪映成片；正式导出仍须在剪映里人工完成")
    print("=" * 60)
    for t, png, size_px, center in cap_meta:
        print(f"    {t['id']}  {size_px}px  中心 {center:6.1f}px  {t['content']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
