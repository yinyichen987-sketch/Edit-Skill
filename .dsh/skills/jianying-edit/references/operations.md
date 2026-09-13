# 剪映操作知识库（JY-OPS）

本文件回答的是**操作层**问题：剪映专业版里某个功能叫什么、在哪、怎么用、做完怎么验证、
**以及这一步能不能由本 skill 自动化**。

它和另外两份文件的分工：

| 文件 | 管什么 | 能不能凭空写 |
|---|---|---|
| `edl-schema.md` | **决策**协议（EDL 怎么写） | 本项目自定义，可以 |
| `editing-rules.md` | **风格**规则（怎么切、切多快） | ❌ 必须从真实成片归纳 |
| **`operations.md`（本文）** | **操作**事实（软件怎么做） | ✅ 可验证，但必须标来源 |

---

## 0. 来源与标注约定

| 标记 | 含义 |
|---|---|
| ✅**实测** | 来自本机剪映 11.4.2.14459 的文件 / 程序字符串 / 配置，第一方证据 |
| 📄**卡片** | 仅来自 `knowledge-cards/jianying-agent-rag-cards-2026-09.md`（53 张，二手，未独立验证） |
| 🌐**网络** | 公开网页，来源已在 §7 列出 |
| ⚠️**存疑** | 来源互相冲突，或找不到任何来源 |

原始卡片（别的 AI 整理的 53 张）已原样收在本 skill 内：
`knowledge-cards/jianying-agent-rag-cards-2026-09.md`
（sha256 `ECCB1D56…3AE88`，57597 字节）。**卡片是学习材料，不是可信源**——本轮已经查出它
有一处高置信度的错误（见 §6.1）。

---

## 1. 本机实测事实（第一方）

