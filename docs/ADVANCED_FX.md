# 进阶画面组件速查

每帧画面由 `seekTime(t)` 决定。新增动效只根据传入时间和固定输入计算；需随机效果时，在 Python 侧用固定种子生成参数。布局与动画属性分层，完整写法见 [创作指南](AUTHORING.md)。

先 `import v2lib as L`。以下函数生成 SVG 片段，可传 `cue=` 绑定旁白中的真实词，或用 `delay=` 设置兜底时间：

| 用途 | 函数或原语 |
| --- | --- |
| 3D 看板、翻转 | `L.holo_panel(...)`、`L.holo(...)`、`L.card_flip(...)`；`holo-3d`、`flip` |
| 路径形变 | `L.morph_path(...)`、`L.lock_unlock(...)`；`morph` |
| 流体与粒子 | `L.gooey_flow(...)`、`L.particle_burst(...)`、`L.coin_fountain(...)`；`flow-blob`、`burst` |
| 数字与标记 | `L.num_burst(...)`、`L.convert(...)`、`L.discount_seal(...)`、`L.pulse_badge(...)` |
| 氛围和仪表 | `L.ambient_motes(...)`、`L.gauge(...)`；`drift`、`pulse` |

颜色常量可用 `L.INK`、`L.ACCENT`、`L.RED`、`L.GOLD`。函数参数以 [v2lib.py](../v2lib.py) 为准；手写原语的实际属性以 [scene_base.html](../templates/scene_base.html) 为准。改完片段运行 `build`、`lint`，再听看 `preview`；确认后才渲染成片。
