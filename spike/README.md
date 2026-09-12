# spike —— 兼容性验证记录

这里是一次性验证脚本和夹具，用来确认 pyJianYingDraft 0.3.0 能否驱动本机的剪映 11.4.2。
结论已固化到 `.dsh/skills/jianying-edit/references/environment.md`。

保留这些脚本是为了**将来剪映升级后可以重跑**，确认兼容性是否还在。

## 内容

| 文件 | 作用 |
|---|---|
| `make_test_draft.py` | 生成最小测试草稿 `DSH_SPIKE_TEST`（1 段视频 + 1 句字幕），验证写路径 |
| `read_existing_draft.py` | 尝试解析已有草稿，验证读路径（结论：加密，失败） |
| `sample-edl.json` | 示例 EDL，用于测试 `edl_to_draft.py` |
| `media/` | 测试夹具（**已被 gitignore**，用下方命令重建） |

## 重建夹具

`media/` 未纳入版本控制。需要时用自带的 ffmpeg 重新生成：

```powershell
$ff = (Resolve-Path ".venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe").Path
$m  = (Resolve-Path "spike\media").Path
New-Item -ItemType Directory -Force -Path $m | Out-Null

# 单镜头素材（带音轨 / 不带音轨）
& $ff -y -f lavfi -i "testsrc2=size=1080x1920:rate=30" -f lavfi -i "sine=frequency=440:sample_rate=44100" -t 6 -c:v libx264 -pix_fmt yuv420p -c:a aac "$m\test_a.mp4"
& $ff -y -f lavfi -i "testsrc2=size=1080x1920:rate=30" -t 5 -c:v libx264 -pix_fmt yuv420p "$m\test_b.mp4"

# 带硬切的多镜头夹具（用于验证切点检测）
& $ff -y -f lavfi -i "color=c=0x1E3A8A:s=1080x1920:d=3:r=30" -c:v libx264 -pix_fmt yuv420p "$m\shot1.mp4"
& $ff -y -f lavfi -i "color=c=0xB91C1C:s=1080x1920:d=2:r=30" -c:v libx264 -pix_fmt yuv420p "$m\shot2.mp4"
& $ff -y -f lavfi -i "testsrc2=s=1080x1920:d=4:r=30"           -c:v libx264 -pix_fmt yuv420p "$m\shot3.mp4"
@("shot1.mp4","shot2.mp4","shot3.mp4") | ForEach-Object { "file '$($m -replace '\\','/')/$_'" } |
  Set-Content "$m\concat.txt" -Encoding ASCII
& $ff -y -f concat -safe 0 -i "$m\concat.txt" -c copy "$m\test_film.mp4"
Remove-Item "$m\concat.txt"
```

> `test_film.mp4` 的 3s 处是深蓝→深红切换，场景分只有 5.47；5s 处是 23.05。
> 这个夹具专门用来验证自适应切点检测能否召回低分切点。

## 重跑验证

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe spike\make_test_draft.py
.venv\Scripts\python.exe spike\read_existing_draft.py
```

`make_test_draft.py` 会把草稿写进剪映草稿目录，需要**在剪映里人工确认能否打开**。
