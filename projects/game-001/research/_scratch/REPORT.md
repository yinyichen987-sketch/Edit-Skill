# 剪映 (CapCut/JianYing) — 击杀瞬间 / 卡点 / 高光 剪辑手法 研究报告
## Web research: Chinese-language sources (B站 / 抖音 / 教程站 / 出版书), 无畏契约 (VALORANT/瓦) montage

**Method note.** `web_search`/`read_page` were broken (Firecrawl 429) and Windows schannel TLS was blocked in
this sandbox, so research ran through Python/OpenSSL: Bilibili search API, Baidu, Sogou, and — most
importantly — **actual frame extraction from 17 downloaded B站 tutorial videos** (yt-dlp, ≤720p, video-only)
which were then read visually. Menu paths below marked "frame" were read off the **real 剪映专业版 UI in the
video**, which is the strongest evidence available.

Evidence root: `_research/` (frames in `_research/frames/<BV>/`).

---

## 1. Technique → 剪映 menu path table

`[frame]` = read directly off the 剪映 UI in a downloaded tutorial video.
`[text]` = from a written source. Confidence reflects corroboration, not effort.

| Technique (中文) | 剪映 menu path | Timing numbers | Source URL | Confidence |
|---|---|---|---|---|
| **曲线变速** (speed ramp) | 选中时间线素材 → 右侧 **画面** → **变速** → 子页签 **常规变速 \| 曲线变速 \| 变速卡点**; 曲线变速 preset row: **蒙太奇 / 英雄时刻 / 子弹时间 / 跳接 / 闪进 / 闪出** | 变速值 seen: **0.1x**, **0.5x**; curve editor 时长 slider, 重置 button | [frame] https://www.bilibili.com/video/BV1FJeRzZEtY/ (t≈42s); [text] https://blog.csdn.net/u013741272/article/details/158009634 | **HIGH** |
| **闪进** (sudden accel — the kill-moment ramp used on 瓦 kills) | same panel → click preset **闪进** | — | [frame] BV1FJeRzZEtY subtitle: 「然后去变速的曲线变速里找到闪进」 | **HIGH** |
| **变速 as top-level tab** (older/newer builds) | right panel top-level tabs **画面 \| 变速 \| 动画 \| 调节 \| AI效果** (some builds) vs. 变速 nested under 画面 (others) | — | [frame] https://www.bilibili.com/video/BV18rrsBdEcD/ ; BV1xQf3BWEEz showed 画面\|动画\|调节\|调整\|AI效果 | **HIGH** (version-dependent) |
| **自定义曲线变速** | 曲线变速 → 自定义: 横轴=时间, 纵轴=速度; 右下角 **+** 添加点, **−** 删点, **重置** 复位 | — | [text] https://blog.csdn.net/u013741272/article/details/158009634 ; [frame] 重置/− visible in BV1FJeRzZEtY | MED–HIGH |
| **定格** (freeze frame) | **icon-only toolbar row directly above the timeline** (no text menu); text sources say 选中素材 → 点击「定格」按钮 | **定格 default duration = 3秒**; freeze clip in 定格卡点 reversed/held; nudge = **「右移6下」** (6 right-arrow presses) | [frame] toolbar row: https://www.bilibili.com/video/BV1wyRmYDERv/ ; [text] https://www.zhihu.com/question/ (title: 「剪映定格默认是3秒」, 1.7万浏览); [frame] BV1g2adz3EvS subtitle 「找要下一个素材开头给个定格（一样右移6下）」 | MED (button position) / **HIGH** (3s default) |
| **帧定格 (mobile)** | 剪映App: 点击 **剪辑** → 向左滑动底部选项至最右侧 → **定格** | can then drag 定格 clip length | [text] https://jingyan.baidu.com/article/29697b917add56ea21de3c31.html ; [text] https://www.jb51.net/softjc/837379.html | HIGH (mobile) |
| **闪白** (white flash) | **媒体 → 官方素材 → 白场** (a white-frame asset) dragged onto a track; combined with **变速 0.5X** | 白场 clip seen at 00:00:20 with **变速 0.5X**; 黑场 clips **000:00:17 / 000:00:20** | [frame] https://www.bilibili.com/video/BV1G1r6BuEsF/ (官方素材 panel shows 黑场 **and** 白场) | **HIGH** |
| **闪白 (via 调节)** | **调节** → **基础** → 亮度 / 光感 / 对比度 / 高光 / 阴影 / 白色 / 黑色 (+ 保存预设) | — | [frame] https://www.bilibili.com/video/BV11hdSYcENH/ (调节 panel: 基础\|HSL\|曲线\|色轮\|蒙版) | **HIGH** |
| **黑场 / 黑帧** | **媒体 → 官方素材 → 黑场** | durations in use: **000:00:17**, **000:00:20** | [frame] BV11hdSYcENH subtitle 「在左边的官方素材里面拖入一个黑场」; BV1G1r6BuEsF, BV1wyRmYDERv | **HIGH** |
| **曝光击杀特效** (blown-out exposure flash) | 媒体→官方素材 add **黑场** + **特效 → 画面特效** (e.g. **黑光聚点 / 瞬间模糊 / 模糊**); and/or **调节 → 基础** raise 亮度/光感 | — | [frame] https://www.bilibili.com/video/BV11hdSYcENH/ (46665 plays) | **HIGH** |
| **抖动 / 震动 / 晃动** (screen shake) | **特效 → 画面特效** → search (e.g. **模糊**, **发光**) → apply; **特效参数**: 名称 / **速度** / **大小** | 特效参数 sliders: 速度, 大小 (=50) | [frame] https://www.bilibili.com/video/BV1wyRmYDERv/ (名称「回弹摇摆」, params 速度/大小) | **HIGH** |
| **内吸击杀抖动** (implosive shake) | **画面** → 基础; keyframes on 缩放/位置, then set keyframe interpolation | keyframe easing option **「三次方缓入」** (cubic ease-in) on a bezier (bezier editor shows 1.00 / 0.00) | [frame] https://www.bilibili.com/video/BV18rrsBdEcD/ subtitle 「这个前面选择3次方缓入」 | MED–HIGH |
| **击杀特效 search term (shake)** | **特效 → 画面特效 → 搜索框** type **「交叉闪震」** | result names returned: 交叉闪震 / 闪震巢黑 / 散震闪 / 震动闪 / 闪电 / 麒麟闪粉; creator then「缩短成只有一个震当转场用」; timeline showed **变速 0.1x 复制片段 x2** | [frame] https://www.bilibili.com/video/BV1FJeRzZEtY/ (t≈54s) — **explicit on-screen search** | **HIGH** |
| **击杀卡片效果** (kill card) | duplicate clip → **画面 → 蒙版** → shape (线性/镜面/圆形/矩形/爱心/星形) + 羽化/圆角 | each 蒙版 clip = **000:03:00 (3s)**; **变速 0.1X**; 「黑白 H851」 | [frame] https://www.bilibili.com/video/BV1HVe8zRE5m/ subtitle 「这样其他的击杀就直接移动蒙版微调一下就行」 | HIGH |
| **回弹万金油转场** | **特效 → 画面特效** (e.g. 回弹摇摆 / 左右晃动) + **变速 0.1X** + 白场/黑场 layering | **变速 0.1X** | [frame] https://www.bilibili.com/video/BV1g2adz3EvS/ | HIGH |
| **发光 / 曝气** | **特效 → 画面特效 → 搜索「发光」** | **发光强度 40 / 滤镜 20 / 光束角度 40** (shown defaults) | [frame] https://www.bilibili.com/video/BV1wyRmYDERv/ | HIGH |
| **卡点 / 自动踩点** (beat sync) | 音频选中 → **自动踩点** → **踩节拍I**; then align effect end to a beat; 画面 also has a **变速卡点** sub-tab | 「调整特效的结尾和音频卡点的**第三个卡点**对齐」; **特效速度 = 7** | [text] https://www.jb51.net/softjc/821033.html ; [frame] 变速卡点 tab in BV1FJeRzZEtY | **HIGH** (path) / MED (numbers) |
| **音量归零** (kill confirm isolation) | **音频** → **基础** → 音量 (drag to 0) — 「去右上角音频把声音调为0」 | 音量 **0.0dB**, 淡入/淡出 **0.0s** | [frame] https://www.bilibili.com/video/BV1G1r6BuEsF/ ; BV1wyRmYDERv | **HIGH** |
| **音效 (audio FX) library** | **音频 → 音效 → 搜索框输入关键词 → 点击右侧「使用」** | confirmed searchable example: **「拍照声」** | [text] published book 《剪映短视频制作全流程》司桂松/邓兴兴, https://read.qq.com/read/1054060985/13 | **HIGH** (workflow) |
| **音效 (mobile)** | 剪映App → **音频** → **音效** (row: 视频原声/音乐/快手收藏/提取音频/智能配音/录音/音效) | — | [frame] https://www.bilibili.com/video/BV1oX4y1U7Sh/ | HIGH |
| **素材库 (stock footage)** | **媒体 → 素材库** → search box | examples: 搜索「风景」, 搜索「夜空」; 官方素材 search 「樱花」 returns 0006/0026/0010/0009/0017/0022/0013/0007/0010-length assets | [text] https://www.jb51.net/softjc/837379.html ; https://www.jb51.net/softjc/821033.html ; [frame] BV1wyRmYDERv | **HIGH** |
| **内置特效名称 (基础/复古)** | **特效 → 基础 → 倒计时特效**; **特效 → 复古 → 白色边框特效**; **特效 → 基础 → 渐显开幕**; **特效 → 氛围 → 萤火特效** | 特效速度=7 | [text] https://www.jb51.net/softjc/837379.html ; https://www.jb51.net/softjc/821033.html | MED–HIGH |
| **文本** | **文本 → 默认文本** → 字体「温柔体」, 样式加粗, 阴影颜色浅蓝, 距离 **15** | 距离 15 | [text] https://www.jb51.net/softjc/837379.html | MED |
| **图片/照片默认时长** | 首页 → **全局设置** → **剪辑** → **图片默认时长** (=3秒) → 保存 | **3秒** | [text] https://jingyan.baidu.com/article/ (剪映专业版如何设置图片默认时长3秒); [text] Sogou SERP 网易订阅 | MED–HIGH |
| **抠像 (chroma key, mobile)** | 剪映App **画中画** → **色度抠图** | **强度 80, 阴影 0**; 抠像 大小 **20** | [frame] BV1oX4y1U7Sh; BV1xQf3BWEEz (智能抠像/自定义抠像/智能画笔/橡皮, 大小 20) | HIGH |
| **快捷键方案切换** | 剪映专业版 → 顶部 **菜单** → **快捷键** → 页面右上角 **倒三角 ▾** → choose preset scheme (默认模式 / 自定义模式 / …) | — | [text] https://zhidao.baidu.com/question/318501630100526964.html | **LOW** — single low-quality source; see §5 |
| **Kill sound effects (枪声/击杀 confirm)** | — | — | creator said he shares 枪声/音效 in his 素材群 rather than using 剪映's library | see §5 (unverified) |