| 项目 | 实测值 | 证据 |
|---|---|---|
| 版本 | 剪映专业版 **11.4.2.14459** | `E:\JianyingPro\JianyingProPacket.xml` → `<full_appver value="11.4.2.14459">` |
| 安装位置 | `E:\JianyingPro\`（**不在** C 盘） | 桌面快捷方式解析 |
| 用户数据 | `%LOCALAPPDATA%\JianyingPro\User Data\` | — |
| **快捷键方案文件** | `…\User Data\Config\Shortcut\*.json` | 见 §2 |
| 当前方案索引 | `keymapSettings` → `currentKeymapIndex=0` | 同上 |
| 视频轨上限 | `video_track_limit=40` | `Config\commonSetting.ini` |
| 默认图片时长 | 5 秒（`imageDefaultSecondDuration=5`） | `Config\globalSetting` |
| 预设帧率 | 30（`fpsNumerator=30`） | `Config\globalSetting` |
| **联动**默认范围 | `linkageEnableTypes=text, effect, sticker, filter, adjust, sound, tts` | `Config\globalSetting` |
| 自带跟踪模块 | 安装目录有 `Tracking.dll`；用户配置有 `Modules\camera_tracking.ini`、`complex_video_mask.ini`、`matting.ini` | ✅ 证明运动跟踪 / 平面跟踪 / 抠像 在本版本真实存在 |
| 界面文案表 | `Resources\po\zh-Hans.po`（1.4 MB gettext 表） | 功能名的**权威**来源 |

> 💡 **可复用的取证手法**：想确认「某功能在这个版本里到底存不存在」，不要靠网页，
> 去查 `Resources\po\zh-Hans.po` 和安装目录的 `VECreator.dll` 字符串表（命令 ID 全在里面），
> 或者直接读 `Config\Shortcut\*.json`。这些是软件自己的话，比任何教程都硬。

---

## 2. 快捷键：剪映有 **5 套键位方案**，不注明方案的表一律无效

这是本轮最重要的发现，它把卡片里那句反复出现的免责声明
（「快捷键可能被自定义；执行前以当前快捷键设置为准」）从**注意事项**升级成了**硬事实**。

### 2.1 实测证据

`…\User Data\Config\Shortcut\` 下有 5 个文件，本机首次运行（2026-09-12 21:39:11）一次性写入：

```
Custom1.json  Custom2.json  Custom3.json  Final Cut Pro X.json  Premiere Pro.json
```

- `Custom1/2/3.json` 内容**逐字节相同**，且**与 `Premiere Pro.json` 只差 `name` 字段**
  （5750 vs 5755 字节，差值 5 = `"Custom1"` 与 `"Premiere Pro"` 的长度差）。
  → 三个自定义槽位是从 **Premiere 风格**的键位播种出来的。
- `Final Cut Pro X.json` 是另一套。
- `keymapSettings` 记录 `currentKeymapIndex=0`。
- 安装目录 `VECreator.dll` 内含键位方案的**内置字符串表**，顺序为
  `Final Cut Pro X` → `Premiere Pro` → `Custom1` → `Custom2` → `Custom3`，
  其后紧跟两张内置键位表（第一张以 `Ctrl+B`/`Ctrl+Shift+B` 开头 = FCPX，第二张以 `Ctrl+K` 开头 = Premiere）。

### 2.2 结论（分事实与推断，别混）

- **事实**：剪映内置多套差异明显的键位方案，**同一功能在不同方案下是不同的键**（实测共 93 条命令，
  其中 **18 条**在两套内置方案间不一致）。
  最典型：**分割** = `Ctrl+K`（Premiere 方案） / `Ctrl+B`（Final Cut Pro X 方案）；
  **导出** = `Ctrl+M`（PR） / `Ctrl+E`（FCPX）。
- **无法确定的**：`currentKeymapIndex=0`，但**「索引 0 = 哪套方案」没有任何可读文件写出来**。
  两条线索互相矛盾，所以本文**不替它下结论**：
  - 线索 A（指向 FCPX）：`VECreator.dll` 里内置方案名表的顺序是
    `Final Cut Pro X → Premiere Pro → Custom1 → Custom2 → Custom3`。
  - 线索 B（指向 Premiere 风格）：本机 `Custom1/2/3.json` 的内容**等于 Premiere 方案**，
    而三个自定义槽位是首次运行时一次性播种的（5 个文件 mtime 精确到同一秒），
    如果当时生效的是 FCPX 方案，播种出来的应当是 FCPX 风格。
- **所以必须人工确认一次**：打开剪映 → 快捷键设置面板 → 看方案名。
  在此之前，**凡是要报给人快捷键的地方，一律带上方案名**；只报一个键就是错的。
  也可以跑脚本拿到全部原始事实（脚本刻意**不**替你断言当前方案）：

  ```powershell
  .venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\keymap_report.py
  .venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\keymap_report.py --compare
  ```

### 2.3 两套内置方案的完整差异（93 条命令里只有 18 条不同）

| 命令 ID | 含义 | Premiere / Custom | Final Cut Pro X |
|---|---|---|---|
| `cutoff` | **分割** | `Ctrl+K` | `Ctrl+B` |
| `batchCut` | 批量分割 | `Ctrl+Shift+K` | `Ctrl+Shift+B` |
| `exportVideo` | **导出** | `Ctrl+M` | `Ctrl+E` |
| `adsorb` | **自动吸附** | `S` | `N` |
| `mainTrackAdsorb` | **主轨磁吸** | `Shift+Backspace` | `P` |
| `linkage` | **联动** | `Ctrl+L` | `` ` `` / `·` |
| `preview` | 预览轴 | `Shift+P` | `S` |
| `switchToSelect` | 鼠标选择模式 | `V` | `A` |
| `switchToCut` | 鼠标分割模式 | `C` | `B` |
| `toggleSegmentVisibe` | 启用/停用片段 | `Shift+E` | `V` |
| `toggleVideoAudio` | 分离/还原音频 | `Alt+Shift+L` | `Ctrl+Shift+S` |
| `copySegAttribute` / `pasteSegAttribute` | 复制/粘贴片段属性 | `Ctrl+Alt+C/V` | `Ctrl+Shift+C/V` |
| `forwardSelect` / `backwardSelect` | 向前/向后选择 | `Shift+A` / `A` | `[` / `]` |
| `toggleFullscreen` | 全屏预览 | `` ` `` / `·` | `Ctrl+Shift+F` |
| `zoomIn` / `zoomOut` | 轨道缩放 | `+` / `-` | `Ctrl++` / `Ctrl+-` |

**两套方案完全一致**的部分（因此可以放心引用，其中就有卡片里最关键的那组）：

| 命令 ID | 含义 | 键 |
|---|---|---|
| `cutLeft` / `cutRight` | **向左裁剪 / 向右裁剪** | `Q` / `W` |
| `del` | 删除片段 | `Backspace` 或 `Del` |
| `undo` / `redo` | 撤销 / 重做 | `Ctrl+Z` / `Ctrl+Shift+Z` |
| `speedPlayBackward` / `speedPlayPause` / `speedPlayForward` | JKL 浏览 | `J` / `K` / `L` |
| `togglePlay` | 播放/暂停 | `Space` |
| `prevFrame` / `nextFrame` | 上一帧 / 下一帧 | `←` / `→` |
| `largePreFrame` / `largeNextFrame` | 大步进退 | `Shift+←` / `Shift+→` |
| `prevCutPoint` / `nextCutPoint` | 上一/下一分割点 | `↑` / `↓` |
| `locateFirstFrame` / `locateLastFrame` | 跳首/尾 | `Home` / `End` |
| `scrollTrackScale` | **时间线缩放** | `Ctrl+滚轮` |
| `scrollTrackH` / `scrollTrackV` | 时间线横/纵滚动 | `Alt+滚轮` / `滚轮` |
| `roughCutHead` / `roughCutTail` / `selectRangeStart/End` | 粗剪头尾 / 选区入出点 | `I` / `O` |
| `selectRangeBySegment` / `cancelRangeSelect` | 以片段定选区 / 取消 | `Shift+X` / `Alt+X` |
| `segmentMakeGroup` / `segmentRemoveGroup` | 创建/解除**组合** | `Ctrl+G` / `Ctrl+Shift+G` |
| `segmentCombination` / `segmentRemoveCombination` | 新建/解除**复合片段** | `Alt+G` / `Alt+Shift+G` |
| `activeSpeedControl` / `divideSpeedSegment` | 变速面板 / 曲线变速切分 | `Ctrl+R` / `Shift+B` |
| `addKeyframe` / `addBasicKeyframe` / `expandKeyframePanel` | 打关键帧 / 基础关键帧 / 面板 | `Shift+左键` / `Shift+Alt+K` / `Alt+K` |
| `mark` / `markWithAnotherColor` | 添加标记 / 另一种颜色 | `M` / `Alt+M` |
| `markBeat` | **手动踩点** | `Ctrl+J` |
| `smartExtend` | 智能扩展 | `Shift+L` |
| `segmentTrimGap` | 修剪间隙（≈闭合空隙） | `Ctrl+Right` |
| `importMedia` / `newProject` / `closeWindow` / `quit` | 导入 / 新建 / 关窗 / 退出 | `Ctrl+I` / `Ctrl+N` / `Ctrl+W` / `Ctrl+Q` |
| `subtitleSplit` / `subtitleNewLine` | 字幕拆分 / 折行 | `Enter` / `Ctrl+Enter` |
| `switchTab` | 切换素材面板 | `Tab` |
| `voiceUp` / `voiceDown` | 音量 +/− | `Ctrl+.` / `Ctrl+,` |
| `tracksHeightUp` / `tracksHeightDown` | 轨道高度 | `Ctrl+Alt+=` / `Ctrl+Alt+-` |
| `storeSingelFrame` | **定格** | **空 = 无默认快捷键** |
| `agentToggleInput` | 唤起 AI 输入 | `Alt+Space` |

> 另有「常按修饰键」型：`disableAlignment = Ctrl_hold`（拖动时按住 `Ctrl` 取消对齐）、
> `autoWrap = Alt+左键`、`customMattingSwitchAiEraser = Alt`。

上表可用脚本随时重生成（换机器 / 换版本后务必重跑）：

```powershell
.venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\keymap_report.py --compare
```

---

## 3. 功能清单：按**意图**索引（核心表）

用法：先看「意图」列找到你要干的事，再看「自动化」列决定这一步该不该交给人。
**「自动化」列写「EDL 可表达」的，一律走 EDL + `edl_to_draft.py`，不要去点界面。**

### 3.1 时间线基础

| 意图 | 剪映叫法 | 入口 / 快捷键 | 完成后验证 | 自动化 |
|---|---|---|---|---|
| 在播放头切开片段 | 分割 | `Ctrl+K`(PR) / `Ctrl+B`(FCPX) | 时间线出现两个相邻独立片段 | **EDL 可表达**（= 片段边界，根本不用切） |
| 批量切 | 批量分割 | `Ctrl+Shift+K` / `Ctrl+Shift+B` | 多处同时切开 | EDL 可表达 |
| 去掉片段左侧/右侧 | 向左裁剪 / 向右裁剪 | `Q` / `W` | 左/右无效内容消失，后续片段未被误裁 | **EDL 可表达**（= 改 `source_in` / `duration`） |
| 丢弃无效片段 | 删除 | `Del` / `Backspace` | 片段消失，上下游关系符合预期 | **EDL 可表达**（= 不写该片段） |
| 纠错 | 撤销 / 重做 | `Ctrl+Z` / `Ctrl+Shift+Z` | 恢复预期状态 | 不适用（脚本层无「误操作」） |
| 快速粗看长素材 | JKL 浏览 | `J`/`K`/`L`；连按 L 加速 ⚠️存疑 | 能快速定位目标区段 | 人不适用；分析器用 ffmpeg |
| 宏观/微观切换 | 时间线缩放 | `Ctrl+滚轮`、`+`/`-` | 切点看得清、整体结构也看得到 | 不适用 |
| 删完不留缝 | 主轨磁吸 | `Shift+Backspace`(PR) / `P`(FCPX)；关闭提示见 `po` `pc_turn_off_the_main_rail_magnet` | 主轨连续、无意外空白 | EDL 天然连续 |
| 消除片段间空隙 | **闭合空隙** ✅实测存在（命令 ID `closeGap` / `closeAllGap`） | 右键片段菜单，**无默认快捷键** | 空隙消失 | EDL 天然连续 |
| 多轨同步移动/删除 | 联动 | `Ctrl+L`(PR) / `` ` ``(FCPX)；作用范围见 §1 `linkageEnableTypes` | 字幕/B-roll/音频未漂移 | ⚠️ 只能人工 |
| 边缘对齐 | 自动吸附 | `S`(PR) / `N`(FCPX) | 素材首尾准确对齐 | EDL 用秒，不存在「吸附」 |

