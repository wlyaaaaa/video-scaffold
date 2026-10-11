# 当前工作流与验收

本页说明默认图文页路线及既有分镜配音入口；项目规则见根目录 AGENTS.md。分镜生产画布仍为 3840×2160、60fps，默认使用 AV1 NVENC；改画幅需要同时修改设计模板、组件和背景，不能只改宽高就宣称竖屏已受支持。

网页作品走独立 [webfilm](../webfilm/README.md)，入口是 `pwsh -File .\webfilm\run.ps1 <命令>` 或 `python -m webfilm <命令>`，不经根 `run.ps1`。主流程是发布当天给双方同一份 CONTRACT、创作要求和工具，各生成 v1，再 render → review → 返回原模型修改一次 → render v2，保留前后版本；[命令示例](../webfilm/README.md) 按双方分别执行。check 校验约定，compare 检查重复捕获，后期命令处理已选产物。普通网页 discover/capture 与自行导出 MP4 是附加能力；demo 是 AI 补充的渲染验收材料。默认 4K 60fps，也可统一指定 1080p；机器路径通过运行适配提供，不复制私人配音、素材或旧场景。来源声明与人工观看独立于结构检查。

## 入口与副作用

本页下述分镜命令通过 `pwsh -File .\run.ps1 <阶段>` 调用。

| 入口 | 实际作用 |
|---|---|
| doctor | 静态只读检查，不启动浏览器、GPU、下载模型或读取密钥文件 |
| status / plan | 只读检查当前来源指纹、产物和编号，解释过期原因与重跑阶段，输出 JSON |
| doctor-local | 明确运行本地浏览器和编码器能力探针 |
| doctor-live | 明确发送一句测试配音，使用 Fish 账户；不代表语音质量验收 |
| test | 运行逻辑回归测试，使用隔离夹具，不碰私人原件 |
| smoke / demo | 在独立空项目中跑完整短片，默认使用合成测试音，绝不覆盖当前工程 |
| serve | 显式启动回环临时端口预览服务；Ctrl+C 停止服务，不修改工程 |

普通生产顺序：scripts → tts → timing → prompts → 审阅 SVG → build → lint → preview/serve → 人工审阅 → render → merge → cover/chapters → 可选 subtitles → verify/manifest → 人工观看。

讲解类默认走下方“图文页：开工、并行与整片”路线。已有分镜配音工程仍按本页对应阶段运行；图文页不调用外部 TTS，不生成或改写生产词轴。

`pipeline.author.generate()` 保持未绑定；人或当前 AI 直接写静态 SVG 是正常路径，并非缺少自动化。

## 环境与初始化

主要支持原生 Python 3.11。用 `pip install -r requirements.txt -c requirements.lock.txt` 安装已核实的直接及传递依赖组合。FFmpeg/ffprobe 和 Playwright 浏览器分别安装；模型权重不在依赖锁文件中，也不隐式下载。

解释器优先级：显式 VIDEO_PYTHON → 项目 .venv → 机器适配 → py -3.11 → 系统 python。机器适配文件 `.video-machine.json` 不进入 Git，不复制到新项目；本机路径变化后重新核实。PCConfig 的 `Initialize-VideoScaffoldRuntime.ps1` 负责本机 Python、FFmpeg、现有 GPU Broker 与 ChineseASR 解释器/根路径的配置，不接管声线、分镜或业务模型参数。

`init <空目标目录>` 在隔离临时目录完成复制后整体移入目标；非空目标或模板缺失直接失败。只复制通用代码、模板、文档、背景、样例及测试，不复制旧工程素材、音频、成片、私密文件、旧定制生成器和旧封面。

密钥仅在明确配音操作时读取。非空 secret_local.py 保持既有优先级；空的本地示例不会覆盖 FISH_API_KEY 环境变量。静态检查不读取它，日志不输出值。

## 来源与恢复

每一阶段重新核验所消费的上游：脚本文本和配音配置、音频字节、时间轴、片段和模板、场景、背景、编码设置及最终输出。编号可以稀疏，但必须相同，例如 01、04、100；数量相同不代表同一组场景。缺记录或失配记录不会自动认可；已知旧配音/词轴记录只有来源与输出哈希都有效时兼容复用，使用 status/plan 查看具体原因，明确审阅后再重建，不手写记录骗过验收。

配音和时间轴以暂存文件及来源记录成组替换，失败保留上一份有效结果。视频分片与合成也先验证再替换；写入入口排他，不能由两个任务同时改变一个工程。GPU 通过已有租约协调，忙碌时停止或明确报告，不结束其他任务。

