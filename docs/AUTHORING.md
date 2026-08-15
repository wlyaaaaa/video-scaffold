# 场景 SVG 创作指南

目标是为每段旁白产出一个前景 SVG 片段，再由
`templates/scene_base.html` 的 `window.seekTime(t)` 确定性驱动动画。

## 三条硬规则

1. 只写 `<svg id="stage">` 内部片段，不写 `<html>`、`<style>`、`<script>` 或外层
   `<svg>`。
2. 定位与动画分离：外层 `<g transform="translate(x,y)">` 摆位置；动画放在内层
   `data-anim` 节点，内层不要再带 `transform` 属性。
3. 背景透明，默认文字 `#0C2B1B`、强调 `#1F7A4D`；留白优先，避免无意义的卡片、
   阴影和装饰边框。

## 从提示词到片段

运行：

```powershell
pwsh -File .\run.ps1 prompts
```

每段旁白会得到 `scene_html/prompt_NN.txt`，其中包含：

- 原旁白
- Whisper 可 cue 的真实词序列
- 本场素材的真实绝对 `file:` URI
- 设计与动画契约

AI 或人工审阅结果后，只把片段保存为 `scene_html/fragment_NN.svg`。不要把提示词中的
说明、Markdown 代码围栏或解释文字写进文件。没有素材时不要虚构路径。

## 动画原语

常用 `data-anim`：

| 值 | 效果 | 额外属性 |
|---|---|---|
| `type` | 文字逐字出现 | `data-dur` |
| `fade` / `fade-up` / `fade-left` / `fade-right` | 淡入与位移 | |
| `zoom` / `pop` / `stamp` | 缩放、落锤与印章 | |
| `draw` | 描边生长 | 箭头可用 `marker-end="url(#arrow)"` |
| `count` | 数字滚动 | `data-to`、`data-decimals`、`data-prefix/suffix` |
| `grow-bar` / `draw-area` | 横条或面积生长 | `data-grow` |
| `wipe` | 幕布揭示 | `data-dir` |
| `highlight-sweep` | 高亮扫过 | `data-mode` |
| `trace-dot` / `move-along` | 沿路径描线或移动 | `data-path` / `data-dot` |
| `float` / `drift` / `pulse` | 持续悬浮、漂移、呼吸 | 对应幅度/频率属性 |
| `holo-3d` / `flip` / `morph` | 3D 面板、卡片翻转、路径形变 | 见 `ADVANCED_FX.md` |
| `flow-blob` / `burst` / `shockwave` | 流体、粒子和冲击波 | 见 `ADVANCED_FX.md` |

所有原语必须只依赖传入的时间 `t`。禁止用 `requestAnimationFrame`、计时器、真实时钟或
运行时随机数推进渲染状态。

## Cue 与时间轴

使用 `data-cue="旁白里的原词"`，构建时会从 `srt_data/srt_NN.json` 查到精确开始秒并
替换为 `data-delay`：

```svg
<g transform="translate(280,520)">
  <text data-anim="type" data-cue="核心结论" data-delay="0.4" data-dur="1.2"
        x="0" y="0" font-size="150" font-weight="700" fill="#0C2B1B">
    核心结论
  </text>
</g>
```

- cue 必须是旁白真实说出的词。
- 屏幕显示“9.5”而旁白念“九点五”时，优先 cue 前后的稳定词。
- 如果专业词识别错误，先设置本期 `WHISPER_INITIAL_PROMPT` 并运行
  `timing --force`；仍错误时只调整 cue 匹配词。
- 没有时间轴或未找到词时，构建结果会保留 `data-cue-missing`。这是阻断项，不能靠
  `data-delay` 掩盖后继续出片。

## 素材与组件

提示词会写入可直接使用的 URI，例如：

```svg
<image href="file:///D:/Videos/project/assets/hero.png"
       x="0" y="0" width="1200" height="1400" preserveAspectRatio="xMidYMid meet"/>
```

实际 URI 以本机生成的 `prompt_NN.txt` 为准，不要照抄示例路径。

可用 `pipeline.components` 生成基础组件，也可用 `v2lib` 的更完整组件：

```python
import v2lib as L

fragment = (
    L.title("核心结论", cue="核心结论")
    + L.num_burst(82, 2900, 1180, suffix="%", cue="八十二")
)
```

素材像素尺寸会从 PNG/JPEG 头自动探测；只有 EXIF 或特殊格式确有需要时才在
`v2lib.DIMS` 添加项目级覆盖。

## 渲染前验收

```powershell
pwsh -File .\run.ps1 build
pwsh -File .\run.ps1 lint
pwsh -File .\run.ps1 preview
```

`build` 必须通过，`lint` 必须没有 HARD 项，然后人工打开 `output/preview.html` 逐场检查。
满意后才运行 `render`。最终仍需 `verify`，预览通过不能替代成片验收。
