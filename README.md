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
| 搞清楚击杀帧怎么提取、坑在哪 | `references/kill-extraction.md`（⚠️ 2026-09-14 已修正：「洋红 = 击杀横幅」是误读） |
| **判定「哪一帧算击杀帧」**（判据/锚点/能精确到哪一步） | `references/kill-frame-criteria.md`（★ 第 7 轮，第 12 轮补准确率） |
| **「我击杀」的人工真值 / 判据到底准不准** | `projects/game-001/verification/icon-review/truth.json`（42 行人工判定）+ 同目录 `README.md` §5–§8 |
| **把击杀帧标进剪映草稿** | `projects/game-001/tools/make_killmark_draft.py` + `projects/game-001/spec/killmark-b61cc53d-交付说明.md` |
| **剪一条「击杀集锦」**（真值 → 取段 → 选片 → EDL + 台账 → 草稿） | `projects/game-001/tools/make_killreel_edl.py`；交付说明见 `projects/game-001/spec/击杀集锦_A01_徽记源-交付说明.md`、`…击杀集锦_B01_密度优先_30s-交付说明.md`（后者含选片规则与 5 种口径对比） |
| **草稿出完的换行归一化**（CRLF→LF，每份必跑） | `.dsh/skills/jianying-edit/scripts/lf_normalize.py` |
| 环境/沙箱/网络/编码踩过的坑 | `references/environment.md` |
| 本项目的**风格**规则（怎么切、切多快） | `references/editing-rules.md`（⚠️ **仍为空**，见下） |
| **剪映曲库的曲子怎么拿来做 BGM** | `projects/game-001/tools/analyze_bgm_cache.py` + `pick_bgm_segment.py`（读**用户本机缓存**，见下） |
| 历轮训练学到了什么、为什么这么决定 | `docs/lessons.md`（按轮次倒序读最后几轮） |

### ★ 剪映曲库 BGM：接口不可用，但**用户缓存里有真曲 + 剪映算好的拍点**

剪映曲库**不能被程序引用**（`AudioSegment` 只收本地文件）。但用户在剪映面板里
试听/下载过的曲子会留在本机，而且**剪映顺手把拍点也算好了**：

```
%LOCALAPPDATA%\JianyingPro\User Data\Cache\music\<hash>.mp3     音频本体
                                              \<hash>.beat    拍点 time(ms)/value(拍号)/energy
                                              \downLoadcfg    下载台账（可看先后）
```

- ⚠️ `.beat` 与 mp3 的**文件名 hash 不相同**，只能按「时长 − 末拍点」最近配对。
- 云曲库接口（`/lv/v1/search/songs` 等，从 `VECreator.dll` 挖出）实测 **403**（缺风控签名头），
  **不去逆向**——与拒绝解密草稿同一立场。取证判据：**404 = 路径不对，403 = 路径对但缺凭据**。
- 用法见 `projects/game-001/spec/剪映曲库BGM版-交付说明.md` §2。

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

## 当前状态（截至第 16 轮）

