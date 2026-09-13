# Edit Skill — 剪映剪辑 Skill

把原始素材剪成符合既定手法的**剪映（JianYing）草稿工程**的 DeepSeek Harness Skill。

## 这个 skill 做什么

```
原始素材 ──[探查]──→ 素材结构
参考成片 ──[分析]──→ 量化指标 ──[归纳]──→ 规则库 (references/editing-rules.md)
                                            │
                                    [决策] ─┘
                                            ↓
                                    EDL 剪辑决策 JSON   ← 核心资产
                                            ↓
                                    [edl_to_draft]
                                            ↓
                                    剪映草稿 → 人工审阅 → 人工导出
```

**定位是「自动生成粗剪草稿 + 可解释的决策记录」，不是「全自动出片」。**
剪映 7+ 没有可供自动化的导出控件，导出必须由人完成。

## 当前状态

| 部分 | 状态 |
|---|---|
| 环境与兼容性验证 | ✅ 完成，结论见 `references/environment.md` |
| EDL 协议规范 | ✅ 完成，见 `references/edl-schema.md` |
| 成片分析工具 | ✅ 可用并已验证 |
| EDL → 草稿工具 | ✅ 可用并已验证 |
| **剪辑规则库** | ⬜ **未填充** —— 需要用户提供有代表性的成片后才能归纳 |

> 规则不能凭空编造。在拿到参考成片之前，`editing-rules.md` 保持为空。

## 环境要求

已验证组合：剪映专业版 **11.4.2.14459** + Python 3.13 + pyJianYingDraft 0.3.0。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

ffmpeg 由 `imageio-ffmpeg` 自带，**无需系统安装**；也没有 ffprobe，媒体信息走 `pymediainfo`。

## 用法

```powershell
# 分析一条素材或成片
.venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\analyze_film.py <视频> --summary

# 校验 EDL（不生成草稿）
.venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\edl_to_draft.py edl.json --dry-run

# 生成剪映草稿（生成前请完全退出剪映）
.venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\edl_to_draft.py edl.json --name "项目名"
```

生成后需**重启剪映或切换草稿**才会在列表中看到（剪映有缓存）。

## 目录结构

```
.
├── .dsh/skills/jianying-edit/     # ← Skill 本体（DSH 自动发现）
│   ├── SKILL.md
│   ├── references/
│   │   ├── edl-schema.md          # EDL 协议（核心）
│   │   ├── environment.md         # 实测环境事实与已知陷阱
│   │   └── editing-rules.md       # 规则库（待填充）
│   └── scripts/
│       ├── analyze_film.py
│       └── edl_to_draft.py
├── spike/                          # 兼容性验证过程记录
├── requirements.txt
└── README.md
```

## 关键限制（重要）

1. **读不了已有草稿** —— 剪映 11.x 的 `draft_content.json` 是加密的，上游库出于合规不提供解密。
   风格反推改走「分析成片」路线。
2. **不能自动导出** —— 剪映 7+ 的限制，导出必须人工完成。
3. **固定阈值切点检测不可靠** —— ffmpeg `scdet` 以亮度差为主，等亮度换色会漏判（实测 5.47 vs 23.05）。
   分析器改用自适应峰值检测。

详见 `references/environment.md`。

## 已知陷阱

都是实际踩过的，会导致**草稿表面正常但内容全错**：

- **时间必须带单位后缀**：`tim(0.5)` 被当作 0.5 微秒取整成 0，必须写 `"0.5s"`。
- **转场必须在入轨前挂好**：`add_segment()` 只在入轨那一刻登记 `materials.transitions`。

详见 `references/edl-schema.md` 末尾。

## 迭代约定：**每轮训练后必须推送**（硬性要求）

**每完成一轮训练/迭代，把有价值的经验追加到 `docs/lessons.md`，然后提交并推送到 GitHub。
没推上去 = 这一轮没结束。**

远程仓库：<https://github.com/yinyichen987-sketch/Edit-Skill>（分支 `game-video`）

```powershell
# 1. 把本轮经验写进 docs/lessons.md（模板在该文件末尾）
# 2. 同步到 GitHub（提交 + 推送）
.\tools\sync.ps1 -Message "第 N 轮：<主题>"
```

`tools/sync.ps1` 会自动探测代理、暂存、提交、推送。它**先提交再推送** ——
推送失败时本轮成果仍留在本地，不会丢。

### 推送失败时的退出码

| 码 | 含义 | 怎么办 |
|---|---|---|
| `0` | 已推送 | 本轮结束 |
| `1` | 网络/代理问题 | 检查 FlClash 是否在跑（`127.0.0.1:10910`） |
| `3` | **被执行沙箱挡住**了 TLS（`SEC_E_NO_CREDENTIALS`） | **不是网络问题**，见下 |

### ⚠️ 本机实测：在 DSH 沙箱里 `git` 的 HTTPS 一律失败

默认沙箱下，**连 `git ls-remote` 都会挂**，报：

```
fatal: unable to access 'https://github.com/...': schannel: AcquireCredentialsHandle
failed: SEC_E_NO_CREDENTIALS (0x8009030E)
```

这是执行环境限制了 schannel/SSPI 的 TLS 凭据初始化，**跟代理、跟 GitHub 通不通无关**
（代理端口开着也照样挂）。所以在这一轮里跑推送，需要**以更宽权限（`danger-full-access`）重跑**，
或者人工在终端执行 `git push`。脚本现在会把这个情况单独认出来（退出码 3），不再误报成网络问题。

> 环境注意：本机访问 GitHub 的 HTTPS 需要代理（FlClash，`127.0.0.1:10910`），
> 已配置在本仓库的 `.git/config`。关掉代理后 `git push` 会失败，重开即可。

**什么算「有价值的经验」**（写进 `docs/lessons.md`）：

- 会重复踩的坑
- 改变了后续做法的判断
- 实测推翻了原本假设的结论

**什么不算**：流水账、一次性的调试过程、已经固化进 `references/` 的技术细节正文
（后者只留一句索引即可，避免两处维护）。

> 环境注意：本机访问 GitHub 的 HTTPS 需要代理（FlClash，`127.0.0.1:10910`），
> 已配置在本仓库的 `.git/config`。关掉代理后 `git push` 会失败，重开即可。
