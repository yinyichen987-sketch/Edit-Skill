# 击杀帧标记（b61cc53d）· 交付说明

**分支**：`kill-frame-training`（从 `game-video` 切出）
**素材**：`原始素材/b61cc53d55e6aa28e89031fc5ec5693c.mp4`（1280x720 / 30fps / 29.000s / 870 帧）
**草稿**：`击杀帧标记_b61cc53d`（已在剪映草稿目录里）

---

## 1. 交付物清单

| 交付物 | 位置 | 说明 |
|---|---|---|
| ★ **剪映标记草稿** | `projects/game-001/draft-out/击杀帧标记_b61cc53d/`（母本）<br>`%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft\击杀帧标记_b61cc53d\`（已拷入） | 原素材整条铺底 + **10 条短标记**，每条只显示 6 帧（0.2s） |
| ★ **标记台账** | `projects/game-001/spec/killmark-b61cc53d.json` | 标记序号 ↔ 突变帧 ↔ 起止帧 ↔ 微秒时间码 |
| **击杀候选 ground truth** | `projects/game-001/analysis2/kills_groundtruth.json` | 10 个候选帧 + 判据 + 已知边界（见 §4） |
| EDL（可复核的决策记录） | `projects/game-001/edl/killmark-b61cc53d.json` | 与工具无关的剪辑决策对象 |
| 判据与校准 | `.dsh/skills/jianying-edit/references/kill-frame-criteria.md` | ★ 本轮的知识落盘（含否掉的两条旧结论） |
| 联网查证记录 | `projects/game-001/research/kill-frame-criteria-web.md` | 含「查不到」清单与来源等级 |
| 证据图 | `projects/game-001/verification/killlabels/`、`killscan/` | 逐帧放大图与逐帧信号 |

---

## 2. 在剪映里怎么看

1. **完全退出剪映再打开**（剪映有草稿列表缓存，不重启可能看不到新草稿）。
2. 打开草稿 `击杀帧标记_b61cc53d`。时间线结构：
   - 主轨：整条 `b61cc53d`（未做任何剪辑，**29.000s 全片**）
   - 文字轨 `mark`：10 条标记，内容形如 `K01 F196 6.533s`
3. 每条约 0.2s，用**方向键逐帧**移动播放头即可停在击杀帧上核对。

> 标记的纵向位置从下往上排（`transform_y` 0.63 → −0.198），
> 这样 10 条标记**不会互相压住**，也都避开了顶部计分板与画面中部。

---

## 3. 标记清单（帧号即口径）

| # | 标记文本 | 突变帧 | 标记覆盖帧 | 起点时间码 | 置信 |
|---|---|---|---|---|---|
| 1 | `K01 F196 6.533s` | 196 | 195–200 | 6.500000s | medium |
| 2 | `K02 F322 10.733s` | 322 | 321–326 | 10.700000s | medium |
| 3 | `K03 F351 11.700s` | 351 | 350–355 | 11.666667s | medium |
| 4 | `K04 F419 13.967s` | 419 | 418–423 | 13.933333s | medium |
| 5 | `K05 F428 14.267s` | 428 | 427–432 | 14.233333s | medium |
| 6 | `K06 F479 15.967s` | 479 | 478–483 | 15.933333s | medium |
| 7 | `K07 F639 21.300s` | 639 | 638–643 | 21.266667s | medium |
| 8 | `K08 F682 22.733s` | 682 | 681–686 | 22.700000s | medium |
| 9 | `K09 F757 25.233s` | 757 | 756–761 | 25.200000s | medium |
| 10 | `K10 F765 25.500s` | 765 | 764–769 | 25.466667s | medium |

**落点规则（本项目策略 L4）**：`标记起点 = 突变帧 − 1 帧`，持续 6 帧。
突变帧的定义是「顶部 HUD（y10..80）相对上一帧的差首次超过 3σ（=28.12）」。

---

## 4. ★ 必须说清的边界（**不要把这份草稿当成确认过的 ground truth**）

| 边界 | 具体 |
|---|---|
| **10 个候选全部只有间接证据** | 判据是「HUD 相对上一帧发生变化」。**没有一条**是「人看着画面说这里有一次击杀」确认的 |
| **HUD 变化 ≠ 击杀发生** | 本素材是**观战/直播 HUD 录屏**：顶部回合计时是**跳变**更新的（帧 196 时 1:25 → 帧 197 时 1:24；15.967s 处 1:15 → 1:09）。HUD 更新时间与真实击杀时间无法从画面本身证明同帧 |
| **洋红不是击杀横幅** | 本轮我先按洋红把第 1 个候选标成 high，**被子 agent 独立抽帧推翻**：6.53~7.43s 的整屏洋红是**技能/特效**；仓库原先记的「底部击杀横幅 y522~613」实为**准星命中标记**。现已全部降为 medium（`.dsh/skills/jianying-edit/references/kill-frame-criteria.md` §2） |
| **旧判据在本素材上失效** | `tools/detect_kills.py`（底部带∩右上播报，legacy）的 10 个候选里，2 个（9.567s / 19.1s）在新锚点里找不到对应突变 ⇒ **疑似误报**；新锚点多出 1 个（15.967s）⇒ **疑似漏报** |
| **两种锚点语义不同** | 子 agent 的「播报卡白色武器剪影模板」给 F309~310（10.333s），本工具给 F322（10.733s），**差 ≈0.40s**。语义不同、**无独立真值，本轮不下结论** |
| **联网没答上核心问题** | 「剪辑师公认对齐哪一帧」「播报相对真实击杀滞后多少毫秒」：YouTube/Reddit/Google/github/arxiv 全超时，B站 搜索接口全程 `-412`，**没有任何可引用的滞后数字** |

---

## 5. 需要人工确认的事（本轮的产物要靠它才能变成训练数据）

请在剪映里打开草稿，**逐条**回答：

1. 标记罩住的那几帧里，**是不是**画面中的一次击杀？
2. 若是，**真实击杀帧**比标记早几帧 / 晚几帧？

把结论交回来，我会：
- 把它写进 `kills_groundtruth.json`（本轮**故意没有预留 `human_verdict` 字段**，
  避免「字段在就算做了」的错觉）；
- 用真实帧号重算落点规则，并复测「锚点 ↔ 真实击杀帧」的偏移是否稳定。

---

## 6. 复现命令

```powershell
# 1. 逐帧信号（洋红/纯红 + 命中行 y）
.venv\Scripts\python.exe projects\game-001\tools\scan_killframes.py b61cc53d

# 2. 双方头像饱和度逐帧跟踪
.venv\Scripts\python.exe projects\game-001\tools\track_portraits.py b61cc53d

# 3. 候选帧 ground truth（含自校验）
.venv\Scripts\python.exe projects\game-001\tools\make_kill_groundtruth.py b61cc53d --check

# 4. 证据图（逐帧放大，供人核对）
.venv\Scripts\python.exe projects\game-001\tools\label_kill_frames.py b61cc53d --auto

# 5. 生成/独立校验标记草稿
.venv\Scripts\python.exe projects\game-001\tools\make_killmark_draft.py b61cc53d --dry-run
.venv\Scripts\python.exe projects\game-001\tools\verify_killmark_draft.py b61cc53d
```

**校验结果**：`edl_to_draft.validate` 通过；`verify_killmark_draft.py` 报
「10 个标记的帧号与 groundtruth 逐条一致，且都落在 30fps 整数帧上」。
草稿已拷进剪映目录，`draft_content.json` 与工作区母本 **sha256 一致**。
