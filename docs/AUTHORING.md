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
| `count` | 数字滚动上升 | `data-to` `data-from`(默认0) `data-decimals` `data-prefix` `data-suffix` |
| `float` | 无重力悬浮（持续） | 用在原画/面板的内层 `<g>` |

## 音画同步（关键）
用 `data-cue="旁白里的原词"` 代替 `data-delay`，元素就会在旁白**念到那个词的那一帧**
才开始动（`build_scene.py` 会去 Whisper 词级时间轴里把它解析成精确秒数）。
- 只能 cue 旁白里**真实说出来**的词，不能 cue 屏幕上的数字（如 "9.5" 旁白其实念
  "九点五"，要 cue 它前面的词，比如 "阻抗强度"）。

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
