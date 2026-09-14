# 环境与兼容性事实

本文件记录**实测**结论，不是推测。每条都标注了验证方式和日期。

验证日期：2026-09（首次搭建时）

---

## 本机环境

| 项目 | 实测值 |
|---|---|
| 剪映专业版 | **11.4.2.14459** |
| 安装位置 | `E:\JianyingPro\`（**不在 C 盘**；`JianyingProPacket.xml` 可直接读出完整版本号） |
| 草稿根目录 | `%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft` |
| 键位方案文件 | `%LOCALAPPDATA%\JianyingPro\User Data\Config\Shortcut\*.json`（实测 5 套） |
| Python | 3.13.14（venv 于 `<repo>/.venv`） |
| pyJianYingDraft | 0.3.0 |
| ffmpeg | 由 `imageio-ffmpeg` 0.6.0 提供（7.1），**无 ffprobe** |
| 媒体信息读取 | `pymediainfo` 7.0.1（因无 ffprobe） |
| Node | v24.21.0 |

---

## 能力矩阵

| 能力 | 状态 | 证据 |
|---|---|---|
| 生成草稿供剪映 11.4.2 打开 | ✅ **可用** | 人工实测：能打开、预览、导出 |
| Python 3.13 兼容 | ✅ | 库文档推荐 3.8/3.11，实测 3.13 正常 |
| 读取已有草稿 | ❌ **不可用** | 见下 |
| 自动导出 | ❌ **不可用** | 库文档：仅剪映 ≤6 支持 |

---

## 限制一：剪映 11.x 草稿是加密的

`draft_content.json` 与 `draft_meta_info.json` **都不是明文 JSON**：

```
大小 134,996 字节 | 前 24 字节: h6ggkxP3C55rB+JfZkCtgi17
DraftContentLoadFailed: 不是合法的明文 JSON
```

目录中还可见 `crypto_key_store.dat` / `crypto_key_store.dat.bak`。

### 上游立场

[pyJianYingDraft v0.2.7 发布说明](https://github.com/GuanYixuan/pyJianYingDraft/releases/tag/0.2.7) 原文：

> 本项目**不内置、不发布、不链接**任何针对第三方应用加密草稿格式的解密实现。
> 此前**关于内置实现的提案**已因项目治理和合规风险而**关闭**。

`DraftFolder(..., fallback_loader=...)` 只是**留给使用者的接口**，库本身不提供实现。

### 本项目的选择

**不接入解密。** 理由：属于绕过商业软件的技术保护措施，有合规风险，且剪映升级即失效。

替代方案：**分析导出的成片**（`scripts/analyze_film.py`）。信息量略少（拿不到未采用素材和
精确参数），但完全合法、不怕升级。

> 若将来确实需要读草稿：社区有 [wanfke/jy-draftc](https://github.com/wanfke/jy-draftc)（解密+回加密），
> 或在剪映 ≤6 上工作（明文草稿 + 自动导出）。这两条都需要使用者自行评估。

---

## 限制二：不能自动导出

剪映 7 及以上版本没有可供自动化的导出控件。**导出必须由人在剪映里完成。**

因此本 skill 的定位是「**自动生成粗剪草稿**」，而不是「全自动出片」。不要在流程设计里
假设可以无人值守地拿到成片。

---

## 限制三：ffmpeg 场景检测以亮度为主

实测：深蓝 `RGB(30,58,138)` → 深红 `RGB(185,28,28)` 的硬切，`scdet` 只给出 **5.47** 分，
而亮暗差异明显的切点给出 **23.05** 分。默认阈值 10 会**漏掉前者**。

后果：**固定阈值不可靠**。

`scripts/analyze_film.py` 的对策：`scdet=threshold=0` 全量采样所有帧的场景分，
再用自适应基线（中位数 + 标准差）做峰值检测，而不是依赖固定阈值。

---

## 限制四：生成的草稿文件比原生少

pyJianYingDraft 生成的草稿只有 2 个文件（`draft_content.json` / `draft_meta_info.json`），
而剪映原生草稿有 24+ 个条目（`root_meta_info.json`、`draft_virtual_store.json`、
`Timelines/`、`Resources/` 等）。

**实测结论：剪映 11.4.2 可以正常识别并打开这种精简草稿**，缺失文件由剪映首次保存时自行补齐。

---

## 草稿 JSON 的三个反直觉结构

校验或解析 `draft_content.json` 时必须知道这三条，否则会**误判"转场丢失"**或"文字为空"。
（由实际编写校验脚本时踩出，两个独立实现先后中招。）

### 1. 没有 `segment.transition` 字段

转场**不存在于片段上**，而是：

```
segment.extra_material_refs[]  ──指向──>  materials.transitions[]
```

因此只看 `segment.transition` 会得到"没有转场"的结论。**必须顺着 `extra_material_refs` 查。**

### 2. 文字内容不在 `segment.content`

文字在 `materials.texts[<material_id>].content`，而且**是再套一层的 JSON 字符串**：

```json
{"styles": [{"fill": {"content": {"solid": {"color": [1.0, 0.9, 0.2]}}}, ...}], "text": "实际文案"}
```

即 `content` 本身是个字符串，需要**二次 `json.loads`** 才能取到 `text`。

### 3. 转场挂在前序片段上

剪映把"进入第 n 段的转场"存储在**第 n−1 段**上。校验时的映射是：

```
draft.segments[j]  ←→  EDL.clips[j+1]      （不是同下标！）
```

**按同下标比对会误报失败**——而且如果同时只跑反例测试，这两个方向的误报会**互相掩盖**
（一边多报、一边少报），看起来"反例都能抓"。必须用**已知正确的正例**才能发现。

> 教训：反例能证明工具不漏报，**只有正例能证明工具不误报**。两者缺一，工具的可信度都是假的。

---

## 画布与构图：`clip.scale` / `clip.transform` 的真实语义（实测，有反直觉）

**这是横屏素材做竖屏成片时最容易整条错的地方**，而且错了以后"特效再多也救不回来"。

### `scale = 1.0` 不是"原始像素"，而是 **contain（等比装进画布）**

实测证据（不是从文档抄的）：把 **1280x720** 素材放进 **1080x1920** 画布、`scale=1.0`，
让剪映自己打开并回存草稿，再读它生成的 `draft_cover.jpg`：

| 项 | 实测 | contain 理论值 |
|---|---|---|
| 画面带 | **1080 x 608** | 1080 x 607.5 |
| 上黑边 | 656 px | (1920−607.5)/2 = 656.25 |
| 下黑边 | 656 px | 656.25 |

**结论**：`scale=1.0` = 等比缩放到完整装进画布。
所以"把 16:9 素材直接丢进 9:16 画布"= **上下各 656px、合计 2/3 的屏幕是纯黑**。
这类草稿在时间线上看着"有画面"，打开却是三明治黑边 —— 极易被误判成"字幕/特效没生效"。

**换算公式**（`band_h` = 期望的画面带像素高）：

```python
def band_scale(canvas_w, canvas_h, src_w, src_h, band_h):
    src_ar, canvas_ar = src_w / src_h, canvas_w / canvas_h
    base_h = canvas_w * src_h / src_w if src_ar >= canvas_ar else canvas_h
    return band_h / base_h          # scale_x = scale_y = 它（不等就变形）
