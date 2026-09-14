# 来源索引（sources）

手法库里每条 L2 证据都指向这里的某个 `BV号`。**没有这条索引，"读自教程画面"就无法复核。**

本机素材位置：`参考视频/教学/`（该目录**不入版本控制** —— 属用户媒体，见 `.gitignore`）。
实测清单（时长/分辨率，L1）：`projects/game-001/research/tutorial-inventory.json`

> ⚠️ **抽查方法**：任何一条 L2 主张都可以这样复核 ——
> ```powershell
> .venv\Scripts\python.exe -c "import imageio_ffmpeg,subprocess;ff=imageio_ffmpeg.get_ffmpeg_exe();subprocess.run([ff,'-y','-ss','42','-i',r'参考视频\教学\BV1FJeRzZEtY.mp4','-frames:v','1','out.png'])"
> ```
> 然后把 `out.png` 交给 `read_image` 看。

---

## A. 瓦 / 无畏契约 专用（优先级最高）

| BV 号 | 标题 | 时长 | 主要教什么 | 覆盖在 |
|---|---|---|---|---|
| `BV1FJeRzZEtY` | 一分钟教你用剪映做出瓦超帅**击杀瞬间切刀**效果 | 63s | 曲线变速→**闪进**；特效搜「**交叉闪震**」当转场；0.1× | `kill-moment.md` |
| `BV11hdSYcENH` | 1分钟教你用剪映做出最简单的**曝光击杀特效** | 78s | 官方素材拖**黑场**；调节→基础；特效 黑光聚点/瞬间模糊 | `kill-moment.md` |
| `BV1HVe8zRE5m` | 一分钟教你用剪映做出瓦超帅**击杀卡片**效果 | 81s | 复制片段 + **蒙版**做 kill card；每段 3s；0.1× | `kill-moment.md`·`masks.md` |
| `BV1wyRmYDERv` | 三分钟教你用剪映公式化剪瓦**定格特效**（附樱花） | 183s | **定格**用法 + 回弹摇摆/晃动模糊；发光强度 40 | `kill-moment.md` |
| `BV1G1r6BuEsF` | 一分半教会你剪映做瓦区卡点大手子**左右闪白** | 99s | **白场/黑场**闪白；音频→基础 音量归零；0.5× | `kill-moment.md` |
| `BV1g2adz3EvS` | 50s教你用剪映做瓦**回弹万金油转场** | 47s | 回弹转场；「定格 右移6下」；0.1× | `transitions.md` |
| `BV1fEbK6xEaP` | ⚡『高能卡点/转场』我居然用18年的剪法剪瓦？！⚡ | 110s | **成片**（非 UI 录屏）：红闪、黑场、辉光；白闪实测 67/100/167ms | `transitions.md`·`kill-moment.md` |
| `BV16E3yzMEWW` | 一分半教你用剪映学会**瓦的三种主流调色** | 85s | 瓦画面调色口径 | `color.md` |
| `BV1We411m7vg` | 【无畏契约剪辑教学】**三步做出帅气的调色效果** | 231s | ⚠️ **实为 After Effects，不是剪映**（面板「插件信息/发光/阈值/混合模式」、图层「调整图层 1…5/预合成 1」、时间码 `0:00:02:12`）—— 只能当画面参考 | `color.md`（**仅取设计意图**） |
| `BV1qx5463Exr` | 【游戏剪辑教学】一分钟教会你无畏契约**音乐击杀卡点** | 67s | 音乐击杀卡点、素材对齐 | `beat-sync.md`·`hooks.md` |
| `BV1ue8y6XE2M` | 超有氛围感的**击杀结尾**教程来了 | 70s | 结尾氛围、黑色噪点素材、0.6s 段 | `hooks.md` |
| `BV1xQf3BWEEz` | 无畏契约帅气**五杀**剪辑教学 | 34s | 五杀；「二十倍速」；抠像大小 20 | `kill-moment.md`（**ACE 无差异化规则**） |
| `BV1o94y1a76h` | 【**AE**教学】如何让自己的视频击杀更有感觉！ | 290s | ⚠️ **AE 不是剪映** —— 只能取设计意图 | `hooks.md` |

## B. 剪映通用核心（L2 菜单路径主要来自这批）

