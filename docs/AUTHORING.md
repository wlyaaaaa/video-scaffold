# 视频创作指南

这是通用制作工具。AI 接到题目后按内容设计画面、再写本期作品；可主动参考互联网和已有创作知识，先判断是否有实际质量收益，再采用。优先补充有用的创作方法；共用能力按根 `AGENTS.md` 的复用价值标准判断，具体画风和故事按本期需要实现。网页作品接口见 `webfilm/CONTRACT.md`；本页后半部分是分镜配音支路的 SVG 写法。

已有旁白和词轴的讲解可沿用分镜配音支路；自由绘制、形变、3D 或互动作品走网页支路。需要搭配已有视频素材时，用现有后期 compose 接片；约定作品自身的媒体限制仍按 CONTRACT 执行，不把不同用途的规则混在一起。

## 文案与创意起步

先把要说的话和推进方式想清楚，再展开画面。本人点名的真实当前期从[本期战略稿](../strategy/2026-10-bilibili-wly0829.md)进入；受众、原话、正文和已定选择沿用该处，不在本指南抄一份。

1. **定受众和一句核心意思。** 写清给谁看、他现在知道什么、看完应明白什么。核心意思用一句自然的话表达，后面的事实、旁白与镜头都服务它。
2. **准备真实材料，或明确虚构。** 真实故事先核对原件、出处和能支持的范围；事实、本人观点、AI 创意分别说明。虚构故事从起点就标明虚构，角色和情节可创作；真实内容里的比喻也要让观众分得清。
3. **提出 2—3 个开场与结构候选。** 每案给少量开场旁白、对应镜头构想和后续推进顺序，例如“先见结果→回到原因→看变化”。展示观众会先看到、听到什么，让候选之间有实质差别。
4. **主持比较并取舍。** 按理解难度、真实性和制作代价比较：是否抓住核心意思、是否夸大材料、关键动作能否做出来。主持写出推荐及理由；本人要定的选择交本人，已授权 AI 取舍的继续推进。本人原话与已定选择留在原出处，AI 补全和判断单列为“AI 取法（AI 整理，不是本人原话）”，可随时改。
5. **协作改稿，保持唯一正文。** 主持把结构和语气，执行者补写、核实和修改；回到材料复核事实，自然朗读检查拗口、停顿与信息密度。每轮改动更新本期同一份正文；分镜、配音及字幕引用该正文，候选和评论保留在旁边，不各自另写正式稿。
6. **试作关键镜头。** 从已选结构挑最影响理解或最难制作的一镜，先验证旁白和画面能共同成立；发现成本或表达问题，回到结构与文案调整，再铺开其余镜头。

例如，明确虚构的题目《丢了影子的小钟》，核心意思是“先试一次，才能找到卡住的原因”：A 用“钟还在走，影子怎么停了？”配钟摆与静止影子，按“发现异常→尝试→揭开原因”推进；B 用“它找了一整天，答案却在脚边。”配影子从底座露出，按“先给线索→回看误判→完成变化”推进。

## 先生图做设计稿，再由代码照着画

需要角色造型、插画气质或明确构图的作品，可以先做设计稿。设计稿定视觉基准：主体长什么样、比例如何、颜色和留白怎样组织；成片代码据此构造可控制的对象、镜头和动作，准确文字与数据在代码里排。

生图按核验后的现行《能力与运行方式》“生成图片和设计画面”执行：派出生图交 Luna，Codex 主对话可以直接调用内置能力；文字提示、代码实现和复核由主持按本期授权、质量要求与现行分工安排。某一期点名 Opus 或已授权的 Astra 照图实现，就在该期落实该要求。设计类先出少量候选，由本人定风格；素材类可由 AI 比对后选样，随后以选定图延续一致性。