> ⚠️ **联动默认范围要当心**：本机 `linkageEnableTypes` 默认包含 `text, effect, sticker, filter, adjust,
> sound, tts`。也就是说**默认情况下字幕不跟随主轨画面**（字幕是独立轨），而**滤镜/调节/贴纸会跟随**。
> 这正好解释卡片 `JY-CORE-009` 的告诫「不要所有轨道无差别联动」。

### 3.2 AI 能力

| 意图 | 剪映叫法 | 证据 | 风险 | 自动化 |
|---|---|---|---|---|
| 自动拆镜头 | 智能镜头分割 | ✅ 命令 ID `cutClipBySceneEditDetection`；官网列名 | 可能切得过碎 | ⚠️ 人工（本 skill 用 ffmpeg 自适应峰值自行检测，见 `environment.md` 限制三） |
| 去口播废话 | 智能剪口播 | ✅ 命令 ID `scriptAiCut`；`po` 有「去水词模式」 | 误删关键语义 | ⚠️ 人工审核后执行 |
| 解说类粗剪 | 智能解说粗剪 | ✅ 命令 ID `scriptRoughCut` / `smartRoughCut` | 只能当候选 | ⚠️ 人工 |
| 自动上字幕 | 智能字幕 / 识别字幕 | ✅ 命令 ID `recognize` | 专有名词、同音字必错 | ⚠️ 人工校对（本 skill 的字幕是**手写 EDL**，不走 ASR） |
| 有稿对轴 | 文稿匹配 | 📄卡片 + 🌐网络 | 稿子与实际不符会错位 | ⚠️ 人工 |
| 找素材 | 智能搜索素材 | ✅ 官网列名 | 结果仍需人工确认 | 不适用 |

