# 通用视频工作流脚手架 (Universal Video Workflow Scaffold)

一个**配置驱动**的自动化视频流水线骨架。导入素材后即可快速产出 4K / 60fps
带透明前景动画的视频。重点：**音画同步、动画、高级感、设计**（不做字幕）。

目标硬件：**RTX 5080 + 9950X3D**（NVENC AV1 硬编码 + 多核并行帧抓取）。

> 设计哲学：让 AI 只写「**一小段静态 SVG 片段**」，而不是每次生成一整个动画
> 网页。所有时间轴动画都由 [`templates/scene_base.html`](templates/scene_base.html)
> 的通用运行时统一接管，确定性、可复用、生成快。

---

## 一分钟跑通 demo

```bash
python run_demo.py
```

产物：`output/final_output.mp4`（4K60 / AV1 / AAC，约 15 秒，两个场景）。
demo 用 Fish Audio **免费模型** `s2.1-pro-free` + **央视音色** reference_id
`59cb5986671546eaa6ca8ae6f29f6d22` 合成旁白，**无需充值**。

> 看第二个场景：三条数据条会在旁白念到「阻抗强度 / 展开兼容 / 续航能力」的
> 那一帧才开始生长——这是 Whisper 词级时间轴驱动的音画同步（见下文）。

---

## 目录结构

通用部分（入库、可复用；区别于一次性的逐项目产物）：
```
config.py                  # ⭐ 集中声明式配置，先读这里
secret_local.py            # API key（git-ignored，不入库）
templates/scene_base.html  # ⭐ 通用 SVG 底板 + 声明式动画运行时（含 ?dur= 预览自驱循环）
templates/cover_base.html  # 4K 矢量封面底板（通用）
templates/cover_md.html    # 实拍封面 16:9（青瓷玻璃矢量底）
templates/cover_md_43.html # 实拍封面 4:3（原画毛玻璃底，cover-fit 不变形）
background/
  background_4k.mp4         # 通用 4K 60s 无缝循环流体玻璃背景（所有视频共用）
  fluid_glass.comp         # 背景着色器源码
  render_background.py      # 背景生成器（改着色器后重渲）
examples/sample_hero.png    # demo 占位原画（版权干净）
pipeline/
  prep.py         # 0.2/1.1 资产扫描 + 文案自动切片
  fish_tts.py     # 1.2 文案 -> Fish Audio 央视配音 (raw_audio/audio_NN.mp3)
  durations.py    # 2.2 ffprobe 精确浮点时长 -> durations.json
  transcribe.py   # 2.1 faster-whisper large-v3 词级时间轴（音画同步用）
  author.py       # 3.1 组装大模型 Prompt（script+srt+asset+规范）
  components.py   # 可复用场景组件（标题/数据条/引用/指示箭头/封底…）
  build_scene.py  # 3.2/4a 片段嵌底板 + 解析 data-cue -> scene_html/scene_NN.html
  preview.py      # 3.5 渲染前自检：output/preview.html 全场景「动态」网格预览
  render.py       # 4 逐帧抓取前景叠加到「循环」4K 背景 + 转场 + 电影感 (NVENC AV1)
  merge.py        # 5 配音拼接 + BGM 闪避混音 + 合成 final_output.mp4
  cover.py        # 6a 4K 矢量封面 -> output/cover.png（通用底板）
  chapters.py     # 6b B站章节 output/chapters.txt（+ 实拍项目的 章节管理.txt）
  cleanup.py      # 6c/6d 临时清理 + 就绪自检
docs/AI_GUIDE.md  # ⭐ 写给 AI 的单一入口（改文案/排版/动效只读这份，别通读源码）
docs/ADVANCED_FX.md # 高级动效备忘录（3D全息/路径形变/流体融合/粒子炸裂…直接调用）
docs/AUTHORING.md # 写给 AI 的场景创作指南（动画原语清单）
docs/VOICE.md     # Fish 情感/音效标记指南
run_demo.py       # 端到端示例（也是各阶段如何调用的活文档）
init_project.py   # 从模板一键拷出一个干净新项目
```

逐项目产物（自动生成、git-ignored、可随时删）：
```
assets/ scripts/ raw_audio/ srt_data/ scene_html/ rendered/ output/  durations.json
```

