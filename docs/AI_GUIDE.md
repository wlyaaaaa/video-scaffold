# AI 开发指引 · 视频生成脚手架（单一入口）

> **这是给 AI 编码助手的唯一必读文档。** 要改文案/排版/分镜/动效/音画同步，
> **只读这一份就够了，不要再去通读 `build_v2.py` / `v2lib.py` / `pipeline/`**——
> 那只会浪费上下文。需要更深的动效细节看 [`ADVANCED_FX.md`](ADVANCED_FX.md)，
> 配音标记看 [`VOICE.md`](VOICE.md)。代码现状稳定、无已知 bug，别去"找 bug 式"通读。

下一期大概率还是同风格（游戏王 MD · 回形针式数据讲解 · 无字幕）。流程完全复用。

---

## 0. 黄金法则（先记这几条）

1. **只写一小段静态 SVG 片段**，时间轴动画交给底板运行时（`scene_base.html` 的 `seekTime(t)`）。
2. **一切动效是 `t` 的纯函数**：底板**没有 rAF**，`render.py` 每帧 `seekTime(t)` 后抓图，
   所以确定、同步、不掉帧。加新动效也必须守这条（随机量在 Python 端用固定种子预生成）。
3. **能用组件就别手写**：`v2lib.py`（`import v2lib as L`）已封装全部排版/动效组件。
4. **改完先 `build` 看 0 WARN，再 `preview` 肉眼验，最后才 `render`**。渲染是唯一耗时步骤。
5. **配音齐全时别强制重配**：`tts`/`timing` 现已幂等，`all` 会自动跳过；要重配音才 `tts force`。

---

## 1. 项目地图（文件职责）

| 文件 | 职责 |
|---|---|
| `config.py` | 全局静态配置（分辨率/FPS/线程/Whisper 热词/Fish 模型/BGM 音量）。 |
| `build_v2.py` | **主业务**：场景数据 `SCENES`、章节 `CHAPTER_GROUPS`、每个 `sNN_*()` 场景的组件拼接、CLI 驱动。**改内容/排版在这里。** |
| `v2lib.py` (`as L`) | **组件库**：画布常量 + 全部排版/动效组件（含 8 个高级 FX）。 |
| `templates/scene_base.html` | 动画底板 + 确定性运行时（`measure()`/`apply()`/`seekTime`）。所有 `data-anim` 原语在此。 |
| `pipeline/` | 各阶段实现（tts/durations/transcribe/build_scene/render/merge/preview/chapters/cleanup）。**通常不用读。** |
| `assets/` | 实拍截图/原画（换项目时整批替换；像素尺寸自动探测，无需手填）。 |

---

## 2. 设计系统常量（`v2lib.py` 定义，`build_v2.py` 直接用）

- **画布**：`WIDTH=3840 HEIGHT=2160`（4K UHD）。中心 `CX=1920 CY=1080`，左边距 `M=240`。
- **调色盘语义**：`INK=#0C2B1B` 墨绿正文 / `ACCENT=#1F7A4D` 浅绿(好·结论·线/箭头) /
  `RED=#C0392B` 代价·警示 / `GOLD=#B8862F` 钱。
- **6 级字号** `T[lvl][0]`：`0`=220 巨幕 / `1`=150 标题 / `2`=100 重点 / `3`=64 正文 /
  `4`=44 次要 / `5`=32 最小。
- **前景设计契约**：背景透明、墨绿文字、强调线浅绿；**默认禁边框/卡片/阴影/毛玻璃**、留白克制。
  （例外：`ADVANCED_FX.md` 的"全息/科技"风组件是 opt-in，允许半透明框+辉光；封面也允许重视觉。）

---

## 3. 音画同步 & Cue 纠偏（关键）

`cue="关键词"` = 该组件在旁白**念到这个词的那一帧**才开始动。原理：运行时拿 `cue` 去
`srt_data/srt_NN.json`（Whisper 词级时间轴）查开始秒，重写成 `data-delay`。

**两步法消除 `WARN cue not found`（成片应做到 0 WARN）：**
1. **热词引导（首选）**：把专业词加进 `config.WHISPER_INITIAL_PROMPT`，重跑 `timing force`，纠正 90%+ 同音错字。
2. **对齐 Whisper 实输出（兜底）**：仍错就把 `cue` 改成 Whisper 实际转写的字（**只动 cue，不动屏幕文本/配音**）。去 `srt_data/srt_NN.json` 看实际词。

常见纠偏：`有偿/无偿→有长/无长`，`免费钻→免费赚`，`代充→代冲`，`正题→阵题`，`盗刷→倒刷`，`某鱼→某于`。

**注意**：只能 cue 旁白**真说出来**的词，不能 cue 纯屏幕数字（"9.5"念"九点五"，cue 它前面的词）。
中文数字会自动归一成阿拉伯（"三十六"↔"36" 都能命中）。标题只 cue 开头一两秒说到的词，别 cue 靠后的词（会迟出被正文抢跑）。