### 3.3 剪辑语言（这些是**手法**，不是按钮）

卡片 `JY-GRAM-001…005` 里的跳剪 / J-cut / L-cut / B-roll 覆盖 / 声音桥，在剪映里**没有对应按钮**，
它们是「用基本操作组合出来的结果」。落到本 skill 就是 EDL 里的写法：

| 手法 | 剪映里的做法 | 在 EDL 里怎么写 |
|---|---|---|
| 跳剪 Jump Cut | 同机位删中间段 | 两个 clip 同 `source`，`source_in` 故意跳跃 |
| L-cut（声音延续） | 上句音频轨比画面多留一段 | 音频片段 `duration` 大于对应视频片段 |
| J-cut（声音先行） | 下句音频提前入 | 下一段音频 `start` 早于其画面 `start` |
| B-roll 覆盖 | 上轨铺 B-roll，主说话声保留 | `role: "broll"` 的片段 + 主轨音频不删 |
| 声音桥 | 环境声/音乐跨切点 | 用 `audio_overlays` 或全局 BGM 轨拉长 |

> ⚠️ 这几条是**手法**，要不要用、用多密属于风格问题 → 归 `editing-rules.md` 管，
> 而那份文件必须从真实成片归纳，**不要在这里凭空定参数**。

### 3.4 画面、合成、调色、音频、字幕、画质