成功分片保留到显式清理，以便增量渲染。只有输入身份、输出哈希、帧数都匹配才复用；局部场景变更仅重建受影响分片，前段时长变化会让受影响的后续时间位置正确失效。

`cleanup --dry-run` 只列计划；`cleanup` 仅将已知可再生文件移入回收站，保留原件和未知文件。回收失败会返回错误和残留路径，不显示假成功，也不会退回永久删除。

Linux/macOS 使用 Send2Trash。Windows 保留既有受信 PowerShell 回收助手协议；用 `VIDEO_RECYCLE_TOOL` 指定已审核助手的绝对路径。未指定时，仅兼容已存在的 `E:\.agents\tools\Move-TaskItemToRecycleBin.ps1`，不会自动下载或搜索其他脚本；指定无效路径时也不会回退。助手接受 `-LiteralPath`、`-AllowedRoot` 和 `-Json`，成功须返回 `{"status":"recycled"}` 且原路径消失。助手必须保证不能回收时失败，不得永久删除。新 Windows 机器没有该助手时，真实清理会明确报错；先配置受信助手再执行。

## 有声审阅与 cue

运行 `preview --open` 可生成并打开有声预览；也可分开运行 preview 与 serve。HTTP 服务只因显式 --open 或 serve 命令启动，Ctrl+C 停止；生成 preview 文件本身不启动服务。页面支持场景切换、音频播放、暂停保留画面、拖动时间、点击词语跳转及词语高亮。

预览不包含最终动态背景、转场、胶片效果或 BGM；它与渲染共享场景时钟，但不代替最终成片观看。HTTP 服务仅提供预览实际依赖的文件，不开放整个项目目录。

```svg
<g transform="translate(280,520)">
  <text data-anim="type" data-cue="核心结论" data-cue-index="2"
        data-cue-offset="0.05" data-delay="0.4" data-dur="1.2"
        x="0" y="0" font-size="150" fill="#0C2B1B">核心结论</text>
</g>
```

单引号、双引号和正常属性空白都支持；解析成功后仅有一个生效延时。重复属性、非法时间、未知动画和未命中 cue 会失败。data-cue-index 选择第几次出现，data-cue-offset 添加偏移。编辑器导出修改后的 SVG，不直接覆盖原件；保存到对应 fragment_NN.svg 后重跑 build/preview。

模型词级时间和词内线性插值不是逐音素真值。动画按帧执行不代表识别绝对准确，必须通过有声审阅判断。布局检查要求真实 #stage、seekTime、已加载图片字体，并采样动画边界；空页面不再被当成零个越界。

## 章节、字幕及交付

chapters.json 使用实际场景编号；第一章从场景 1 开始，之后编号唯一递增。只有 1、4、9 三场时，scene:4 是真实第二场，而非数组第四项。时间必须在成片内，秒级取整后的章节时间仍需严格递增。

subtitles 生成全片 SRT/WebVTT，不烧进画面，并绑定词轴来源。manifest 在 verify 成功后生成 delivery.json，记录成片、封面、章节的哈希和来源；存在字幕时，字幕必须验证通过才可加入清单。

要给本人看或上传的烧字幕副本另做，不改 final_output.mp4 和 delivery.json：`subtitles.karaoke_ass(原文, 词轴, duration, reveal=True)` 按当前主题出 ASS，按标点分句、念到后逐步显字，当前词用强调色；`reveal=False` 保留传统整句字幕选项。`subtitles.playable_copy(成片, 输出, ass=…, audio=…)` 给出 1080p H.264 High@4.2、yuv420p、BT.709、AAC、faststart 的 ffmpeg 命令。原文要和词轴逐字对得上（空格和标点不算），对不上直接报错，不猜。

## 图文页：开工、并行与整片

从 video-scaffold 根目录执行，影片目录必须为空：

```powershell
python -m pipeline.pages init E:/VideoProductions/新一期 --render
python -m pipeline.pages <影片/pages/段落.json> plan
python -m pipeline.pages <影片/pages/段落.json> stills 3.0 5.0
python -m pipeline.pages <影片/pages/段落.json> render
```

`init` 搭好 pages、art、narration、assets、_samples/checkpoint 和登记 README；`--render` 实际产出 6 秒可播放试片。它使用明确标注的合成测试音，只验证管线。正式创作将 `narration` 指向本期已定稿的音频、原文、真实词轴；不覆盖示例以外的原件，不复制其他期素材。

