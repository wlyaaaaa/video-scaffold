# video-scaffold

面向哔哩哔哩成片的本地视频工作流：Fish Audio 旁白、faster-whisper 词级时间轴、
确定性 SVG 动画、Playwright 逐帧抓取，以及 FFmpeg/NVENC 4K60 合成。

这个仓库只提供工具链，不替你决定选题、文案或画面。`doctor` 只检查环境；真正的
视频内容从你创建 `scripts/script_NN.txt` 后才开始。

## 先判断机器是否 Ready

PowerShell 7 中运行：

```powershell
pwsh -File .\run.ps1 doctor
```

该命令不生成视频内容，检查以下本地能力：

- Python 3.11+ 与 `requirements.txt` 中的运行依赖
- FFmpeg / ffprobe
- 4K60 背景素材
- Playwright + SVG `seekTime(t)` 运行时
- NVIDIA NVENC 的 4K AV1 实际编码
- CUDA faster-whisper 与 `large-v3` 模型缓存
- Fish 模型、声线和密钥配置是否完整

如果编码器存在但显存正被其他任务占满，doctor 会报告 `BUSY` 并返回非零，而不是把
一次资源争用误判成 NVENC 缺失。释放当前 GPU 工作负载后重跑即可。

需要验证 Fish 的真实网络链路时，再运行：

```powershell
pwsh -File .\run.ps1 doctor-live
```

它只合成一句“连通性测试。”，用 ffprobe 验证 MP3 后立即删除临时目录；不会写入
当前视频的 `raw_audio/`。Fish 模型和声线只以 `config.py` 为准，避免多处配置漂移。

运行仓库回归测试：

```powershell
pwsh -File .\run.ps1 test
```

## 环境

- Windows + PowerShell 7
- Python 3.11（优先 `.venv`，否则入口自动选择 `py -3.11`）
- FFmpeg 8 或兼容版本
- 支持 AV1 NVENC 的 NVIDIA GPU
- Chrome/Chromium（Playwright 可用）

建议在 Python 3.11 虚拟环境中安装：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Fish 密钥通过环境变量 `FISH_API_KEY` 注入，或写入被 Git 忽略的
`secret_local.py`：

```python
FISH_API_KEY = "..."
```

不要把密钥写进 `config.py`、文档、日志或提交。

## 创建一个空白项目

```powershell
py -3.11 .\init_project.py D:\Videos\my-next-video
Set-Location D:\Videos\my-next-video
pwsh -File .\run.ps1 test
pwsh -File .\run.ps1 doctor
```

初始化会复制通用运行时、组件库、文档、背景、示例和回归测试，不复制旧项目的
`build_v2.py` 或定制封面模板。先用 `test` 验证新项目自身完整，再用不发起网络请求的
`doctor` 检查本机环境。只有后续需要验证真实 Fish 链路时，才设置
`secret_local.py` 并运行：

```powershell
pwsh -File .\run.ps1 doctor-live
```

初始化还会创建这些空目录：

```text
assets/       素材
scripts/      script_01.txt ... 每场旁白
raw_audio/    Fish 生成的 audio_01.mp3 ...
srt_data/     Whisper 词级时间轴
scene_html/   prompt、fragment_NN.svg 与构建后的 scene_NN.html
rendered/     可再生中间帧/片段
output/       成片、封面、章节和预览
```

开始视频前至少设置 `config.PROJECT_TITLE`（也可用环境变量
`VIDEO_PROJECT_TITLE`）。`WHISPER_INITIAL_PROMPT` 默认为空；只有确定本期专业词后
才补热词。

## 通用工作流

每个阶段都有同一个入口：

```powershell
pwsh -File .\run.ps1 <阶段> [参数]
```

推荐顺序如下：

1. 写入 `scripts/script_01.txt`、`script_02.txt`……每场一份旁白。
2. `tts`：Fish 生成旁白。已有非空音频默认复用；只有明确要重配时用 `tts --force`。
3. `timing`：生成 `durations.json` 和 Whisper 词级时间轴；默认复用已验收时间轴，
   `timing --force` 才重跑。
