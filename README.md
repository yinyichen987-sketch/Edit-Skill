# Edit Skill — 剪映剪辑 Skill

把原始素材剪成符合既定手法的**剪映（JianYing）草稿工程**，并沉淀**可复核的剪辑知识**的 DeepSeek Harness Skill。

**定位是「自动生成粗剪草稿 + 可解释的决策记录」，不是「全自动出片」** —— 剪映 7+ 没有可自动化的导出控件，导出必须由人完成。

---

## ★ 先读这里（入口导航）

**新对话请按这张表找东西，不要重新推导。**

| 你想干什么 | 读哪个文件 |
|---|---|
| 写/校验/生成一个剪映草稿 | `.dsh/skills/jianying-edit/SKILL.md`（工作流）+ `references/edl-schema.md`（EDL 协议） |
| 知道某个剪映功能叫什么、在哪、**能不能自动生成** | `references/operations.md` |
| 知道**某个效果怎么做出来**（菜单路径/参数/时长/坑） | `references/techniques/README.md`（索引）→ 对应专题 |
| 查某个说法的**来源与证据等级** | `references/techniques/sources.md` |
| 遥控剪映界面时按什么键 | 跑 `scripts/keymap_report.py`（**不要背快捷键，见下**） |
| 搞清楚击杀帧怎么提取、坑在哪 | `references/kill-extraction.md` |
| 环境/沙箱/网络/编码踩过的坑 | `references/environment.md` |
| 本项目的**风格**规则（怎么切、切多快） | `references/editing-rules.md`（⚠️ **仍为空**，见下） |
| 历轮训练学到了什么、为什么这么决定 | `docs/lessons.md`（按轮次倒序读最后几轮） |

### 三类知识的边界（很容易搞混，务必分清）

| 文件 | 管什么 | 能不能凭空写 |
|---|---|---|
| `editing-rules.md` | **风格**：你自己的片子怎么切、节奏档位 | ❌ **必须从用户真实成片归纳** |
| `operations.md` | **操作**：某功能叫什么、在哪、能否自动化 | ✅ 标来源即可 |
| `techniques/` | **手法**：做出某个效果的做法与参数 | ✅ 但**必须带证据等级 L1–L4** |

> **证据等级**：**L1** 本机逐帧/逐像素实测 · **L2** 读自教程里的剪映 UI · **L3** 二手 · **L4** 本项目策略。
> **没有等级标注的数字，不许写进 EDL 或规则。** 本项目已抓到多个「零来源」的流传数字
> （「闪白 0.1 秒」「cut 后 3 帧」「变速 0.5 秒前开始」）—— 见 `techniques/kill-moment.md` §4。

---

## 当前状态（截至第 5 轮）

