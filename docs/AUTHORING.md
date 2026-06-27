# 场景创作指南（写给 AI 的）

目标：为每段旁白产出**一个场景**的前景 SVG 片段，叠在循环玻璃背景上，做到
**高级感 + 音画分毫不差**。你只写 `<svg id="stage">` 内部的**静态片段**，时间轴动画
全部交给底板运行时（`templates/scene_base.html` 的 `window.seekTime(t)`）。

## 三条铁律
1. **只写片段**：不要写 `<html>`/`<head>`/`<style>`/`<script>`，也不要写 `<svg>` 标签本身。
2. **定位与动画分离**：用「外层 `<g transform="translate(x,y)">` 属性」摆位置；
   动画放在「内层 `<g data-anim>`」上，且该内层节点**不要带 transform 属性**
   （CSS transform 会和属性冲突）。
3. **守设计契约**：背景透明；文字深黛绿 `#0C2B1B`；强调线/箭头浅绿 `#1F7A4D`
   或 `url(#accent-grad)`；**禁止边框/卡片/阴影/毛玻璃**；留白克制。

## 动画清单（`data-anim` + `data-delay`/`data-dur` 秒）
| 值 | 效果 | 额外属性 |
|---|---|---|
| `type` | 文字逐字淡入 | 用在 `<text>` |
| `fade` / `fade-up` / `fade-left` / `fade-right` | 淡入（可带方向位移） | |
| `zoom` | 0.92→1 缩放淡入 | |
| `draw` | 描边从 0 生长 | 箭头加 `marker-end="url(#arrow)"`，箭头会随线尖到达才出现 |
| `count` | 数字滚动上升 | `data-to` `data-from`(默认0) `data-decimals` `data-prefix` `data-suffix` `data-comma="1"`(千分位) |
| `float` | 无重力悬浮（持续） | 用在原画/面板的内层 `<g>` |

**v2 回形针原语（已加入运行时）：**
| 值 | 效果 | 额外属性 |
|---|---|---|
| `fade-out` | 退场（讲完即清） | `data-delay`=退场时刻 |
| `grow-bar` | 数字成条（横/竖生长） | `data-grow="x"\|"y"`（作用于无 transform 的 rect）|
| `draw-area` | 柱/面积自底涨水 | scaleY 0→1 |
| `pop` | 过冲落锤强调 | — |
| `stamp` | 印章盖下 | — |
| `wipe` | 幕布揭示（截图/块） | `data-dir="left\|right\|up\|down"` |
| `highlight-sweep` | 荧光扫过结论词 | `data-mode="stay\|pass"` |
| `trace-dot` | 描线+亮点骑笔尖 | `data-dot="#id"`（趋势线/路线）|
| `move-along` | 令牌沿路径运送 | `data-path="#id"` `data-x0` `data-y0` |
| `play-head` | 时间轴扫动播放头 | `data-span`=像素长 |
| `tilt` | 天平绕支点倾摆 | `data-to`=±度 |
| `split-push` | vs 分屏从中缝推开 | `data-side="left\|right"` `data-gap` |
| `push` | 截图肯·伯恩斯推镜 | `data-sc0/tx0/ty0/sc1/tx1/ty1` `data-origin` |
| `xfade` | 反向淡出（截图间） | `data-delay` `data-dur` |

**高级 FX 原语（AE 级；全是 `t` 的纯函数，详见 [`ADVANCED_FX.md`](ADVANCED_FX.md)）：**
| 值 | 效果 | 额外属性 |
|---|---|---|
| `holo-3d` | 3D 全息看板翻转滑入 | `data-rx0/ry0/rx1/ry1` `data-persp` |
| `morph` | 矢量路径顺滑形变（重采样，无需 GSAP） | `data-to="#id"` `data-samples` `data-close` |
| `flow-blob` | 资金流体融合（配 `filter="url(#goo)"`） | `data-path="#id"` `data-speed` `data-phase` `data-x0/y0` |
| `burst` | 重力粒子炸裂（种子在 Python 端定，零运行时随机） | `data-vx/vy/g/life/spin` |
| `shockwave` | 印章/落锤冲击波环 | `data-max` |
| `flip` | 游戏王卡牌翻转揭示 | `data-ry0` `data-persp` |
| `pulse` | 呼吸辉光（最优/最划算徽章） | `data-amp` `data-spd` `data-opmin` |
| `drift` | 氛围浮尘缓慢游走 | `data-ax/ay` `data-fx/fy` `data-px/py` `data-op` |
> 优先调 `v2lib` 现成组件（`holo_panel`/`morph_path`/`gooey_flow`/`num_burst`/`convert`/
> `discount_seal`/`pulse_badge`/`card_flip`/`lock_unlock`/`ambient_motes`），别手写。
> 组件库见 `E:\video\v2lib.py`（栅格/6级字号/对比条/对照表/账本/时间轴/流程令牌/截图聚焦/天平…）。
> 制作脚本 `E:\video\build_v2.py`。cue 解析已支持中文数字→阿拉伯数字归一（Whisper 把数字转成阿拉伯）。