`plan` 只读，核对绑词、逐字时间和动画退场，不生成背景、不抽录屏帧。`stills` 与 `render` 复用相同检查。`render` 构建 SVG/HTML、检查布局、生成画面轨，再合入原配音与逐字字幕，输出可播放的 H.264/AAC 1080p 副本；各步骤的中间文件位于分镜表 `work`。坐标仍使用 3840×2160；可用 `render_height: 1080` 在浏览器捕获阶段整体缩放，保持构图；默认 `2160` 先生成 4K 轨道再下采样。此默认可按同帧对比结果调整，不是本人定过的硬要求。

`render` 和 `stills` 已内置全机先来后到排队，直接调用 Project 方法也排队。旧 `python -m pipeline.render_queue -- <命令>` 仍兼容，不重复占位。固定队列目录不随各任务 TEMP 改变；名额持有操作系统锁，进程退出自动回收。`VIDEO_RENDER_SLOTS` 默认 2，已有任务时 `VIDEO_RENDER_MIN_FREE_GB` 默认要求至少 14 GiB 可用内存；这些是 AI 估值，可改。编码路数在放行后按当前内存和全部名额预算计算，默认 1—4 路；`VIDEO_RENDER_WORKERS` 仍可显式覆盖。日志记录票号、到达/放行时刻、等待时长、可用内存与实际路数。它是资源估算，不能承诺其他程序永远不改变可用内存。

几段并行各用自己的底座工作副本和本期不同的 work/out 路径；不要共写同一个输出。共用代码由一个合并负责人按段落顺序整合。每段使用完整的一张表出片，段与段在拼接表中连接；同段中途拆开会改变动画边界，需要单独验证。

### 已通过画面与新内容

默认文字按原文的实际词轴逐字出现；重复词选择对应的 cue。染色覆盖层不得先于底字，概括字样须明确 `summary: true`。新内容的提前文字、未放完的有限动画会阻止 plan 和出片。

已审定元素的 `hold_check: "warn"` 同时作用于动画和逐字检查，只提示；只能在本期明确审定的范围使用。给旧表新增该标记时同时用 `preserve_svg: true`，校验包装只存在于检查副本，真正输出的 SVG 字节不变；已有旧标记保持原包装兼容。不能为让新表过检查而擅自加此标记。

```powershell
python -m pipeline.page_compare snapshot <影片/pages目录> <证据/之前.json>
# 在独立底座工作副本中修改通用代码后：
python -m pipeline.page_compare snapshot <影片/pages目录> <证据/之后.json>
python -m pipeline.page_compare compare <证据/之前.json> <证据/之后.json> <证据/差异.json>
```

快照生成完整页和每元素片段，逐字节比较并报告页、元素；不把无法识别的元素算作相同。旧基线缺新版式时，再对照各段实际出片分支的片段。选填的 `rail.replay`、`chat.text_with_bubble`、`level.compact_veil` 等用于复现明确选过的效果，不偷偷改全部旧页。

### 版式一览

```powershell
python -m pipeline.pages atlas E:/VideoProductions/版式一览 --render
```

此命令在空目录生成 [一览分镜表](../templates/pages/atlas.json)、明确标注的测试音、可播放片及 `_samples/atlas-contacts-*.png` 每秒联系表。画面标有元素名；可打开某张表只看其中一类。新增注册版式同步加一个示例；测试只核对注册名是否包含在表里。一览展示能力，不规定每期的风格组合或镜头数量。

### 整片与章节

```powershell
python -m pipeline.pages assemble <影片/pages/拼接表.json> --plan
python -m pipeline.pages assemble <影片/pages/拼接表.json>
```

拼接表写 `parts: [{id, path}]`、新文件名 `out`、`chapters: [{title, from: 段id}]`，可选 `max_title_chars`。章的起点对应所选段；省略中间段的章起点即可把几段合并一章。本期方案为 6 章、每章不超过 6 字，此数目不固定给往后各期。

AI 取法，可改：60fps 下按实际片尾静音检测，每个非末段保留到念完约 0.45 秒，接口以 0.2 秒画面叠化接下一段，最后一段保留收尾。音频顺序串接，全部时刻量化为整帧；视频多留叠化余量，不从旁白里扣时间。沿用已通过各段的文字、声音和画面。输出同名前缀的 `.chapters.txt` 和 `.assembly.json`，记录每段裁剪、段起点、章节及最终流信息；已有输出一律拒绝覆盖。自动核对总帧数和音视频/容器时长，误差须小于 1 帧。此检查不等于真人已听看整片，也不产生投稿授权。

