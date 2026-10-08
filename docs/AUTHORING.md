# 视频创作指南

这是通用制作工具。AI 接到题目后按内容设计画面、再写本期作品；可主动参考互联网和已有创作知识，先判断是否有实际质量收益，再采用。优先补充有用的创作方法；共用能力按根 `AGENTS.md` 的复用价值标准判断，具体画风和故事按本期需要实现。网页作品接口见 `webfilm/CONTRACT.md`；本页后半部分是分镜配音支路的 SVG 写法。

已有旁白和词轴的讲解可沿用分镜配音支路；自由绘制、形变、3D 或互动作品走网页支路。需要搭配已有视频素材时，用现有后期 compose 接片；约定作品自身的媒体限制仍按 CONTRACT 执行，不把不同用途的规则混在一起。

## 先找到能讲清楚的画面

先用一句话写清观众最后应明白什么，再想“什么东西发生怎样的变化，能让人看懂”。题目没要求的细节由 AI 合理补齐；内容事实、用户已选方案与 AI 创意分开。用户授权 AI 取舍时，AI 自行选样、检查并继续制作。

| 要讲清的内容 | 可尝试的画面思路 |
| --- | --- |
| 一件事怎么发生 | 让同一个物件穿过流程，关键动作显示因果；可用等距、平面、实拍素材，按题目选。 |
| 内部结构与关系 | 分层、剖面、拆解或连线；真正需要空间关系时再用 3D。 |
| 大小、数量、变化 | 共享比例尺、面积、分组或时间轴；半径、面积、体积不能混用，标清单位和来源。 |
| 抽象概念 | 找一个可追踪的比喻，如接力、递归嵌套、聚合与分流；动作要对应概念本身。 |
| 人物、典故与情绪 | 用角色动作和前后变化推进；皮影、像素、绘本等是表现选择，故事与事实仍要成立。 |

从参考中借用镜头组织和动作思路，不照抄无关主题、数字或品牌。历史、地图、文字演变、数据与数学先核事实；艺术示意不能冒充准确复原。比例变化要真的作用于对象，公式动画要展示对应的变换。

## 把想法变成可制作的镜头

每期目录写一份短分镜：`时间｜这一镜讲什么｜画面和动作｜屏幕文字｜声音落点｜如何接到下一镜`。长度以能开工为准，现有战略稿和用户要求直接引用，不重建一套配置或审批系统。

- 先挑最能决定风格的一镜，做几张关键帧或数秒小样。画面、文字能看清，动起来也成立，再铺开其余镜头。
- 一个镜头有明确焦点；字体、色彩、主体造型保持连贯。转场可以让上一镜的线、形状、物件自然接到下一镜，具体风格由内容决定。
- 位置、镜头推拉和形变采用有意图的缓动；图表、标记和主体共用同一进度，避免线已到终点、点还没到。弹簧、粒子、拖影只在表达需要时用。
- 新旧文字分别安排离场和入场，避免瞬间重叠。按实际中文长度留阅读时间，并缩到手机观看尺寸检查；不套用固定的每词一拍或每镜几秒。
- 有旁白时先服务意思与停顿，使用现有词轴；配乐驱动的短片再按节拍安排动作和音效。保留声音余量，转场和结尾也要听看。代码音乐可直接共用设定的节拍，不必先造自动节拍分析器。
- 自检不仅看均匀抽帧：重点看转场前后、文字更替、动作极值和声音落点，再完整播放。记录带时间点的实质问题，优先修最影响理解的几处；分数和波形不能替代作品判断。

网页作品用 `webfilm stills` 看指定时刻、用 `webfilm render --start/--end` 看局部动作；用法见 `webfilm/README.md`。有交互时带同一份动作脚本，预览与整片按同一时钟执行。`webfilm/examples/story-flow` 是原创方法示例与验收样片，不是所有作品应遵守的样式，也不自动发给模型比赛参赛者。

## 按需找灵感

有需要时再查参考，不批量抓取、安装或维护风格库。[Prompt Motion](https://www.prompt-motion.com/) 可用于定位作者和提示词；提示词、海报与实际成片质量分开判断，选中后再看成片。具体结构参考：[单一圆点贯穿多个场景](https://www.prompt-motion.com/ultimaxbt-bbebf5)、[同一形状连续切换界面状态](https://www.prompt-motion.com/twoclipping-5cba86)。

[xilo 的制作方法](https://github.com/Kianzzz/xilo-opus-video)可帮助组织创作思路；[Remotion 的确定性渲染说明](https://www.remotion.dev/docs/flickering)与[音频说明](https://www.remotion.dev/docs/media/audio)可供查证原理。现有工具已处理按时间取帧、等待字体和资源、程序音频与响度，不因参考采用别的框架就更换本项目。

## 分镜配音支路：场景 SVG

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
- 当前时间轴可 cue 的词序列
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

使用 `data-cue="旁白里的原词"`，构建时会从 `srt_data/srt_NN.json` 查到估计的开始时间并
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
- 如果专业词识别错误，先核对原音频与文案；必要时用 `timing --source chinese-asr --force` 重做对齐，或单独调用 ChineseASR 识别复核。不要用对齐成功证明发音正确；仍有歧义时回听原音频，选取真实、稳定的 cue 匹配词。
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

## 当前审阅入口

有声预览、重复 cue 次数、偏移、片段导出及验收边界见 WORKFLOW.md。data-cue-index 选择第几次出现，data-cue-offset 调整相对偏移。单引号和双引号均支持，重复属性拒绝，解析成功后只保留唯一生效延时。词级时间及词内插值不是逐音素真值，必须结合实际音频审阅。
