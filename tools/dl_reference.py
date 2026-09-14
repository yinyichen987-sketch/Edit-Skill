"""下载参考视频（B站/YouTube 等）到工作区，供 `analyze_film.py` 反推剪辑手法。

## 为什么是"薄封装 yt-dlp"而不是自己写

用户问："找找有没有插件可以帮助下载视频，没有的话你自己写一个。"

**结论：不自己写。** 自己实现 B站 的下载链路要处理
**WBI 签名**（`w_rid`/`wts`，参数需按特定规则排序后 MD5）、`buvid` 指纹、
分段音视频流（DASH）分别下载再合流 —— 这些会随平台改动而失效，维护成本远高于收益。
`yt-dlp` 是这一领域事实标准，B站 支持成熟。所以**本脚本是它的薄封装**，
只解决三件本项目特有的事：

1. **`--print` 隐含 `--simulate` 的坑**：yt-dlp 里加了 `--print` 就**只打印不下载**，
   必须同时给 `--no-simulate`。本项目第一次用就踩了 —— 元数据打印得很漂亮，
   磁盘上却一个文件都没有。本脚本固定带上 `--no-simulate`。
2. **落盘位置统一**到工作区的 `参考视频/`（而不是当前目录），便于 `analyze_film.py` 批量读。
3. **下载完立刻体检**：打印时长/分辨率/帧率，并对"低分辨率重传稿"给出提示
   （B站 上不少高播放是 480p 重传，量字高/构图时会失真，需要按比例换算）。

## 用法

    .venv\\Scripts\\python.exe tools\\dl_reference.py <url> [<url> ...]
    .venv\\Scripts\\python.exe tools\\dl_reference.py --list urls.txt

## 依赖

    .venv\\Scripts\\python.exe -m pip install yt-dlp

⚠️ 安装时的两个沙箱坑（本项目实测）：
  · pip 的临时目录**必须在工作区内**（`TEMP`/`TMP` 指过来），否则
    `[Errno 13] Permission denied: ...\\Temp\\dsh-xxxx\\pip-unpack-...`；
  · 从 Python 里发 TLS 请求会被沙箱拦（`SSL: UNEXPECTED_EOF_WHILE_READING`），
    所以安装与下载都需要放宽到完整网络权限。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "参考视频"

# 优先取 1080p 以内的最佳画面 + 最佳音轨并合流；取不到就退回单文件。
FORMAT = "bv*[height<=1080]+ba/b[height<=1080]/b"


def ensure_ytdlp() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        print("[FAIL] 没装 yt-dlp。先装：")
        print("       .venv\\Scripts\\python.exe -m pip install yt-dlp")
        print("       （装之前先把 TEMP/TMP 指到工作区内，否则 pip 解包会被拒）")
        return False


def probe(path: Path) -> dict:
    try:
        from pymediainfo import MediaInfo
    except ImportError:
        return {}
    for t in MediaInfo.parse(str(path)).tracks:
        if t.track_type == "Video":
            return {"w": t.width, "h": t.height,
                    "dur": (t.duration or 0) / 1000.0,
                    "fps": t.frame_rate}
    return {}


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2

    urls: list[str] = []
    if args[0] == "--list":
        if len(args) < 2:
            print("[FAIL] --list 需要给一个文件路径")
            return 2
        f = Path(args[1])
        if not f.is_absolute():
            f = ROOT / f
        urls = [l.strip() for l in f.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.strip().startswith("#")]
    else:
        urls = args

    if not ensure_ytdlp():
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=== 下载 {len(urls)} 个参考视频 -> {OUT_DIR.relative_to(ROOT)} ===")
    rc = 0
    for i, u in enumerate(urls, 1):
        print(f"\n--- [{i}/{len(urls)}] {u}")
        cmd = [sys.executable, "-m", "yt_dlp",
               "--no-playlist", "--no-warnings",
               "--no-simulate",              # ★ 关键：不加这个，下面的 --print 会让它只打印不下载
               "--merge-output-format", "mp4",
               "-f", FORMAT,
               "-o", str(OUT_DIR / "%(id)s.%(ext)s"),
               "--print", "after_move:  已下载 %(id)s  %(duration)s秒  %(width)sx%(height)s",
               u]
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        for line in out.splitlines()[-4:]:
            print("   " + line)
        if p.returncode != 0:
            rc = 1
            continue

    print("\n=== 体检 ===")
    files = sorted(OUT_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    for f in files:
        info = probe(f)
        w, h = info.get("w", 0), info.get("h", 0)
        tag = ""
        if w and w < 1000:
            tag = ("  ⚠️ 低分辨率（多半是重传稿）—— 量字高/构图时需按比例换算到 1080，"
                   "结论精度会下降")
        print(f"  {f.name:22} {info.get('dur', 0):6.2f}s  {w}x{h}  {info.get('fps')}fps{tag}")
    print("\n下一步：.venv\\Scripts\\python.exe .dsh\\skills\\jianying-edit\\scripts\\"
          "analyze_film.py 参考视频\\<文件>.mp4 --summary")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