```

`edl_to_draft.py` 里已内置同名函数 `band_scale()`，可直接调用。

### `transform_x / transform_y` 的单位是**半个画布宽/高**，正方向为**上/左**

```
y_px(距画面顶部) = H/2 − (H/2) · transform_y
```

**四个数交叉验证全部吻合**（跨两种画布，排除"只在一个画布上凑巧成立"）：

| 画布 | transform_y | 算出 y_px | 设计值 |
|---|---|---|---|
| 1920x1080 (横屏) | −0.7407 | 940.0 | 940 |
| 1920x1080 | −0.79 | 966.6 | 966.6 |
| 1080x1920 (竖屏) | +0.6875 | 300.0 | 300 |
| 1080x1920 | −0.5104 | 1450.0 | 1450 |

pyJianYingDraft 的 `ClipSettings` 文档（"单位为半个画布宽/高"）与此**独立吻合**。

### 竖屏构图的正解：模糊背景填充，而不是"裁满"

横屏 → 竖屏若要**铺满**必须裁掉约 **68%** 的宽度。对 FPS 游戏素材这等于同时砍掉
左上小地图与右上击杀播报 —— 而这两者往往正是**高光的证据**。所以正确做法是：

```json
{ "background_filling": { "type": "blur", "blur": 0.75 }, "clip": { "scale": 1.18 } }
```

- `background_filling` 用素材自身的放大模糊版填满画布，**黑边消失且零信息损失**。
- **`blur` 只有四档合法值**：`0.0625`(弱) / `0.375`(中) / `0.75`(强) / `1.0`(最强)。
  它**不是 0–1 连续值**，写 0.5 这种数不保证被认。
- 该效果**只对最底层视频轨的片段生效**（库文档明写）。
- 导出时它落在 `materials.canvases[]`（与画布物料同一个数组），**不是**独立物料键；
  按独立键去找会误判成"背景填充没写进去"。

---

## 免费验证通道：剪映回存的**草稿封面**

剪映成功打开一份草稿后，会在草稿目录里写出一整套文件：

```
draft_cover.jpg  draft_settings  key_value.json  Resources/  Timelines/
performance_opt_info.json  draft_content.json.bak  template-2.tmp
```

这给了两条**不依赖人工肉眼**的验证能力：

1. **"草稿到底有没有被打开/加载成功"** —— 只列目录即可判断：
   只有 `draft_content.json` + `draft_meta_info.json` ⇒ **从未被打开过**；
   出现 `draft_cover.jpg` / `Resources/` ⇒ 剪映**确实成功加载并回存**了。
2. **"剪映眼里这稿长什么样"** —— `draft_cover.jpg` 是**剪映自己渲染**的 1080x1920 图。
   把它读出来做像素分析，就能反推构图（本文件的 `scale=1.0=contain` 就是这样测出来的）。

**注意**：加载成功后剪映会用**加密**内容覆盖 `draft_content.json`（大小会大幅变化，
例如 34,631B → 18,820B；开头是可打印的 base64 样式乱码）。所以：

- **不要把"回存后 JSON 变小/解不开"当成内容丢失** —— 那是加密，不是丢数据。
- 回存会覆盖明文草稿 ⇒ **工作区里必须保留一份明文副本**（本 skill 的 `draft-out/` 就是干这个的），
  否则改不动了。
- `draft_settings` 是**明文**，其中 `real_edit_seconds` / `real_edit_keys` 能反映人工在剪映里
  实际编辑了多久、敲了几个键 —— 可用来判断"人到底有没有真的打开过"。

---

## 素材落在哪个 materials 键里（**同类误判已经发生三次**）

写草稿的检查脚本最容易犯的错，是**凭直觉猜物料落在哪个数组**。本项目已经因此误判三次：

| 物料 | **正确的键** | 曾经误判成 |
|---|---|---|
| 转场 | `materials.transitions[]`（经 `segment.extra_material_refs` 引用） | `segment.transition`（不存在） |
| 背景填充 | **`materials.canvases[]`**（与画布物料同一个数组） | 一个叫 `canvas_blur` 的独立键 |
| **滤镜** | **`materials.effects[]`**（`type: "filter"`） | `materials.video_effects[]` |

**规律**：`materials.effects[]` 是**滤镜 + 花字(`text_effect`) + 气泡(`text_shape`)** 共用的数组；
而**画面特效**才在 `materials.video_effects[]`（`type: "video_effect"` / `"face_effect"`）。
**"滤镜也算特效所以应该在 video_effects 里"是错的** —— 这个直觉正是第三次误判的来源
（当时结论是"滤镜没写进去"，实际 15/15 片段都正确引用了）。

> **教训**：判断"某物料有没有写进去"，不要猜键名，要**顺着 `segment.extra_material_refs` 反查**
> 它到底指向哪个数组里的哪一条。反向查一次，胜过猜三次。

---

## 音频：三个只在"量真峰值"时才会暴露的坑

### 1. `alimiter` 默认 `level=1`（auto level）会把限幅结果**再拉回去**

同一段素材，只差这一个参数：

| 设置 | 实测响度 | 实测真峰值 |
|---|---|---|
| `alimiter=limit=0.70:...`（默认 level） | −10.5 LUFS | **+0.6 dBFS（削顶）** |
| `alimiter=limit=0.70:...:level=0` | −13.4 LUFS | **−1.7 dBFS（正常）** |

**"加了限幅器"和"限幅生效"是两件事。** 必须用 `ebur128=peak=true` 量**真峰值**才算数；
只看"我挂了 limiter"会得到一段听起来更响、实际已经削顶的成片。
另注意 `limit` 是**线性值**不是 dB，且 AAC 编码后还有 intersample 过冲 —— 所以要留余量。

### 2. 逐段 AAC 编码的 padding 会累积成可见偏移

每段独立编码时，AAC 会把音频补齐到 1024 采样的整数倍（≈21ms）。15 段累积出 **+0.13s**，
末尾画面比 BGM 晚约 4 帧 —— 对卡点片是硬伤。**做法**：片段只出视频（`-an`），
音频在**最后一次 pass 里统一从素材取**并按 `adelay` 定位。

### 3. `fps` 滤镜会把帧数**向上取整**，逐段累积

0.46875s @30fps = 14.0625 帧 → 编出 15 帧 = 0.5s。15 段累积 **+0.18s**。
**做法**：视频用 `-frames:v floor(dur×fps)`（向下取整），音频 `apad=whole_dur` 补齐，
容器时长 = max(视频, 音频) 就严格等于 EDL 时长；最后再加输出侧 `-t` 兜底。

> 附带结论：**128 BPM 的拍点在 30fps 下本来就不落在帧边界上**（一拍 = 14.0625 帧）。
> 所以任何按拍切的片子都会有 ±1 帧的取整误差，这是正常的；要避免的是**误差逐段累积**。

---

## VIP 素材：**"写进草稿"≠"打开就能用"**

剪映的滤镜/特效/字体/花字都是**按 id 联网下载**的。本机
`User Data\Cache\effect\` 只缓存了 **483 个 effect_id**；而调研抽查的候选 VIP 素材
（哈苏蓝、暗调电影、像素故障、花屏故障…）在**全部 29,724 个 User Data 文件里 0 命中**。

⇒ **每一个没用过的 VIP 素材都需要剪映在首次打开时下载，下载超时会表现为"xx 加载失败"。**
而且剪映会把草稿**加密回存**，所以"先打开预热、再改草稿"这条路会丢掉明文母本。

**工程口径**：
- **交付默认走免费素材**（枚举里 `is_vip=False`），它们通常已缓存/秒下 —— 保证一次成功。
- VIP 作为**可选升级**列给人，由人在剪映里一键替换。
- 若确实要用新 VIP 素材，**预算一次"打开预热 + 关闭"**，然后用工作区里的**明文母本重新生成**
  （不要去改剪映目录里那份，它已被加密）。

枚举规模参考（本地库实测）：`FilterType` 1052（250 免费 / 802 VIP）、
`TransitionType` 453（130/323）、`VideoSceneEffectType` 1097（635/462）、
`FontType` 798（480/318）、`TextIntro` 145（67/78）、`TextLoopAnim` 93（41/52）；
`MaskType` **6 个全部免费**、`MixModeType` **10 个全部免费**（VIP 门槛不在蒙版/混合模式上）。

**另一条硬限制**：`AudioSegment` 只接受**本地文件路径**，导出时 `type` 硬编码为
`extract_music`、`category_name: "local"` —— **剪映的曲库/音效库无法程序化引用**。
所以 BGM 与音效要么本地合成，要么人工在剪映里挂。

## ★★★ 最重要的一条：剪映 11.x 是**多时间线**结构 —— 已打开的草稿**覆盖外层文件无效**

这是本项目排查最久、代价最大的坑，**它让"我明明改了、你打开却还是旧的"反复发生**。

### 机制（实测）

草稿**第一次**被剪映打开之后，目录里会多出：

```
<草稿名>/
├── draft_content.json                  ← 你写的那份（外层）
├── draft_meta_info.json
├── timeline_layout.json                ← {"activeTimeline":"91E08AC5-…", "dockItems":[…]}
└── Timelines/
    └── 91E08AC5-22FB-47e2-9AA0-7DC300FAEA2B/     ← **真正的活动时间线**
        ├── draft_content.json          ← ★ 剪映之后只读这一份
        ├── draft_content.json.bak
        ├── template.tmp / template-2.tmp
        └── common_attachment/…