| 部分 | 状态 |
|---|---|
| 环境与兼容性验证 | ✅ 见 `references/environment.md` |
| EDL 协议规范 | ✅ 见 `references/edl-schema.md` |
| 成片分析工具 | ✅ `scripts/analyze_film.py` |
| EDL → 草稿工具 | ✅ `scripts/edl_to_draft.py` |
| **操作知识库** | ✅ `references/operations.md`（功能名/入口/**能否自动化** + 键位方案实测） |
| **手法库** | ✅ `references/techniques/`（11 份：击杀瞬间/转场/卡点/调色/蒙版/关键帧/字幕/开场/音频 + 索引 + 来源） |
| **击杀帧提取校准** | ✅ `references/kill-extraction.md`（含一处**实证的标定错误**） |
| 网络取证工具 | ✅ `tools/web/`（本机唯一能过 HTTPS 的通道，见下） + `tools/dl_reference.py` |
| **剪辑规则库（风格）** | ⬜ **仍为空** —— 需要用户提供有代表性的成片后才能归纳 |

> **规则不能凭空编造。** 在拿到参考成片之前，`editing-rules.md` 保持为空。
> 第 4–5 轮已经把**手法**（怎么做）和**操作**（在哪做）填起来了，但**风格**（切成什么样）依然只能等成片。

---

## 目录结构

```
.
├── .dsh/skills/jianying-edit/          # ← Skill 本体（DSH 自动发现）
│   ├── SKILL.md                        # 使命 / 工作流 / 硬约束
│   ├── references/
│   │   ├── edl-schema.md               # ★ EDL 决策协议（核心）
│   │   ├── operations.md               # ★ 操作知识库（功能名/入口/能否自动化）
│   │   ├── kill-extraction.md          # ★ 击杀帧提取的标定与校准
│   │   ├── techniques/                 # ★ 手法库（证据等级 L1–L4）
│   │   │   ├── README.md               #   索引 + 等级约定
│   │   │   ├── sources.md              #   来源索引（31 条教程 → 覆盖在哪）
│   │   │   ├── kill-moment.md  transitions.md  beat-sync.md
│   │   │   ├── color.md  masks.md  keyframes.md
│   │   │   └── captions.md  hooks.md  audio.md
│   │   ├── environment.md              # 环境/沙箱/网络/编码实测事实
│   │   ├── editing-rules.md            # 风格规则库（⬜ 待填充）
│   │   ├── knowledge-cards/            # 外部知识卡片原件（二手，非可信源）
│   │   └── styles/                     # 体裁规则集（叙事型 / 集锦）
│   └── scripts/
│       ├── analyze_film.py             # 成片/素材 → 结构分析
│       ├── edl_to_draft.py             # EDL → 剪映草稿
│       └── keymap_report.py            # 读本机剪映真实键位方案
├── tools/                              # 仓库级工具
│   ├── dl_reference.py                 # 参考视频下载（yt-dlp 薄封装）
│   ├── detect_kills.py                 # 击杀帧检测（--band legacy|measured）
│   ├── verify_kill_frames.py           # ★ 目视核对击杀帧（带子叠图）
│   ├── measure_kill_edit.py            # 击杀 × 切点上下文测量
│   ├── sync.ps1 / push.ps1             # 提交 + 推送
│   └── web/                            # 本机唯一能过 HTTPS 的通道（Node）
├── projects/game-001/                  # 第一个项目：瓦洛兰特集锦
│   ├── research/                       # 调研产出（含 kill-moment-report.md）
│   ├── edl/  draft-out/  verification/
│   └── ref-analysis/                   # 参考成片分析
├── docs/lessons.md                     # ★ 逐轮经验沉淀（每轮必写）
├── spike/                              # 兼容性验证过程记录
└── requirements.txt
```

**不入版本控制**（体积/版权，见 `.gitignore`）：`原始素材/`、`参考视频/`、`瓦参考素材/`、
`bgm-license-check/`、抽帧目录、预览片。
⇒ **新克隆拿不到素材，但拿得到全部知识与工具。**

---

## 环境要求

已验证组合：剪映专业版 **11.4.2.14459** + Python 3.13 + pyJianYingDraft 0.3.0。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

ffmpeg 由 `imageio-ffmpeg` 自带，**无需系统安装**；也没有 ffprobe，媒体信息走 `pymediainfo`。

## 常用命令

```powershell
# 分析一条素材或成片
.venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\analyze_film.py <视频> --summary

# 校验 EDL（不生成草稿）
.venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\edl_to_draft.py edl.json --dry-run

# 生成剪映草稿（生成前请完全退出剪映；之后需重启/切换草稿才能看到）
.venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\edl_to_draft.py edl.json --name "项目名"

# 本机剪映键位方案（同一功能在不同方案下键位不同）
.venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\keymap_report.py --compare

# 目视核对击杀帧
.venv\Scripts\python.exe tools\verify_kill_frames.py 原始素材\<文件>.mp4 14.73

# 下载参考视频
.venv\Scripts\python.exe tools\dl_reference.py --list urls.txt
```

---

## 关键限制（重要）

1. **读不了已有草稿** —— 剪映 11.x 的 `draft_content.json` 是加密的，上游库出于合规不提供解密。
   风格反推改走「分析成片」路线。
2. **不能自动导出** —— 剪映 7+ 的限制，导出必须人工完成。
3. **固定阈值切点检测不可靠** —— ffmpeg `scdet` 以亮度差为主，等亮度换色会漏判（实测 5.47 vs 23.05）。
   分析器改用自适应峰值检测。
4. **本机上网只有三条窄路** —— `yt-dlp`（能搜 B站、能下载）✅、Node（`tools/web/`）✅、
   明文 HTTP ✅；PowerShell/Python 的 HTTPS 被沙箱挡 ❌；`web_search`/YouTube/Reddit ❌。
   详见 `references/environment.md`。

## 已知陷阱（索引）

| 陷阱 | 在哪 |
|---|---|
| 时间必须带单位后缀（`tim(0.5)` → 0） | `references/edl-schema.md` 末尾 |
| 转场必须在入轨前挂好 | `references/edl-schema.md` 末尾 |
| **剪映有多套键位方案，同一功能键不同** | `references/operations.md` §2 |
| **击杀检测的底部标定是错的**（只截到横幅 14px） | `references/kill-extraction.md` §1–2 |
| **同一判据在成片上退化成切点探测器** | `references/kill-extraction.md` §4 |
| **效果时长只能在成片上量，不能在教程录屏上量** | `references/techniques/kill-moment.md` §3 |
| 沙箱挡 git TLS / pip %TEMP% / Python TLS / ps1 的 BOM | `references/environment.md` |

---

## 迭代约定：**每轮训练后必须推送**（硬性要求）

**每完成一轮，把有价值的经验追加到 `docs/lessons.md`，然后提交并推送到 GitHub。
没推上去 = 这一轮没结束。**

远程仓库：<https://github.com/yinyichen987-sketch/Edit-Skill>（分支 `game-video`）

```powershell
# 1. 把本轮经验写进 docs/lessons.md（模板在该文件末尾）
# 2. 同步到 GitHub（提交 + 推送）
.\tools\sync.ps1 -Message "第 N 轮：<主题>"
```

### 推送失败时的退出码

| 码 | 含义 | 怎么办 |
|---|---|---|
| `0` | 已推送 | 本轮结束 |
| `1` | 网络/代理问题 | 检查 FlClash（`127.0.0.1:10910`） |
| `3` | **被执行沙箱挡住**了 TLS（`SEC_E_NO_CREDENTIALS`） | **不是网络问题**，加宽权限重跑 |

三种典型现象与真因（本项目都踩过）：

| 现象 | 真因 |
|---|---|
| `schannel … SEC_E_NO_CREDENTIALS` | 沙箱挡 TLS → 加宽权限 |
| `Failed to connect to 127.0.0.1 port 10910` | **代理配置残留** + 代理已关 → 脚本会主动 unset |
| `Recv failure: Connection was reset` | 代理没开且直连不通 → 开代理 |

> **代理时有时无**：第 4 轮代理通、第 5 轮代理关着但**直连成功**。
> 脚本行为（探测代理 → 清残留 → 直连）正好适配这种不确定性，**别写死结论**。

**什么算「有价值的经验」**：会重复踩的坑 / 改变了后续做法的判断 / 实测推翻了原本假设的结论。
**什么不算**：流水账、一次性调试过程、已固化进 `references/` 的技术细节正文（只留一句索引）。

---

## 跨对话可见性（重要，别误以为有"记忆"）

| 通道 | 状态 |
|---|---|
| **仓库文件**（本 README + `SKILL.md` + `references/` + `docs/lessons.md`） | ✅ **唯一可靠通道**，且已推送 GitHub，换机器克隆也能拿到 |
| DSH Skill 目录（自动注入 `<available_skills>`） | ✅ 靠 `SKILL.md` 的 frontmatter，新对话能看到这个 skill 存在 |
| Hindsight 知识页 / 语义记忆 | ❌ **本机未配置 API key（401），不可用** |
| `.agent-teams/` | 只是协作状态，**不是知识库** |

**结论**：跨对话「找得到」完全依赖**把结论写进文件**。
所以每轮必须做两件事：①把新知识写进 `references/`；②把判断与踩坑写进 `docs/lessons.md`。
**只在对话里说过、没落盘的东西，下一轮等于不存在。**