- **图留在本期 `art/`，按版本命名。** 例如 `art/role-front_v01.png`、`art/shot-01_v02.png`；新版本保留旧图，核对文件实际落盘。把基准图路径、用途与待解决问题记进本期分镜；审定后以该图为基准，内容变了再改相应部分。
- **先提炼视觉，再拆成能动的对象。** 对照设计稿提炼身份特征、轮廓、比例、色彩和构图；角色按动作需要拆成身体、头、肢体等部件，定关节锚点和前后遮挡层。可以描图、提取路径或复用合适工具；检查提炼后的整体是否像设计稿，再安排动作。
- **按选定支路实现。** 分镜配音支路只生成静态 SVG，布局与动画分离，动画交 `seekTime(t)` 驱动；网页支路在本期用 Canvas/SVG/WebGL/DOM，画面由绝对时间 `window.webfilm.render(t)` 决定，离线声音由 `audio(ctx)` 一次性安排。两者运行时都不联网，不靠真实时钟、计时器或运行时随机数推进，不用视频生成模型。
- **先验关键镜头，再铺开。** 把设计稿和代码关键帧以同一画幅、同一显示尺寸并排看，逐项对照角色身份、轮廓、比例、色彩和构图。另看动作极值、遮挡关系和转场前后；完成构建与布局检查后，再看局部有声动作，确认主体、文字和声音落点一起成立，再扩展其余镜头，最后按对应工作流验整片。

角色、画风和路线以本期选择为准；这套做法可用于不同题目，具体样稿只承担示范和对照作用。

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

## 图文页：一页上元素按念到的词进来

适合讲清“几件事、几条、几种”的段落：画面是一张页（米白底、黑色粗字、重点词绿色、旧说法灰或删除线、细线时间轴、等宽小标签、白色圆角卡片、底部分段进度），可配写实照片或抠图角色，也可以没有角色。走分镜配音支路，零件在 `v2lib` 后半部，样式只取 `config.PAGE_THEMES` 一处。

**内容与动作。** 有旁白时，字不早于念到它的时间出现。每个新内容绑真实词轴，重复词用 `index`，错开用非负 `offset`。入场、停留、离场和转场由内容与所选参考决定；逐字、描线、图表增长、局部持续运动、推拉和叠化都可组合。`scene_base.html` 已有这些原语，`pipeline.components` 与 `v2lib` 已有组件，优先复用，不另起动画引擎。无声图形和已讲过的内容可以随镜头组织运动。

**通用动作默认（AI 取法，可改）。** `config.PAGE_MOTION` 集中提供 0.55 秒文字入场、0.7 秒主视觉入场、0.65 秒描线、1 秒数字增长、0.12 秒错开、100 像素位移和 0.18 秒换页。默认连续采样，不强制定格。原文文字自动按每字词轴揭示，图片可轻微推近，抠图可轻微浮动；数字与横条一起增长，进度条在整段里连续前进。标题、正文、标签的建议字号分别约 220–300、96–144、64–84 个 4K 像素，按实际构图调整；小字号提示不阻止创作。`data-ease="out|in-out|linear"` 可选缓动。超过 3.5 秒的主内容静止会提示检查；进度条不能掩盖主内容停滞。这些是可覆盖的创作默认，不是用户禁令。

**看参考的方法。** 参考作品看它的设计语言和作者公开的做法（提示卡、简介、置顶评论），例如 BV1s2aV6cE5i 作品 01 是“搜索信息 + JavaScript 动态图形，用 OpenAI 的设计元素”。怎么动、多快、什么节奏由做的人凭动态图形的感觉定，不逐帧照抄、不量参考的时长；参考只当底线，目标比它好。

**主题。** `config.PAGE_THEMES` 定颜色（page/ink/accent/muted/faint/rule/block/pen）、字体（heavy/sans/mono/hand）、边距、卡片、气泡、进度条和烧录字幕样式；`config.PAGE_THEME` 选当前主题，现有 `white-green`（默认，白底绿）和 `paper-red`（米色纸页、红笔、胶带照片卡）。零件的颜色和字体参数写角色名，换主题或在本期 `L.use_theme(dict(L.theme("white-green"), accent="#..."))` 改几项，不改零件。背景用 `L.page_background(<本期>/assets/page.png)` 写一张主题底色的整画布图，把 `config.BG_VIDEO` 指向它（静图会铺满画布且不动；纸纹等图片也可以直接作背景）。