| 意图 | 剪映叫法 | 入口 / 快捷键 | 自动化（本 skill `edl_to_draft.py` 现状） |
|---|---|---|---|
| 属性随时间变化 | 关键帧 | `Shift+左键` / `Shift+Alt+K` | ✅ 已支持（`keyframes`） |
| 非线性变速 | 曲线变速 | `Ctrl+R` 面板 / `Shift+B` 切分 | ❌ 未表达（只有恒速 `speed`） |
| 整体加减速 | 常规变速 ⚠️存疑（`po` 中未单独命中该词） | `Ctrl+R` | ✅ 已支持（`speed`） |
| 静帧强调 | 定格 | 命令 `storeSingelFrame`，**无默认键** | ❌ 未表达 |
| 反向播放 | 倒放 | 命令 `reverse` | ❌ 未表达 |
| 局部显示 | 蒙版 | 线形/圆形/文字/钢笔 | ✅ 已支持（`mask`） |
| 分离主体 | 抠像 / 智能抠像 | ✅ `matting.ini`、官网列名 | ❌ 未表达 |
| 图形跟随目标 | 运动跟踪 / 平面跟踪 | ✅ `camera_tracking.ini`、`Tracking.dll` | ❌ 未表达 |
| 叠加光效纹理 | 混合模式 | ✅ `po` 命中 | ❌ 未表达 |
| 曝光/白平衡统一 | 基础校色 | — | ❌ 未表达（滤镜 `filter` 已支持） |
| 单色相调整 | HSL | ✅ 官网列名 | ❌ 未表达 |
| 精细曲线 | RGB 曲线 | ✅ 官网列名 | ❌ 未表达 |
| 多机位统一 | 色彩克隆/匹配 | `color_match_lv.mp4` 引导片 | ❌ 未表达 |
| 人声/背景分离 | 声音分离 / 人声分离 | ✅ 命令 `separationHumanAudio` | ❌ 未表达 |
| 去底噪 | 音频降噪 | ✅ 官网列名 | ❌ 未表达（`audio` 层无降噪字段） |
| 音量一致 | 响度统一 | ✅ `po` 命中；本机 `targetLoudnessIndex=0` | ❌ 未表达（只能逐片段 `volume`） |
| 平滑进出 | 淡入淡出 | 属性面板 | ✅ 已支持（`fade.in` / `fade.out`，音频同理） |
| 卡点 | 音乐节拍标记 | `Ctrl+J` 手动踩点 / 自动节拍 | ❌ 未表达（BGM 轨是整条铺） |
| 台词上屏 | 智能字幕 | `recognize` | ✅ 手写 `texts`（更可控） |
| 统一字幕样式 | 字幕版式 | 文本属性面板 | ✅ 部分（`style.size/bold/color/位置`） |
| 稳定手持 | 视频防抖 | ✅ `po` 命中 | ❌ 未表达 |
| 提升帧率 | AI 补帧 | ✅ 官网列名 | ❌ 未表达 |
| 低清修复 | 超清画质 | ✅ 官网列名 | ❌ 未表达 |

