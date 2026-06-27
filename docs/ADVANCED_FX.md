# 高级动效备忘录（下次直接调用）· Advanced FX

> 写给 AI 的速查表。要加 AE 级硬核动效时，**直接调 `v2lib` 的现成函数**即可，
> 不用读运行时源码。每个效果都已落地为 `templates/scene_base.html` 里的一个
> `data-anim` 原语 + `v2lib.py` 里的一个 Python 组件。**改数据就批量出片**。

---

## ⚙️ 底层命门：确定性时间步进（已是架构本身，不用额外做）

痛点：粒子 / 滤镜 / 3D 这类重动效，若依赖浏览器物理时钟（`requestAnimationFrame`、
`Date.now`、`Math.random`），Playwright 截图一变慢就会**掉帧、卡顿、音画不同步**。

本管线**从根上免疫**这个问题：

- 模板里**没有 rAF 驱动渲染**。每一帧的画面都是 `window.seekTime(t)` 的**纯函数**
  —— `render.py` 每截一帧前先 `page.evaluate("window.seekTime(t)")` 把场景**强行步进**
  到那一刻，再截图（见 `pipeline/render.py` 的 `render_chunk`）。浏览器动一帧、Python 截一张，
  **掉帧在物理上不可能发生**。这就是你说的 `animation.tick(16.666)`，只是粒度是 `1/60s`。

### 🔒 唯一铁律：新动效必须是 `t` 的纯函数

加任何新动效，**只准**用 `t` 推算状态，**禁止**：
- ❌ `requestAnimationFrame` / `setInterval` / `setTimeout` 驱动状态
- ❌ `Date.now()` / `performance.now()`（预览自驱循环除外，渲染不走它）
- ❌ 运行时 `Math.random()`（要随机就**在 Python 端用固定种子 `random.Random(seed)` 预生成**，
  把结果写进 `data-*` 属性，运行时只读不算 —— 见 `particle_burst` / `ambient_motes`）

只要守住这条，再炫的动效都**逐帧确定、音画分毫不差**。

---

## 🎨 组件库（8 个原语 / 一堆现成组件）

> 所有 `v2lib` 函数都吃 `cue=`（旁白真词，词级踩点）和 `delay=`（兜底秒）。
> `import v2lib as L`。颜色：`L.INK` 墨绿正文 / `L.ACCENT` 浅绿好结论 / `L.RED` 代价坏 / `L.GOLD` 钱。

### 1) 3D 全息数据看板 —— `holo-3d`
带空间纵深感翻转滑入镜头的"星战全息大屏"。CSS `perspective + rotateX/rotateY`，
Chrome 截图里正常渲染（已验证）。
```python
L.holo_panel("全息数据看板",
             [("阻抗强度", 9.5, 0.95, ""), ("整体折扣", 74.8, 0.748, "%")],
             x=200, y=420, w=1700, cue="数据", settle=True)   # settle=False 停在倾角
L.holo(inner_svg, cue="...", rx=18, ry=-14)                   # 把任意片段裹成全息平面
```

### 2) 矢量路径顺滑形变 —— `morph`
「热潮武器箱」图标流体般扭曲重组成「日元硬币」。**自带按弧长重采样**，前后节点数
可不同，**不需要 GSAP MorphSVG**。
```python
box  = "M-120,-120 L120,-120 L120,120 L-120,120 Z"
coin = "M0,-120 A120,120 0 1 1 0,120 A120,120 0 1 1 0,-120 Z"
L.morph_path(box, coin, x=2900, y=560, cue="变现", close=True, stroke=L.GOLD)
L.lock_unlock(x=3050, y=1700, cue="解锁")            # 现成：闭锁→开锁（绑令牌/解锁市场）
```

### 3) 资金流向·流体融合 —— `flow-blob`（goo 滤镜）
金球在管道里流动，靠近彼此时像水银互相吸引拉伸融合。强化"资金流转/闭环"。
```python
L.gooey_flow([(300,1180),(1100,1180),(1700,1020),(2300,1180)],
             cue="流转", n=6, r=52, speed=0.3, color=L.GOLD)
```

