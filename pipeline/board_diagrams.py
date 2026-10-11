# -*- coding: utf-8 -*-
"""词轴驱动的通用动态图解；只输出静态 SVG，运动复用 boards/runtime。"""
from __future__ import annotations

import math

from pipeline import boards as B


def rect(x, y, w, h, fill, *, radius=24, stroke="none", sw=3, extra=""):
    return (f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{radius:g}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw:g}"{extra}/>')


def circle(x, y, r, fill, *, stroke="none", sw=4, extra=""):
    return (f'<circle cx="{x:g}" cy="{y:g}" r="{r:g}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw:g}"{extra}/>')


def line(ctx, d, at, dur=0.6, *, color="accent", sw=8, extra=""):
    return (f'<path data-anim="draw" data-delay="{at:.4f}" data-dur="{dur:g}" d="{d}" '
            f'fill="none" stroke="{ctx.col(color)}" stroke-width="{sw:g}" stroke-linecap="round" '
            f'stroke-linejoin="round"{extra}/>')


def label(ctx, s, cue, x, y, size=84, **opts):
    return B.text(ctx, s, x, y, size, ctx.glyphs(B.plain_of(s), cue), **opts)


def pulse(ctx, x, y, r, at, *, amp=0.08):
    return B.anim("pulse", at, 0.4, circle(x, y, r, ctx.col("accent"), extra=' fill-opacity="0.12"'),
                  f' data-amp="{amp}" data-spd="4" data-opmin="0.4"')


def travelling_dot(ctx, d, at, dur, *, r=14, loop=False):
    pid = B._id("route")
    path = f'<path id="{pid}" d="{d}" fill="none" stroke="none"/>'
    kind = "flow-blob" if loop else "move-along"
    extra = f' data-path="#{pid}" data-x0="0" data-y0="0" data-speed="{1 / max(dur, .01):g}"'
    return path + B.anim(kind, at, dur, circle(0, 0, r, ctx.col("accent")), extra)


def screenshot_stamp(ctx, el):
    """完整原图等比贴入；强调框在图外叠加，不裁切、不重画截图内容。"""
    from pipeline.pages import _resolve
    src = _resolve(ctx.b.base, el["screenshot"])
    iw, ih = ctx.L.img_dims(str(src))
    x, y, w = el.get("x", 2140), el.get("y", 650), el.get("w", 1420)
    h, at = w * ih / iw, ctx.at(el["at"])
    dur = el.get("dur", 0.65)
    sid = B._id("stamp")
    pad = el.get("pad", 20)
    paper = (f'<defs><filter id="{sid}" x="-20%" y="-20%" width="140%" height="150%">'
             '<feDropShadow dx="0" dy="20" stdDeviation="24" flood-opacity="0.10"/></filter></defs>'
             + rect(-pad, -pad, w + pad * 2, h + pad * 2, "#FFFFFF", radius=22,
                    stroke=ctx.col("rule"), extra=f' filter="url(#{sid})"')
             + f'<image href="{ctx.L.FU(str(src))}" x="0" y="0" width="{w:g}" height="{h:g}" '
               'preserveAspectRatio="xMidYMid meet"/>')
    # 从上方落下并轻轻压实，缩放和平移均作用于完整原图。
    track = [[at, 0, -130, 1.04, 0], [at + dur * .7, 0, 8, .996, 1], [at + dur, 0, 0, 1, 1]]
    out = [f'<g transform="translate({x},{y})">{B.keys(track, paper)}</g>']
    if el.get("focus"):
        fx, fy, fw, fh = el["focus"]  # 原图的归一化区域
        ta = ctx.at(el["focus_at"]) if el.get("focus_at") else at + dur
        out.append(rect(x + fx*w, y + fy*h, fw*w, fh*h, "none", radius=16,
                        stroke=ctx.col("accent"), sw=7,
                        extra=f' data-anim="draw" data-delay="{ta:.4f}" data-dur="0.6"'))
    if el.get("caption"):
        out.append(label(ctx, el["caption"], el.get("caption_at", el["at"]), x, y + h + 96,
                         64, font="mono", weight=600, fill="muted"))
    return "".join(out)


def repeat_flow(ctx, el):
    """相同输入反复送入，输出保持不变；适用于重试、循环和重复沟通。"""
    cfg = el["repeat_flow"]
    x, y = el.get("x", 2090), el.get("y", 730)
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    t0, repeats, end = ctx.at(el["at"]), [ctx.at(c) for c in cfg["repeats"]], ctx.at(cfg["result_at"])
    out = []
    for k, ta in enumerate([t0] + repeats):
        ry = k * 175
        box = rect(0, 0, 600, 132, "#FFFFFF", stroke=rule)
        box += label(ctx, cfg["input"], el["at"], 300, 90, 74, anchor="middle")
        track = [[ta, -140, ry + 35, 1, 0], [ta + .28, 0, ry, 1, 1]]
        out.append(f'<g transform="translate({x},{y})">{B.keys(track, box)}</g>')
        d = f'M{x+640},{y+ry+65} C{x+930},{y+ry+65} {x+780},{y+300} {x+1080},{y+300}'
        out.append(line(ctx, d, ta+.12, .5, color="rule", sw=6))
        out.append(travelling_dot(ctx, d, ta+.18, .66, r=19))
    receiver = rect(x+1050, y+170, 340, 270, "#FFFFFF", stroke=rule)
    for k in range(3):
        receiver += rect(x+1110, y+230+k*58, 220, 18, ink, radius=8)
    out.append(B.anim("fade-up", t0, .45, receiver))
    out.append(pulse(ctx, x+1220, y+300, 230, end))
    out.append(label(ctx, cfg["result"], cfg["result_at"], x+1220, y+690, 144,
                     anchor="middle", fill="accent"))
    loop = f'M{x+1190},{y+70} C{x+1150},{y-65} {x+930},{y-30} {x+970},{y+115}'
    out.append(line(ctx, loop, repeats[-1], .5, sw=10))
    return "".join(out)