### 剪映专业版 top-level tab bar observed in frames
`媒体 | 音频 | 文本 | 贴纸 | 特效 | 转场 | 滤镜 | 调节 | 模板 | 数字人` (some builds add 智能包装).
Right-hand contextual panel tabs observed: `画面 | 变速 | 动画 | 调节 | AI效果` (video clip) and their
sub-tabs `基础 | 抠像 | 蒙版 | 美颜美体`; `调节 → 基础 | HSL | 曲线 | 色轮 | 蒙版`;
`音频 → 基础 | 换音色 | 声音效果`; `特效 → 基础 | 蒙版`.

---

## 2. Bilibili tutorials found (title + URL + play count + what it teaches)

### A. 无畏契约 / 瓦 specific (highest relevance)
| Title | URL | Plays | Teaches |
|---|---|---|---|
| 一分钟教你用剪映做出瓦超帅**击杀瞬间切刀**效果 — zhen_ren123 | https://www.bilibili.com/video/BV1FJeRzZEtY | 31,595 | 曲线变速→**闪进**; 特效搜「**交叉闪震**」当转场; 变速 0.1x; 每击杀标记 3 点 |
| 1分钟教你用剪映做出最简单的**曝光击杀特效** — zhen_ren123 | https://www.bilibili.com/video/BV11hdSYcENH | 46,665 | 官方素材拖**黑场**; 调节→基础(亮度/光感); 特效 黑光聚点/瞬间模糊/模糊 |
| 一分钟教你用剪映做出瓦超帅**击杀卡片效果** — zhen_ren123 | https://www.bilibili.com/video/BV1HVe8zRE5m | 6,386 | 复制片段 + **蒙版**(矩形/星形) 做 kill card; 每段 3s; 变速 0.1X |
| 三分钟教你用剪映公式化剪瓦**定格特效**（附带樱花教程）— zhen_ren123 | https://www.bilibili.com/video/BV1wyRmYDERv | 19,005 | **定格**用法 + 特效 回弹摇摆/左右晃动/晃动模糊/缩放震荡; 发光强度40; 官方素材搜「樱花」 |
| 一分半教会你剪映做**瓦区卡点大手子左右闪白**效果 — zhen_ren123 | https://www.bilibili.com/video/BV1G1r6BuEsF | 3,630 | **白场/黑场** 闪白; 音频→基础 音量归零; 变速 0.5X |
| 50s教你用剪映做**瓦回弹万金油转场** — zhen_ren123 | https://www.bilibili.com/video/BV1g2adz3EvS | 11,218 | 回弹转场; 「定格 右移6下」; 变速 0.1X |
| cs2和**无畏契约的热门剪辑** 一个视频全学会II — Breast_Clamp代剪 | https://www.bilibili.com/video/BV194afzDE6h | 130,494 | 汇总 fps 热门剪辑手法 (用剪映); 33 分钟长教程 |
| 【游戏剪辑教学】一分钟教会你无畏契约**音乐击杀卡点**效果 — 知识区的UP主 | https://www.bilibili.com/video/BV1qx5463Exr | 5,273 | 音乐击杀卡点; 素材裁剪与对齐 |
| 【游戏剪辑教学】一分钟教会你在剪映中实现超火的**丝滑慢放结尾** — 知识区的UP主 | https://www.bilibili.com/video/BV1mn9uBMEwP | 22,713 | 慢放收尾 |
| 一分钟教会你**超燃击杀效果**怎么剪 — 橘子TV9 | https://www.bilibili.com/video/BV11AyEBuEo9 | 17,356 | 击杀效果 |
| 超帅的**曝光击杀转场**怎么做，一分钟教会你 — 橘子TV9 | https://www.bilibili.com/video/BV1uWrZB7Ewc | 1,783 | 曝光转场 |
| **无畏契约慢动作结尾**剪辑教学 — 洛宇丶无畏契约 | https://www.bilibili.com/video/BV1ZHKE6aEkb | 3,557 | 慢动作结尾 |
| 【无畏契约剪辑教学】三步做出帅气的**调色**效果 — 一点没了丶 | https://www.bilibili.com/video/BV1We411m7vg | 174,278 | 三步调色 |
| 【教程】从0开始制作一部完整的**无畏契约编辑** — SpringYearn | https://www.bilibili.com/video/BV18CcUz3E86 | 4,568 | 完整流程 (**DaVinci Resolve 20**, not 剪映) |
| **无畏契约帅气五杀剪辑教学** | https://www.bilibili.com/video/BV1xQf3BWEEz | 320 | 五杀; 「**二十倍速播放！**」; 抠像大小20 |
| 切刀**定格结尾**教程来了 — 疯狂学剪辑1 | https://www.bilibili.com/video/BV1sqtt6fEbR | 1,259 | 切刀定格结尾 |
| 超有氛围感的**击杀结尾**教程来了 — 疯狂学剪辑1 | https://www.bilibili.com/video/BV1ue8y6XE2M | 1,993 | 击杀结尾; 黑色噪点素材; 0.6s 段 |
| 【B站最全】**游戏集锦应该这么剪**！从零开始学游戏剪辑 — 三三教剪辑 | https://www.bilibili.com/video/BV17tEqzeEXr | 93,692 | 多P (回溯转场/emo结尾/漏光拉镜/湍流扭曲…) — mostly **PR/AE**, not 剪映 |