### 复用脚手架 / 重渲背景
- **开新视频**：直接在本目录放素材跑流程；或解压 `video-scaffold-backup.zip` / 拷贝整个
  目录作为干净模板（逐项目产物都是 git-ignored，复制后即空白工作区）。
- **换背景**：改 `background/fluid_glass.comp` 后 `python background/render_background.py`
  重渲 `background/background_4k.mp4`（~90s@5080）；所有视频自动共用新背景。

---

## 通用 SVG 底板：怎么写一个场景

AI / 人只需写 `<svg>` 内部的**静态片段**，用 `data-anim` 声明动画，
其余交给底板运行时。运行时是 `t`（秒）的纯函数，无 `requestAnimationFrame`，
因此每一帧都可被渲染器确定性地抓取，天然音画同步。

```html
<!-- 用「外层 g 的 transform 属性」定位；用「内层 g 的 data-anim」做动画 -->
<g transform="translate(2500,560)">
  <g data-anim="float" data-delay="0.6" data-dur="1.6">
    <image href="file:///E:/video/assets/weapon_01.png" width="980" height="1400"/>
  </g>
</g>
```

支持的 `data-anim`（配 `data-delay` 起始秒、`data-dur` 时长秒）：

| 值            | 效果                         | 适用            |
|---------------|------------------------------|-----------------|
| `type`        | 文字逐字平滑淡入             | `<text>` 标题   |
| `fade`        | 纯淡入                       | 任意            |
| `fade-up`     | 上浮淡入                     | 文字 / 面板     |
| `fade-left/right` | 横向滑入淡入             | 文字 / 面板     |
| `zoom`        | 0.92→1 缩放淡入              | 徽章 / 主图     |
| `draw`        | 描边从 0 生长 (dashoffset)   | 线条 / 路径 / 箭头（箭头随线尖到达才出现） |
| `count`       | 数字滚动上升 (data-to/decimals) | 数据 / 评分     |
| `float`       | 无重力悬浮（持续）           | 原画 / 面板     |

> 音画同步首选 `data-cue="旁白里的词"`（替代 `data-delay`）：`build_scene.py` 会去
> Whisper 词级时间轴解析成精确秒数。完整写法见 [docs/AUTHORING.md](docs/AUTHORING.md)。

设计契约（底板已内置）：背景全透明、文字深黛绿 `#0C2B1B`、强调线 `#1F7A4D`、
无边框 / 无卡片 / 无阴影。`<defs>` 已提供 `accent-grad` 渐变与 `arrow` 箭头
marker（用 `marker-end="url(#arrow)"`）。

---

## 正式做视频（非 demo）

1. 把无背景游戏原画放入 `assets/`（`prep.scan_assets()` 可校验）。
2. 把整篇文案用 `prep.slice_script()` + `prep.write_scripts()` 切成 `scripts/script_NN.txt`
   （或手动切；可内嵌 Fish 情感标记，见 docs/VOICE.md）。
3. 配音（央视音色，免费）：`python -m pipeline.fish_tts`。
4. `python -m pipeline.durations` → `durations.json`（精确浮点时长）。
5. `python -m pipeline.transcribe` → `srt_data/srt_NN.json`（词级时间轴，音画同步用）。
6. `author.assemble_all()` 组装每个场景的 Prompt；让大模型按 [docs/AUTHORING.md](docs/AUTHORING.md)
   产出 SVG 片段（动画用 `data-cue="旁白里的词"` 打点）；
   `build_scene.build(fragment, "scene_html/scene_NN.html", srt="srt_data/srt_NN.json")`。
7. `render.render_timeline(scene_html_paths, durations)` → `output/video_track.mp4`。
8. `merge.concat_audio()` + `merge.mux(...)` → `output/final_output.mp4`。
9. `cover.build(标题,...)`、`chapters.write(...)`、`cleanup.cleanup()` + `cleanup.verify()`。

---

## 实拍项目工具链（build_v2.py + v2lib.py）

demo / 上面那套走的是通用 `author.py` 路径（大模型吐 SVG）。本仓库的成片
**《游戏王MD氪金指南》**走的是更直接的**手写组件**路径：23 个场景全部在
[`build_v2.py`](build_v2.py) 里用 [`v2lib.py`](v2lib.py) 的组件函数拼出（标题 /
对比条 / 对照表 / 时间轴 / 流程令牌 / 截图聚焦推镜 / 天平 / 账本…），真相源
`assets/氪金指南_v2数据与分镜.md`。`s00` 是 17s 冷启动开头（先勾人，再由 s01 自我
介绍），其后 `s01..s21` 是正片，全片 ≈ 9:47。