### 生图派单

```powershell
python -m pipeline.image_jobs generate <图片清单.json> <新派单目录>
python -m pipeline.image_jobs accept <某图.result.json> --saved-path <生成源文件> --run-dir <实际任务目录> --note <看图后的核验说明>
```

清单顶层为 `source`（本次需求出处）、`repository`（底座绝对路径）、`base_ref`，以及 `images: [{name, purpose, prompt, references: [绝对路径], output: 绝对路径}]`。用 JSON 序列化生成清单，别在解释器字符串里手写反斜杠。工具原样写入 Markdown，不经 shell 二次转义；控制字符、未展开的变量、重复派单或目标均报错。新图按版本命名，生成后核对真实文件，再看图并显式登记；planned 回执不是已生图或已验收。

生成提示可直接交给 Codex 内置生图。通过本机包装器派 Luna 时，先做该包装器当前版本的 DryRun；通用包装器的字段规则由基座负责，项目派单不额外补写本项目禁止的提醒。派单职责和已定要求见 [派单模板](../templates/pages/assignment.md)。

verify 检查完整来源链、视频与音频流、画布、编码、帧率、预期总帧数和总时长、可确定的流时长和起点、PNG 封面以及章节来源和范围。不能用两个同样短的音视频流或文件存在冒充完整交付。READY 只表示自动结构验收通过，不表示人工看过、语音绝对准确或已经投稿。

## 原生时间戳与共享对齐

默认 auto 先保留有效现有词轴，生成时优先 Fish 原生时间戳，缺失时使用已登记的 ChineseASR。新 TTS 默认使用带时间戳流式接口，与选择哪个词轴相互独立。消费者拼接音频，按 chunk sequence 取最新时间轴快照，应用片段偏移，不把同一片段重复快照累加。

显式 `timing --source chinese-asr --force` 对现有音频重做对齐；不会调用 TTS。旧普通配音没有原生时间戳时使用共享对齐，不能凭空补写来源或强迫重新合成。`VIDEO_FISH_NATIVE_TIMESTAMPS=0` 可显式使用普通 TTS；它只控制新生成的声音请求，不影响已接受的音频。接口解析测试不是云端账户、声线、中文读法或情感标记的实测证明；真实内容仍需单独验收。

## 隔离验收

smoke 默认使用明确的 CPU H.264 测试配置，`smoke --gpu` 使用生产编码器，不存在 GPU 失败后的静默降级。样例生成两段明确标注的合成测试音，运行有声预览与完整交付，然后改一场景验证旧成片被拒绝、部分分片复用。`--target <空目录>` 保留隔离样例，否则结束清理临时样例。真实云端测试需显式 --live-fish 和环境变量密钥，不复制原工程密钥文件。

持续集成配置包含 Windows/Linux 逻辑测试及 Linux CPU 完整短片，不使用个人配置、真实 Fish 账户或任何 ASR 模型权重。Windows 逻辑测试用隔离移动夹具模拟系统回收后端，并验证助手调用和失败协议，不证明真实系统回收可用；真实 Windows 集成需在已配置受信助手的机器上另跑 smoke。Linux CPU smoke 使用真实 Send2Trash。源码测试、本机安装、硬件实测、云端链路、持续集成和人工观看各自提供证据，不互相冒充。

## 最小依赖与使用边界

核心 Python 依赖为 requests、Playwright、非 Windows 回收所需的 Send2Trash，以及图像读取和隔离预览验收所需的 Pillow；CI 和本地均从 requirements.txt 配合 requirements.lock.txt 安装。背景生成器依赖放在 requirements-background.txt。本地识别、对齐模型和 CUDA 依赖由 ChineseASR 独立维护，不在每个视频工程重复安装。`durations` 只探测音频，chapters 只使用场景 ID、时长及章节定义，不依赖词轴；字幕、触发动画才需要词级时间。

共享对齐使用 `python -m zh_asr align`，调用既有 broker/supervisor，300 秒单场上限与显式执行超时。它对已知文案定位，不证明配音没有漏读、错读或代词；需文字复核时另用 ChineseASR 识别能力，不默认加双模型处理。LocalOCR 仅供素材文字读取，不用 OCR 重新识别自己生成的 SVG。

只读 status/verify 对同一轮文件哈希复用内存结果，文件大小、时间或身份变化会重新读取，轮次结束立即丢弃。Python 注释、排版及 docstring 不导致媒体失效，实际代码变化仍失效。历史输出没有这项代码指纹时，可能需要重建可再生画面，但不会重配音。