### B. Core-technique 剪映 tutorials (used for menu paths)
| Title | URL | Plays | Teaches |
|---|---|---|---|
| 【剪映教程】内吸**击杀抖动** — Billzc7 | https://www.bilibili.com/video/BV18rrsBdEcD | 6,943 | 击杀抖动; 关键帧 **三次方缓入** |
| 【剪映电脑端教程】怎么给画面添加**抖动效果**（做游戏视频必备）— 凡叔哇 | https://www.bilibili.com/video/BV1Yj41197ui | 44,798 | 抖动 |
| 【剪映电脑端教程】怎么用**黑场突出主体**，做手电筒/聚焦效果 — 凡叔哇 | https://www.bilibili.com/video/BV1Q841127YH | 24,053 | 黑场用法 |
| **定格卡点**教程来啦～这次学会了吗？— 小白学剪辑-干货分享 | https://www.bilibili.com/video/BV1QmpnznEZF | 34,603 | 定格卡点 (手机版: 节拍工具) |
| 推拉**闪白转场**教程-专业版剪映教程 — 剪辑师袁大宝 | https://www.bilibili.com/video/BV1xjh7zWEjh | 13,283 | 推拉闪白转场 (专业版) |
| 1分钟学会**蒙版闪白卡点**-专业版剪映【第338期】— 袁大宝 | https://www.bilibili.com/video/BV1hHGQ6AErb | 1,942 | 蒙版闪白卡点 |
| 【手机剪辑】制作**闪白的三种方法** — 散角寒暑 | https://www.bilibili.com/video/BV1Yu4y1v7vg | 25,512 | 三种闪白 |
| 45_【剪辑课】电脑剪映-视频**变速及曲线变速**讲解 — DCM小明 | https://www.bilibili.com/video/BV1TeibBJELh | 5,732 | 常规/曲线变速 |
| 【剪映进阶课】**曲线变速和卡点视频** — 爱叨叨的老张 | https://www.bilibili.com/video/BV1Pq42zZEZj | 10,746 | 曲线变速 + 卡点 |
| 最系统的剪映电脑版教程 **常规变速和曲线变速** — 有知公开课 | https://www.bilibili.com/video/BV14J4m1P7PN | 31,903 | 变速系统课 |
| 原来**曲线变速**这么简单啊 — 在沉淀的王业同学 | https://www.bilibili.com/video/BV1k3LczZEAc | 203,998 | 曲线变速 |
| **曲线变速**总是卡不准点？作弊的方法 — 路过我的生活呀 | https://www.bilibili.com/video/BV1yK411b72Z | 23,764 | 卡点对齐 |
| 教你制作游戏**击杀慢放效果** — 路过我的生活呀 | https://www.bilibili.com/video/BV1rR4y1c7pc | 8,520 | 击杀慢放 |
| 【剪映教程】cs2/csgo 模糊开场+电影感滤镜+**击杀效果**+慢动作过渡 — 顾谦w | https://www.bilibili.com/video/BV1VK421t78N | 202,083 | CS 击杀效果合集 |
| **击杀秀音乐转动转场**视频教程 — 硬币哥游戏解说 | https://www.bilibili.com/video/BV1oX4y1U7Sh | 12,643 | 音频→音效; 变速0.1x; 色度抠图 强度80/阴影0 |
| 【剪辑教学】全网最简单**炸麦/全损音质**教程 — Scream呐喊 | https://www.bilibili.com/video/BV1mZYyemE8B | 30,580 | 炸麦/失真音质 |
| 剪映专业版教程16：时间线的常用操作及**快捷键**的用法 — 阿勇朗诵背景 | https://www.bilibili.com/video/BV1pE421M7V1 | 15,311 | 快捷键 |
| 剪映专业版**快捷键**（Ctrl＆Alt）篇 — 白云和嘉嘉的小课堂 | https://www.bilibili.com/video/BV1DAdrY7EyL | 2,446 | 快捷键 |
| 剪映专业版**快捷键教程** — 万木春_剪辑 | https://www.bilibili.com/video/BV1Y5RRYWEyD | 10,102 | 快捷键 |
| **无畏契约击杀特效大全** — 功夫阿达 | https://www.bilibili.com/video/BV1SCto67EKG | 355 | 游戏内特效展示 (非剪辑) |
| **无畏契约击杀图标及击杀音效**修改版 — 鲑鱼33号 | https://www.bilibili.com/video/BV1KrkPBFEmN | 725,471 | 游戏内击杀图标/音效替换 (非剪辑) |
| 一个网站搞定**无畏契约击杀图标和音效素材** — 柯楠Kernan | https://www.bilibili.com/video/BV1ba5C63EJ9 | 15,271 | 击杀图标/音效素材来源 |
| 【无畏契约PR教程】一分钟实现**曝光击杀反馈**效果 — 梦梦梦境ovo | https://www.bilibili.com/video/BV197W4eUEtv | 81,412 | **PR** (not 剪映) |
| 【无畏契约AE教程】如何实现 op光 **击杀反馈**效果 — 梦梦梦境ovo | https://www.bilibili.com/video/BV1p4kiYJEA5 | 34,995 | **AE** (not 剪映) |
| 【无畏契约PR教程】如何实现**变速景深结尾** — 梦梦梦境ovo | https://www.bilibili.com/video/BV1gccfe3ENc | 89,792 | **PR** (not 剪映) |