一个命令一个阶段：`python build_v2.py <stage>`

| 阶段 | 作用 |
|---|---|
| `build`    | 片段嵌底板 → `scene_html/`（**改文案/分镜后先跑这个**） |
| `preview`  | **渲染前自检**：生成 `output/preview.html`，浏览器里逐场景「动态」循环播放 |
| `render`   | 逐帧抓取叠背景 → `video_track.mp4`，**自动接 merge** 出带声音的 `final_output.mp4` |
| `cover`    | `output/cover.png`(16:9 矢量) + `output/cover_4x3.png`(4:3 原画毛玻璃底) |
| `chapters` | `output/chapters.txt` + `章节管理.txt`（B站章节，可直接粘进「章节文本编辑器」） |
| `scripts`/`tts`/`timing` | 文案落盘 / Fish 合成 / 时长+词级时间轴 |
| `all`      | 以上全跑一遍 |

**渲染前先 preview。** 渲染是唯一耗时步骤（NVENC 多分钟）。`build` 后跑 `preview`，
双击 `output/preview.html`：每个场景在网格里循环自播（无声、无转场、带真背景），
可拖动缩放、暂停，5 秒就能抓出错位 / 文字溢出 / cue 不对，改完再 `render`。原理：
场景被 `?dur=秒` 打开时，底板运行时**自驱一个 rAF 循环**（见 `scene_base.html` 末尾，
渲染器不带该参数，逐帧 `seekTime` 不受影响），每个 iframe 各驱各的，`file://` 直接打开即可。

> ⚠️ **别再跑 `tts` / `all`**：`raw_audio/` 已是审过的配音；重合成会改时长、需重新过审。
> 加开头时是「整体后移一位、只合成新开头那一条」来保住其余 22 条配音的。日常迭代
> 固定走 **`build → preview →（满意）render`**。

**音画同步铁律仍在**：cue 只能打在**旁白真说出来的词**上（屏幕上的字/数字不算）。
若 `build` 打印 `WARN cue not found`，说明该词 Whisper 没那么转（如「盗刷」听成
「倒刷」、「价钉死」听成「价盯死」），元素会退回 `data-delay` 兜底——把 cue 改成
Whisper 实际转出的词即可（当前 0 警告）。

---

## 成片质感

- **可复用组件**（`pipeline/components.py`）：`title_block` / `stat_panel` / `stat_bar`
  / `quote` / `pointer` / `hero` / `lower_third` / `end_card`，都返回符合设计契约的
  SVG 片段，AI 几行调用即可拼出一致、高级的场景（demo 即用它们搭的）。
- **场景转场**（`config.TRANSITION`）：`rise`(默认) / `slide-left·right` / `zoom` / `fade`，
  在场景边界做带位移的交叉溶解；时序不变，**不破坏音画/词级同步**。
- **电影感收尾**（`config.CINEMATIC`）：渲染时逐切片就地叠加极淡暗角 `vignette` +
  时间性胶片颗粒 `noise`，并行无额外串行 pass。
- **BGM 闪避**（你提供音乐）：把任意音频放到 `config.BGM_PATH`（默认 `bgm.mp3`），
  `merge.mux` 自动循环垫乐、用 sidechain 在旁白处压低音乐、并在结尾淡出。

## 音画同步怎么做到「分毫不差」（两层）

1. **宏观（场景 ↔ 配音）**：每个场景严格渲染成 `durations[i]` 长；视频选场景和
   音频拼接用**同一套 offsets**，所以任意时刻屏幕上的场景与正在播放的配音一一对应，
   误差 ≤ 1 帧（1/60s），且**不累积漂移**（都来自同一个 `durations.json`）。
2. **微观（动画 ↔ 具体词）**：`data-cue="续航能力"` 由 `build_scene.py` 在
   Whisper 词级时间轴里查到该词的毫秒级起始时刻，改写成 `data-delay`，于是元素在
   旁白念到那个词的**精确帧**才动。demo 场景二的三条数据条就是这么 0.58s / 2.24s /
   4.26s 依次生长的。

## 性能（RTX 5080 + 9950X3D 最大化）