## 音画同步（关键）
用 `data-cue="旁白里的原词"` 代替 `data-delay`，元素就会在旁白**念到那个词的那一帧**
才开始动（`build_scene.py` 会去 Whisper 词级时间轴里把它解析成精确秒数）。
- 只能 cue 旁白里**真实说出来**的词，不能 cue 屏幕上的数字（如 "9.5" 旁白其实念
  "九点五"，要 cue 它前面的词，比如 "阻抗强度"）；也别 cue 只在屏幕上、旁白没说的标题词。
- **两步法解决 ASR 识别偏差（消除 `WARN cue not found` 警告）**：
  由于 Whisper 会因为语言模型先验偏置（Language Model Bias）把特定术语（如“倒余额”、“区服”、“有偿钻”）误识别为常见的同音字：
  1. **第一步：热词引导（首选）**：在 `config.py` 的 `WHISPER_INITIAL_PROMPT` 中加入游戏专业词汇，然后运行 `python build_v2.py timing` 重新转写。这样可以纠正 90% 以上的同音错字，使代码中的 `cue` 可以保持正常的中文写法。
  2. **第二步：定位标记微调（兜底）**：如果某些词（如“免费钻”因发音和语境被强行识别为“免费赚”）依然识别错误，可直接将代码中的 `cue` 标签修改为 Whisper 转写后的字（例如 `cue="免费赚"`）。**这仅作为时间轴匹配使用，绝不影响画面和视频中显示的正确汉字。**
  3. `build` 阶段如果打印 `WARN cue not found` 警告，请前往 `srt_data/srt_NN.json` 查看 Whisper 实际输出的词并进行调整，成片构建应做到 **0 警告**。
- 标题别 cue 在很靠后才说的词，否则标题会迟迟不出、被正文抢跑（曾经 s14b 标题 cue 在
  8 秒处的"赠送"上）。标题就 cue 开头一两秒内说到的词。

## 渲染前预览（必做，省时间）
渲染是唯一耗时的步骤。改完 `build_v2.py` 先 `python build_v2.py build`，再
`python build_v2.py preview`，双击 `output/preview.html`——23 个场景在网格里**循环自播**
（带真背景、无声、无转场），拖缩放、可暂停，几秒就能扫出错位 / 文字溢出框 / cue 不对。
确认无误再 `render`。自驱循环由底板在 `?dur=秒` 时开启，不影响渲染的逐帧抓取。

> 注意：上面的"禁止毛玻璃/边框/卡片"只约束**场景前景**；封面（`templates/cover_md*.html`）
> 是独立产物，允许毛玻璃、原画底等更重的视觉。

## 片段示例
```svg
<!-- 标题：念到「传说级武器」时逐字浮现 -->
<g transform="translate(280,520)">
  <text data-anim="type" data-cue="传说级武器" data-dur="1.4"
        font-family="'Source Han Serif CN',serif" font-size="200"
        font-weight="bold" fill="#0C2B1B">传说级武器解禁</text>
  <line data-anim="draw" data-delay="0.4" data-dur="1.2"
        x1="6" y1="230" x2="1500" y2="230" stroke="url(#accent-grad)" stroke-width="10"/>
</g>

<!-- 悬浮原画 -->
<g transform="translate(2500,560)">
  <g data-anim="float" data-cue="硬核装备" data-dur="1.4">
    <image href="file:///E:/video/assets/weapon_01.png" width="980" height="1400"/>
  </g>
</g>

<!-- 数据：念到「续航能力」时，数字 0→9.0 滚动，进度条同步生长 -->
<g transform="translate(330,900)">
  <text data-anim="fade-up" data-cue="续航能力" data-dur="0.6" font-size="56" fill="#0C2B1B">续航能力</text>
  <line x1="0" y1="40" x2="1500" y2="40" stroke="#0C2B1B" stroke-width="10" opacity="0.12"/>
  <line data-anim="draw" data-cue="续航能力" data-dur="1.0" x1="0" y1="40" x2="1350" y2="40"
        stroke="url(#accent-grad)" stroke-width="10" stroke-linecap="round"/>
  <text data-anim="count" data-to="9.0" data-decimals="1" data-cue="续航能力" data-dur="1.0"
        x="1500" y="0" font-size="56" font-weight="bold" fill="#1F7A4D" text-anchor="end">0.0</text>
</g>
```

`<defs>` 已内置 `accent-grad`（渐变）与 `arrow`（箭头 marker），直接引用即可。

## 优先用组件（pipeline/components.py）
能用组件就别手写，保证一致与高级感。每个函数返回一段合规片段：
- `title_block(main, kicker, sub, x, y, cue)` 大标题块（逐字+下划线）
- `stat_panel([(label, value, frac, cue), ...], x, y)` 数据条面板（数字滚动+进度条）
- `stat_bar(label, value, frac, y, cue)` 单条数据
- `quote(lines, x, y, cue)` 引用块
- `pointer(x1,y1,x2,y2,label,cue)` 指示箭头+标签
- `hero(image_uri, x, y, w, h, cue)` 悬浮原画
- `lower_third(title, sub, cue)` 无边框名条
- `end_card(main, sub, cue)` 居中封底

示例（一个场景由组件拼成）：
```python
from pipeline import components as C
frag = (C.title_block("核心数据全面解析", cue="核心数据", size=150)
        + C.stat_panel([("阻抗强度","9.5",0.95,"阻抗强度"),
                        ("续航能力","9.0",0.90,"续航能力")], x=330, y=900)
        + C.hero(hero_uri, cue="续航能力"))
```