**零件。** 文字一律用 `page_text`（可传 `[("说了", None), ("好几遍", "accent")]` 分段上色）。

| 要放的东西 | 零件 |
|---|---|
| 页眉：等宽小标、大标题、副标题 | `page_title` |
| 编号、点亮当前编号 | `number_row`、`mark_label` |
| 左侧目录、短横清单 | `nav_list`、`bullets` |
| 大数字、引语、等宽胶囊标签 | `figure`、`quote_block`、`tag` |
| 旧说法（灰字、到点划删除线） | `old_text` |
| 细线时间轴、坐在轴上的时间块（实黑、绿、浅灰、斜线） | `time_axis`、`time_block` |
| 方块计量（■■■□，每念一次亮一格） | `meter` |
| 白色圆角卡片、照片卡、抠图主体 | `card`、`photo_card`、`cutout`（嘴的位置用 `image_point`） |
| 对话气泡、规整框、手画圈、一笔笔写、“正”字计数 | `speech_bubble`（外框 `bubble_bounds`）、`hl_box`、`pen_circle`、`pen_strokes`、`tally` |
| 底部分段进度 | `progress` |
| 逐字一行写出 | `hand_line` |

**从分镜表到页面。** 分镜表就是一个 JSON 文件，`python -m pipeline.pages <表.json> plan|stills|render` 直接把它做成有声、带字幕的 1080p 片子（详见 `pipeline/pages.py` 文件头）。一张表管一段片子：

- `narration`：按顺序用哪几段配音，`audio` 指 mp3，词轴默认取同名 `.timestamps.json`，原文默认取同名 `.original.txt`；只要其中几句时写 `take`（原文里连续的一段，按句子边界写）。
- `theme`、`out`、`work`、`tail`（片尾停留秒数）、`progress`（底部分段进度，可每页覆盖）、`transition`（换页秒数，默认取动作配置）。
- `pages`：每页写 `say`（这页念的原句，方便对照）和 `elements`。页面在它第一个绑词前 0.08 秒准备换页，内容从词轴时刻开始；`top`、`width`、`x` 可改版式。`step_fps` 默认 0，显式填写正数才使用定格采样。
- 元素：`kicker` 等宽小标、`title` 大标题、`big` 大字句、`text` 正文、`note`（`label` 小标签 + 一行粗体）、`old` 旧说法（`strike` 绑划线的词）、`bullets` `[[文字, 绑词], …]`、`numbers`（`mark`/`mark_at` 点亮第几个）、`figures`、`bars`（横条对比）、`meter`（`steps` 每格绑词）、`quote`、`tag`、`photo`、`cutout`（`mouth` 嘴的相对位置）、`bubble`（`box_at`/`box_label` 框出并标字）、`gap` 空白。文字里 `*重点*` 用强调色、`~旧说法~` 用灰色。
- 绑词 `at` 写原文里显示的字（如“846”，不用写读法“八百四十六”）；同页第二次出现写 `词#2`，错开写 `词+0.2s`（偏移带 s，“GPT-6”这类原文不会被当成偏移）。缺失、未命中或负偏移直接报错，不退回页首。原文文字自动逐字显现；概括标题与图形用明确的 `at`，已讲过的内容可在后面重现。不用写坐标：左栏文字自上而下排，右栏放主视觉；个别元素可写 `y`、`x`、`cx`/`cy` 等覆盖。
- `anim`、`dur`、`shift` 可覆盖入场；`exit_at`、`exit_dur` 安排离场。照片 `hold: false` 关闭轻推近，`zoom` 改推近比例；抠图 `ambient: false` 关闭轻浮动。`bars` 的 `dur` 控制条形和数字，`label_at` 单独绑定标签。原始文字、单位和未来数值要分别按词轴组织。
- 复杂、一次性的主视觉写在本期静态 SVG，元素用 `fragment: "visual.svg"` 接入。片段可直接用现有原语和 `data-cue`、`data-cue-index`、非负 `data-cue-offset`，分镜表统一解析成本页秒数；找不到的词仍失败。图表、流程和准确文字用代码；写实素材用生图，全部在本期目录保存。

