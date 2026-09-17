# video-scaffold

本地视频制作工具链：Fish Audio 配音、Whisper 或可选 Fish 原生时间戳、确定性 SVG 动画、有声审阅、FFmpeg 合成、封面、章节与可选字幕。默认生产规格为 **3840×2160、60fps、AV1 NVENC**。不替用户决定选题，也不自动投稿。

## 查看环境和工程状态

```powershell
pwsh -File .\run.ps1 doctor --json
pwsh -File .\run.ps1 status --json
pwsh -File .\run.ps1 plan --json
```

这三个入口只读，不启动浏览器/GPU、不下载模型、不读取密钥文件、不调用配音。status/plan 会说明过期产物、编号不一致及重跑原因。需要真实本地能力探针时用 `doctor-local`；需要发送一句测试配音时才用 `doctor-live`，后者有外部请求与账户额度消耗。

## 安装与创建项目

主要支持 Windows、PowerShell 7 和原生 Python 3.11。另需 FFmpeg/ffprobe 及 Playwright 浏览器；生产编码需对应的 NVIDIA 编码能力。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -c requirements.lock.txt
.\.venv\Scripts\python.exe -m playwright install chromium
pwsh -File .\run.ps1 test
pwsh -File .\run.ps1 init D:\Videos\my-next-video
```

初始化只接受空目标目录，不复制旧工程素材、音频、成片或密钥；先暂存完整模板再移入目标。进入新目录后运行 test 和 doctor。解释器优先级为 VIDEO_PYTHON、项目 .venv、机器适配、py -3.11、系统 python。依赖锁记录本项目的实际依赖闭包，不包含个人全局环境的其它软件。

Fish 密钥通过 FISH_API_KEY 环境变量或被忽略的 secret_local.py 提供。非空本地值保持既有优先级；空示例不会覆盖环境变量。机器适配 `.video-machine.json` 不进入 Git，也不复制到新项目；本机安装与恢复由 PCConfig 对应入口负责。

## 标准工作流

设置 PROJECT_TITLE，写好 `scripts/script_NN.txt`，把素材放入 assets。每场静态 SVG 保存为 `scene_html/fragment_NN.svg`。允许 01、04、100 等稀疏编号，但全部阶段必须使用同一组真实编号。

```text
scripts → tts → timing → prompts → 人或当前 AI 审阅 SVG
                                     ↓
                                   build → lint → preview / serve → 人工审阅
                                                                  ↓
                                                         render → merge
                                                         cover + chapters
                                                         可选 subtitles
                                                                  ↓
                                                          verify → manifest
                                                                  ↓
                                                              人工观看
```

阶段调用方式为 `pwsh -File .\run.ps1 <阶段>`。配音和时间轴只复用来源匹配的结果，明确重建用 `--force`；它不是忽略错误。每个后续阶段重新验证来源，不因文件存在或数量相等而放行。局部场景修改支持分片增量重渲染，成功分片保留到显式清理。

```powershell
pwsh -File .\run.ps1 preview
pwsh -File .\run.ps1 serve --open
pwsh -File .\run.ps1 cleanup --dry-run
```

有声预览支持词语跳转、时间拖动、场景切换和暂停保留画面。cue 编辑器导出修改片段，不直接覆盖原件；保存后重建才能生效。serve 只在回环临时端口提供预览依赖，Ctrl+C 停止；preview 自身不启动服务。

cleanup 的 dry-run 只列清单；实际清理只删除已知可再生文件，保留未知文件和原件。任何失败都要报告，不显示假成功。

## cue、章节与验收

```svg
<g transform="translate(280,520)">
  <text data-anim="type" data-cue="核心结论" data-cue-index="2"
        data-cue-offset="0.05" data-delay="0.4" data-dur="1.2"
        x="0" y="0" font-size="150" fill="#0C2B1B">核心结论</text>
</g>
```

单引号和双引号均支持，解析成功后只保留一个生效延时；重复属性、未命中 cue、非法时间和未知动画都会失败。data-cue-index 选择词语出现次数，data-cue-offset 表示偏移。语音时间来自模型估计及词内插值，按帧执行动画不意味着语音时间绝对准确。

chapters.json 引用真实场景编号，第一章从场景 1 开始，之后唯一递增。subtitles 输出全片 SRT/WebVTT；manifest 在验证成功后生成 delivery.json，纳入成片、封面、章节及存在且验证通过的字幕。

verify 检查当前来源、真实总帧数和总时长、音视频流时长与起点、编码/画布/帧率、PNG 封面和章节。**READY 只表示自动结构验收通过，不表示人工观看、配音绝对准确或已经投稿。**

## 隔离演示与开发验证

```powershell
pwsh -File .\run.ps1 test
pwsh -File .\run.ps1 smoke
pwsh -File .\run.ps1 smoke --gpu
pwsh -File .\run.ps1 demo --target D:\Videos\isolated-demo
```

smoke/demo 只在独立空项目运行，默认使用明确标注的合成测试音。它会测试真实 HTTP 预览、词语跳转、片段导出、完整媒体交付、旧结果拒绝与增量分片复用。默认 CPU H.264 测试配置，--gpu 使用生产编码器，不是失败后自动降级。显式 --live-fish 才测试云端配音，不复制本地密钥文件。

持续集成包含 Windows/Linux 逻辑测试及 Linux CPU 隔离短片，不接触个人数据或云端账户。默认 Whisper 路线不变；Fish 原生时间戳是单独的可选适配，解析回归测试不能代替其真实账户/声线验收。

完整用法、恢复语义和验证边界见 [当前工作流](docs/WORKFLOW.md)，SVG 方法见 [创作指南](docs/AUTHORING.md)，进阶视觉组件见 [高级动效](docs/ADVANCED_FX.md)。项目规则入口为 AGENTS.md。

build_v2.py 与两个 cover_md 模板仅保留为旧定制样例，不是通用入口，不复制到新项目；不要用它们的旧重置/归档功能处理正在制作的工程。