```

`timeline_layout.json` 的 `activeTimeline` 指名哪条时间线是活动的。**剪映此后只认
`Timelines/<UUID>/draft_content.json`**；外层那份会被它回存（并加密），你的改动被彻底忽略。

### 症状对照（全部真实发生过）

| 现象 | 真相 |
|---|---|
| 第一版草稿用户能看到 | 那时还没有 `Timelines/`，剪映读的是外层文件 |
| 之后每次改都说"已交付"，用户打开还是旧的 | 内容早已搬进 `Timelines/`，外层改动无效 |
| 用户报"还是 15 秒" | 同上（把 15s 改成 30s 的那次也在其中） |
| 剪映目录里那份**变成密文**、修改时间**晚于**我的拷贝 | 剪映回存了它 `Timelines/` 里的版本，覆盖外层 |

> ⚠️ 我一度把原因只归结为"剪映开着造成写入冲突"。**那只是次要因素** ——
> 即使剪映关闭，只写外层文件也**不会**生效。必须按下面的协议交付。

### 正确的交付协议

1. **每次都交付到一个全新的草稿名**，例如 `瓦集锦_B站_v1` → 下一版 `…_v2`。
   新草稿没有 `Timelines/`，剪映首次打开读的就是你写的明文外层文件。
2. **不要试图原地更新**一个已被剪映打开过的草稿。
3. 拷贝时**剪映应处于关闭状态**（避免它用内存里的版本回存）。
4. **自检**（拷完立刻做，不要凭感觉宣称"已交付"）：
   - 目标草稿目录里**不存在** `Timelines/` 与 `timeline_layout.json`；
   - `draft_content.json` 是**明文**（首字节 `{`）；
   - 它的修改时间**不晚于**你的拷贝时间；
   - 顶层 `duration` 与各片段之和一致。
5. **绝不手动删除草稿文件夹** —— 见下。

### 连带教训：不要手动删草稿文件夹

剪映有一份草稿注册表 `<草稿根>/root_meta_info.json`（明文，含 `all_draft_store[]` 与
`draft_ids`）。**删掉文件夹而不更新注册表，剪映会报"草稿箱损坏"**（本项目已发生一次）。
要删草稿请在**剪映界面里删**；若已误删，重启剪映通常会让它自己重写注册表恢复一致
（实测重启后注册表条目与文件夹重新对上、报错消失），但不要依赖这一点。

### 另一条同类教训：总结性元数据要实算

EDL 的 `target_duration_s` 一度写死 `15.0`，取消时长限制后没跟着改 ——
于是排查"为什么还是 15 秒"时，那个字段与实际（30.0s）矛盾，**把排查方向带偏**。
凡"总结性元数据"都应从片段**实算**，不要手写常量。

---

## ⚠️ 拷草稿进剪映目录前**必须完全退出剪映** —— 否则你的稿会被它静默覆盖

这条以前在下面只写成"最好退出，避免写入冲突"，语气太软。**它是硬性前提**，
本项目已经因此真实翻车一次：

**现象**：把改好的 30.000s 草稿拷进剪映目录，用户打开剪映却"还是 15 秒"。

**取证**（全部可复现）：
- 工作区母本 `draft-out/GAME_MONT_LS/draft_content.json` → `duration=30000000`（30.0s）✓
- 预览 `montage_preview.mp4` → 实测 30.00s ✓
- **剪映目录里那份** → 91,492B、**密文**、修改时间比我的拷贝**更晚**
  （但**真正的根因是上文的「多时间线结构」**，不是剪映开着本身）
- `Get-Process JianyingPro` → **剪映正在运行**

⇒ 剪映把内存里的旧版本回存，**覆盖了我刚拷进去的新稿**。而且它写回的是密文，
所以事后连"里面到底是哪一版"都验不了 —— **这个故障没有任何报错**。

**正确的交付顺序**（不可颠倒）：

1. **先让用户完全退出剪映**（含托盘/后台进程，`Get-Process JianyingPro` 应为空）
2. 再拷 `draft_content.json` + `draft_meta_info.json`
3. 用户重新打开剪映 → 列表刷新、看到的才是新稿

**自检**：拷完不要立刻宣称"已交付"，而是**核对剪映目录里那份的修改时间**
是否**晚于**你的拷贝时间；若更晚且变成密文，就是被覆盖了。

**顺带一条同类教训**：EDL 里的 `target_duration_s` 一度写死 `15.0`，
取消时长限制后没跟着改 —— 于是排查"为什么还是 15 秒"时，
那个字段和实际（30.0s）矛盾，**把排查方向带偏**。
凡"总结性元数据"都应当**从片段实算**，不要手写常量。

---

## 其他操作要点

- 生成草稿后，若剪映已在运行，需要**重启剪映或切换草稿**才会刷新列表（有缓存）。
- ⚠️ **拷草稿进剪映目录前必须完全退出剪映** —— 这是硬性前提，不是建议。
  剪映运行时会把内存里的旧版本回存、**静默覆盖**你刚拷进去的新稿（本项目已真实翻车一次，
  详见上文「拷草稿进剪映目录前必须完全退出剪映」一节）。
- 草稿名重复时用 `create_draft(..., allow_replace=True)` 覆盖。
- **转场是"重叠"不是"额外占时"**：`start(n) = start(n−1) + duration(n−1)`，相邻片段零间隙。
  若按"额外占时"建模留出转场时长，那段空隙**在时间线上没有素材 → 每处转场都闪黑**，
  违反 `no-black-frame`，且 `Σ duration ≠ end`。
  自检口径：**若 `Σ duration < end`，就一定有黑洞。**

---

## 环境陷阱：Windows GBK 控制台无法打印部分 Unicode 字符

在 Windows 默认控制台（代码页 GBK）下，Python 脚本打印 `⊂`（U+2282）等字符会抛：

```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2282' in position 24
```

**后果比"打印失败"更严重**：脚本会在**收尾汇总之前**崩溃，
于是**拿不到最终结论、也不能当 pass/fail 门禁用**——它的"绿"可能来自崩溃前的中途退出。

### 更危险的一层：崩溃的退出码与"检查未通过"的退出码撞车

实测：Python 异常终止的退出码是 **1**，而脚本自定义的"审计发现异常"退出码**往往也是 1**。
后果是**双向误判**：

- 崩溃 → 被读成"审计未通过"（以为查出了问题，实际什么都没查到）
- 真正的"审计未通过" → 被读成崩溃（以为工具坏了，实际它正确报了问题）

**约定：退出码语义必须显式分离**

| 码 | 含义 |
|---|---|
| `0` | 通过 |
| `1` | 审计发现异常（**结论有效**） |
| `2` | 用法/环境错误（**结论无效**） |

并把崩溃路径彻底消除（`errors="replace"`），使 `1` 只可能来自真实的审计结论。

### 一个反复出现的自欺：被污染的环境

用 `PYTHONIOENCODING=utf-8` 测过就以为"已修复"——**那次是环境变量掩盖了问题**。
本陷阱必须在**默认环境**（不设任何编码变量）下验证，否则"修复通过"只说明那个 shell 里成立。

**约定：本 skill 下所有 CLI 脚本必须在 `main()` 开头加一行**

```python
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass
```

**这条是环境级陷阱，不是个别脚本的疏漏**：同一条命令打印同一行，不同人写都会崩在同一个字符上。
新增任何带输出的脚本时先加这一行，再写别的。
**并且要全量检查同类脚本**——只修暴露出来的那一个，会把同一颗雷留在别的门禁脚本里。


## 推送：网络环境会变，别把代理写死

本仓库远程是 GitHub，而本机网络**时而需要本地代理（FlClash 127.0.0.1:10910）、时而直连可通**。
把代理写进 repo-local 配置后，代理一关推送就报
Failed to connect to 127.0.0.1 port 10910（本项目已发生一次）。

**改用 	ools/push.ps1**：它按「直连 → 本地代理」依次尝试，每次都显式覆盖 http.proxy，
两种环境都能推。提交信息含多行或中文标点时**用 -MessageFile 而不是 -Message** ——
-m … 里的中文引号（“”）会被 PowerShell 当成字符串结束符，把消息截断并让 git 报 pathspec 错误
（本项目已发生一次）。

---

## Windows PowerShell 脚本：**含中文的 .ps1 必须带 UTF-8 BOM**

Windows PowerShell 5.1 读取**无 BOM** 的 .ps1 时按 **ANSI(GBK)** 解码，
于是文件里的中文注释/字符串全变乱码，并引发一堆莫名其妙的解析错误：

`
Write-Host "[i] 鍒嗘敮 "
Missing closing '}' in statement block ...
`

**约定**：本仓库新增任何含中文的 .ps1，一律用 encoding="utf-8-sig" 写入（带 BOM）。

**⚠️ 而 `edit` 工具会把 BOM 吃掉**（2026-09-13 实测）：用通用文本编辑器改完这两个脚本后，
BOM 就没了，脚本随即报一串看似无关的 `Missing closing '}' in statement block`
（UTF-8 中文被按 ANSI 解码后吃掉了引号/花括号）。**所以改完 .ps1 必须复检 BOM，缺了就补：**

```powershell
$b = [System.IO.File]::ReadAllBytes($f)
if (-not ($b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)) {
    [System.IO.File]::WriteAllBytes($f, [byte[]](0xEF,0xBB,0xBF) + $b)
}
```

改完再过一遍解析器（比肉眼可靠）：

```powershell
$err = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$err)
if ($err) { $err | ForEach-Object { $_.Message } }   # 有输出就是有语法错误
```
	ools/push.ps1、	ools/sync.ps1 都已带 BOM；自检一行：

`powershell
[System.IO.File]::ReadAllBytes('tools/push.ps1')[0..2] -join ','   # 应为 239,187,191
`

**另一条**：在这个 harness 里 pwsh 命令**不在 PATH 上**（当前 shell 本身就是 PowerShell），
所以要直接调用脚本本体 & .\tools\push.ps1 ...，不要写 pwsh -File ...。\n
## 装 Python 包 / 下载参考视频：两个沙箱坑（本项目实测）

### 1. pip 的临时目录必须在**工作区内**
pip install 会往 %TEMP% 解包，而沙箱拒写那里，报：

`
ERROR: Could not install packages due to an OSError:
[Errno 13] Permission denied: 'C:\\Users\\...\\Temp\\dsh-xxxx\\pip-unpack-...\\xxx.whl.metadata'
`

**先看 Collecting <包名> 是否出现** —— 出现了就说明**网络是通的、包已下好**，
只是解包被拒（别误判成网络问题）。修法：把 TEMP/TMP 指到工作区内再装。

### 2. 从 Python 里发 TLS 请求会被拦
urllib 报 ssl.SSLEOFError: UNEXPECTED_EOF_WHILE_READING。安装与下载都需要放宽权限。
（pip 自身能走通，是因为它用 vendored 的 urllib3/certifi。）

### 3. 下载视频：**薄封装 yt-dlp，不要自己写**
自己实现 B站 链路要处理 **WBI 签名**（w_rid/wts）、uvid 指纹、DASH 分段合流 ——
会随平台改动失效。用 	ools/dl_reference.py（yt-dlp 的薄封装）。

**⚠️ yt-dlp 的 --print 隐含 --simulate**：加了 --print 就**只打印不下载**，
必须同时给 --no-simulate。本项目第一次用就踩了 —— 元数据打印得很漂亮，磁盘上却一个文件都没有。

### 4. `git` 的 HTTPS 在默认沙箱下**一律失败**（不是网络问题）

默认沙箱模式下，**连只读的 `git ls-remote` 都会挂**：

```
fatal: unable to access 'https://github.com/...': schannel: AcquireCredentialsHandle
failed: SEC_E_NO_CREDENTIALS (0x8009030E)
```

这是执行环境限制了 schannel/SSPI 的 TLS 凭据初始化，**与代理、与 GitHub 可达性无关** ——
实测代理端口 `127.0.0.1:10910` 明明开着，照样报这个错；而以 `danger-full-access` 重跑，
同一条命令立刻推送成功。

**约定**：

- `tools/sync.ps1` / `tools/push.ps1` 都要能**认出这个错误**（退出码 **3**），
  不要把 `SEC_E_NO_CREDENTIALS` 误报成「检查代理/凭据」——那会把排查方向带偏一轮。
- 脚本必须**先提交再推送**：推送被沙箱挡住时，本轮成果仍留在本地。
- ⚠️ 这两个脚本开头都是 `$ErrorActionPreference = 'Stop'`，而 git 把 SSL 错误写到 **stderr**；
  用 `2>&1` 捕获时 PowerShell 会把它升级成**终止性错误**，脚本在诊断代码之前就挂了。
  捕获原生命令输出前必须临时切回 `Continue`（本项目实测踩过）。

### 5. 本机唯一能过 HTTPS 的通道是 **Node.js**

2026-09-13 实测，同一台机器同一时刻：

| 通道 | 结果 |
|---|---|
| PowerShell `Invoke-WebRequest` / `curl.exe` / .NET `HttpClient` | ❌ `schannel: SEC_E_NO_CREDENTIALS` |
| Python `urllib` / `requests` | ❌ `SSL: UNEXPECTED_EOF_WHILE_READING` |
| 明文 **HTTP** | ✅ 能过 |
| **Node.js v24** | ✅ **能过**（自带 OpenSSL，不走 schannel） |

所以本仓库留了一组兜底脚本在 **`tools/web/`**（`_fetch.mjs` / `_search.mjs` / `_probe.mjs` /
`_bili.mjs`），用法与可达主机清单见 `tools/web/README.md`。

**可达性**：bilibili / zhihu / baidu / capcut.cn / liquipedia / riotgames ✅；
**youtube / reddit / google / wikipedia ❌ 连接超时**。
并且**没有可用的通用搜索引擎**（Bing 只回导航类头部结果，DDG/SearX 不可达）。

> **结论：本机「上网查资料」≈「搜 B站 + 直接猜 URL」。**
> 视频素材反而是最稳的一条路：`yt-dlp` 不需要浏览器，
> `tools/dl_reference.py` 在**默认沙箱**下就能搜 B站 并下载（实测通过）。

参考：视频侧的完整链路口径见 `references/kill-extraction.md` §8。

> 与推送无关但也属于同一类：`pip` 的 `%TEMP%` 与 Python 自己的 TLS 请求同样被沙箱拦，
> 见上面 1、2 两条。**遇到「像网络问题」的失败，先想到沙箱。**

---

## 关键位方案：**剪映的快捷键不是唯一值**（2026-09-13 实测）

这条推翻了「剪映的 XX 快捷键是什么」这类问题的**提问方式**。

`…\User Data\Config\Shortcut\` 下有 **5 个键位方案 JSON**，本机首次运行
（2026-09-12 21:39:11）一次性写入，mtime 精确到同一秒：

```
Custom1.json  Custom2.json  Custom3.json  Final Cut Pro X.json  Premiere Pro.json
```

实测结果：

1. **Custom1/2/3 三份内容完全相同**，且与 `Premiere Pro.json` **只差 `name` 字段**
   （5750 vs 5755 字节，差值恰为两个 `name` 字符串的长度差）。→ 自定义槽位是从 Premiere 风格播种的。
2. 两套内置方案共 **93 条** 命令，其中 **18 条**键位不同。最要命的差异：

   | 命令 | Final Cut Pro X | Premiere Pro / Custom1-3 |
   |---|---|---|
   | 分割 `cutoff` | **Ctrl+B** | **Ctrl+K** |
   | 导出 `exportVideo` | **Ctrl+E** | **Ctrl+M** |
   | 主轨磁吸 `mainTrackAdsorb` | P | Shift+Backspace |
   | 自动吸附 `adsorb` | N | S |
   | 联动 `linkage` | `` ` `` | Ctrl+L |

