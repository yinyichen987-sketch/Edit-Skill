# 环境与兼容性事实

本文件记录**实测**结论，不是推测。每条都标注了验证方式和日期。

验证日期：2026-09（首次搭建时）

---

## 本机环境

| 项目 | 实测值 |
|---|---|
| 剪映专业版 | **11.4.2.14459** |
| 草稿根目录 | `%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft` |
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

## 其他操作要点

- 生成草稿后，若剪映已在运行，需要**重启剪映或切换草稿**才会刷新列表（有缓存）。
- 生成草稿前最好**完全退出剪映**，避免写入冲突。
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
