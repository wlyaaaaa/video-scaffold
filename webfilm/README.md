# 网页代码短片

给模型 [同一份约定](CONTRACT.md)、创作要求和工具，让它写原创网页作品；制作中用 preview 实时有声审片，修改后刷新，确定画面后再 render 出片。`webfilm/` 是独立支路，整体复制后仍可作为 Python 包使用；无需旧分镜、SVG 模板、配音或词轴流程。

```powershell
pwsh -File .\webfilm\run.ps1 doctor
pwsh -File .\webfilm\run.ps1 preview "entries/A/v1"
# 已有配音可在同一声音时钟播放；不调用配音服务，不写入作品。
pwsh -File .\webfilm\run.ps1 preview "entries/A/v1" --narration "output/narration.wav"
# 后台只提供地址用 --no-open；预览服务按 Ctrl+C 停止。
# 发布当天，A/B 获得相同 CONTRACT.md、要求和工具，各生成 entries/<名字>/v1。
foreach ($name in @('A','B')) {
  pwsh -File .\webfilm\run.ps1 render "entries/$name/v1" "output/$name-v1.mp4"
  pwsh -File .\webfilm\run.ps1 review "output/$name-v1.mp4" "output/$name-review-v1"
}
# 各自根据 review 结果修改一次，保存为 entries/<名字>/v2，保留 v1。
foreach ($name in @('A','B')) {
  pwsh -File .\webfilm\run.ps1 render "entries/$name/v2" "output/$name-v2.mp4"
}
```

也可通过 `python -m webfilm <命令>` 使用。作品按约定提供 `work.json`、`window.webfilm.render(t)` 与可选 `audio(ctx)`；可用 Canvas、SVG、WebGL 或普通网页，不要求旧项目的静态 SVG。`runtime.js` 是可选现场播放器。双方用相同捕获配置，默认 4K、60fps、20秒，也可明确统一改为 1080p。完整参数见各子命令 `--help`。

创作思路与按需参考见 [创作指南](../docs/AUTHORING.md)：先按题目想清楚怎么讲、挑关键镜头看效果，再按本期作品写代码；共用层按根规则的复用价值标准取舍。[从想法，到表达](examples/story-flow/brief.md) 是 24 秒原创代码与程序音乐样片，可直接作为预览和渲染的输入，不是模型比赛的统一创作模板。

## 制作时先看关键帧与局部

```powershell
# 不必先渲整片，直接检查关键时刻。
pwsh -File .\webfilm\run.ps1 stills "entries/A/v1" "output/A-stills" --at 1.5 4.5 7.5 --1080p
# 仅渲原作品第 6 秒到第 9 秒，画面与音轨都保留原来的时间位置。
pwsh -File .\webfilm\run.ps1 render "entries/A/v1" "output/A-detail.mp4" --start 6 --end 9 --1080p
```

`stills` 输出原画幅 PNG、带秒数的拼图与来源记录；时刻自动排序去重。采样时刻、片段起止须落在 60fps 的帧边界，片段为 `[start,end)`，关键帧不采作品终点以外的帧。省略 `--start/--end` 保持整片渲染。输出使用新文件或新目录，不覆盖旧结果，也不改 `work.json` 的总时长。

交互作品在这两个命令中都传入相同 `--actions actions.json`：工具按原时钟重放起点之前的操作，只跳过前段截图和编码，因此重放仍需时间。带声作品先从原片 0 秒安排音频，片段按相同区间裁切；关键帧也执行音频图以保持与整片一致。来源记录注明实际范围，局部通过不等于整片通过。默认时长上限与整片一致，长作品显式使用相同的 `--max-duration`。这些入口只处理约定作品，普通网页仍走 `capture`。

看过实时预览后再渲整片，review 用于检查实际成片。模型比较时给双方相同工具和预览机会，仍保留各自 v1、一次审阅修改与 v2。

## 显卡出片与断点

render 默认 auto：一个全屏 Canvas2D 或 WebGL 画布使用 WebCodecs 硬件编码请求，逐帧按绝对时间调用原 render(t)，保留全部编码帧与时间戳；FFmpeg 只封装并合成音轨。可见 DOM/SVG、交互光标或无法证明完整画面的 CSS 效果继续走截图路线。`--renderer webcodecs` 要求快路，`--renderer png` 显式使用原来的 PNG、x264 fast CRF18。硬件编码使用 quality 模式与 120Mbps 请求，不能把该码率直接称为 CRF18 的等价质量，编码器/颜色证据写入来源记录。GPU 绘制与旧软件栅格化可能有抗锯齿差异。

Windows 快路开启 Chrome 的共享显卡图像编码路径；渲染器新建的临时画面和匿名浏览器目录在退出后直接删除，失败会报告路径。不会删除作品、成片或断点缓存。原 PNG 路线和显式回收接口保留原来的回收方式。

默认记录本次范围的首、中、末三个源帧样本；`--verify-frames` 才记录全部源帧像素，会增加读回耗时。compare 明确返回 `all_source_frames_compared` 与采样位置，仍逐帧核对两份 MP4 的解码像素和离线 PCM。抽样不能证明未采到的像素相同。