4. `prompts`：生成 `scene_html/prompt_NN.txt`。素材会以真实绝对 `file:` URI 注入。
5. 人或 AI 审阅提示词并把每场静态 SVG 片段保存成
   `scene_html/fragment_NN.svg`。`pipeline.author.generate()` 故意不绑定任何模型；
   直接由当前 AI 写 SVG 是受支持的主路径。
6. `build`：把片段、词级 cue 和确定性底板组装成 `scene_NN.html`。缺片段、缺时间轴、
   编号不一致或 cue 未命中都会失败，不会静默带病进入长渲染。
7. `lint`：阻断画布外文字等 HARD 布局错误。
8. `preview`：生成 `output/preview.html`，人工检查所有动画、留白和 cue。
9. `render`：逐帧生成 `output/video_track.mp4`，并核验每个分片和整轨帧数。
10. `merge`：拼接旁白，可选 BGM 侧链闪避，生成 `output/final_output.mp4`。
11. `cover`：按 `PROJECT_TITLE` 生成 3840×2160 封面。可传
    `--subtitle`、`--kicker`、`--hero`。
12. `chapters`：读取项目根目录 `chapters.json` 生成哔哩哔哩章节。
13. `verify`：最终交付验收；通过后才是可投稿状态。
14. `cleanup`：仅删除可再生的渲染临时文件，保留时间轴和场景 HTML。

`chapters.json` 使用 1-based 场景编号：

```json
[
  {"scene": 1, "title": "开场"},
  {"scene": 4, "title": "核心结论"}
]
```

第一章必须从 scene 1 开始，后续编号必须唯一且严格递增。

## SVG 动画契约

每场只写 `<svg id="stage">` 内部的静态片段，不写 `<html>`、`<style>` 或运行脚本。
定位放在外层 `<g transform="translate(...) ">`，动画放在内层无 `transform` 的节点：

```svg
<g transform="translate(280,520)">
  <text data-anim="type" data-cue="核心结论" data-delay="0.4" data-dur="1.2"
        x="0" y="0" font-size="150" fill="#0C2B1B">核心结论</text>
</g>
```

`data-cue` 必须是旁白真实说出的词。构建时会换成精确 `data-delay`；若时间轴缺失或
词未命中，系统保留 `data-cue-missing` 标记，`build` 和最终 `verify` 都会失败。
运行时的每一帧只由 `seekTime(t)` 决定，因此渲染速度不会改变动画时间。

更多规则见 [场景创作指南](docs/AUTHORING.md)、[高级动效](docs/ADVANCED_FX.md) 和
[Fish 配音标记](docs/VOICE.md)。

## 最终验收合同

`verify` 不只检查“文件存在”，还检查：

- 项目标题不是占位值
- `final_output.mp4` 有视频流和音频流
- 3840×2160、60fps、与 `config.VCODEC` 对应的编码
- 正时长，以及可读时的音视频时长差
- `cover.png` 为 3840×2160
- `chapters.txt` 从 `00:00` 开始
- 至少一个场景，且没有任何 `data-cue-missing`

看到 `[verify] READY` 才代表这一期成片可进入人工观看与投稿环节；环境体检通过只代表
工具链 Ready，不代表某个视频已经完成。

## 仓库中的旧示例

源模板仓库里的 `build_v2.py` 和两个 `templates/cover_md*.html` 是保留的定制项目示例，
不是新项目入口，也不会被 `init_project.py` 复制。当前通用入口是 `run.ps1` +
`pipeline/workflow.py`；`run_demo.py` 只在明确需要生成演示内容时运行。

## 开发原则

- 不在未授权时自动生成选题、脚本、分镜或演示视频。
- 已验收旁白默认不可变，避免重跑 TTS 造成 cue 与画面漂移。
- 长渲染前必须先过 `build`、`lint` 和人工 `preview`。
- 所有随机视觉参数在 Python 端用固定种子预生成；浏览器运行时禁止依赖真实时钟或
  `Math.random()`。
- 不提交 `secret_local.py`、生成音频、素材、成片或本机缓存。
