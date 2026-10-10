# 进阶画面组件速查

分镜配音支路的每帧画面由 `seekTime(t)` 决定。新增动效只根据传入时间和固定输入计算；需随机效果时，在 Python 侧用固定种子生成参数。布局与动画属性分层，完整写法见 [创作指南](AUTHORING.md)。

## 从表达找到现成做法

先选想讲清的变化，再看对应实现。下面是可查用的方法索引，案例的画风与镜头数由本期内容决定。

| 想讲什么 | 现成手段 | 实例和源码 | 建议查看时刻 | 已有局限 |
| --- | --- | --- | --- | --- |
| 一个数有多大、落在哪个区间 | 数字滚动、共用刻度的仪表 | [组件源码][v2lib]：`num_burst`、`gauge`；[运行时][scene]：`count`、`tilt` | 组件局部 0.1–2 秒，看数值到位与指针落点 | 刻度、单位、区间和数值需本期明确提供；粒子只用于强调 |
| 揭开信息、让一组数据出现 | 平面翻转与看板进入 | [组件源码][v2lib]：`card_flip`、`holo_panel`；[运行时][scene]：`flip`、`holo-3d` | 组件局部 0.4–1.5 秒，看侧面进入到正面可读 | 是 SVG 平面的透视变换；`settle=False` 保留倾角会降低可读性 |
| 从锁定到开放、同一形状改变状态 | 只让关键部件形变 | [组件源码][v2lib]：`lock_unlock`、`morph_path`；[运行时][scene]：`morph` | `lock_unlock` 局部 0.65–1.65 秒，看锁梁抬起 | 形变限单段子路径；多部件要拆开，否则可能出现跨接直线 |
| 流转、循环与靠近融合 | 粒子沿路径移动，滤镜融合邻近圆点 | [组件源码][v2lib]：`gooey_flow`；[运行时][scene]：`flow-blob` | 组件局部 0.5–5 秒，看源头、终点与循环衔接 | 是循环流向示意；粒子数量不自动代表真实流量，也不模拟液体物理 |
| 用同一物件串起因果与节奏 | 圆点沿主线移动，再展开为下一镜 | [圆点样片源码][story]：`drawStructure`、`drawRhythm`；[分镜说明][story-brief] | 7.5、10、13.5 秒；转场另看 5.5–6.5、10.5–12.5 秒 | 24 秒代码样片；有程序音乐，没有真实旁白或业务数据 |
| 温柔、探索、从日常进入想象 | 固定纸纹、多层透明色块、草地到星空 | [水彩小鸟原件][bird]：`wash`、`meadow`、`night`、`paint`；[彩排交付记录][delivery] | 3、7.5、10.5、17.5 秒；草地到夜空另看 8.8–10.3 秒 | 水彩感由 Canvas 色块叠加近似；彩排记录把人工连续观看与听感列为后续事项 |
| 主体前进时，翅膀和配件各自运动 | 拆开绘制，在局部关节先平移再旋转 | [小鸟关节源码][bird]：`bird` 的翅根 `(-33,3)`、围巾根 `(-1,53)`；[彩排记录][delivery] | 8.2–9.4 秒连续看；可对照 8.4、8.6、9 秒 | 这是代码绘制部件的局部旋转；没有通用骨骼、蒙皮或自动拆图功能 |
| 操作后得到看得见的回应 | 点击改变状态、滚动换区域、悬停强调 | [互动演示源码][demo]：`_INTERACTIVE` 与 `create_demo` 的 `actions.json` | 按演示动作脚本：1 秒点击，2–3 秒滚动，4 秒悬停 | 点击后花朵立即变大，没有渐进生长；演示无音轨，捕获须带同一动作脚本 |

组件行给的是默认参数、未绑定 `cue` 时的局部查看范围，并非已有成片时码；绑定后以当前词轴与参数为准。样片行给的是作品时码；互动行需先用现有 `webfilm demo` 生成隔离作品，再带它的动作脚本查看。

`data-anim` 只由分镜运行时 [scene_base.html][scene] 解释。网页作品须在本期 `window.webfilm.render(t)` 中实现对应画面，交互状态还需同一动作脚本；同名效果不会自动调用分镜组件。接口见 [网页作品契约](../webfilm/CONTRACT.md)。

上述时刻是按源码与分镜说明选出的观察点，用于查动作和转场；不是当前视觉、听感或投稿质量的证明，实际质量仍需在本期预览与成片中审阅。

[v2lib]: ../v2lib.py
[scene]: ../templates/scene_base.html
[story]: ../webfilm/examples/story-flow/index.html
[story-brief]: ../webfilm/examples/story-flow/brief.md
[demo]: ../webfilm/demo.py
[delivery]: E:/Projects/VideoProductions/20261004-webfilm-rehearsal/DELIVERY.md
[bird]: E:/Projects/VideoProductions/20261004-webfilm-rehearsal/works/animation/index.html

## 分镜组件速查

先 `import v2lib as L`。以下函数生成 SVG 片段，可传 `cue=` 绑定旁白中的真实词，或用 `delay=` 设置兜底时间：

| 用途 | 函数或原语 |
| --- | --- |
| 3D 看板、翻转 | `L.holo_panel(...)`、`L.holo(...)`、`L.card_flip(...)`；`holo-3d`、`flip` |
| 路径形变 | `L.morph_path(...)`、`L.lock_unlock(...)`；`morph` |
| 流体与粒子 | `L.gooey_flow(...)`、`L.particle_burst(...)`、`L.coin_fountain(...)`；`flow-blob`、`burst` |
| 数字与标记 | `L.num_burst(...)`、`L.convert(...)`、`L.discount_seal(...)`、`L.pulse_badge(...)` |
| 氛围和仪表 | `L.ambient_motes(...)`、`L.gauge(...)`；`drift`、`pulse` |

颜色常量可用 `L.INK`、`L.ACCENT`、`L.RED`、`L.GOLD`。函数参数以 [v2lib.py](../v2lib.py) 为准；手写原语的实际属性以 [scene_base.html](../templates/scene_base.html) 为准。改完片段运行 `build`、`lint`，再听看 `preview`；确认后才渲染成片。