def focus_network(ctx, el):
    """中心与节点的注意力：只追某点，或逐步展开到完整关系。"""
    cfg = el["focus_network"]
    cx, cy, radius = el.get("x", 2810), el.get("y", 1140), el.get("r", 500)
    nr, hr = el.get("node_r", 60), el.get("hub_r", 112)    # 节点、中心圆半径，可按画面放大
    t0 = ctx.at(el["at"])
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    nodes, points, out = cfg["nodes"], [], []
    for k, node in enumerate(nodes):
        angle = node.get("angle", -90 + k * 360 / len(nodes)) * math.pi / 180
        nx, ny = cx + radius*math.cos(angle), cy + radius*math.sin(angle)
        points.append((nx, ny))
        at = ctx.at(node.get("at", el["at"]))
        out.append(line(ctx, f'M{cx},{cy} L{nx},{ny}', at, .6, color="rule", sw=5))
        node_svg = (B.brand_mark(ctx, node["logo"], nx, ny, nr, sw=5) if node.get("logo")
                    else circle(nx, ny, nr, "#FFFFFF", stroke=rule, sw=5))
        out.append(B.anim("pop", at, .45, node_svg))
        if node.get("label"):
            dx, dy = node.get("label_offset", [0, nr + 64])
            out.append(label(ctx, node["label"], node.get("at", el["at"]), nx+dx, ny+dy,
                             node.get("size", 74), anchor="middle", font="sans", weight=700))
    hub = [B.anim("pop", t0, .5, circle(cx, cy, hr, ink))]
    if cfg.get("center"):
        cs = el.get("center_size", 70)
        if cfg.get("center_at"):     # 前面已讲过的名字：从 center_at 起直接打出
            ca = ctx.at(cfg["center_at"])
            g = [round(ca + B.TYPE_STEP * k, 4) for k in range(len(cfg["center"]))]
            hub.append(B.text(ctx, cfg["center"], cx, cy + cs * .38, cs, g, fill="#FFFFFF", anchor="middle",
                              settle=False))
        else:
            hub.append(label(ctx, cfg["center"], el["at"], cx, cy + cs * .38, cs, fill="#FFFFFF", anchor="middle"))
    ring = f'M{cx},{cy-hr-43} A{hr+43},{hr+43} 0 1 1 {cx-.1},{cy-hr-43}'
    out.append(line(ctx, ring, t0, .7, color="rule", sw=5))
    out.append(travelling_dot(ctx, ring, t0+.2, 3, r=15, loop=True))
    visits = cfg.get("visits", [])
    for k, visit in enumerate(visits):
        nx, ny = points[visit["node"]]
        ta = ctx.at(visit["at"])
        nxt = ctx.at(visits[k+1]["at"]) if k+1 < len(visits) else None
        d = f'M{cx},{cy} L{nx},{ny}'
        lit = line(ctx, d, ta, .4, sw=12) + pulse(ctx, nx, ny, nr * 1.8, ta)
        lit += travelling_dot(ctx, d, ta, .7, r=20)
        out.append(B.out_at(nxt, lit))
    if cfg.get("expand_at"):
        ta = ctx.at(cfg["expand_at"])
        for k, (nx, ny) in enumerate(points):
            at = ta + k * .09
            d = f'M{cx},{cy} L{nx},{ny}'
            out.append(line(ctx, d, at, .65, sw=10))
            out.append(travelling_dot(ctx, d, at, 1, r=17))
            out.append(B.anim("pop", at+.4, .35, circle(nx, ny, nr * .63, a)))
        for k, (nx, ny) in enumerate(points):
            ex, ey = points[(k+1) % len(points)]
            out.append(line(ctx, f'M{nx},{ny} L{ex},{ey}', ta+.35+k*.08, .55, sw=4))
    return "".join(out + hub)


def time_stretch(ctx, el):
    """时间从一个单位拉长为整排；刻度和节点共用词轴。"""
    cfg = el["time_stretch"]
    x, y, w = el.get("x", 2040), el.get("y", 760), el.get("w", 1500)
    t0, ta, tb = ctx.at(el["at"]), ctx.at(cfg["stretch_at"]), ctx.at(cfg["end_at"])
    if tb <= ta:
        raise ValueError("time_stretch.end_at must follow stretch_at")
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    cx, cy, r = x+w/2, y+270, 260
    out = [B.anim("fade", t0, .4, circle(cx, cy, r, "#FFFFFF", stroke=rule, sw=6))]
    for k in range(12):
        ang = k*math.pi/6
        d = f'M{cx+225*math.sin(ang)},{cy-225*math.cos(ang)} L{cx+240*math.sin(ang)},{cy-240*math.cos(ang)}'
        out.append(line(ctx, d, t0+k*.025, .2, color="ink", sw=7))
    arc = f'M{cx},{cy-r} A{r},{r} 0 1 1 {cx-.1},{cy-r}'
    out.append(line(ctx, arc, ta, tb-ta, sw=13, extra=' data-ease="linear"'))
    out.append(travelling_dot(ctx, arc, ta, tb-ta, r=20))
    out.append(label(ctx, cfg["start_label"], el["at"], cx, cy+30, 94, anchor="middle"))
    cells = cfg.get("units", 24)
    unit, gap = w/cells, 8
    for k in range(cells):
        cell = rect(x, y+660, unit-gap, 170, a if k == 0 else ink, radius=7)
        st = ta + (tb-ta)*k/cells
        track = [[t0, 0, 0, 1, 1 if k == 0 else 0], [st, 0, 0, 1, 1 if k == 0 else 0],
                 [st+.22, k*unit, 0, 1, 1]]
        out.append(B.keys(track, cell))
    out.append(line(ctx, f'M{x},{y+910} L{x+w},{y+910}', ta, tb-ta, color="rule", sw=4))
    out.append(label(ctx, cfg["end_label"], cfg["end_at"], x+w, y+1070, 138,
                     anchor="end", fill="accent"))
    return "".join(out)