Full machine-readable search results: `_research/bili_batch1.json`, `_research/bili_batch1.txt`,
video metadata `_research/bili_details.json`.

---

## 3. Quantified rules found (numbers with sources)

| Number | Rule | Source | Confidence |
|---|---|---|---|
| **3 秒** | **定格 (freeze frame) default duration = 3 秒** in 剪映 | Zhihu question title 「剪映定格默认是3秒,我想让定格时间加长或缩短,怎么操作?」 (1.7万 views), surfaced via Sogou SERP: https://www.sogou.com/web?query=剪映+定格+默认+时长+3秒 | **HIGH** (multiple independent hits) |
| **3 秒** | 图片/照片插入默认显示时长 = 3秒; changed at 全局设置 → 剪辑 → 图片默认时长 | https://jingyan.baidu.com/article/ (剪映专业版如何设置图片默认时长3秒), 2022-10-11 | MED–HIGH |
| **3 秒 (000:03:00)** | 可复用的「击杀卡片」蒙版片段每段 3s | frame: https://www.bilibili.com/video/BV1HVe8zRE5m/ | HIGH |
| **0.1x** | 慢放/回弹 baseline speed repeatedly used on kills | frames: BV1FJeRzZEtY (变速 0.1x 复制片段 x2), BV1g2adz3EvS (变速 0.1X), BV1HVe8zRE5m (变速 0.1X), BV1oX4y1U7Sh (0.1x) | **HIGH** |
| **0.5x** | 闪白/黑场辅助片段变速 | frame: https://www.bilibili.com/video/BV1G1r6BuEsF/ (变速 0.5X) | HIGH |
| **20x (二十倍速)** | 五杀 highlight uses a 20× speed segment | frame/subtitle: https://www.bilibili.com/video/BV1xQf3BWEEz/ 「二十倍速播放！」 | MED (single video) |
| **右移6下** | Nudge the 定格 clip right 6 times (~6 frames) to land the freeze | frame/subtitle: https://www.bilibili.com/video/BV1g2adz3EvS/ 「找要下一个素材开头给个定格（一样右移6下）」 | MED |
| **17 / 20 frames** | 黑场 filler clip lengths actually used (000:00:17, 000:00:20) | frame: https://www.bilibili.com/video/BV1wyRmYDERv/ | MED |
| **0.6 秒** | 混合模式 overlay segment length | frame: https://www.bilibili.com/video/BV1ue8y6XE2M/ | MED |
| **6.3 秒** | 定格/慢放片段「拉满时长」到 6.3S (mobile) | frame: https://www.bilibili.com/video/BV1oX4y1U7Sh/ | MED |
| **第5秒** | 定格 applied at ~5s mark in a taught example | book 《剪映短视频制作全流程》 https://read.qq.com/read/1054060985/13 | MED |
| **特效速度 = 7** | 渐显开幕特效 speed set to 7, end aligned to 第3个卡点 | https://www.jb51.net/softjc/821033.html | MED |
| **发光强度 40 / 滤镜 20 / 光束角度 40** | 发光 effect param defaults | frame: https://www.bilibili.com/video/BV1wyRmYDERv/ | MED (defaults, not a "rule") |
| **色度抠图 强度 80 / 阴影 0** | mobile chroma-key for green-screen kill overlay | frame: https://www.bilibili.com/video/BV1oX4y1U7Sh/ | MED |
| **缩放 100%**, **旋转 0.00°** | 画面→基础 defaults | frames: BV11hdSYcENH, BV18rrsBdEcD | HIGH (defaults) |
| **关键帧缓入** | keyframe interpolation offered as 「三次方缓入」(cubic ease-in) | frame: https://www.bilibili.com/video/BV18rrsBdEcD/ | MED–HIGH |
| **3 keyframes per kill** | creator marks 3 points per kill before editing (「这里我们要注意三个点，我提前标记出来了」) | frame: https://www.bilibili.com/video/BV1FJeRzZEtY/ | MED (one creator's workflow, not a universal rule) |

