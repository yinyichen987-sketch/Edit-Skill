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

# 字号映射：剪映 `size` → 渲染像素。**实测换算，不是设计值**。
#   em_px ≈ 5.29 × size（**4 点标定实测**：8/14/20/26 四档反算均为 5.28–5.30，极差 0.02 线性成立；单点估计曾为 5.55，偏差 5%）
#   依据：剪映自己渲染的草稿封面里，pyJianYingDraft 默认字号 8.0 的文案
#   `DSH SPIKE 测试字幕` 测得 ink 高 43px、总宽 456px，两个独立量都收敛到 em≈44.4px。
#   同时证伪了 `size/100×画布高` 的假设（那样字符串要有 1470px 宽，画面放不下）。
#   旧代码用 {6.0:72, 5.0:56}（隐含 size×12），把字号高估了约 2.2 倍。
EM_PER_SIZE = 5.29


def ff() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args: list[str], desc: str) -> None:
    proc = subprocess.run([ff(), "-hide_banner", "-loglevel", "error", *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        # 报错重点常在**开头**（"matches no streams" 之类），尾部反而是滤镜串 —— 故打印头部
        print(f"[FAIL] {desc}\n{err[:2000]}")
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


def seg_audio_filter(volume: float, speed: float, duration: float) -> str:
    """片段音频滤镜：音量 + 变速 + **裁/补齐到精确时长**。

    为什么要 apad：每段独立编码后拼接时，容器时长 = max(视频, 音频)。
    音频补齐到精确时长，视频侧则由 -frames:v + tpad 凑齐**精确帧数**
    （见 main() 里 n_frames 的注释）—— 两边都精确，容器时长才严格等于 EDL 时长。
    ⚠️ 第 18 轮修正：此前视频用 `int(x*FPS)` 向下取整，实测**每段少 1 帧**
    （14 段无一例外），画面累计比音频早 0.300 s ⇒ 预览里听什么都延后。
    """
    parts = [f"volume={volume}"]
    if speed != 1.0:
        parts.append(f"atempo={speed:.6f}")
    parts.append(f"atrim=0:{duration:.6f}")
    parts.append(f"apad=whole_dur={duration:.6f}")
    return ",".join(parts)


def make_caption_png(text: str, size_px: int, W: int, H: int, center_px: float, out: Path,
                     panel: bool = False, center_x: float | None = None) -> None:
    """渲染一条字幕为透明 PNG（白字 + 黑描边），水平居中，中心位于 center_px。

    `panel=True` 时额外画一块**半透明深色底板** —— 这是用户参考成片（瓦参考素材）的标签形态：
    白粗字 + 半透明底，让字在亮画面上也读得清。预览要能反映它，否则会误判成"没有底板"。
    """
    font = ImageFont.truetype(FONT_PATH if os.path.exists(FONT_PATH) else FONT_PATH_FALLBACK, size_px)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stroke = max(2, size_px // 18)
    box = d.textbbox((0, 0), text, font=font, stroke_width=stroke)
    tw, th = box[2] - box[0], box[3] - box[1]
    cx = (W / 2) if center_x is None else center_x      # transform_x 支持（计分板式贴右）
    x = cx - tw / 2 - box[0]
    y = center_px - th / 2 - box[1]
    if panel:
        padx, pady = round(size_px * 0.55), round(size_px * 0.22)
        d.rounded_rectangle(
            [x + box[0] - stroke - padx, center_px - th / 2 - pady,
             x + box[0] + tw + stroke + padx, center_px + th / 2 + pady],
            radius=round(size_px * 0.10), fill=(0, 0, 0, 115))   # ≈ #00000073
    d.text((x, y), text, font=font, fill=(255, 255, 255, 255),
           stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
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
    # ⚠️ 叠加轨（`ovl_*`：白场/黑场**素材**，见 references/techniques/kill-moment.md §1）
    #    不是主轨片段。早期版本把它们当主轨顺序拼进去 ⇒ 预览里会整屏变白变黑一大段，
    #    与剪映里的实际效果**完全不同**。这里单独渲染，最后按 start 叠上去。
    ovl_clips = [c for c in edl["clips"] if str(c.get("track", "")).startswith("ovl_")]
    main_clips = [c for c in edl["clips"] if not str(c.get("track", "")).startswith("ovl_")]
    seg_files = []
    for i, c in enumerate(main_clips):
        src = Path(c["source"]) if os.path.isabs(c["source"]) else (base / c["source"]).resolve()
        out = WORK / f"seg{i}.mp4"

        clip_cfg = c.get("clip") or {}
        band_scale = float(clip_cfg.get("scale", clip_cfg.get("scale_y", 1.0)))
        bf = c.get("background_filling") or {}
        blur_bg = bf.get("type") == "blur"

        # 变速：**素材窗口 = 时间线长度 × 速度**（timeline = source / speed）。
        # 预览里用 setpts 放慢/加快视频、atempo 同步音频，使预览与 EDL 时间线一致。
        speed = float(c.get("speed", 1.0)) or 1.0
        src_window = float(c["duration"]) * speed
        speed_v = [f"setpts=PTS/{speed:.6f}", f"fps={FPS}"] if speed != 1.0 else []
        # 视频帧数**必须精确**，不能向下取整。EDL 的每段时长本来就是整数帧，
        # 但 JSON 只保留 6 位小数（如 2.233334 s），浮点误差会让 `int(x*FPS)` 掉一帧。
        # 实测后果（第 18 轮）：14 段**每段都少 1 帧**，画面累计比音频**早 0.300 s** ——
        # 于是预览里**所有音效（whoosh / impact）听起来都延后**最多 0.3 s。
        # 修法：round() 求精确帧数 + 滤镜链尾 tpad 克隆末帧，保证 -frames:v 一定凑得齐。
        n_frames = max(1, int(round(float(c["duration"]) * FPS)))
        TPAD = "tpad=stop_mode=clone:stop_duration=1"
        afilter = seg_audio_filter(float(c.get("volume", 1.0)), speed, float(c["duration"]))

        # 调色：EDL 给了 filter 就近似成调研给出的廉价等价式
        # （对比 +5% / 饱和 +9% / 暗角 / 轻噪点）—— 让预览反映"全片同一个 grade"。
        grade = []
        if c.get("filter"):
            # 近似教学文（diantuoyi 8990 技巧2）的调色公式：
            #   对比度 +15 / 颗粒 5% / 暗角 10% / 锐化 —— 滤镜本身由 剪映 的 青橙 提供
            grade = ["eq=contrast=1.15:saturation=1.09",
                     "unsharp=5:5:0.6:5:5:0.0",
                     "vignette=PI/4.4",
                     "noise=alls=8:allf=t+u"]

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
            tail = grade + speed_v + [TPAD]
            fc += f";[{last}]{','.join(tail)}[vfin]"
            last = "vfin"
            run(["-y", "-ss", f"{c.get('source_in', 0)}", "-t", f"{src_window}", "-i", str(src),
                 "-filter_complex", fc, "-map", f"[{last}]",
                 # ⚠️ 用了 -map 就**只**输出被映射的流：这里必须显式再映射音频，
                 # 否则片段文件里**根本没有音轨**（实测 seg0.mp4 只有一条 Video 流），
                 # 后面 amix 时 [0:a] 找不到流 → "matches no streams"。
                 "-an",   # 片段只出视频：音频在最后一次 pass 里统一构建，避免逐段 AAC padding
                 "-frames:v", str(n_frames),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)],
                f"clip {c['id']}  {src.name}  in={c.get('source_in',0)}  dur={c['duration']}  "
                f"竖屏构图 画面带{band_w}x{band_h}({band_scale}x) + 模糊底 sigma={sigma:.0f}"
                + (f"  推拉关键帧{len(sc)}个" if sc else "")
                + (f"  亮度关键帧{len(br)}个" if br else "")
                + (f"  grade" if grade else "")
                + (f"  变速{speed}x(吃素材{src_window:.4f}s)" if speed != 1.0 else ""))
            seg_files.append(out)
            continue

        vf = base_f + [f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"]
        if sc:
            z = piecewise(sc)
            vf.append(f"crop=w='iw/({z})':h='ih/({z})':x='(iw-ow)/2':y='(ih-oh)/2'")
            vf.append(f"scale={W}:{H}:flags=bicubic")
        if br:
            vf.append(f"eq=brightness='{piecewise(br)}':eval=frame")
        vf.extend(grade)
        vf.extend(speed_v)
        vf.append(TPAD)

        run(["-y", "-ss", f"{c.get('source_in', 0)}", "-t", f"{src_window}", "-i", str(src),
             "-vf", ",".join(vf),
             "-an",
             "-frames:v", str(n_frames),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)],
            f"clip {c['id']}  {src.name}  in={c.get('source_in',0)}  dur={c['duration']}  vol={c.get('volume',1.0)}"
            + (f"  推拉关键帧{len(sc)}个" if sc else "") + (f"  亮度关键帧{len(br)}个" if br else ""))
        seg_files.append(out)

    # ---- 2. 拼接（零间隙，与 EDL 的 start 递进一致）----
    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in seg_files), encoding="utf-8")
    joined = WORK / "joined.mp4"
    run(["-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)],
        f"拼接 {len(seg_files)} 片段")

    # ---- 2b. 叠加轨：白场/黑场素材按各自 start 压到主轨上 ----
    # 这些是**素材**（媒体 → 官方素材 → 白场/黑场），不是"调亮度"，所以做法就是 overlay。
    total_main = max(float(c["start"]) + float(c["duration"]) for c in main_clips)
    if ovl_clips:
        args = ["-y", "-i", str(joined)]
        chain, prev, inp = [], "0:v", 1
        for c in sorted(ovl_clips, key=lambda x: float(x["start"])):
            src_o = Path(c["source"]) if os.path.isabs(c["source"]) else (base / c["source"]).resolve()
            args += ["-ss", f"{c.get('source_in', 0)}", "-t", f"{c['duration']}",
                     "-i", str(src_o)]
            chain.append(
                f"[{inp}:v]scale={W}:{H},setsar=1,fps={FPS},format=rgba,"
                f"colorchannelmixer=aa=1.0,setpts=PTS-STARTPTS+{float(c['start']):.4f}/TB[o{inp}]")
            chain.append(f"[{prev}][o{inp}]overlay=0:0:eof_action=pass:format=auto[v{inp}]")
            prev = f"v{inp}"
            inp += 1
        ovl_out = WORK / "overlaid.mp4"
        args += ["-filter_complex", ";".join(chain), "-map", f"[{prev}]", "-map", "0:a?",
                 "-t", f"{total_main:.4f}",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "copy", str(ovl_out)]
        run(args, f"叠加轨 ×{len(ovl_clips)}（白场/黑场素材，按 start 压在主轨上）")
        joined = ovl_out

    # ---- 3. 转场：闪白 ----
    # 实现要点（踩过的坑）：不能用 video 层的 `fade=t=in:st=X` 来做局部白闪——
    # `fade=in` 会把 X **之前**的所有帧都置为"淡入起始态"（即纯白），
    # 多段叠加后整片变白（实测 flashed.mp4 只剩 1.3 KB 的纯白）。
    # 正确做法：另起一个 **白色叠加层**，只对它的 **alpha** 做 in/out 包络，再 overlay。
    total = sum(float(c["duration"]) for c in edl["clips"])
    cur = joined
    trans = [c for c in edl["clips"] if c.get("transition")]
    # 按类型分开近似：**不能用一种近似冒充所有转场**。
    #   闪白类 → 白色叠加层 + alpha 包络
    #   信号故障/故障类 → RGB 通道错位 + 噪声爆发（时间窗用 enable 门控），
    #     否则预览会把它显示成"白闪"，让人误判成上一版那种基础转场。
    FLASHY = {"闪白", "闪白_II", "闪黑", "闪屏", "曝光"}
    glitch = [c for c in trans if c["transition"].get("type") not in FLASHY]
    flashy = [c for c in trans if c["transition"].get("type") in FLASHY]
    if glitch:
        args = ["-y", "-i", str(joined)]
        chain, prev = [], "0:v"
        for i, c in enumerate(glitch):
            T = float(c["start"])
            d = float(c["transition"].get("duration", 0.13))
            a, b = max(0.0, T - d / 2), T + d / 2
            lab = f"g{i}"
            chain.append(
                f"[{prev}]rgbashift=rh=16:bh=-16:enable='between(t,{a:.3f},{b:.3f})',"
                f"noise=alls=32:allf=t:enable='between(t,{a:.3f},{b:.3f})'[{lab}]")
            prev = lab
        glitched = WORK / "glitched.mp4"
        args += ["-filter_complex", ";".join(chain), "-map", f"[{prev}]", "-map", "0:a?",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "copy", str(glitched)]
        run(args, f"转场故障 ×{len(glitch)}（RGB 错位 + 噪声窗近似；剪映实际是 信号故障）")
        cur = glitched
    if flashy:
        args = ["-y", "-i", str(cur)]
        chain, prev, inp = [], "0:v", 1
        for c in flashy:
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
        run(args, f"转场闪白 ×{len(flashy)}（白色叠加层 + alpha 包络）")
        cur = flashed
    # ---- 4. 字幕叠加 ----
    cap_inputs, cap_filters, cap_meta = [], [], []
    for t in edl["texts"]:
        size_px = round(EM_PER_SIZE * float(t.get("style", {}).get("size", 8.0)))
        center = px_from_y(float(t["style"]["transform_y"]), H)
        cx = (1.0 - float(t["style"].get("transform_x", 0.0))) / 2.0 * W
        png = WORK / f"cap_{t['id']}.png"
        make_caption_png(t["content"], size_px, W, H, center, png,
                         panel=bool(t.get("background")), center_x=cx)
        cap_meta.append((t, png, size_px, center))

    args = ["-y", "-i", str(cur)]
    for _, png, _, _ in cap_meta:
        args += ["-i", str(png)]
    # 音频叠加（BGM + 音效）：此前预览**完全没渲染** audio_overlays —— 于是
    # 预览里既听不到 BGM 也听不到音效，"卡点"根本无从判断。这里补上。
    audio_inputs = []
    for ao in edl.get("audio_overlays") or []:
        ap = Path(ao["source"]) if os.path.isabs(ao["source"]) else (base / ao["source"]).resolve()
        if not ap.exists():
            print(f"  [WARN] 音频叠加素材缺失，已跳过: {ap}")
            continue
        audio_inputs.append((len(cap_meta) + 1 + len(audio_inputs), ao))
        args += ["-i", str(ap)]

    # 游戏原声：**在这里**从素材直接取，逐片段 adelay 定位。
    #   为什么不复用片段文件里的音轨：每段独立 AAC 编码都会把音频补齐到 1024 采样的整数倍
    #   （≈21ms），15 段累积出 +0.13s 偏移，末尾画面比 BGM 晚 4 帧 —— 对卡点片是硬伤。
    #   从这里统一构建，时间线就严格由 EDL 决定。
    base_n = len(cap_meta) + 1 + len(audio_inputs)
    clip_audio = []
    _added = 0          # 实际加进去的音频输入数（不能再用 j，跳过之后会错位）
    for c in main_clips:
        # 静音的纯视觉叠加片段（白场/黑场素材）**没有音轨**，不能当音频输入：
        # 引用 [k:a] 会让 ffmpeg 报 "matches no streams"。
        if float(c.get("volume", 1.0)) <= 0:
            continue
        src = Path(c["source"]) if os.path.isabs(c["source"]) else (base / c["source"]).resolve()
        sp = float(c.get("speed", 1.0)) or 1.0
        args += ["-ss", f"{c.get('source_in', 0)}", "-t", f"{float(c['duration']) * sp}",
                 "-i", str(src)]
        clip_audio.append((base_n + _added, c))
        _added += 1

    chain = []
    prev = "0:v"
    for idx, (t, png, size_px, center) in enumerate(cap_meta):
        st, en = float(t["start"]), float(t["start"]) + float(t["duration"])
        lab = f"v{idx}"
        chain.append(f"[{prev}][{idx+1}:v]overlay=0:0:enable='between(t,{st:.3f},{en:.3f})'[{lab}]")
        prev = lab
    if not cap_meta:
        # **没有任何字幕时必须补一个直通滤镜**：否则链路里没有任何滤镜定义输出标签，
        # 最后 -map [0:v] 会报
        # "Output with label '0:v' does not exist in any defined filter graph"。
        # （删掉全部文字后第一次渲染就是这么炸的。）
        chain.append("[0:v]null[vpass]")
        prev = "vpass"

    alabels = []
    for k, (i_off, c) in enumerate(clip_audio):
        st = float(c["start"]); du = float(c["duration"]); sp = float(c.get("speed", 1.0)) or 1.0
        parts = [f"volume={float(c.get('volume', 1.0))}"]
        if sp != 1.0:
            parts.append(f"atempo={sp:.6f}")
        parts.append(f"atrim=0:{du:.6f}")
        parts.append(f"adelay={int(round(st * 1000))}:all=1")
        chain.append(f"[{i_off}:a]" + ",".join(parts) + f"[ga{k}]")
        alabels.append(f"ga{k}")

    for k, (i_off, ao) in enumerate(audio_inputs):
        st = float(ao["start"]); du = float(ao["duration"]); vol = float(ao.get("volume", 1.0))
        fade = ao.get("fade") or {}
        fi, fo = float(fade.get("in", 0.0)), float(fade.get("out", 0.0))
        parts = [f"atrim=start=0:end={du:.4f}", f"volume={vol}"]
        if fi > 0:
            parts.append(f"afade=t=in:st=0:d={fi:.3f}")
        if fo > 0:
            parts.append(f"afade=t=out:st={max(0.0, du - fo):.4f}:d={fo:.3f}")
        # 位置靠 adelay 落在时间线上（不是 -ss：-ss 是文件内定位，不是时间线定位）
        parts.append(f"adelay={int(round(st * 1000))}:all=1")
        lab = f"ao{k}"
        chain.append(f"[{i_off}:a]" + ",".join(parts) + f"[{lab}]")
        alabels.append(lab)

    # normalize=0 很关键：amix 默认会按 1/N 衰减，把所有音轨都压没
    # ⚠️ 成片长度只算**主轨**（叠加的白场/黑场不占时间线，见 §1 的说明）。
    #    用 sum(所有 clips) 会把白场/黑场算进去，-t 就比真实成片长。
    total = max(float(c["start"]) + float(c["duration"]) for c in main_clips)
    chain.append("[" + "][".join(alabels) +
                 f"]amix=inputs={len(alabels)}:duration=longest:normalize=0[mixed]")
    # 实测教训（两处，都不是"调个参数"级别的坑）：
    #   ① alimiter 的 limit 是线性值，且 **AAC 编码后还有 intersample 过冲** ——
    #      第一版 limit=0.891（−1 dBFS）实测真峰值 **+1.1 dBFS，仍在削顶**。
    #   ② **alimiter 默认 level=1（auto level），它会把限幅结果再拉回去** ——
    #      同一素材：level 默认时 I=−10.5 LUFS / Peak=+0.6 dBFS（削顶）；
    #      加 level=0 后 I=−13.4 LUFS / Peak=−1.7 dBFS（正常）。
    #      也就是说"加了限幅器"和"限幅生效"是两件事，必须量真峰值才算数。
    chain.append("[mixed]alimiter=limit=0.70:attack=5:release=60:level=0[afinal]")
    amap = "[afinal]"

    fc = ";".join(chain)
    out_file = OUT_DIR / f"{name}_preview.mp4"
    args += ["-filter_complex", fc, "-map", f"[{prev}]", "-map", amap,
             # -t 强制成片长度严格等于 EDL 总长（差一点点也算错，卡点片对时间很敏感）
             "-t", f"{total:.6f}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_file)]
    run(args, f"叠加 {len(cap_meta)} 条字幕 + {len(clip_audio)} 条游戏原声 + "
              f"{len(audio_inputs)} 条音频叠加（含限幅器 −1 dBTP）")

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
    print(f"  字幕 {len(cap_meta)} 条 | 音频叠加 {len(audio_inputs)} 条（含 −1 dBTP 限幅）")
    tt = sorted({c["transition"]["type"] for c in edl["clips"] if c.get("transition")})
    print(f"  转场 {len([c for c in edl['clips'] if c.get('transition')])} 处"
          f"{('：' + '/'.join(tt) + '（近似渲染）') if tt else ''}")
    print("  ⚠️ 这是 ffmpeg 预览，不是剪映成片；正式导出仍须在剪映里人工完成")
    print("=" * 60)
    for t, png, size_px, center in cap_meta:
        print(f"    {t['id']}  {size_px}px  中心 {center:6.1f}px  {t['content']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