### 3.5 结构、性能、导出

| 意图 | 剪映叫法 | 证据 | 自动化 |
|---|---|---|---|
| 多机位切换 | 多机位（4/9 机位） | ✅ 命令 `newMultiCameraSegment`；官网列名 | ⚠️ 人工 |
| 一稿多版本 | 多时间线（上限 50） | ✅ 命令 `addMultiTimeline`；官网明确「新增上限可达50条」 | ⚠️ 人工 |
| 打包多个图层 | 复合片段 / 预合成 | ✅ 命令 `segmentCombination`，`Alt+G` | ❌ 未表达 |
| 编辑卡顿 | 代理 | 本机 `globalSetting` 只见 `streamingEditEnable` / `streamingEditUseCloudProxy`（云端代理）⚠️存疑 | ⚠️ 人工 |
| 定规格 | 分辨率/帧率/宽高比 | `canvas` 三字段 | ✅ 已支持（`canvas.width/height/fps`） |
| 出片 | 导出 | `Ctrl+M`(PR) / `Ctrl+E`(FCPX) | ❌ **不可能自动化**（见 `environment.md` 限制二） |

---

## 4. Agent 使用规则（把本文变成行为）

1. **先语义，再工具**（卡片 JY-AGENT-001）。识别意图 → 判断目标范围 → 选**最小且可逆**的操作 → 执行 → 验证。
2. **不确定时禁止猜快捷键**（卡片 JY-AGENT-002）——本轮已证明这条不只是「谨慎」：
   同一功能在不同键位方案下**真的**是不同的键。需要报快捷键给人时，**必须同时报方案名**；
   否则改用功能名 / 菜单语义描述（例如说「向右裁剪」而不是「按 W」）。
3. **粗剪与精剪分离**（卡片 JY-AGENT-003）：先结构 → 再字幕/音频 → 最后特效/调色/关键帧。
   落到本项目就是：**先把 EDL 的片段结构定死，再往上加转场/关键帧/字幕**，
   否则结构一改，包装全白做。
4. **能走 EDL 的绝不点界面**。§3 标「EDL 可表达」的，用 `edl_to_draft.py` 生成；
   标「未表达」的，写进交付说明让人在做人工验收时顺手做掉，**不要假装已经做了**。
5. **交付时必须说清哪些是人工步骤**：导出、需要试听/试看的音频处理、需要肉眼确认的抠像/跟踪。

---

## 5. 和 EDL 执行层的对应

```
意图层（本文 §3）          决策层（edl-schema.md）         执行层（edl_to_draft.py）
─────────────────────     ──────────────────────────      ────────────────────────
分割 / 裁剪 / 删除     →    clips[].source_in/duration  →   segment 的 source_timerange
转场                   →    clips[].transition          →   add_transition（须入轨前挂好）
常规变速               →    clips[].speed               →   speed（⚠️ 只传 source_timerange）
音量                   →    clips[].volume              →   volume
淡入淡出               →    fade.in / fade.out          →   add_fade
关键帧                 →    clips[].keyframes           →   add_keyframe
蒙版 / 滤镜            →    mask / filter               →   add_mask / add_filter
字幕                   →    texts[]                     →   文本 segment + style
BGM / 音效             →    audio.bgm_volume / audio_overlays → 独立音频轨
✗ 定格 / 倒放 / 曲线变速 / 抠像 / 跟踪 / 降噪 / 分离 / 多机位 / 复合片段 / 导出 → 人工
```

---

## 6. 卡片勘误与存疑清单

### 6.1 已证伪 / 需修正