完整成功段保留在输出目录的 `.webfilm-cache/`，中断后用相同作品、画幅、范围重跑，换一个未存在的输出名称即可恢复；损坏或来源失配的段会重建。缓存段最多两秒，并在声明的场景边界切开。旧作品修改任意输入后重建画面；按场景拆文件的作品可在 work.json 增加可选声明，例如：

```json
"render_segments": [
  {"start": 0, "end": 12, "files": ["scene-one.js"]},
  {"start": 12, "end": 24, "files": ["scene-two.js"]}
]
```

范围须完整覆盖作品并落在帧边界。未列出的文件视为全局依赖，共用文件应在所有使用它的场景列出；声明是作者对影响范围的说明，程序不能证明漏报的跨场景状态。修改某场景的文件只重建依赖它的段，源码变更后的采样相同不会作为复用依据。音轨仍从零安排完整母带，最后按原采样位置裁切并合成。缓存属于可再生文件，确认不再需要恢复后可以清理，原件和成片保留。

`demo <新目录>` 只写入不存在或全空的目标目录，是 AI 补充的渲染验收材料。样片含 20 秒水彩纸面动画、12 秒互动网页、8 秒知识卡片、4 秒片头、6 秒片尾和静态封面。打开任一 `index.html` 即可现场播放，点“开启音乐”解锁声音；音乐、低音、轻打击和飞行音效都由代码生成。动作样例在 `interactive/actions.json`。

顶层 `prompt.txt` 保存原始统一提示，`site.json` 保存虚构彩排作者与版本；两位作者都指向同一代码作品，不能把样片展示说成真实模型比赛。参考只用于观察纸纹、水彩、手绘线条和连贯旅程，样片不包含参考图或任何预录媒体。

附加能力包括 `discover INPUT` 发现普通网页入口、`capture INPUT output.mp4 --entry index.html --duration 20` 捕获已有网页；有多个入口时明确指定 `--entry`。模型自行导出的 MP4 也可 review 或进入后期。compare 检查两次捕获，compose/cover/package/upload-template/narrate 处理已选产物；投稿模板只准备内容，不替本人发布。普通网页的时钟与音频覆盖范围按实际方式记录，不能冒充约定接口的逐帧与离线音频证明。

运行依赖为原生 Python 3.11+、Playwright、Pillow、requests，以及 FFmpeg / ffprobe 和本人自己的 Chrome；移到另一台机器后先重新配置这些工具。Windows 的回收使用已有受信助手，非 Windows 使用 Send2Trash。机器适配可用 `WEBFILM_MACHINE` 显式指向 JSON，或通过 `WEBFILM_CHROME`、`WEBFILM_FFMPEG`、`WEBFILM_FFPROBE` 等环境变量设置。机器路径和凭据不进入作品配置，重型 GPU 编码走现有 Broker 租约。

独立搬走后，Python 依赖可按 `python -m pip install -r webfilm/requirements.txt` 安装。narrate 是显式外接现有 Fish 生产能力的适配器，调用时指定 `--legacy-root`；其余命令不导入旧 pipeline 或业务 config，不需要旧生产线目录。

check 的通过表示可检查的目录、资源和结构符合约定；有声样片、同机重复捕获、成片与人工观看各自提供自己的证据。作者的生成来源声明与人工审阅独立保留。

渲染保留 `.mp4.wav` 离线母带和来源记录。相同作品、动作、画幅与 Chrome 的后续渲染只复用字节核验通过的同源母带，来源记录标明复用位置；任何源码或素材变化都会使复用失效。这样可以避开浏览器浮点音频计算偶发的末位变化。compare 核验当前影片、每帧像素与母带字节；它不承诺两次完全独立的冷启动音频计算逐位相同。作品和产物应放本期独立目录，不写到通用源码树；复用的母带属于该期成果，保留到本期结束。

compose 的时间线为 `{"clips":[...]}`：单片提供 `path/start/duration`，并排提供 `left/right/duration`，字幕为片段内 `cues:[{start,end,text}]`，旁白为 `narration`。两遍响度处理默认 -14 LUFS、真峰值目标 -1.5 dBTP，AAC 48kHz 双声道；编码后测量值写入来源记录，AAC可能带来少量峰值偏移。自行导出的视频可标 `self_exported:true`，保持源帧时钟，整片相应允许可变帧率，画幅只等比缩放并加边。CPU 是当前编码路线，不占用 GPU；已有分镜支路的 GPU 操作继续使用原有租约。

附加 capture 接管主页面的 rAF、定时器、Date/performance、Math.random/视觉用 crypto 随机数、CSS/WAAPI 与常见 Web Audio 排音。固定 `--seed`，按帧号向前重放；要倒放或跳回需重新加载。Worker/AudioWorklet、声频分析器驱动画面、设备媒体流、随时间断开音频图以及未登记的外部时钟不能据此保证确定性，会报出已发现的限制。此时接收模型自行导出的 MP4，或另作明确标注的实时录制；当前工具没有实现可保证音画质量的通用实时录制。没有任何网页工具能无条件接管任意程序。