**NOT found anywhere:** any numeric 闪白 0.1秒 / "cut 后 3 帧" / "变速 0.5秒前开始" rule stated by a tutorial.
Those specific numbers in the research brief **could not be verified** — see §4.

---

## 4. 击杀音效 (kill sound effects) — searchable keywords

**Verified:** 剪映's 音效 library IS keyword-searchable and the flow is
**音频 → 音效 → 搜索关键词 → 点击「使用」**. Confirmed by a published book using the keyword
**「拍照声」**: 《剪映短视频制作全流程：剪辑、调色、字幕、音效》(司桂松/邓兴兴)
https://read.qq.com/read/1054060985/13

**Verified for 击杀死声 in general:** creators of 瓦 edit tutorials source kill/gunshot audio
**externally, not from 剪映's library** — zhen_ren123's on-screen tip says
「后期枪声我会发在素材群里」 ("I'll post the gunshot audio in the material group")
(frame: https://www.bilibili.com/video/BV1G1r6BuEsF/), and B站 has dedicated 无畏契约 击杀音效/图标
素材 videos (BV1ba5C63EJ9 「一个网站搞定无畏契约击杀图标和音效素材」, BV1KrkPBFEmN).

**UNVERIFIED — could not confirm:** that 剪映's built-in 音效 search returns results for the keywords
「击杀」, 「爆头」, 「重低音」, or 「转场」 as kill-moment sounds. No source found. **Do not assume these work.**

---

## 5. Could NOT verify

1. **定格 button exact position in 剪映专业版.** The toolbar above the timeline is **icon-only** (no text
   labels visible in frames: undo/redo/split/delete/icons — see `_research/rail_c.jpg`). Written sources all
   say only 「点击定格按钮」 and the *official Microsoft Store listing* lists it as a one-click function
   ("支持一键分割，定格，倒放，镜像，旋转": https://apps.microsoft.com/detail/xpdm5fwdzzvhbx) — but no source
   gives a text menu path like 「画面 → 基础 → 定格」. **There is no evidence 定格 lives under 画面→基础.**
2. **剪映's "5 keymap schemes".** Only found one low-quality 百度知道 answer describing
   菜单 → 快捷键 → 右上角倒三角 ▾ → 选择预设模式 (mentions 默认模式/自定义模式, **no count**).
   https://zhidao.baidu.com/question/318501630100526964.html — **LOW confidence, content-farm style**
   (answer by "赛玖百科小窍门", 百度认证企业号, 2025-12-24). The number **5 is unverified**; no scheme names
   were confirmed.
3. **Any stated 快捷键 for 定格 / 变速 / 卡点.** Only generic 快捷键 videos were found (BV1DAdrY7EyL
   Ctrl&Alt 篇, BV1Y5RRYWEyD); none enumerated per-scheme bindings in text. Unverified.
4. **闪白 = 0.1秒; cut+3帧; 变速 starting 0.5秒 before the kill.** No source states these. The nearest real
   numbers found are 变速 **0.1x** (speed multiplier, *not* duration) and 白场/黑场 clip lengths of
   17/20 frames. **These brief-supplied numbers appear to be unsourced — treat as invented until proven.**
5. **三杀 / 四杀 / 五杀 differentiated treatment.** Only one 五杀 tutorial exists (BV1xQf3BWEEz, 320 plays)
   and it shows a 20× speed segment; no 三杀/四杀-specific ruleset, no ACE-specific effect chain found.
6. **剪映 击杀特效/击杀图标 (built-in kill-pop assets).** Not found in 剪映's 特效/贴纸 library in any
   evidence; 击杀图标 sources found are for the *game* or for AE/PR, not 剪映 built-ins.
7. **抖音 sources.** Douyin pages appeared in Baidu SERPs
   (e.g. https://www.douyin.com/video/7367565886619815177 「剪映专业版高级教程 卡点定格拍照的制作教程」)
   but Douyin blocked extraction (JS/login wall) — titles only, no technique detail.
8. 知乎 (403), 360搜索 (captcha), CSDN full text of some articles, and `web_search`/`read_page`/`modlens`
   were all unavailable in this environment.

## 6. Source-quality warnings (content farm / AI-generated — treat with care)

- **FLAG — AI-generated SEO**: `https://m.sohu.com/a/816626870_122054911/` 「剪映的帧定格在哪里」
  by 天空树下. Vague, promotes a 公众号 "滴答宝库", and describes a generic "截图按钮（通常是一个相机图标）"
  that does not match 剪映's real UI. **Do not cite.**
- **FLAG — likely AI-generated SEO**: `https://blog.csdn.net/u013741272/article/details/158009634`
  「剪映专业版曲线变速完全教程」. Carries a "GEO检测" tag and reads as a generated 10-part series; however its
  **6 preset names (蒙太奇/英雄时刻/子弹时间/跳接/闪进/闪出) were independently confirmed from video frames**,
  so use it for the preset list, not for the prose.
- **FLAG — low-quality Q&A farm**: `https://zhidao.baidu.com/question/318501630100526964.html`
  (快捷键使用模式) — see §5.2.
- **Reliable-ish**: `jb51.net` walkthroughs (screenshot-driven, but 2022-era and authored 佚名),
  `read.qq.com` published book, `jingyan.baidu.com` user tutorials, `pconline.com.cn`.
- **Version caveat**: 剪映专业版's right panel moved 变速 between a top-level tab and a tab under 画面 across
  versions (both observed in 2025–2026 videos). Always record the 剪映 version when citing a path.
- **Mobile vs 专业版**: many blog "定格在哪" answers describe the **phone app** (剪辑 → 滑到最右 → 定格),
  not 剪映专业版. Do not mix them.

## 7. Reproducibility

Tools built for this research (in `_research/`): `net.py` (OpenSSL fetch/search), `cn.py` (Baidu SERP +
Bilibili search API), `engines.py` (Sogou + Baidu w/ cookie jar & retry), `bili_detail.py`,
`download.py` (yt-dlp ≤720p), `extract.py` (ffmpeg frame extraction), `crop.py` (zoom small UI text).
17 videos downloaded; 660+ frames in `_research/frames/`.