### 4) 多巴胺终结·粒子炸裂 —— `burst`
核心数字落盘的刹那，以数字坐标为中心爆出上百颗带重力抛物线的金色微粒。**种子在
Python 端固定 → 运行时零随机 → 逐帧确定**。
```python
L.num_burst(74.8, 3100, 1180, lvl=0, suffix="%", dec=1, cue="七四八", n=120)  # 数字+炸裂二合一
L.particle_burst(x, y, cue="到账", n=110)                                      # 纯炸裂
L.coin_fountain(x=1920, y=1500, cue="收益")                                    # 金币喷泉（偏上抛慢重力）
```

### 5)–8) 本系列（游戏王 MD）专属顺手动效
| 函数 | 效果 | 用在哪 |
|---|---|---|
| `L.convert(495.32,"RMB",11770,"日元", cue="换算")` | 币种换算条：左值→[÷0.04207]→右值，两数滚动 | **币种铁律**：截图标人民币、旁白讲日元 |
| `L.discount_seal("74.8折", cue="折")` | 折扣大印章砸下 + 冲击波环（`shockwave`） | 折扣/结论落锤 |
| `L.pulse_badge("当前最优", cue="最优")` | 呼吸辉光徽章（`pulse`） | "亲测可行/最划算"标记 |
| `L.card_flip(inner, cue="揭示")` | 游戏王卡牌翻转揭示（`flip`，3D rotateY） | 主题契合的揭示/反转 |
| `L.ambient_motes(n=22)` | 背景缓慢游走光点（`drift`，种子相位） | 加高级氛围、不抢戏（默认右侧空域避开文字） |

---

## 原语清单（运行时 `data-anim`，手写片段时用）

| 原语 | 关键 `data-*` | 纯函数公式（要点） |
|---|---|---|
| `holo-3d` | `rx0/ry0/rx1/ry1` `persp` | `perspective·rotateX·rotateY`，q=easeOut |
| `morph` | `to="#id"` `samples` `close` | 两路径重采样后逐点 `lerp` 重建 `d` |
| `flow-blob` | `path="#id"` `speed` `phase` `x0/y0` | `f=((t·speed+phase) mod 1)`，沿路径取点 |
| `burst` | `vx/vy/g/life/spin` | `x=vx·t, y=vy·t+½g·t²`，`(1-u)²` 淡出 |
| `shockwave` | `max` | `scale(0.2+p·max)`，`opacity=1-p` |
| `flip` | `ry0` `persp` | `rotateY(lerp(ry0,0,q))`，边沿(>88°)时隐藏 |
| `pulse` | `amp` `spd` `opmin` | `scale(1+amp·sin) · opacity(opmin..1)` |
| `drift` | `ax/ay` `fx/fy` `px/py` `op` | `translate(ax·sin(t·fx+px), ay·sin(t·fy+py))` |

> 之前已有的回形针原语（`grow-bar`/`draw-area`/`pop`/`stamp`/`wipe`/`highlight-sweep`/
> `trace-dot`/`move-along`/`play-head`/`tilt`/`split-push`/`push`/`fade-out`/`xfade` 等）
> 见 `docs/AUTHORING.md`。新原语全部追加在 `scene_base.html` 的 `measure()`/`apply()` 里，
> 与旧的同机制并存，**不影响已发布场景**。

---

## 工业化用法（一劳永逸）

这套底层 SVG/CSS 模板写好后，**以后只改 Python 里传入的数据**就能成批吐出 AE 级视频：
1. 在 `build_v2.py` 的某个 `sNN_*()` 场景函数里，把上面任意 `L.xxx(...)` 拼进 `return`。
2. `python build_v2.py build` →（0 WARN）→ `python build_v2.py preview` 浏览器里秒验动效。
3. 满意再 `python build_v2.py render`。

> 验证记录：8 个原语已用 Playwright 在确定性抓帧路径下逐帧截图确认渲染正常
> （3D 全息 / 路径形变 / goo 流体 / 粒子炸裂 / 印章冲击波 / 卡牌翻转 / 脉冲 / 浮尘）。
