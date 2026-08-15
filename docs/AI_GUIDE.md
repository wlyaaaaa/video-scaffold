# AI 执行指引：通用视频工作流

这份文档约束 AI 如何使用脚手架。除非用户明确授权开始某一期视频，否则只允许做
环境体检、工作流测试和通用代码维护；不要自行确定选题、写文案、做分镜或生成演示内容。

## 开工门槛

1. 先运行 `pwsh -File .\run.ps1 doctor`。
2. 需要验证 Fish 真实链路时运行 `doctor-live`；它只产生并删除一条临时探针音频。
3. 确认 `config.py` 中的 Fish 模型/声线仍是唯一配置源，不复制 ID 到业务脚本。
4. 只有用户明确给出本期目标后，才设置 `PROJECT_TITLE`、Whisper 热词和内容文件。

环境 Ready 与视频 Ready 必须分开报告。前者只表示依赖、Fish、SVG、GPU 和编码可用；
后者必须等成片、封面、章节和最终 `verify` 全部通过。

## 文件职责

| 路径 | 职责 |
|---|---|
| `config.py` | 画布、编码、Fish、Whisper、项目标题与路径的唯一配置源 |
| `run.ps1` | Python 3.11 选择与统一命令入口 |
| `pipeline/workflow.py` | 通用阶段编排与跨阶段编号/数量校验 |
| `v2lib.py` / `pipeline/components.py` | 可复用 SVG 组件 |
| `templates/scene_base.html` | `seekTime(t)` 确定性动画运行时 |
| `scripts/` | 每场旁白，`script_NN.txt` |
| `scene_html/fragment_NN.svg` | AI/人工审阅后的场景 SVG 源片段 |
| `output/` | 预览、视频轨、最终成片、封面和章节 |

`build_v2.py` 和 `templates/cover_md*.html` 是旧定制示例，不是当前入口，也不会复制到
新项目。不要为了开始新视频去改它们。

## 标准阶段

```text
doctor / doctor-live
  ↓
scripts → tts → timing → prompts
                         ↓ 人或 AI 审阅并写 fragment_NN.svg
                      build → lint → preview（人工观看）
                                         ↓
                              render → merge
                              cover + chapters
                                         ↓
                                      verify
```

对应命令统一为 `pwsh -File .\run.ps1 <stage>`。

- `tts` 和 `timing` 默认复用已有非空结果。只有用户明确要变更旁白/重跑识别时使用
  `--force`；重配音后必须重跑 timing、build、preview 和后续阶段。
- `prompts` 只组装提示词，不自动调用外部模型。当前 Codex/AI 直接生成并审阅 SVG 是
  正常路径，`pipeline.author.generate()` 保持未绑定不构成 blocker。
- `build` 要求 scripts、fragments、word timelines 编号完全一致。任何 cue 未命中都会
  生成可审计标记并使阶段失败。
- `lint` 的 HARD 项必须修复。soft 项可结合全出血图片的设计意图人工判断。
- `preview` 必须人工观看；自动检查不能替代动画节奏、信息层级和审美验收。
- `render` 是耗时阶段，只能在 build、lint、preview 已完成后启动。
- `verify` 是交付门。不得用“已渲染”“文件存在”或一次截图冒充最终 Ready。

## 场景编写规则

- 每场只输出 `<svg id="stage">` 内部片段，不含外层 `<svg>`、HTML、CSS 或脚本。
- 外层 `<g transform>` 负责定位；带 `data-anim` 的内层节点不要再带 transform。
- 优先使用 `data-cue="旁白真词"`，并附合理 `data-delay` 作为视觉兜底。
- cue 只能引用真实发音，不可引用只显示在屏幕上的数字或标题。
- 专业词先写入本期 `WHISPER_INITIAL_PROMPT` 后重跑 timing；仍不匹配时根据
  `srt_data/srt_NN.json` 修正 cue，不改正确的屏幕文案。
- 素材 URI 使用 `prompt_NN.txt` 注入的真实绝对 `file:` URI，不拼写虚构路径。
- 新动画必须是时间 `t` 的纯函数。随机数在 Python 端用固定种子生成。

## 交付前检查

1. `build` 无未解析 cue。
2. `lint` 无 HARD 错误。
3. 人工打开 `output/preview.html`，逐场确认布局、节奏和素材。
4. `render` 与 `merge` 成功且没有缺帧/短分片。
5. `cover` 与 `chapters` 已按本期内容人工审阅。
6. `verify` 输出 `[verify] READY`。
7. 真实观看最终 MP4 后，才能报告“视频可投稿”。

## 安全边界

- Fish 密钥仅通过环境变量或被忽略的 `secret_local.py` 注入。
- 不输出密钥，不把临时音频、素材、成片或缓存加入 Git。
- 不擅自调用投稿、上传或其他外部发布能力。