3. `Config\keymapSettings` 只写了 `currentKeymapIndex=0`，**「索引→方案名」没有任何可读文件**。
   两条线索还互相矛盾（`VECreator.dll` 的字符串表顺序是 FCPX 在前；
   但按「自定义槽位从当前方案播种」推断当前应当是 Premiere 风格）。
   **结论：不要推断，去界面确认一次。**
4. 与本项目强相关的**稳定**键位（所有方案一致，可放心写进文档）：
   `Q`/`W` = 向左/向右裁剪、`Del`/`Backspace` = 删除、`Ctrl+Z` = 撤销、
   `J`/`K`/`L` = 反向/暂停/正向、`Ctrl+滚轮` = 时间线缩放、`Space` = 播放暂停、
   `I`/`O` = 入点/出点、`M` = 标记、`Ctrl+J` = 手动踩点。
   （**定格** `storeSingelFrame` 在所有方案里都是空 —— 它没有默认快捷键。）

**约定**：以后凡是要写「剪映快捷键」，必须写成「功能名（方案名：键）」，
或者干脆只写功能名。核查工具：`scripts/keymap_report.py`。

> 取证手法：判断「某功能在这个版本里存不存在」，**不要搜网页**，去读剪映自己的文件 ——
> `Resources\po\zh-Hans.po`（界面文案表）、`VECreator.dll`（命令 ID 与内置键位表）、
> `Config\Shortcut\*.json`。第一方证据能直接推翻二手教程。
> 本轮就是靠这个方法查出了知识卡片里一条**标着 high 置信度的错误**（见 `operations.md` §6.1）。