**通用版式（动态图形，`pipeline/boards.py`）。** 下面几种元素各自是一整块会动的版式，绝对定位、带默认坐标，按词轴安排每个动作；一页可以叠几种，用 `exit_at` 让一组退场，用 `wipe` 换段落。所有字都逐字出现：原文里有的字用各自被念到的时刻，概括字样（卡片标题、标签）从绑定的词起快速打出。

| 元素 | 画面与动作 | 主要字段 |
|---|---|---|
| `head` | 左上粗体小标题逐字打出，后跟绿色胶囊标签弹出，下一行灰色小字可分段出现 | `head`、`at`、`kicker`/`kicker_at`、`tag`/`tag_at`、`sub`（字符串或 `[[字, 绑词], …]`） |
| `claims` | 说法堆叠：当前说法大字逐字出现，重点被绿色划过（底色条 + 逐字变绿）；下一句来时旧说法缩小上移成一摞；到 `strike` 时变灰并划线。`quote: true` 加引号，`*…*` 整句绿色 | `claims: [{text, at, mark, mark_at, strike, size, quote}]`、`y`、`size`、`stack_y` |
| `deck` | 右侧卡片组：一张接一张替换（旧卡淡出上移，新卡升起；`enter` 可选 `rise`/`pop`/`drop`/`iris`）。卡内：等宽小标签、标题（右侧可配动态图标 `icon`）、内容块 | `deck: [{at, label, title, title_at, icon, icon_at, body, frame, pad, enter}]`、`x`/`y`/`w`/`h` |
| 卡片内容 `body` | `photo`（照片缓慢推近，`bleed` 铺满卡片）、`wave`（说话声波，`at`–`until`）、`grid`（方块逐个出现，`flip` 到点变黑）、`comments`（短评论气泡逐条弹出）；`pipeline/board_bodies.py` 另有 `chat`（对话气泡，可描框/加注/变淡）、`dial`（表盘：说好的时长→拖满一圈）、`scan`（人一眼圈出毛病、扫描带扫过）、`gauges`（容量槽依次涨、全满变黑一震）、`ring`（注意力从一点扫满一圈）、`bar`（进度条涨或退）、`flow`（点从左框流到右框）、`terminal`（代码行依次写出）、`inspect`（一排排看着都对、逐行打勾，放大镜移到一行，那行原来不对：`rows`、`tick_at`、`lens_at`、`wrong_at`、`target`）、`todo`（任务单逐条列出、打勾；某条 `drop_at` 划掉掉落，`ghost_at` 留虚线空位，`restore_at` 补回；`absent` 一开始就不在；`scan_at` 扫描带扫过）、`level`（水位条按 `steps: [[绑词, 比例, 时长?, 颜色?]]` 一段段涨，碰 `limit` 虚线时 `hit_at` 一震，`blind_at` 盖上划掉的眼睛表示“看不到”）。卡片标题图标另有 `check`、`hook`、`eye`、`lock`；`grid` 可写 `glyph: "image"`（图片占位）、`center: true` | 每块 `{kind, …}` |
| `cards` | 一排（或一张）固定卡片，各自到点升起、一直留着，卡内同 `deck` | `cards: [卡…]`、`x`/`y`/`w`/`h`/`gap` |
| `tiles` | 分类网格、并列对照或逐项清单；卡片按词轴进入，可移位、加锁、划线或变淡 | `tiles: [{title, at, title_at?, size?, lines: [{text, at, size?, color?, gap?}], dark?, accent?, focus_at?, lock_at?, strike_at?, dim_at?, move_at?, move_to: [x,y]}]`；`cols`、`x/y/w/h/gap` 控制网格，`w/h` 是每张卡的大小 |
| 卡片内容 `context_stack` | 对话条保持固定位置，最新一条突出；旧条目可淡去、聚拢到窗口中 | `body: [{kind: "context_stack", items: [{at, text?, text_at?, size?, dim_at?}], window_at?, collapse_at?, h?}]`；文字仍使用逐字词轴，聚拢为可完成并检查的有限动画 |
| `timeline` | 细轴画出、刻度依次弹出；节点按念到弹出，最新节点绿色呼吸；`trace` 让一个点沿轴走过去，刻度随之变绿 | `timeline: [{label, at, x, anchor, sub}]`、`y`、`trace: {from, to, at, until}` |
| `checklist` | 清单逐条出现，每条配会动的图标（`bolt` 呼吸、`wander` 点沿弯路走、`burst` 冲击波、`math` 描线、`quote`）；绿色指示条跟着念到的那条走，旧条变淡 | `checklist: [{text, at, icon, pre, pre_at}]`、`focus` |
| `tally` | 数字条形：条从左长出、数字滚动、单位按念到出现；有 `total` 时后面的条移上去接成一整条，总数滚动（小标签在数字上方） | `tally: [{label, value, at, dur, unit, unit_at, number}]`、`total: {label, at, value, count_at, unit, unit_at}` |
| `wipe` | 底色圆从一点扩大盖住整页（边上一圈细绿线），用在换段落前 | `wipe`（绑词）、`x`/`y`、`dur` |