| BV 号 | 标题 | 时长 | 主要教什么 | 覆盖在 |
|---|---|---|---|---|
| `BV19T4y1W7ct` | 【剪映教程】86-**深度讲解关键帧** | 692s | 关键帧系统 | `keyframes.md` |
| `BV18rrsBdEcD` | 【剪映教程】**内吸击杀抖动** | 149s | 关键帧 **三次方缓入** | `keyframes.md`·`kill-moment.md` |
| `BV1KFKz6MEmL` | 从零学剪映调色！**HSL / 色轮 / 曲线**保姆级教学 | **2189s** | 调色全套（最长的课） | `color.md` |
| `BV1PuSKBLEcS` | 三分钟带你快速学会剪映**蒙版**的基本用法 | 280s | 蒙版基础 | `masks.md` |
| `BV1sM4y1e7XL` | 手机剪映**蒙版的5种玩法** | 398s | 蒙版五种用法 | `masks.md` |
| `BV1hHGQ6AErb` | 1分钟学会**蒙版闪白卡点**（第338期） | 203s | 蒙版+闪白+卡点组合 | `masks.md`·`beat-sync.md` |
| `BV1xjh7zWEjh` | **推拉闪白转场**教程 | 81s | 推拉 + 闪白 | `transitions.md` |
| `BV1LguyzoEbz` | 剪辑教程 **大佬常用的几种转场** | 105s | 转场集合 | `transitions.md` |
| `BV1zz4y1N7Dp` | 【剪辑教程】剪映的**简单卡点+转场** | 157s | 卡点 + 转场 | `transitions.md`·`beat-sync.md` |
| `BV1EahSzYEc8` | **抽帧卡点**教程 | 50s | 抽帧卡点 | `beat-sync.md` |
| `BV1M9KB6GEQA` | 剪辑教程｜**Nocap低饱和滤镜卡点** | 116s | 滤镜 + 卡点 | `beat-sync.md`·`color.md` |
| `BV1QmpnznEZF` | **定格卡点**教程 | 44s | 定格卡点（手机版节拍工具） | `beat-sync.md` |
| `BV1QrN9eGECm` | 剪映视频**玩转字幕** | 571s | 字幕系统 | `captions.md` |
| `BV1gD421u75J` | 剪映**加字幕的三种方法** | 128s | 字幕入门三法 | `captions.md` |
| `BV1oX4y1U7Sh` | **击杀秀音乐转动转场**视频教程 | 224s | 音频→音效；0.1×；色度抠图 强度80/阴影0 | `audio.md`·`masks.md` |
| `BV1mZYyemE8B` | 【剪辑教学】全网最简单**炸麦/全损音质**教程 | 102s | 失真音质 | `audio.md` |
| `BV1rR4y1c7pc` | 教你制作游戏**击杀慢放**效果 | 70s | 击杀慢放 | `kill-moment.md` |
| `BV1J1Vc6BESA` | *（标题未记录）* 278s | 278s | **待补** | — |

## C. 原始研究报告（比本索引更细，但**未按本库的证据等级重编**）

| 文件 | 内容 |
|---|---|
| `projects/game-001/research/kill-moment-report.md` | 击杀瞬间报告 + 11 条未能验证 |
| `projects/game-001/research/_scratch/REPORT.md` | 菜单路径总表（L2 细节）、B站清单、来源质量警告 |
| `projects/game-001/research/format-research.md` | 形式/规格调研 |
| `projects/game-001/research/reference-films-notes.md` | **用户自己的参考成片**实测（切点密度 2.76–4.84/分） |
| `projects/game-001/research/effect-durations-tutorials.json` | 教程批次的定格/白闪/黑场实测 |
| `projects/game-001/research/killmoment2.json` | 成片批次的定格/白闪/黑场实测 |

---

## 引用来源时的三条纪律

1. **说清是"成片"还是"教程录屏"。** 两者用途完全不同：成片能量效果时长（L1），
   教程录屏才能读菜单路径（L2）。**在教程录屏上量效果时长会得到荒谬结果**（见 `kill-moment.md` §3）。
2. **标版本差异。** 剪映把「变速」在**顶级标签页**和**画面下的子页签**之间来回搬过，
   2025–2026 的教程两种都出现过。引用路径时注明"某版本下"。
   同样要区分**手机版**与**专业版** —— 大量「定格在哪」的答案是手机 App 路径。
3. **★ 先确认这条教程教的是不是剪映。** 本库已抓到**两次**标题写着"剪辑教学"、实际是
   **AE / PR** 的视频（`BV1We411m7vg`、`BV1o94y1a76h`）。
   识别特征：面板出现「插件信息 / 阈值 / 调整图层 / 预合成」、时间码形如 `0:00:02:12`。
   **AE/PR 的菜单路径一律不能进剪映的手法表**，只能取设计意图。
