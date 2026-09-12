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

## 其他操作要点

- 生成草稿后，若剪映已在运行，需要**重启剪映或切换草稿**才会刷新列表（有缓存）。
- 生成草稿前最好**完全退出剪映**，避免写入冲突。
- 草稿名重复时用 `create_draft(..., allow_replace=True)` 覆盖。