**用标志代表某一方（logo）。** 圆点代表某个公司或模型时（Claude、Claude Code、Opus 一方；OpenAI、Codex、GPT 一方……），可以换成标志图：分镜表顶层写 `"brands": {"claude": "../art/brand/claude.png", "openai": "../art/brand/openai.png"}`，元素里写 `"logo": "claude"`（也可直接写图片路径）。标志放进白底圆里，按圆裁切，透明底和纯白底的方图都行；找不到图直接报错。不写 `logo` 的地方画法和原来完全一样。支持的位置：`timeline` 节点（`logo`、`logo_r` 默认 52，最新节点描绿圈）、`tally` 行（名字前放标志）、卡片 `logo`（标题右侧，和 `icon` 二选一）、`comments` 胶囊（条目写 `[文字, 绑词, 标志]` 或 `{text, at, logo}`）、`focus_network` 节点、`cross_check` 的 `checker.logo`、`lanes` 的 `spawn.logo`、`condense` 的 `worker.logo`。圆里原来写名字的节点（如核对者、分出去的模型）有标志时名字改写在圆下方，保持看得清。标志只代表“哪一方”，不代表数据。

**动画放完才退场（出片时检查，不过就报错）。** 每个有限的动画（入场、描线、滚动、移动、划线……）都要在它所在的组退场（`exit_at`）、整页被 `wipe` 盖住或换页之前放完，并停够 `config.PAGE_MOTION["hold"]`（0.25 秒）；呼吸、循环流动、照片推近、声波和进度条不算。念得快放不下，就缩短动画、提前到前一个词，或换动法，不许半路切走。本人已审定、不再改的旧元素可写 `"hold_check": "warn"`，只提示不拦。一段配音一张表整段出片，不分段拼接。

这些版式用到的运行时原语：`type`（`data-glyph-times` 逐字、`data-glyph-from` 由浅变深）、`keys`（关键帧移动/缩放/透明度）、`mark`（按字的位置画底色条、删除线、下划线）、`iris`（圆半径，盖页或圆形揭示）、`wave`、`shake`，以及文字的 `data-follow`（单位跟在滚动数字后面）。一期的内容写在本期 `pages\*.json`，版式不够用时在 `boards.py` 加一种（会复用的才加）。