- **快速截图（最大提速点）**：用 CDP `Page.captureScreenshot` + `optimizeForSpeed`
  取代 `page.screenshot`，4K 透明帧实测 **~2.0× 提速**（12.7→25.4 fps），像素无损
  （只改 PNG 压缩力度，画面不变）。`config.SCREENSHOT_FAST`。
- **内存（解除 worker 上限）**：每个 worker 只保留 `MAX_PAGES_PER_WORKER`(默认 3) 个
  常驻页（LRU），而非「每个场景一页」。19 场景时内存从 O(worker×场景) 降到
  O(worker×3)——这正是过去 5 个 worker 就爆内存的根因。内存降下来后可把
  `NUM_WORKERS` 往上调（项目已优化并设置为 `6`，能完美吃满你的 5080 和 9950X3D，避免编码会话溢出的同时最大化多核性能）。
- **抗中断缝合**：每个切片 ffmpeg 失败会自动重试 `CHUNK_RETRIES`(默认 2) 次；合并前
  校验所有切片**存在且非空**，缺一即报错中止，**绝不**产出有缺口/被截断的成片。
- **自适应切片**：短视频也能喂满所有 worker（修了「13s 只用 3 核」）。
- **NVENC AV1** `p6 + spatial/temporal-AQ + lookahead`，4K 近视觉无损、体积小。
- **Whisper**：`large-v3` cuda/float16 + `BatchedInferencePipeline`(batch 16) + VAD，
  cpu_threads=16，长音频吞吐显著提升。支持 `config.WHISPER_INITIAL_PROMPT` 热词表注入，从根本上解决游戏特定词（如“倒余额”、“区服”）在通用 ASR 识别时的同音错字问题。
- **背景循环修复**：背景片只有 60s。渲染用 `-stream_loop -1` + `起始时间 % 背景时长`
  取模，任意总时长都不再出现「设 15 分钟却只有 1 分钟背景」的空帧。
- **时长是唯一真相**：`durations.json` 决定每个场景的精确帧数。
- **音频零损拼接**：同一 TTS 批次编码一致，`merge.concat_audio` 直接 `-c copy`。
- **BGM 缝合稳健**：背景乐用 `-stream_loop -1`（解复用层循环，**不**把整轨灌进内存，
  修了 `aloop` 巨量缓冲可能爆内存的隐患）；旁白/音乐统一为立体声再做 sidechain 闪避，
  末尾 `alimiter` 防削顶——音轨/画面一定缝得起来。

## 配置要点

- **API key**：`config.py` 从环境变量 `FISH_API_KEY` 或 `secret_local.py`（已 gitignore）
  读取，**不入库**。央视音色用免费模型 `s2.1-pro-free` + reference_id
  `59cb5986671546eaa6ca8ae6f29f6d22`，无需充值。
- **配音演绎**：文案可内嵌 Fish 情感/音效标记（`[excited]`/`[emphasis]`/`[pause]`…），
  见 [docs/VOICE.md](docs/VOICE.md)。
- **章节**：B站用 `output/chapters.txt`（`MM:SS 标题`，首行须 00:00，标题短、别太多）。
- **Whisper / Windows CUDA**：需 `pip install nvidia-cublas-cu12 nvidia-cuda-runtime-cu12`
  （cuDNN 随 ctranslate2 自带）；`transcribe.py` 启动时把这些 DLL 目录加进
  `add_dll_directory` 和 `PATH`。

## 现状

已接线、demo 全程跑通：阶段 **0.2/1.1**（prep）、**1.2**（央视 TTS）、**2.1**（Whisper 词级）、
**2.2**（浮点时长）、**3.1**（Prompt 组装 author）、**3.2/4**（底板+渲染）、
**5**（偏移/拼接/淡入淡出/AV1）、**6**（封面/章节/清理/自检），以及**词级音画同步**。

唯一留作接口的是 `author.generate()`——把组装好的 Prompt 真正发给某个大模型 API、
自动落 `scene_NN.html`。底板就是为它设计的（模型只需吐一小段 SVG 片段）；接上 key 即全自动。

**实拍成片现状**：《游戏王MD氪金指南》（`build_v2.py`）已全程就绪——23 场景（含 17s 冷启动
开头 s00）、配音/词级时间轴/0 cue 警告、两版封面、11 章节、`preview.html` 全场景动态自检。
渲染前 `build → preview` 自检无误后，一条 `render` 即出带声音的 `output/final_output.mp4`。
