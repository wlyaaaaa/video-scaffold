# AI 开发指引 · 游戏王MD视频生成脚手架开发规约 (AI Guide)

本文件是为 AI 编码助手（如 Gemini, Claude, Cursor 等）编写的**免源码通读开发参考指南**。
当需要 AI 协助修改文案、调整排版、修补音画同步或重组场景时，**直接向 AI 喂入此文档即可，无需让其通读 build_v2.py 或 pipeline/ 目录**。

---

## 1. 项目目录与文件职责 (Project Map)

*   `config.py`: 全局静态配置（画布分辨率、FPS、渲染线程数、Whisper热词表）。
*   `build_v2.py`: **主业务逻辑**。包含场景数据 `SCENES`、章节划分 `CHAPTER_GROUPS` 以及每个场景 `s00` - `s21` 的组件拼接逻辑。修改排版和内容均在此文件。
*   `v2lib.py` (`import v2lib as L`): **排版核心组件库**。声明了画布常量和所有渲染组件。
*   `templates/scene_base.html`: 动画与网页底座。定义了各种入场/退场动效（如 `fade-up`, `stamp`, `draw`, `fade-out`）的 JS 运行逻辑。
*   `docs/VOICE.md`: 配音情感和停顿标记说明。

---

## 2. 画布与设计系统常量 (Design System)

在 `v2lib.py` 中定义，在 `build_v2.py` 中直接作为全局变量使用：
*   **分辨率**: 宽 `WIDTH = 3840`，高 `HEIGHT = 2160` (标准的 4K UHD 画布)。
*   **坐标参考点**: Center X `CX = 1920`，Center Y `CY = 1080`，左边边距 `M = 240`。
*   **调色盘**:
    *   `INK = "#0C2B1B"`: 主文本字色（深黛绿）。
    *   `ACCENT = "#1F7A4D"`: 高亮/线条/箭头颜色（流光浅绿）。
    *   `RED = "#A83232"`: 负面/警示颜色。
    *   `GOLD = "#C29638"`: 特殊奖励/亮点颜色。
*   **字号层级 (`T[lvl][0]`)**:
    *   `lvl=0` (200px, 巨幕标语) | `lvl=1` (130px, 场景标题) | `lvl=2` (96px, 重点字) | `lvl=3` (68px, 正文说明) | `lvl=4` (52px, 次要小字)。

---

## 3. 音画同步机制与 Cue 纠偏规则 (A/V Sync & Cueing)

### 3.1 踩点机制
组件中的 `cue="关键字"` 代表该组件会在音频中**念出此字词的那一瞬间**开始播放动画。
它的原理是：运行时 JS 引擎拿着 `cue` 里的词，去 `srt_data/` 的词级时间轴 JSON 里查找其开始时间（例如第 `1.24s`），然后在渲染第 `1.24s` 帧时准时启动网页中对应的 SVG 动画。

### 3.2 ⚠️ 拼音与多音字纠偏（两步法）
Whisper 语音转写可能会因为同音字/缩写产生识别偏差，此时**不要修改音频，也不要修改网页显示的文本**，只需修改 `cue` 绑定的 key 以对准 Whisper 转写的错字：
*   *例 1*：配音念“免费钻”（有偿钻的钻），Whisper 转写为“免费赚”。
    **解决方案**：组件属性改为 `cue="免费赚"`，屏幕显示的文本依然保持 `L.pop("免费钻", ...)`。
*   *例 2*：配音念“代充”，Whisper 在第 5 场景中转写为“代冲”。
    **解决方案**：改写为 `cue="代冲"`。

*常见的 Whisper 转写纠偏速查*：
*   `有偿` / `无偿` ➔ `有长` / `无长`
*   `免费钻` ➔ `免费赚`
*   `代充` ➔ `代冲`
*   `正题` ➔ `阵题`
*   `绿卡` ➔ `日卡`
*   `到余额` ➔ `倒余额` 或 `到余额` (以 `srt_*.json` 为准)

---

## 4. 排版核心组件库定义 (v2lib.py API)

所有 API 均支持 `cue`（时间轴绑定）和 `delay`（相对该 `cue` 的额外延迟，单位为秒）。