**词轴动态图解（`pipeline/board_diagrams.py`）。** 复用同一运行时，不引入另一个动画引擎。所有版式都有顶层 `at`，坐标仍为 4K 画布；准确标签逐字走词轴。图解是表达关系的示意，不能当成真实监控数据。

| 元素 | 动作与主要字段 |
|---|---|
| `screenshot` | 值为完整原截图路径；按 `at` 平移落入、轻微缩放压实。`x/y/w` 定位置和宽度，高度按原图比例计算；不裁切、不改像素、不重画内容。`focus: [x,y,w,h]` 是原图归一化区域，只叠加描边；`focus_at` 单独定强调时刻，`caption/caption_at` 可加图外说明。整张截图在关联内容念到后才出现。 |
| `repeat_flow` | `{input, repeats: [绑词,…], result, result_at}`：相同输入卡片逐次汇入同一输出；`x/y` 调整整组。适合反复沟通、重试、结果未变。 |
| `focus_network` | `{center?, nodes: [{label?, at?, angle?, label_offset?, size?}], visits: [{node, at}], expand_at?}`：注意点沿关系移动，或从一个节点扩展到所有节点。`x/y/r` 为中心与半径；无标签节点仅作图形，标签仍独立绑定词轴。 |
| `time_stretch` | `{start_label, stretch_at, end_label, end_at, units?}`：圆周计时与单位格展开同步；`x/y/w` 调整区域。`end_at` 必须晚于 `stretch_at`，`units` 默认 24，可按真实含义改。 |
| `scan_grid` | `{reveal_at, miss_at, cols?, rows?, odd?}`：规则格中有一个异形，扫描带经过第一行，异常独立圈出。`odd` 为从 0 起算的异常索引，`x/y` 为左上角。表示“扫描”与“发现”是两件事。 |
| `capacity_gauges` | `{items: [{label, at},…], full_at, noise_at?}`：容量槽按各自词轴上升，在 `full_at` 到顶，随后轮廓轻震；不额外生成百分比。`x/y` 定左上角。 |
| `device_flow` | `{phone_label, computer_label, computer_at, move_at}`：手机内文件块移出，电脑界面按时进入，连接点沿线流动。顶层 `at` 绑定手机，`x/y` 调整整组。 |
| `condense` | `{rows: [{at, user?, keep?, lines?}], collapse_at, summary_label?, stamp?: {text, at}, worker?: {at, label, below?}, keep_at?}`：一长串对话按念到依次进来，到 `collapse_at` 压成一张摘要卡；`keep` 的几条缩进摘要，其余用户原话变淡掉落；`stamp` 盖章、`worker` 画照着摘要干活的 AI（`below` 放在摘要下方），`keep_at` 圈出留下的几条。`summary_w/h/x/y`、`row_h`、`chip_scale` 调尺寸。 |
| `cross_check` | `{left_label, right_label, checker: {label, at}, rows: [{at, status, link_at?, status_at?, note?, right_text?, restore_at?}]}`：左列原话、右列结果，中间核对者逐条连线；`status` 为 `ok`（对上打勾）、`missing`（虚线空位）、`unproven`（问号）、`changed`（划掉、不等号）。 |
| `lanes` | `{lanes: [{label, at}], spawn?: {at, node_text?, offset?}, dots?}`：几条并行轨道，主线一直在走，另一条从某点分出来并行跑，互不等待。 |
| `rail` | 值为步骤列表（字符串或 `{label, at}`），`current` 当前第几步、`go_at` 从上一步走过来：章节进度轨，已讲过的黑点灰字、当前绿点绿字，没讲到的只留空点、不提前写字。 |
| `focus_network` 补充 | `node_r`、`hub_r`、`center_size` 放大节点和中心；`center_at` 让前面已讲过的中心名字从该词起直接打出。 |

一段拆成多次出片时，`progress` 可用四项 `[总段数, 当前段下标, 结束比例, 起始比例]`，例如后半段从 0.42 走到 1；原来的三项写法继续从 0 开始。起止比例只控制这一段的进度，不修改旁白时钟。