| 卡片 | 卡片原话 | 实际情况 |
|---|---|---|
| **JY-CORE-001**（置信度标 high） | 「Ctrl+B（Mac 为 Command+B）」= 分割 | ❌ **不完整**。`Ctrl+B` 只属于内置的 **Final Cut Pro X** 键位方案；另一套内置方案（Premiere，也是本机 Custom 槽位的来源）里分割是 `Ctrl+K`。原文标 high 是错的，应为「方案相关」。 |
| JY-CORE-002 | 「多轨情况下注意是否联动」 | ✅ 成立，且本机默认联动范围是 `text, effect, sticker, filter, adjust, sound, tts`（§3.1） |

### 6.2 已确认（第一方）

`Q`/`W` = 向左/向右裁剪（**两套方案一致**，卡片 JY-CORE-004/005 正确）；
`Ctrl+Z` 撤销、`Del`/`Backspace` 删除、`JKL` 浏览、`Ctrl+滚轮` 时间线缩放、
主轨磁吸、自动吸附、联动、闭合空隙（命令存在）、复合片段（`Alt+G`）、
多时间线、多机位、智能镜头分割、智能剪口播、智能解说粗剪、智能字幕、文稿匹配、
人声分离、音频降噪、响度统一、AI 补帧、超清画质、视频防抖、抠像、蒙版、关键帧、
混合模式、HSL、RGB 曲线 —— **所有这些功能名在本机 11.4.2 里都真实存在**（§1 证据）。

### 6.3 存疑（不要当事实用）

| 项 | 状态 |
|---|---|
| 「连按 L 加速」 | 键位表只证明 `L` = 正向播放，**没有**证明连按加速 ⚠️ |
| 「常规变速」这个叫法 | `po` 里 `曲线变速` 命中 6 次，`常规变速` 未命中；可能是用户口语而非界面词 ⚠️ |
| 代理模式 | 本机配置只见 `streamingEdit*`（云端代理）；本地代理工作流未见证据 ⚠️ |
| Mac 端键位 | 完全未验证（本机只有 Windows） |
| 各功能的**菜单位置** | 只有功能名/命令 ID 级别证据，**具体在哪个菜单第几项没有验证** ⚠️ |

---

## 7. 来源

**第一方（本机实测，2026-09-13 取证）**

- `E:\JianyingPro\JianyingProPacket.xml`、`E:\JianyingPro\11.4.2.14459\Resources\po\zh-Hans.po`
- `…\11.4.2.14459\VECreator.dll`（命令 ID 串、内置键位表、内置方案名表）
- `%LOCALAPPDATA%\JianyingPro\User Data\Config\Shortcut\*.json`、`Config\keymapSettings`、
  `Config\globalSetting`、`Config\commonSetting.ini`

**网络（二手，仅作交叉印证）**

- 剪映官网功能名（蒙版/关键帧/调色/多机位/多时间线上限 50 条/AI 能力清单）：https://www.capcut.cn/
- 快捷键对照（CapCut 英文站改编，可靠性一般）：https://www.meowtool.com/capcut-keyboard-shortcuts/
- 剪映专业版快捷键（含 Premiere 习惯方案）：https://blog.csdn.net/qq_41176800/article/details/128229468
- 智能剪口播菜单位置：https://www.zhihu.com/tardis/zm/art/2080412875
- 文稿匹配入口：https://blog.csdn.net/ke_mo_duo/article/details/147855742
- 不能自动导出（剪映 ≤6 才支持）：https://github.com/GuanYixuan/pyJianYingDraft

**已失效的引用**（卡片 §8 里列的证据来源）

- `https://blog.iflux.art/posts/jianying-shortcuts` —— **域名已解析不了**（`getaddrinfo ENOTFOUND`）。
  卡片里 CORE-001/002/003/007/010、AGENT-001/002 全部引用了这一条，**该来源已不可核查**。
- 卡片反复引用的 B 站课程页 `bilibili.com/cheese/play/...`、抖音 `douyin.com/shipin/...`
  为付费/客户端内容，**无法作为可复核证据**。

> 结论：**卡片的「证据来源」栏基本不可核查**。它的价值在于把功能清单列全了，
> 而每一个事实都需要像本轮这样回到第一方去验。