def scan_grid(ctx, el):
    """扫描器经过规则方格，异常格被独立圈出；两者故意不自动等同。"""
    cfg = el["scan_grid"]
    x, y, cell, gap = el.get("x", 2180), el.get("y", 690), 220, 40
    cols, rows = cfg.get("cols", 4), cfg.get("rows", 3)
    odd = cfg.get("odd", 6)
    t0, ta, miss = ctx.at(el["at"]), ctx.at(cfg["reveal_at"]), ctx.at(cfg["miss_at"])
    rule, a, ink = ctx.col("rule"), ctx.col("accent"), ctx.col("ink")
    out = []
    for k in range(cols*rows):
        px, py = x+(k%cols)*(cell+gap), y+(k//cols)*(cell+gap)
        box = rect(px, py, cell, cell, "#FFFFFF", stroke=rule)
        shape = rect(px+65, py+65, 90, 90, a, radius=14)
        if k == odd:
            shape = f'<g transform="rotate(45 {px+110} {py+110})">{rect(px+65, py+65, 90, 90, ink, radius=8)}</g>'
        out.append(B.anim("pop", t0+k*.025, .35, box+shape))
    ox, oy = x+(odd%cols)*(cell+gap)+110, y+(odd//cols)*(cell+gap)+110
    out.append(circle(ox, oy, 150, "none", stroke=a, sw=10,
                      extra=f' data-anim="draw" data-delay="{ta:.4f}" data-dur="0.5"'))
    # 扫描光带只看第一行，异常在下面；视觉上确实“漏看”。
    scan = rect(-20, -25, 150, cell+50, a, radius=18, extra=' fill-opacity="0.13"')
    scan += line(ctx, 'M0,-25 L0,245', t0, .2, sw=8)
    track = [[t0, 0, 0, 1, 0], [t0+.22, 0, 0, 1, 1], [miss, 900, 0, 1, 1],
             [miss+.45, 1030, 0, 1, 0]]
    out.append(f'<g transform="translate({x},{y})">{B.keys(track, scan)}</g>')
    out.append(pulse(ctx, ox, oy, 175, miss))
    return "".join(out)


def capacity_gauges(ctx, el):
    """并行容量槽逐个上升，到饱和点汇合；不虚构监控数值。"""
    cfg = el["capacity_gauges"]
    x, y, w, h = el.get("x", 2080), el.get("y", 760), 390, 680
    t0, full = ctx.at(el["at"]), ctx.at(cfg["full_at"])
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    out = []
    for k, item in enumerate(cfg["items"]):
        px, ta = x+k*500, ctx.at(item["at"])
        out.append(B.anim("fade-up", t0+k*.12, .6, rect(px, y, w, h, "#FFFFFF", stroke=rule)))
        inside = rect(px+26, y+26, w-52, h-52, a, radius=10,
                      extra=f' data-anim="grow-bar" data-grow="y" data-delay="{ta:.4f}" data-dur="{max(.35,full-ta):g}"')
        out.append(inside)
        for j in range(1, 8):
            out.append(B.anim("fade", t0+.3+j*.03, .2,
                              rect(px+26, y+26+j*(h-52)/8, w-52, 5, "#FFFFFF", radius=0)))
        out.append(label(ctx, item["label"], item["at"], px+w/2, y+h+140, 118, anchor="middle"))
        outline = rect(px-10, y-10, w+20, h+20, "none", stroke=ink, sw=8,
                       extra=f' data-anim="draw" data-delay="{full:.4f}" data-dur="0.4"')
        out.append(B.anim("shake", full+.15, .4, outline, ' data-amp="18"'))
    # 在幻觉时进入的无文字扰动，可用于负载/噪声图解。
    if cfg.get("noise_at"):
        ta = ctx.at(cfg["noise_at"])
        for k in range(12):
            px, py = x+55+(k%6)*230, y-180+(k//6)*80
            block = rect(px, py, 130, 24, ink if k%3 else a, radius=5)
            out.append(B.anim("wave", ta, max(.1,full-ta), block,
                              f' data-phase="{k*1.7:g}" data-spd="{8+k%4}" data-amp="1" data-base="0.1"'))
    return "".join(out)


def device_flow(ctx, el):
    """手机清理或设备迁移示意：文件块真正离开或沿线进入目标。"""
    cfg = el["device_flow"]
    x, y = el.get("x", 2050), el.get("y", 690)
    phone, computer, move = ctx.at(el["at"]), ctx.at(cfg["computer_at"]), ctx.at(cfg["move_at"])
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    pbody = rect(x, y, 500, 870, "#FFFFFF", radius=65, stroke=ink, sw=9)
    pbody += rect(x+180, y+26, 140, 22, ink, radius=11)
    pbody += rect(x+165, y+817, 170, 13, ink, radius=6)
    out = [B.anim("fade-up", phone, .55, pbody)]
    for k in range(12):
        px, py = x+55+(k%3)*135, y+140+(k//3)*135
        shape = rect(0, 0, 110, 110, a if k<3 else rule, radius=24)
        ta = phone+.2+k*.025
        leave = move+k*.035
        track = [[ta, 0, 35, .8, 0], [ta+.35, 0, 0, 1, 1]]
        if k >= 3:
            track += [[leave, 0, 0, 1, 1], [leave+.65, 630, -160+(k%3)*50, .3, 0]]
        out.append(f'<g transform="translate({px},{py})">{B.keys(track, shape)}</g>')
    cx, cy = x+860, y+140
    desktop = rect(cx, cy, 740, 530, "#FFFFFF", radius=30, stroke=ink, sw=9)
    desktop += rect(cx+25, cy+25, 690, 430, ctx.col("page"), radius=10)
    desktop += rect(cx+334, cy+534, 72, 144, ink, radius=5)
    desktop += rect(cx+225, cy+672, 290, 18, ink, radius=8)
    out.append(B.anim("fade-up", computer, .6, desktop))
    for k in range(6):
        bx, by = cx+85+(k%3)*200, cy+100+(k//3)*155
        out.append(B.anim("pop", computer+.4+k*.10, .45,
                          rect(bx, by, 155, 115, a if k==0 else rule, radius=16)))
    d = f'M{x+550},{y+420} C{x+760},{y+420} {cx-160},{cy+265} {cx-25},{cy+265}'
    out.append(line(ctx, d, computer+.1, .55, color="rule", sw=7))
    out.append(travelling_dot(ctx, d, computer+.25, 1.4, r=19, loop=True))
    out.append(label(ctx, cfg["phone_label"], el["at"], x+250, y+1020, 120, anchor="middle"))
    out.append(label(ctx, cfg["computer_label"], cfg["computer_at"], cx+370, y+1020, 120, anchor="middle"))
    return "".join(out)


def _bubble(ctx, w, h, user, lines=1):
    """对话条（局部坐标 0,0 起）：用户条浅绿、带引号；AI 条白底。只画占位横线，不编造内容。"""
    a, rule = ctx.col("accent"), ctx.col("rule")
    fill = "#E6F4EF" if user else "#FFFFFF"
    out = rect(0, 0, w, h, fill, radius=h / 2, stroke=a if user else rule, sw=4 if user else 3)
    x0 = 96 if user else 50
    if user:
        out += (f'<text x="34" y="{h * 0.5 + h * 0.32:g}" font-family="{B.esc(ctx.font("heavy"))}" '
                f'font-size="{h * 0.9:g}" font-weight="900" fill="{a}">“</text>')
    for j in range(lines):
        lw = (w - x0 - 60) * (0.82 if j == 0 else 0.5)
        ly = h / 2 - (lines - 1) * 13 + j * 26 - 8
        out += rect(x0, ly, lw, 16, a if user else ctx.col("faint"), radius=8,
                    extra=f' fill-opacity="{0.45 if user else 0.55}"')
    return out


def condense(ctx, el):
    """一长串对话按念到依次进来，到点压成一张摘要：挑中的几条缩进摘要，其余用户原话掉落消失。"""
    cfg = el["condense"]
    x, y, w = el.get("x", 2000), el.get("y", 560), el.get("w", 1600)
    rows = cfg["rows"]
    rh, gap = cfg.get("row_h", 92), cfg.get("gap", 22)
    ca = ctx.at(cfg["collapse_at"])
    a, ink = ctx.col("accent"), ctx.col("ink")
    sw_, sh_ = cfg.get("summary_w", 1120), cfg.get("summary_h", 560)
    sx, sy = x + cfg.get("summary_x", 0), y + cfg.get("summary_y", 240)
    widths = [0.78, 0.92, 0.66, 0.86, 0.72, 0.95, 0.6, 0.84, 0.7, 0.9]
    out, kept = [], []
    slot = 0
    for k, r in enumerate(rows):
        user = r.get("user", False)
        at = ctx.at(r["at"])
        bw = w * widths[k % len(widths)] * (0.8 if user else 1)
        rx = x + (w - bw if user else 0)
        ry = y + k * (rh + gap)
        body = _bubble(ctx, bw, rh, user, r.get("lines", 1))
        lag = 0.03 * k
        if r.get("keep"):
            s = cfg.get("chip_scale", 0.72)
            dx = sx + 70 - rx
            dy = sy + 170 + slot * (rh * s + 26) - ry
            slot += 1
            track = [[0, 0, 0, 1, 1], [ca + lag, 0, 0, 1, 1], [ca + lag + 0.65, dx, dy, s, 1]]
            inner = B.anim("fade-up", at, 0.35, body, ' data-shift="40"')    # 挑中的也要念到才进来
            kept.append(f'<g transform="translate({rx:g},{ry:g})">{B.keys(track, inner)}</g>')
            continue
        if user:      # 没挑中的原话：先变淡，再往下掉出画面
            track = [[0, 0, 0, 1, 1], [ca + lag, 0, 0, 1, 1], [ca + lag + 0.25, 0, 0, 1, .45],
                     [ca + lag + 0.7, 0, 140, 1, 0]]
        else:         # 其余内容并进摘要
            track = [[0, 0, 0, 1, 1], [ca + lag, 0, 0, 1, 1],
                     [ca + lag + 0.55, sx + sw_ / 2 - rx - bw * 0.15, sy + sh_ / 2 - ry, 0.3, 0]]
        inner = B.anim("fade-up", at, 0.35, body, ' data-shift="40"')
        out.append(f'<g transform="translate({rx:g},{ry:g})">{B.keys(track, inner)}</g>')
    # 摘要卡在并入的同时出现，压在挑中的几条下面
    summary = rect(sx, sy, sw_, sh_, "#FFFFFF", radius=36, stroke=ink, sw=6)
    summary += rect(sx, sy, 16, sh_, a, radius=8)
    st = ca + 0.3
    card = B.anim("pop", st, 0.45, summary)
    if cfg.get("summary_label"):
        card += label(ctx, cfg["summary_label"], cfg.get("summary_label_at") or cfg["collapse_at"], sx + 70, sy + 115,
                      90, font="heavy")
    out.append(card)
    if kept:
        for k in range(len(kept)):   # 被挑中的几条占进摘要里
            out.append(kept[k])
    if cfg.get("stamp"):
        sp = cfg["stamp"]
        ta = ctx.at(sp["at"])
        fs = sp.get("size", 76)
        tw = ctx.width(sp["text"], fs) + 80
        tx, ty = sx + sw_ - tw + 30, sy - 70
        tag = (f'<g transform="rotate(-6 {tx + tw / 2:g} {ty + 60:g})">'
               + rect(tx, ty, tw, 120, "#FFFFFF", radius=20, stroke=ink, sw=7)
               + f'<text x="{tx + tw / 2:g}" y="{ty + 60 + fs * 0.36:g}" text-anchor="middle" '
                 f'font-family="{B.esc(ctx.font("heavy"))}" font-size="{fs}" font-weight="900" fill="{ink}">'
                 f'{B.esc(sp["text"])}</text></g>')
        out.append(B.anim("stamp", ta, 0.35, tag))
    if cfg.get("worker"):
        wk = cfg["worker"]
        ta = ctx.at(wk["at"])
        below = wk.get("below", False)    # below：干活的 AI 放在摘要下方，标签在它右边（右侧放不下时用）
        if below:
            nx, ny = sx + wk.get("dx", sw_ / 2), sy + sh_ + wk.get("dy", 250)
            d = f'M{nx:g},{sy + sh_ + 20:g} L{nx:g},{ny - 120:g}'
        else:
            nx, ny = sx + sw_ + 260, sy + sh_ / 2
            d = f'M{sx + sw_ + 20:g},{ny:g} L{nx - 120:g},{ny:g}'
        out.append(line(ctx, d, ta, .35, color="rule", sw=8))
        node = (B.brand_mark(ctx, wk["logo"], nx, ny, 105, ring="ink", sw=6) if wk.get("logo") else
                circle(nx, ny, 105, ink) + f'<text x="{nx:g}" y="{ny + 26:g}" text-anchor="middle" '
                f'font-family="{B.esc(ctx.font("mono"))}" font-size="70" font-weight="700" fill="#FFFFFF">AI</text>')
        out.append(B.anim("pop", ta + .2, .4, node))
        out.append(travelling_dot(ctx, d, ta + .3, 1.1, r=16, loop=True))
        if wk.get("label"):
            ls = wk.get("label_size", 76)
            lx, ly, anc = (nx + 160, ny + ls * 0.36, "start") if below else (nx, ny + 220, "middle")
            out.append(label(ctx, wk["label"], wk.get("label_at") or wk["at"], lx, ly, ls, anchor=anc,
                             font="sans", weight=700))
    if cfg.get("keep_at"):
        ka = ctx.at(cfg["keep_at"])
        s = cfg.get("chip_scale", 0.72)
        for j in range(slot):
            cy_ = sy + 170 + j * (rh * s + 26)
            out.append(rect(sx + 52, cy_ - 16, sw_ - 104, rh * s + 32, "none", radius=(rh * s + 32) / 2, stroke=a, sw=8,
                            extra=f' data-anim="draw" data-delay="{ka + j * 0.15:.4f}" data-dur="0.45"'))
    return "".join(out)


def cross_check(ctx, el):
    """左列原话、右列结果，中间核对者逐条连线；每条给出对上、漏进、拿不出证据或被改掉的结论。"""
    cfg = el["cross_check"]
    x, y, w = el.get("x", 240), el.get("y", 620), el.get("w", 3360)
    rows = cfg["rows"]
    n = len(rows)
    rh, gap = cfg.get("row_h", 170), cfg.get("gap", 46)
    cw = cfg.get("col_w", 1150)
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    lx, rx = x, x + w - cw
    cx, cy = x + w / 2, y + (n * (rh + gap) - gap) / 2
    out = []
    t_head = ctx.at(el["at"])
    for side, key, hx in (("left", "left_label", lx), ("right", "right_label", rx)):
        if cfg.get(key):
            out.append(label(ctx, cfg[key], cfg.get(key + "_at") or el["at"], hx, y - 50, 84))
    chk = cfg.get("checker", {})
    ca = ctx.at(chk["at"]) if chk.get("at") else t_head
    if chk.get("logo"):    # 核对者是某一方的模型：圆里放标志，名字写在圆下方
        hub = [pulse(ctx, cx, cy, 190, ca + .4), B.anim("pop", ca, .45, B.brand_mark(ctx, chk["logo"], cx, cy, 140, ring="ink", sw=7))]
        if chk.get("label"):
            hub.append(B.text(ctx, chk["label"], cx, cy + 140 + 100, chk.get("label_size", 84),
                              ctx.glyphs(chk["label"], chk.get("label_at") or chk.get("at") or el["at"]),
                              anchor="middle", settle=False))
    else:
        hub = [pulse(ctx, cx, cy, 190, ca + .4), B.anim("pop", ca, .45, circle(cx, cy, 140, ink))]
        if chk.get("label"):
            hub.append(B.text(ctx, chk["label"], cx, cy + 26, 74,
                              ctx.glyphs(chk["label"], chk.get("label_at") or chk.get("at") or el["at"]),
                              fill="#FFFFFF", anchor="middle", settle=False))
    for k, r in enumerate(rows):
        ry = y + k * (rh + gap)
        at = ctx.at(r["at"])
        left = rect(lx, ry, cw, rh, "#FFFFFF", radius=26, stroke=rule) + rect(lx, ry + 26, 12, rh - 52, a, radius=6)
        left += (f'<text x="{lx + 50:g}" y="{ry + rh * 0.72:g}" font-family="{B.esc(ctx.font("heavy"))}" '
                 f'font-size="{rh * 0.8:g}" font-weight="900" fill="{a}">“</text>')
        if r.get("left_text"):
            left_t = label(ctx, r["left_text"], r.get("left_text_at") or r["at"], lx + 140, ry + rh / 2 + 28, 78,
                           font="sans", weight=700)
        else:
            left += rect(lx + 140, ry + rh / 2 - 12, (cw - 220) * (0.78 - 0.1 * (k % 3)), 24, a, radius=12,
                         extra=' fill-opacity="0.4"')
            left_t = ""
        out.append(B.anim("fade-left", at, .4, left, ' data-shift="50"') + left_t)
        status = r.get("status", "ok")
        st = ctx.at(r["status_at"]) if r.get("status_at") else at + .5
        rt = ctx.at(r["right_at"]) if r.get("right_at") else at
        link_t = ctx.at(r["link_at"]) if r.get("link_at") else st - .1
        d = (f'M{lx + cw + 16:g},{ry + rh / 2:g} C{cx - 260:g},{ry + rh / 2:g} {cx - 200:g},{cy:g} {cx - 150:g},{cy:g} '
             f'M{cx + 150:g},{cy:g} C{cx + 200:g},{cy:g} {rx - 260:g},{ry + rh / 2:g} {rx - 16:g},{ry + rh / 2:g}')
        out.insert(0, line(ctx, d, link_t, .5, color="accent" if status == "ok" else "rule", sw=7))
        right = ""
        if status != "missing":
            right = rect(rx, ry, cw, rh, "#FFFFFF", radius=26, stroke=rule)
            if not r.get("right_text"):
                right += rect(rx + 60, ry + rh / 2 - 12, (cw - 300) * (0.7 + 0.1 * (k % 2)), 24, ctx.col("faint"),
                              radius=12, extra=' fill-opacity="0.6"')
            out.append(B.anim("fade-right", rt, .4, right, ' data-shift="50"'))
            if r.get("right_text"):
                out.append(label(ctx, r["right_text"], r.get("right_text_at") or r.get("right_at") or r["at"],
                                 rx + 60, ry + rh / 2 + 28, 78, font="sans", weight=700))
        mx, my = rx + cw - 90, ry + rh / 2
        if status == "ok":
            out.append(B.anim("pop", st, .3, circle(mx, my, 44, a, extra=' fill-opacity="0.15"'))
                       + _check(ctx, mx, my, 50, st + .1))
        elif status == "missing":
            ghost = rect(rx, ry, cw, rh, a, radius=26, stroke=a, sw=6,
                         extra=' fill-opacity="0.05" stroke-dasharray="24 16"')
            out.append(B.anim("pop", st, .35, ghost))
            if r.get("restore_at"):
                rs = ctx.at(r["restore_at"])
                fill = rect(rx, ry, cw, rh, a, radius=26, extra=' fill-opacity="0.16"')
                out.append(B.anim("fade-right", rs, .4, fill, ' data-shift="60"') + _check(ctx, mx, my, 50, rs + .3))
        elif status == "unproven":
            q = circle(mx, my, 50, ink) + (f'<text x="{mx:g}" y="{my + 26:g}" text-anchor="middle" '
                                           f'font-family="{B.esc(ctx.font("heavy"))}" font-size="78" font-weight="900" '
                                           f'fill="#FFFFFF">?</text>')
            out.append(B.anim("pop", st, .35, q))
        elif status == "changed":
            out.append(line(ctx, f'M{rx + 40:g},{my:g} L{rx + cw - 170:g},{my:g}', st, .3, color="ink", sw=10))
            out.append(B.anim("pop", st + .25, .3, circle(mx, my, 50, ink)
                              + (f'<path d="M{mx - 22:g},{my - 4:g} L{mx + 22:g},{my - 4:g} M{mx - 22:g},{my + 14:g} '
                                 f'L{mx + 22:g},{my + 14:g}" stroke="#FFFFFF" stroke-width="8" stroke-linecap="round"/>')))
        if r.get("note"):
            nt = r.get("note_at") or r.get("status_at") or r["at"]
            nx = rx + cw / 2 if status == "missing" else rx + cw + 40
            anchor = "middle" if status == "missing" else "start"
            yy = ry + rh / 2 + 26 if status == "missing" else ry + rh / 2 + 26
            out.append(label(ctx, r["note"], nt, nx, yy, r.get("note_size", 74), font="sans", weight=800,
                             fill="accent" if status == "missing" else "ink", anchor=anchor))
    return "".join(out + hub)


def _check(ctx, cx, cy, s, at):
    d = f"M{cx - s * .45:g},{cy:g} L{cx - s * .12:g},{cy + s * .32:g} L{cx + s * .5:g},{cy - s * .36:g}"
    return line(ctx, d, at, .3, sw=11)


def lanes(ctx, el):
    """并行的几条轨道：主线一直在走，另一条在某点分出来并行跑，互不等待。"""
    cfg = el["lanes"]
    x, y, w = el.get("x", 240), el.get("y", 1200), el.get("w", 3360)
    gap, lw = cfg.get("gap", 280), cfg.get("label_w", 520)
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    out = []
    starts = []
    spawn = cfg.get("spawn")
    for k, ln in enumerate(cfg["lanes"]):
        ly = y + k * gap
        at = ctx.at(ln["at"])
        x0 = x + lw if not (spawn and k == spawn.get("to", 1)) else x + lw + spawn.get("offset", 520)
        starts.append(x0)
        d = f'M{x0:g},{ly:g} L{x + w:g},{ly:g}'
        out.append(line(ctx, d, at, .5, color="rule", sw=10))
        out.append(label(ctx, ln["label"], ln.get("label_at") or ln["at"], x, ly + 30, ln.get("size", 96)))
        speed = ln.get("speed", 0.32)
        for j in range(cfg.get("dots", 4)):
            pid = B._id("lane")
            out.append(f'<path id="{pid}" d="{d}" fill="none" stroke="none"/>'
                       + B.anim("flow-blob", at + .4, .4, rect(-34, -14, 68, 28, a if k else ink, radius=14),
                                f' data-path="#{pid}" data-x0="0" data-y0="0" data-speed="{speed:g}" '
                                f'data-phase="{j / cfg.get("dots", 4):.3f}"'))
    if spawn:
        ta = ctx.at(spawn["at"])
        f, t = spawn.get("from", 0), spawn.get("to", 1)
        bx = starts[f] + spawn.get("branch", 200)
        d = f'M{bx:g},{y + f * gap:g} C{bx + 200:g},{y + f * gap:g} {starts[t] - 220:g},{y + t * gap:g} {starts[t]:g},{y + t * gap:g}'
        out.append(line(ctx, d, ta, .5, sw=8))
        nr = spawn.get("node_r", 110 if spawn.get("logo") else 92)
        if spawn.get("logo"):        # 分出去的是某一方的模型：圆里放标志，短名写在圆下方、保持看得清
            node = B.brand_mark(ctx, spawn["logo"], starts[t], y + t * gap, nr, ring="accent", sw=8)
            if spawn.get("node_text"):
                node += (f'<text x="{starts[t]:g}" y="{y + t * gap + nr + 96:g}" text-anchor="middle" '
                         f'font-family="{B.esc(ctx.font("heavy"))}" font-size="{spawn.get("node_text_size", 84)}" '
                         f'font-weight="900" fill="{ink}">{B.esc(spawn["node_text"])}</text>')
        else:
            node = circle(starts[t], y + t * gap, nr, a)
            if spawn.get("node_text"):   # 节点里的短名（已念过的名字），随节点一起弹出
                node += (f'<text x="{starts[t]:g}" y="{y + t * gap + 24:g}" text-anchor="middle" '
                         f'font-family="{B.esc(ctx.font("mono"))}" font-size="64" font-weight="700" fill="#FFFFFF">'
                         f'{B.esc(spawn["node_text"])}</text>')
        out.append(B.anim("pop", ta + .4, .4, node))
        out.append(pulse(ctx, starts[t], y + t * gap, 130, ta + .8))
        if spawn.get("label"):
            out.append(label(ctx, spawn["label"], spawn.get("label_at") or spawn["at"], starts[t],
                             y + t * gap + 200, 76, anchor="middle", font="mono", weight=700))
    return "".join(out)


def rail(ctx, el):
    """章节进度轨：几个步骤一排，已讲过的黑点、当前绿点；没讲到的步骤只留空点、不提前写字。"""
    steps = el["rail"]
    x, y, w = el.get("x", 2040), el.get("y", 300), el.get("w", 1560)
    cur = el.get("current", 0)
    t0 = ctx.at(el["at"])
    a, ink, rule, faint = ctx.col("accent"), ctx.col("ink"), ctx.col("rule"), ctx.col("faint")
    n = len(steps)
    xs = [x + w * k / (n - 1) for k in range(n)]
    out = [B.anim("fade", t0, .25, f'<path d="M{x:g},{y:g} L{x + w:g},{y:g}" stroke="{rule}" stroke-width="8" '
                                    f'stroke-linecap="round"/>')]
    go = ctx.at(el["go_at"]) if el.get("go_at") else None
    if cur > 0:
        done_end = xs[cur - 1] if go is not None else xs[cur]
        out.append(B.anim("fade", t0, .25, f'<path d="M{x:g},{y:g} L{done_end:g},{y:g}" stroke="{ink}" '
                                            f'stroke-width="8" stroke-linecap="round"/>'))
        if go is not None:
            out.append(line(ctx, f'M{xs[cur - 1]:g},{y:g} L{xs[cur]:g},{y:g}', go, .5, color="ink", sw=8))
    for k, s in enumerate(steps):
        st = s if isinstance(s, dict) else {"label": s}
        if k > cur:
            out.append(B.anim("fade", t0, .25, circle(xs[k], y, 16, "#FFFFFF", stroke=faint, sw=6)))
            continue
        when = ctx.at(st["at"]) if st.get("at") else (go if (k == cur and go is not None) else t0)
        if k < cur:
            out.append(B.anim("fade", min(when, t0) if not st.get("at") else when, .25, circle(xs[k], y, 20, ink)))
            g = ctx.glyphs(st["label"], st.get("at"), start=None if st.get("at") else when)
            out.append(B.text(ctx, st["label"], xs[k], y + 100, 58, g, font="sans", weight=700, fill="muted",
                              anchor="middle", settle=False))
        else:
            out.append(B.anim("pop", when, .35, circle(xs[k], y, 30, a)))
            out.append(pulse(ctx, xs[k], y, 54, when + .35))
            g = ctx.glyphs(st["label"], st.get("at"), start=None if st.get("at") else when)
            out.append(B.text(ctx, st["label"], xs[k], y + 100, 62, g, font="sans", weight=800, fill="accent",
                              anchor="middle", settle=False))
    return "".join(out)


def _link_icon(ctx, name, cx, cy, r, at):
    """简介行的小图标：globe 地球、code 代码尖括号、play 播放；线条依次描出。"""
    if name == "globe":
        d = [f"M{cx + r:g},{cy:g} A{r:g},{r:g} 0 1 1 {cx + r - .01:g},{cy - .5:g}",
             f"M{cx:g},{cy - r:g} C{cx + r * .62:g},{cy - r * .5:g} {cx + r * .62:g},{cy + r * .5:g} {cx:g},{cy + r:g} "
             f"C{cx - r * .62:g},{cy + r * .5:g} {cx - r * .62:g},{cy - r * .5:g} {cx:g},{cy - r:g}",
             f"M{cx - r:g},{cy:g} L{cx + r:g},{cy:g}"]
    elif name == "code":
        d = [f"M{cx - r * .35:g},{cy - r * .6:g} L{cx - r:g},{cy:g} L{cx - r * .35:g},{cy + r * .6:g}",
             f"M{cx + r * .35:g},{cy - r * .6:g} L{cx + r:g},{cy:g} L{cx + r * .35:g},{cy + r * .6:g}",
             f"M{cx + r * .18:g},{cy - r * .8:g} L{cx - r * .18:g},{cy + r * .8:g}"]
    elif name == "play":
        d = [f"M{cx - r * .5:g},{cy - r * .75:g} L{cx + r * .8:g},{cy:g} L{cx - r * .5:g},{cy + r * .75:g} Z"]
    else:
        raise ValueError(f"unknown link icon {name!r}")
    return "".join(line(ctx, p, at + .12 * k, .45, color="accent" if k == 0 else "ink", sw=max(6, r / 7))
                   for k, p in enumerate(d))


def desc_links(ctx, el):
    """“地址在简介里”：简介框里一行一个去处（图标 + 名称 + 打码的地址条，不写真实地址）；
    `point_at` 时框描绿、下方箭头指向简介。"""
    rows = el["desc_links"]
    x, y, w = el.get("x", 2100), el.get("y", 620), el.get("w", 1400)
    a, rule, faint = ctx.col("accent"), ctx.col("rule"), ctx.col("faint")
    t0 = ctx.at(el["at"]) if el.get("at") else ctx.at(rows[0]["at"])
    rh, head_h = el.get("row_h", 220), 170
    h = head_h + len(rows) * rh + 30
    out = [B.anim("fade-up", t0, .45, rect(x, y, w, h, "#FFFFFF", radius=36, stroke=rule), ' data-shift="60"')]
    title = el.get("title", "简介")
    tg = ctx.glyphs(title, el.get("title_at"), start=None if el.get("title_at") else t0 + .1)
    out.append(B.text(ctx, title, x + 80, y + 118, 64, tg, font="mono", weight=700, fill="muted", ls=6, settle=False))
    out.append(line(ctx, f"M{x + 80:g},{y + head_h - 6:g} L{x + w - 80:g},{y + head_h - 6:g}", t0 + .2, .5,
                    color="rule", sw=4))
    for k, r in enumerate(rows):
        ry = y + head_h + k * rh + rh / 2
        ta = ctx.at(r["at"])
        out.append(_link_icon(ctx, r.get("icon", "globe"), x + 150, ry, 62, ta))
        out.append(label(ctx, r["label"], r["at"], x + 270, ry - 6, r.get("size", 88), font="sans", weight=800))
        bw = (w - 350) * r.get("w", .78)
        out.append(f'<rect data-anim="grow-bar" data-delay="{ta + .2:.4f}" data-dur="0.5" x="{x + 270:g}" '
                   f'y="{ry + 40:g}" width="{bw:g}" height="38" rx="19" fill="{faint}" fill-opacity="0.55"/>')
    if el.get("point_at"):
        pa = ctx.at(el["point_at"])
        out.append(rect(x - 10, y - 10, w + 20, h + 20, "none", radius=44, stroke=a, sw=8,
                        extra=f' data-anim="draw" data-delay="{pa:.4f}" data-dur="0.5"'))
        ax = x + w / 2
        out.append(line(ctx, f"M{ax:g},{y + h + 50:g} L{ax:g},{y + h + 250:g}", pa + .1, .35, sw=14))
        out.append(line(ctx, f"M{ax - 60:g},{y + h + 190:g} L{ax:g},{y + h + 250:g} L{ax + 60:g},{y + h + 190:g}",
                        pa + .4, .25, sw=14))
    return "".join(out)


def _sanlian_shape(ctx, k, f, *, fill=None, stroke=None, sw=5):
    """点赞（竖拇指）、投币（硬币）、收藏（星）三个图形；局部坐标约 ±45，再按 f 缩放。"""
    st = f' stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"' if stroke else ""
    fl = fill or "none"
    if k == 0:
        return (f'<path d="M-40,-4 L-24,-4 L-24,38 L-40,38 Z M-16,-4 L2,-38 C7,-47 20,-44 17,-31 L13,-13 L34,-13 '
                f'C45,-13 49,-4 47,4 L41,31 C39,37 35,38 29,38 L-16,38 Z" fill="{fl}"{st}/>')
    if k == 1:
        inner = "#FFFFFF" if fill else (stroke or fl)
        return (f'<circle r="42" fill="{fl}"{st}/><circle r="29" fill="none" stroke="{inner}" stroke-width="{sw}"/>'
                f'<text y="15" text-anchor="middle" font-family="{B.esc(ctx.font("heavy"))}" font-size="40" '
                f'font-weight="900" fill="{inner}">币</text>')
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = 46 if i % 2 == 0 else 19
        pts.append(f"{rr * math.cos(ang):.1f},{rr * math.sin(ang) + 3:.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fl}"{st}/>'


def sanlian(ctx, el):
    """一键三连：点赞、投币、收藏三枚图标弹出，外圈一起“长按蓄力”描满，同时点亮并冲击波；
    `follow_at` 时下面弹出“+ 关注”按钮，随即变成“已关注”。"""
    cfg = el["sanlian"]
    cx, cy = el.get("x", 2800), el.get("y", 900)
    gap, s = el.get("gap", 430), el.get("size", 120)
    a, ink, rule, muted = ctx.col("accent"), ctx.col("ink"), ctx.col("rule"), ctx.col("muted")
    t = ctx.at(cfg.get("at") or el["at"])
    charge = cfg.get("charge", .7)
    lit = t + .2 + charge
    f = s / 50
    labels = cfg.get("labels", ["点赞", "投币", "收藏"])
    out = []
    for k in range(3):
        x = cx + (k - 1) * gap
        g0 = t + .08 * k
        base = (circle(0, 0, s * 1.05, "#FFFFFF", stroke=rule, sw=5)
                + f'<g transform="scale({f:g})">{_sanlian_shape(ctx, k, f, stroke=muted, sw=5)}</g>')
        out.append(f'<g transform="translate({x:g},{cy:g})">{B.anim("pop", g0, .4, base)}</g>')
        out.append(f'<g transform="translate({x:g},{cy:g}) rotate(-90)"><circle data-anim="draw" data-ease="in-out" '
                   f'data-delay="{t + .2:.4f}" data-dur="{charge:g}" r="{s * 1.24:g}" fill="none" stroke="{a}" '
                   f'stroke-width="{max(8, s / 10):g}" stroke-linecap="round"/></g>')
        on = (circle(0, 0, s * 1.05, a, extra=' fill-opacity="0.12"')
              + f'<g transform="scale({f:g})">{_sanlian_shape(ctx, k, f, fill=a)}</g>')
        out.append(f'<g transform="translate({x:g},{cy:g})">{B.anim("pop", lit, .35, on)}</g>')
        out.append(f'<g transform="translate({x:g},{cy:g})"><circle data-anim="shockwave" data-delay="{lit:.4f}" '
                   f'data-dur="0.7" data-max="2.2" r="{s * .7:g}" fill="none" stroke="{a}" stroke-width="6"/></g>')
        lab = labels[k]
        out.append(B.text(ctx, lab, x, cy + s * 1.24 + 120, 64,
                          [round(g0 + .15 + B.TYPE_STEP * i, 4) for i in range(len(lab))],
                          font="sans", weight=700, fill="muted", anchor="middle", settle=False))
    if cfg.get("follow_at"):
        fa = ctx.at(cfg["follow_at"])
        bw, bh = el.get("button_w", 620), 170
        bx, by = cx - bw / 2, cy + s * 1.24 + 260
        font = B.esc(ctx.font("heavy"))
        btn = (rect(bx, by, bw, bh, ink, radius=bh / 2)
               + f'<text x="{cx:g}" y="{by + bh / 2 + 30:g}" text-anchor="middle" font-family="{font}" '
                 f'font-size="84" font-weight="900" fill="#FFFFFF">{B.esc(cfg.get("follow", "+ 关注"))}</text>')
        done = (rect(bx, by, bw, bh, "#FFFFFF", radius=bh / 2, stroke=a, sw=8)
                + f'<text x="{cx:g}" y="{by + bh / 2 + 30:g}" text-anchor="middle" font-family="{font}" '
                  f'font-size="84" font-weight="900" fill="{a}">{B.esc(cfg.get("followed", "已关注"))}</text>')
        out.append(B.anim("pop", fa, .4, btn))
        out.append(B.anim("fade", fa + .6, .25, done))
    return "".join(out)


KINDS = {"screenshot": screenshot_stamp, "repeat_flow": repeat_flow, "focus_network": focus_network,
         "time_stretch": time_stretch, "scan_grid": scan_grid, "capacity_gauges": capacity_gauges,
         "device_flow": device_flow, "condense": condense, "cross_check": cross_check, "lanes": lanes,
         "rail": rail, "desc_links": desc_links, "sanlian": sanlian}