素材写现有路径；要生图的按[先生图做设计稿](#先生图做设计稿再由代码照着画)交出，落盘后填路径。同一个主体只出现一次：照片卡里放场景，角色另用抠图从卡前出来，不在卡里和卡前各放一只。先做一段几十秒的样片定稿，再按同一张表往下写。表里没有的版式，先在 `PageBuilder` 加一种元素（会复用的才加），一次性的画面直接写进本期片段。

**背景。** 图文页默认用主题底色，保持白底绿的清晰层次；分镜表 `background` 可指定已有图片或视频。是否使用流体玻璃、纹理或环境运动按本期视觉方向判断，背景运动不限制前景动画。

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
3. **背景必须透明。** 未提供本期视觉方向时，前景默认文字 `#0C2B1B`、强调
   `#1F7A4D`，留白优先；有选定视觉方向时，可更换前景色彩，并使用有明确表达作用的
   卡片、阴影和边框。

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

本期可选写 `scripts/visual-direction.md`，描述主体、造型、配色、构图和动作目的。
生成提示词时只读取一次，把同一份方向用于全场；没有该文件就使用默认前景方向。
例如（只是写法示意，具体角色与画风按本期选择）：

```text
主体是圆耳小狐狸，头大身小；低饱和水彩赭橙与靛蓝，角色在左，道具卡片在右，卡片承载路线提示。
让狐狸伸手指向卡片上的岔路，突出“先选方向，再迈步”；造型与配色沿用 art/role-front_v01.png。
```

这份方向只影响前景提示；选定的背景需在本期另行实现与验收，文件不会自动把默认背景换成纸纹。

AI 或人工审阅结果后，只把片段保存为 `scene_html/fragment_NN.svg`。不要把提示词中的
说明、Markdown 代码围栏或解释文字写进文件。没有素材时不要虚构路径。

## 动画原语

常用 `data-anim`：

| 值 | 效果 | 额外属性 |
|---|---|---|
| `type` | 文字逐字出现 | `data-dur` |
| `fade` / `fade-up` / `fade-left` / `fade-right` | 淡入与位移 | |
| `zoom` / `pop` / `stamp` | 缩放、落锤与印章 | |
| `drop` | 照片卡落到纸面：下落、微转后停住 | `data-shift`、`data-spin` |
| `draw` | 描边生长 | 箭头可用 `marker-end="url(#arrow)"` |
| `count` | 数字滚动 | `data-to`、`data-decimals`、`data-prefix/suffix` |
| `grow-bar` / `draw-area` | 横条或面积生长 | `data-grow` |
| `wipe` | 幕布揭示 | `data-dir` |
| `highlight-sweep` | 高亮扫过 | `data-mode` |
| `trace-dot` / `move-along` | 沿路径描线或移动 | `data-path` / `data-dot` |
| `float` / `drift` / `pulse` | 持续悬浮、漂移、呼吸 | 对应幅度/频率属性 |
| `holo-3d` / `flip` / `morph` | 3D 面板、卡片翻转、路径形变 | 见 `ADVANCED_FX.md` |
| `flow-blob` / `burst` / `shockwave` | 流体、粒子和冲击波 | 见 `ADVANCED_FX.md` |

`fade-up` / `fade-left` / `fade-right` / `drop` 可用 `data-shift` 改位移像素。`<g data-step-fps="12"/>`（`v2lib.step_fps(12)`）是可选的定格效果；不写或写 0 时连续采样。逐字文本可用 `data-glyph-times` 指定每个字的本页时刻，`data-glyph-fade` 改单字淡入时长；页生成器从既有词轴填入，文字颜色保持原分段设置。

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

图文页版式用 `v2lib` 后半部的图文页零件和 `config.PAGE_THEMES` 主题，做法见上文[图文页](#图文页一页上元素按念到的词进来)。

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
