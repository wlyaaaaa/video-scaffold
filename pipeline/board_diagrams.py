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
    t0 = ctx.at(el["at"])
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    nodes, points, out = cfg["nodes"], [], []
    for k, node in enumerate(nodes):
        angle = node.get("angle", -90 + k * 360 / len(nodes)) * math.pi / 180
        nx, ny = cx + radius*math.cos(angle), cy + radius*math.sin(angle)
        points.append((nx, ny))
        at = ctx.at(node.get("at", el["at"]))
        out.append(line(ctx, f'M{cx},{cy} L{nx},{ny}', at, .6, color="rule", sw=5))
        out.append(B.anim("pop", at, .45, circle(nx, ny, 60, "#FFFFFF", stroke=rule, sw=5)))
        if node.get("label"):
            dx, dy = node.get("label_offset", [0, 124])
            out.append(label(ctx, node["label"], node.get("at", el["at"]), nx+dx, ny+dy,
                             node.get("size", 74), anchor="middle", font="sans", weight=700))
    hub = [B.anim("pop", t0, .5, circle(cx, cy, 112, ink))]
    if cfg.get("center"):
        hub.append(label(ctx, cfg["center"], el["at"], cx, cy+28, 70, fill="#FFFFFF", anchor="middle"))
    ring = f'M{cx},{cy-155} A155,155 0 1 1 {cx-.1},{cy-155}'
    out.append(line(ctx, ring, t0, .7, color="rule", sw=5))
    out.append(travelling_dot(ctx, ring, t0+.2, 3, r=15, loop=True))
    visits = cfg.get("visits", [])
    for k, visit in enumerate(visits):
        nx, ny = points[visit["node"]]
        ta = ctx.at(visit["at"])
        nxt = ctx.at(visits[k+1]["at"]) if k+1 < len(visits) else None
        d = f'M{cx},{cy} L{nx},{ny}'
        lit = line(ctx, d, ta, .4, sw=12) + pulse(ctx, nx, ny, 110, ta)
        lit += travelling_dot(ctx, d, ta, .7, r=20)
        out.append(B.out_at(nxt, lit))
    if cfg.get("expand_at"):
        ta = ctx.at(cfg["expand_at"])
        for k, (nx, ny) in enumerate(points):
            at = ta + k * .09
            d = f'M{cx},{cy} L{nx},{ny}'
            out.append(line(ctx, d, at, .65, sw=10))
            out.append(travelling_dot(ctx, d, at, 1, r=17))
            out.append(B.anim("pop", at+.4, .35, circle(nx, ny, 38, a)))
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


KINDS = {"screenshot": screenshot_stamp, "repeat_flow": repeat_flow, "focus_network": focus_network,
         "time_stretch": time_stretch, "scan_grid": scan_grid, "capacity_gauges": capacity_gauges,
         "device_flow": device_flow}