### 4.1 基础文本与装饰
*   `L.title(s, x, y, lvl=1, kick="", cue=None, delay=0.3)`: 场景大标题。
*   `L.text(s, x, y, lvl=3, cue=None, delay=0.3, dur=0.7, anim="fade-up", fill=None, anchor="start", weight=600)`: 基础文本（支持 `fade-up`, `fade-left`, `fade-out` 等动画）。
*   `L.pop(s, x, y, lvl=2, cue=None, delay=0.0, fill=None, anchor="start")`: 弹出缩放文本（常用于警示、数据强调，默认带气泡回弹特效）。
*   `L.num(val, x, y, lvl=1, cue=None, delay=0.1, dur=1.0, prefix="", suffix="", dec=0, fill=None)`: 滚动数字特效。
*   `L.strike(x, y, w, cue=None, delay=0.45, color=RED)`: 删除线（划掉某个价格）。
*   `L.rule(x, y, w, delay=0.3, color=INK)`: 分割横线。

### 4.2 结构化组件
*   `L.image(name, x, y, w, h=None, anim="wipe", cue=None, delay=0.3)`: 插入 `assets/` 目录下的图片。
*   `L.hl_box(x, y, w, h, cue=None, delay=0.0, color=ACCENT)`: 红/绿圈高亮框，用于在游戏截图上框选出重点（如框住“自动收货”按钮）。
*   `L.chip(s, x, y, lvl=3, cue=None, delay=0.0, color=None)`: 带边框的胶囊药丸文本，用于强调标签或小贴士。
*   `L.compare_table(headers, rows, x, y, colw, row_h=130, delay=0.6, hi_col=None)`: 数据对比表格。
    *   `colw`: 各列宽度的数组，如 `[820, 560, 900, 920]`。
*   `L.flow_token(nodes, x=M, y=1100, gap=560, delay=0.8, token_label="¥")`: 流程链与行驶的金币动画。
    *   `nodes`: 格式为 `[(节点文案, 踩点cue, 是否高亮ACCENT)]`。
*   `L.checklist(title_s, items, x=M, y=560, delay=0.6, lvl=3)`: 带复选勾动画的清单。
    *   `items`: 格式为 `[(清单文案, 踩点cue)]`。
*   `L.balance(left_label, left_items, right_label, right_items, tilt_to=8, x=CX, y=1240, beam=2400, delay=0.8)`: 称重天平组件。
    *   `tilt_to`: 倾斜角度，正数向右倾，负数向左倾。
*   `L.stamp(s, x, y, lvl=1, cue=None, delay=0.5, fill=None)`: 红色/绿色复古大图章（如“通过”、“翻车”）。
*   `L.end_card(main, sub, cue=None, delay=0.4)`: 视频结尾黑屏拉线与鸣谢卡。

---

## 5. 开发日常流命令 (CLI Guide)

当 AI 助手完成代码修改后，引导用户顺序执行以下命令以完成本地部署和生产发布：

1.  **编译网页底版**:
    ```bash
    python build_v2.py build
    ```
    *AI 注意*：如果提示 `WARN cue not found`，说明你的 `cue` 写错了，请按照 **第 3 节** 的纠偏规则修正 `cue` 的中文字，重新执行此命令，直到警告清零。

2.  **极速自检预览 (不花时间的验证)**:
    ```bash
    python build_v2.py preview
    ```
    运行后引导用户双击双开 [output/preview.html](file:///E:/video/output/preview.html)，这能在浏览器里以 1:1 的高真度和完全一致的配音时间轴，以毫秒为单位播放所有的网页动效，用于肉眼检查排版是否越界。

3.  **渲染出片（GPU并发加速 + 智能断点续传）**:
    ```bash
    python build_v2.py render
    ```
    *   此步骤会自动调用 **断点续传**，若仅修改了部分场景且大部分分片已生成，系统将只重渲染被更改/损坏的分片，几秒钟内便可极速拼接完毕。
    *   最终成品输出在 `output/final_output.mp4`，背景音乐和侧链压缩闪避混音会自动完成。

4.  **B站章节大纲**:
    ```bash
    python build_v2.py chapters
    ```
    运行后可直接去根目录下复制 `章节管理.txt` 中的章节，直接粘贴至 B站 视频章节栏中。