---

## 4. `v2lib` 组件 API（`import v2lib as L`）

所有函数都支持 `cue=`（踩点）和 `delay=`（兜底秒）。

**基础原子**：`text / type_in / num(滚动数字,可 comma 千分位) / pop(弹出) / kicker / title /
rule(分割线) / chip(药丸) / strike(删除线) / sweep(荧光扫) / arrow / hl_box(高亮框) / callout`。

**结构化设备**：
- `image(name,x,y,w/h,anim="wipe",cue)` 插 `assets/` 图（**尺寸自动探测**）；`push_image(...)` 缓推镜；`hero_feather(...)` 羽化融进背景的原画。
- `compare_table(headers,rows,colw,hi_col)` 对比表（可高亮"我们"列）。
- `bar_race(rows)` 条形竞赛；`ledger(title,items,total)` 账本逐行；`checklist(title,items)` 勾选清单。
- `flow_token(nodes)` 流程链+金币行驶；`timeline_scrub(nodes)` 时间轴扫播；`balance(...)` 天平。
- `stamp(s)` 大图章；`end_card(main,sub)` 封底。

**高级 FX（详见 [`ADVANCED_FX.md`](ADVANCED_FX.md)）**：
- `holo_panel(title,items)` / `holo(inner)` —— ① 3D 全息数据看板
- `morph_path(from_d,to_d)` / `lock_unlock()` —— ② 矢量路径形变
- `gooey_flow(pts)` —— ③ 资金流向流体融合
- `num_burst(val,...)` / `particle_burst()` / `coin_fountain()` —— ④ 粒子炸裂/金币喷泉
- `convert(a,"RMB",b,"日元")` 币种换算 · `discount_seal("74.8折")` 折扣印章+冲击波 ·
  `pulse_badge("当前最优")` 脉冲徽章 · `card_flip(inner)` 卡牌翻转 · `ambient_motes()` 氛围浮尘 ·
  `gauge(82,zones=[...])` 风险/力度/收益半圆仪表盘

---

## 5. CLI（`python build_v2.py <stage>`）

| 阶段 | 作用 |
|---|---|
| `doctor` | 渲染前体检：ffmpeg/ffprobe/背景/Fish key/playwright/assets 就绪？（**长渲染前先跑**） |
| `scripts` | 把 `SCENES` 的旁白写成 `scripts/script_NN.txt` |
| `tts` | 旁白→Fish 配音（**幂等**：配音齐全自动跳过；`tts force` 强制重配） |
| `timing` | ffprobe 时长 + Whisper 词级转写（`all` 里 srt 齐全则跳过；`timing force` 强转） |
| `build` | 片段嵌底板 → `scene_html/`（**改了文案/分镜先跑这个，盯 0 WARN**） |
| `lint` | **越界自检**：自动找离开画布的文字(HARD,必修)/离开毛玻璃的元素(soft,看情况)。渲染前先跑，省得 90min 后才发现文字被切 |
| `preview` | 生成 `output/preview.html`，浏览器逐场景**动态**自检（渲染前必看） |
| `cover` | 渲染 `output/cover.png`(16:9) 与 `cover_4x3.png` |
| `chapters` | 生成 `output/chapters.txt` 与 `章节管理.txt`（B 站章节，直接粘贴） |
| `render` | 逐帧抓取叠背景 → `video_track.mp4`，**自动接 merge** 出带声音成片（4 worker + 帧校验，约 80–90min） |
| `merge` | 配音拼接 + BGM 侧链闪避 → `output/final_output.mp4` |
| `verify` | 核对成片/封面已生成且非空 |
| `cleanup` | 清临时分片/中间产物 |
| `ship` | verify 通过则 cleanup，一键收尾 |
| `reset` | 清空可再生工作区为下期腾位（`reset yes` 确认；保留 assets/ 与代码） |
| `all` | 端到端（已幂等，可安全重跑） |

日常迭代回路：**改 `build_v2.py` → `build`（0 WARN）→ `preview`（肉眼）→ 满意 `render`**。

---

## 6. 开下一期视频的清单

1. `python build_v2.py reset yes` 清空上一期工作区（保留代码）。
2. 把新素材丢进 `assets/`（尺寸自动探测，不用填 `DIMS`；要 EXIF 校正可在 `v2lib.DIMS` 覆盖）。
3. 改 `build_v2.py`：重写 `SCENES`（旁白 + 用 `L.*` 组件拼前景，多用高级 FX）、`CHAPTER_GROUPS`、
   `COVERS` 封面、片名常量；按需更新 `config.WHISPER_INITIAL_PROMPT` 热词。
4. `doctor` → `all`（首跑会合成配音+转写）。听配音/看 `preview` 满意后再让它跑到 `render`。
5. 出片：`verify` → `ship`。`chapters` 复制到 B 站。
6. 收尾：更新 `video-scaffold-backup.zip`（`git archive HEAD`）并 push GitHub。