| 部分 | 状态 |
|---|---|
| 环境与兼容性验证 | ✅ 见 `references/environment.md` |
| EDL 协议规范 | ✅ 见 `references/edl-schema.md` |
| 成片分析工具 | ✅ `scripts/analyze_film.py` |
| EDL → 草稿工具 | ✅ `scripts/edl_to_draft.py` |
| **操作知识库** | ✅ `references/operations.md`（功能名/入口/**能否自动化** + 键位方案实测） |
| **手法库** | ✅ `references/techniques/`（11 份：击杀瞬间/转场/卡点/调色/蒙版/关键帧/字幕/开场/音频 + 索引 + 来源） |
| **击杀帧判据（第 7 轮重标 + 第 10 轮修正）** | ✅ `references/kill-frame-criteria.md` ★ —— 含**被推翻的旧结论**（「洋红 = 横幅」、「横幅在底部 y522~613」、「横幅首现 = 锚点+1」）与「帧能精确到哪一步」。第 10 轮补：**播报在右上角 `x≈880..1280, y≈56..82`**，条目约 26px、**新条目追加在下面** |
| **剪映标记草稿（击杀帧）** | ✅ 第 7 轮：`击杀帧标记_b61cc53d`（原素材铺底 + 10 条 0.2s 短标记），独立校验通过 |
| 击杀帧提取校准（旧） | ⚠️ `references/kill-extraction.md`：方法论仍成立，但**「洋红 = 击杀横幅」已被推翻**（文件顶注） |
| 网络取证工具 | ✅ `tools/web/`（本机唯一能过 HTTPS 的通道）+ `tools/dl_reference.py`；⚠️ 第 7 轮 **B站 搜索接口 `-412`**，可达性会漂移 |
| **剪辑规则库（风格）** | ⬜ **仍为空** —— 需要用户提供有代表性的成片后才能归纳 |
| **剪映曲库 BGM 链路** | ✅ 第 6 轮打通：读用户本机 `Cache\music\`（mp3 + **剪映自算的 `.beat` 拍点**）→ 取段 → 切点对齐拍点。接口不可用（403），不去逆向 |
| **自动击杀判据** | ⚠️⚠️ **第 6、7 轮连续被打穿两次**。第 7 轮结论：`detect_kills.py` 在**观战/直播 HUD 素材**上失效；**10 个候选全部只有间接证据（无一拿到正面证据）**。详见 `docs/lessons.md` 第 6、7 轮 |
| **击杀播报检测（右上角白色剪影）** | ✅ 第 10 轮：`projects/game-001/tools/feed_scan.py`（第二版判据 + `--rows` 逐行带诊断 + `x --cross` 汇总检验）→ `verification/feed-scan/`。⚠️ 它的事件 = **播报由空变非空**，**不是全部击杀**（只覆盖一批播报里的第一次） |
| **中心击杀徽记检测（「我」击杀）** | ✅ 第 11 轮：`projects/game-001/tools/center_kill_icon.py` → `verification/icon-scan/`（11 条素材 **42 个高置信事件**；对音频 **9/9 显著**、最佳滞后 **+0.04s**，比播报的 −0.20s 更接近击杀时刻） |
| **★ 人工真值（第 12 轮拿到）** | ✅ 玩家本人填完 `verification/icon-review/review.csv` 的 42 行 ⇒ `truth.json`。这是本项目**第一份人工真值表**，也是第一次能报**准确率**（此前只有对齐性） |
| **★ 徽记的准确率（第 12 轮）** | ⚠️ 事件级 **34 / 42 = 81.0%** 是「我击杀」；按「事件窗口内到底有没有真徽记」算是 **37 / 42 = 88.1%**。**帧级**：给了整数偏移的 29 行里 **28 行是 `0/-1` 帧**，均值 **−0.45 帧（−15 ms）** ⇒ 徽记**首现帧可以当击杀帧**（误差 ≤1 帧 = 33 ms），但**事件级只能当候选源**（误报＝亮地面/武器皮肤/地图/购买界面；「加几何量」「段尾模板重锚定」两条提精度路线**都试过并否掉**，见 `icon-review/README.md` §7） |
| **第 13 轮：推翻「34% 漏报」** | ✅ 那个数字是**口径错**（把「播报事件里有几个带徽记」当成了召回率），重算脚本 `projects/game-001/tools/feed_icon_recall.py` ⇒ **召回率仍然没有分母** |
| **★ 击杀集锦管线（第 14–16 轮）** | ✅ `projects/game-001/tools/make_killreel_edl.py`：击杀源 = 人工真值 → **排除法取段**（GAP 3.0s / POST 1.5s / PRE 0.6s / 切点吸附 ±0.35s / 整数帧对齐）→ EDL + **取段台账** → 剪映草稿。第 16 轮起**选片也进规则**：`--order-by density --target-seconds 30`（不再手敲 `--materials`），台账记 `pool/selected/dropped_materials` |
| **★ 已交付的两条集锦（都被真人看过）** | ① **A01**（手挑 3 条素材）：11 段 / **27.767s** / 12 杀 —— 原话「刚刚好」② **B01**（规则自动选 5 条）：14 段 / **32.167s** / 15 杀（目标 30s，超 7.2% 已被接受） —— 原话「我感觉差不多了」，并确认**已在剪映里看过**。⇒ **取段参数（GAP 3.0 / POST 1.5 / PRE 0.6 / 切点吸附 ±0.35s）在 2 条片子上被本人判为可用**，其中一条还是规则选片的素材 |
| **第 15 轮：锚点字段修正** | ✅ 击杀时刻要取 `frame_true_note`（含人工在 `review.csv` 里写的偏移），旧的 `frame_true` 漏了备注 ⇒ 5 次击杀锚点早了 0.5s。⚠️ 但人工写的「0.5 秒」本身是粗估（实测有 +1.2s 的行）⇒ 锚点带 **±0.7s** 误差，对取段无害、对帧级对齐致命 |
| **草稿换行归一化** | ✅ 第 16 轮固化：`.dsh/skills/jianying-edit/scripts/lf_normalize.py`（pyJianYingDraft 在 Windows 上写 CRLF，本仓库不许 CRLF，所以每份草稿都要过一遍） |

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
│   │   ├── kill-extraction.md          # ★ 击杀帧提取的标定（⚠️ 顶注：洋红≠横幅）
│   │   ├── kill-frame-criteria.md      # ★ 击杀帧判据与锚点（第 7 轮 + 第 10 轮修正，含被推翻的结论）
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
│       ├── lf_normalize.py             # ★ 草稿 CRLF→LF 归一化（每份新草稿必跑）
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
│   ├── tools/                          # ★ 本项目工具（make_killreel_edl.py 击杀集锦取段+选片、center_kill_icon.py 徽记检测等）
│   ├── spec/                           # ★ 交付说明（击杀集锦 A01/B01、剪映导出清单、format-spec）
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

# 剪一条击杀集锦：取段 + 选片 + 台账（加 --dry-run 可先看一遍不写盘）
.venv\Scripts\python.exe projects\game-001\tools\make_killreel_edl.py --materials <短id,短id,...> `
    --order-by density --target-seconds 30 --name 击杀集锦_B01_密度优先_30s

# 草稿 CRLF→LF 归一化（每份新草稿必跑；带 JSON 自检）
.venv\Scripts\python.exe .dsh\skills\jianying-edit\scripts\lf_normalize.py "projects\game-001\draft-out\<草稿名>"

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

远程仓库：<https://github.com/yinyichen987-sketch/Edit-Skill>（分支 `game-video`；
第 7 轮的击杀帧训练在分支 `kill-frame-training`，从 `game-video` 切出；
**第 8–16 轮的成果在 `kill-frame-training-2`** —— 见下「第 12 轮的推送状态」）

### 第 7 轮的推送状态

- ✅ **已提交并推送**：`kill-frame-training` 已推到 GitHub（`origin/kill-frame-training`，
  含第 6 轮在本机未推的 2 个提交）。
- 但**本轮把两种「像网络问题」的失败都遇到了**，值得留档 —— 它们现象相似、处置相反：

| 尝试 | 报错 | 真因 | 处置 |
|---|---|---|---|
| 1 | `schannel … SEC_E_NO_CREDENTIALS` | **沙箱挡 TLS** | 加宽权限重跑 |
| 2 | `Recv failure: Connection was reset` | **TLS 已通，但代理没开、GitHub 直连不通** | **过一会儿 / 开 FlClash 后重跑，成功** |
| 3 | `fatal: The current branch … has no upstream branch` | **不是网络问题**：新建的分支没设上游 | `git push --set-upstream origin <分支>` |

> 第 3 条是本轮**新踩**的：本项目以前只在 `game-video` 上推过，第一次在**新分支**上推送，
> `sync.ps1` 里的裸 `git push` 就会因为「没有上游」而失败 —— 它的诊断分支只认 TLS 类错误，
> 于是把这条报成了「检查代理是否运行」，**指向了错误的方向**。
> ⇒ 下次在**新分支**上收工时，直接用 `git push --set-upstream origin <分支>`。

### 第 10 轮的推送状态：**本机推不上去，改成交 patch/bundle**

- 第 8–10 轮的提交都还在本机 `kill-frame-training`：**本地领先 `origin/kill-frame-training`
  （`fef3f9e`）5 个提交**（`bf47f4a` 第 8 轮 → `1ce728d` 第 10 轮）。
- `git push` 在本机**挂在 Windows 凭据管理器上**（要交互输入凭据）：
  `GIT_TERMINAL_PROMPT=0` 时会直接失败；代理通、`git ls-remote` 也通，所以**不是网络问题**。
- ⇒ 交付方式改成 **`git format-patch` + `git bundle`**（做法见 `docs/lessons.md` 第 9 轮），
  由有权限的一方 `git am` / `git fetch <bundle>` 落地。

```powershell
# 1. 把本轮经验写进 docs/lessons.md（模板在该文件末尾）
# 2. 同步到 GitHub（提交 + 推送）
.\tools\sync.ps1 -Message "第 N 轮：<主题>"
```

### ★ 第 12 轮的推送状态：**推成功了** —— 第 10 轮那个结论要修正

- ✅ **第 8–12 轮（14 个提交）已推到 GitHub，分支 `kill-frame-training-2`**
  （`origin/kill-frame-training-2 = b2508ba`，与本地逐字节一致；`kill-frame-training` 仍停在 `fef3f9e`）。
- **真因不是「本机推不上去」，是「本机没有存凭据」+「被我们自己的非交互设置挡住了提示」**：
  `credential.helper = manager`，但 Windows 凭据管理器里**没有 github 条目**，
  也没有 `GITHUB_TOKEN` / `.git-credentials` / `.netrc`；而先前显式设了
  `GIT_TERMINAL_PROMPT=0` 与 `GCM_INTERACTIVE=never` ⇒ git 只能报
  `Cannot prompt because user interactivity has been disabled` / `unable to get password from user`。
- ⇒ **别主动禁用交互**：允许交互时 Git Credential Manager 会自己弹窗/走浏览器登录，
  登一次就成功（本轮 27 秒推完）。第 10 轮那句「本机推不上去」应改写成
  **「本机没有凭据，且被非交互设置挡住了提示」** —— 否则会一直误判成「只能走补丁」。
- 代理仍用 `-c` **临时**传，**不要写进 `.git/config`**（本项目被残留代理配置坑过）：

```powershell
git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 `
    push --set-upstream origin <分支>
```

- **patch/bundle 通道不算废**：它仍然是「**不需要凭据**」的交付方式（对方 `git am` /
  `git fetch <bundle>`），在拿不到凭据的场景下继续有用；但**不再是唯一出路**。

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
