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


def dashed(ctx, d, at, dur=0.5, *, color="faint", sw=6, dash="4 22", direction="left"):
    """虚线按方向揭开（描线原语会覆盖虚线样式，所以虚线用幕布揭示）。"""
    return (f'<g data-anim="wipe" data-dir="{direction}" data-delay="{at:.4f}" data-dur="{dur:g}">'
            f'<path d="{d}" fill="none" stroke="{ctx.col(color)}" stroke-width="{sw:g}" stroke-linecap="round" '
            f'stroke-dasharray="{dash}"/></g>')


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
        # 原图的归一化区域；可写一个 [x,y,w,h]，或几个 [x,y,w,h,绑词?]（按各自绑词依次描出）
        boxes = el["focus"] if isinstance(el["focus"][0], (list, tuple)) else [el["focus"]]
        for box in boxes:
            fx, fy, fw, fh = box[:4]
            cue = box[4] if len(box) > 4 else el.get("focus_at")
            ta = ctx.at(cue) if cue else at + dur
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
        logo = st.get("logo")
        if k < cur:
            dot = (B.brand_mark(ctx, logo, xs[k], y, el.get("logo_r", 34) * .8, sw=4) if logo
                   else circle(xs[k], y, 20, ink))
            out.append(B.anim("fade", min(when, t0) if not st.get("at") else when, .25, dot))
            # 讲过的步骤：名字早已念过，跟着点直接打出，不去后文里找同名的字
            g = (ctx.glyphs(st["label"], st["at"]) if st.get("at") else
                 [round(min(when, t0) + B.TYPE_STEP * i, 4) for i in range(len(st["label"]))])
            out.append(B.text(ctx, st["label"], xs[k], y + 100, 58, g, font="sans", weight=700, fill="muted",
                              anchor="middle", settle=False))
        else:
            lr = el.get("logo_r", 34) * 1.25
            if logo:    # 这一步代表某一方：当前点换成描绿圈的标志
                out.append(pulse(ctx, xs[k], y, lr * 1.6, when + .35))
                out.append(B.anim("pop", when, .35, B.brand_mark(ctx, logo, xs[k], y, lr, ring="accent", sw=6)))
            else:
                out.append(B.anim("pop", when, .35, circle(xs[k], y, 30, a)))
                out.append(pulse(ctx, xs[k], y, 54, when + .35))
            g = ctx.glyphs(st["label"], st.get("at"), start=None if st.get("at") else when)
            out.append(B.text(ctx, st["label"], xs[k], y + 100, 62, g, font="sans", weight=800, fill="accent",
                              anchor="middle", settle=False))
    return "".join(out)


def _clip_frames(src, crop, start, end, fps, width):
    """录屏片段 → 一串 JPEG 帧（按源文件、区间、裁切、帧率、宽度缓存在本次工作目录）。"""
    import hashlib
    import subprocess
    from pathlib import Path

    import config
    st = src.stat()
    key = hashlib.sha256(repr((str(src), st.st_size, st.st_mtime_ns, crop, start, end, fps, width))
                         .encode()).hexdigest()[:16]
    out = Path(config.DIR_ASSETS) / "screen-clips" / key
    done = out / "done.json"
    if not done.exists():
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("f_*.jpg"):
            old.unlink()
        cx, cy, cw, ch = crop
        vf = f"crop={cw}:{ch}:{cx}:{cy},fps={fps},scale={width}:-2"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-i", str(src),
                        "-t", f"{end - start:.3f}", "-vf", vf, "-q:v", "3", str(out / "f_%04d.jpg")], check=True)
        done.write_text("{}", encoding="utf-8")
    frames = sorted(out.glob("f_*.jpg"))
    if not frames:
        raise ValueError(f"screen clip {src.name}: no frames in {start}–{end}s")
    return frames


def _video_dims(src):
    import subprocess
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(src)], capture_output=True, text=True, check=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def _fit(crop, cx, cy, cw, ch):
    """源图区域 crop=(x,y,w,h) 铺满内容区（等比、居中裁掉多余）：返回 (平移x, 平移y, 缩放)。"""
    x, y, w, h = crop
    s = max(cw / w, ch / h)
    return cx + cw / 2 - (x + w / 2) * s, cy + ch / 2 - (y + h / 2) * s, s


def screen(ctx, el):
    """网页/软件窗口：里面按词轴换几段真截图或录屏，可裁切、平移、圈出局部。

    shots: [{at, image|clip, crop?: [x,y,w,h] 源像素, pan?: {to, at, dur}, from?, to?, fps?, play_at?, label?,
             marks?: [{at, box: [x,y,w,h] 源像素, shape?: rect|circle, label?, label_at?, side?}]}]
    录屏先按区间、裁切抽成帧，运行时按 t 显示当前帧（data-anim="frames"），放完停在最后一帧。
    """
    from pipeline.pages import _resolve
    shots = el["screen"]
    x, y, w, h = el.get("x", 1960), el.get("y", 470), el.get("w", 1680), el.get("h", 1060)
    bar = el.get("bar", 76)
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    cx, cy, cw, ch = x, y + bar, w, h - bar
    t_in = ctx.at(el["at"])
    wid = B._id("scr")
    out = [f'<defs><clipPath id="{wid}c"><rect x="{cx:g}" y="{cy:g}" width="{cw:g}" height="{ch:g}" rx="0"/></clipPath>'
           f'<filter id="{wid}s" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="24" '
           f'stdDeviation="34" flood-color="#1A1A17" flood-opacity="0.10"/></filter></defs>',
           rect(x, y, w, h, "#FFFFFF", radius=30, stroke=rule, sw=3, extra=f' filter="url(#{wid}s)"')]
    for k, dot in enumerate(("#E5E2DA", "#E5E2DA", "#E5E2DA")):
        out.append(circle(x + 52 + k * 46, y + bar / 2, 13, dot))
    starts = [ctx.at(s["at"]) for s in shots]
    layers = []
    for k, sh in enumerate(shots):
        t0 = starts[k]
        nxt = starts[k + 1] if k + 1 < len(shots) else None
        src = _resolve(ctx.b.base, sh.get("image") or sh["clip"])
        parts = []
        if sh.get("image"):
            iw, ih = ctx.L.img_dims(str(src))
            crop = sh.get("crop", [0, 0, iw, ih])
            tx, ty, s = _fit(crop, cx, cy, cw, ch)
            img = (f'<image href="{ctx.L.FU(str(src))}" x="0" y="0" width="{iw}" height="{ih}" '
                   f'preserveAspectRatio="none"/>')
            final = (tx, ty, s)
            if sh.get("pan"):
                pan = sh["pan"]
                pa = ctx.at(pan["at"]) if pan.get("at") else t0 + 0.4
                tx1, ty1, s1 = _fit(pan["to"], cx, cy, cw, ch)
                track = [[0, tx, ty, s, 1], [pa, tx, ty, s, 1], [pa + pan.get("dur", 1.2), tx1, ty1, s1, 1]]
                parts.append(B.keys(track, img))
                final = (tx1, ty1, s1)
            else:
                parts.append(f'<g transform="translate({tx:.2f},{ty:.2f}) scale({s:.5f})">{img}</g>')
        else:
            vw, vh = _video_dims(src)
            crop = [int(v) for v in sh.get("crop", [0, 0, vw, vh])]
            fps = sh.get("fps", 30)
            frames = _clip_frames(src, tuple(crop), float(sh.get("from", 0)), float(sh["to"]), fps,
                                  int(sh.get("frame_w", 1280)))
            tx, ty, s = _fit(crop, cx, cy, cw, ch)          # 帧本身就是裁好的区域，标注仍按源像素算
            fw, fh = crop[2], crop[3]
            place = f'x="{tx + crop[0] * s:.2f}" y="{ty + crop[1] * s:.2f}" width="{fw * s:.2f}" height="{fh * s:.2f}"'
            final = (tx, ty, s)
            play = ctx.at(sh["play_at"]) if sh.get("play_at") else t0
            parts.append(f'<image href="{frames[0].as_uri()}" {place} preserveAspectRatio="none"/>')
            imgs = "".join(f'<image href="{f.as_uri()}" {place} preserveAspectRatio="none"/>' for f in frames)
            parts.append(f'<g data-anim="frames" data-delay="{play:.4f}" data-dur="{len(frames) / fps:.4f}" '
                         f'data-fps="{fps:g}">{imgs}</g>')
        content = f'<g clip-path="url(#{wid}c)">{"".join(parts)}</g>'
        if sh.get("label"):
            fs = 44
            lt = ctx.glyphs(sh["label"], sh.get("label_at"), start=None if sh.get("label_at") else t0 + 0.1)
            pw = ctx.width(sh["label"], fs) + 90
            content += (rect(x + w / 2 - pw / 2, y + bar / 2 - 26, pw, 52, ctx.col("page"), radius=26)
                        + B.text(ctx, sh["label"], x + w / 2, y + bar / 2 + 15, fs, lt, font="mono", weight=700,
                                 fill="muted", anchor="middle", settle=False))
        tx, ty, s = final
        for m in sh.get("marks", []):
            ma = ctx.at(m["at"])
            bx, by, bw, bh = m["box"]
            X, Y, W, H = tx + bx * s, ty + by * s, bw * s, bh * s
            if m.get("shape") == "none":      # 只放说明胶囊（例如对着会动的东西，不画框）
                pass
            elif m.get("shape") == "circle":
                r = max(W, H) / 2
                d = f'M{X + W / 2:.1f},{Y + H / 2 - r:.1f} A{r:.1f},{r:.1f} 0 1 1 {X + W / 2 - .1:.1f},{Y + H / 2 - r:.1f}'
                content += line(ctx, d, ma, .5, sw=9)
                content += pulse(ctx, X + W / 2, Y + H / 2, r * 1.15, ma + .5)
            else:
                content += rect(X, Y, W, H, "none", radius=14, stroke=a, sw=8,
                                extra=f' data-anim="draw" data-delay="{ma:.4f}" data-dur="0.5"')
            if m.get("label"):
                fs = m.get("size", 64)
                lw = ctx.width(m["label"], fs) + 64
                side = m.get("side", "below")
                lx = min(max(X + W / 2 - lw / 2, cx + 20), cx + cw - lw - 20)
                ly = Y + H + 26 if side == "below" else Y - fs * 1.6 - 26
                lt = ctx.glyphs(m["label"], m.get("label_at"), start=None if m.get("label_at") else ma + .35)
                chip = (rect(lx, ly, lw, fs * 1.6, a, radius=fs * .8)
                        + B.text(ctx, m["label"], lx + lw / 2, ly + fs * 1.15, fs, lt, font="sans", weight=800,
                                 fill="#FFFFFF", anchor="middle", settle=False))
                content += B.anim("pop", min(lt), .35, chip)
        enter = 0.0 if k == 0 else 0.35
        shot = content if k == 0 else B.anim("fade", t0, enter, content)
        if nxt is not None:
            shot = B.out_at(nxt + 0.35, shot, 0.05)
        layers.append(shot)
    out.extend(layers)
    body = "".join(out)
    if el.get("enter", "rise") == "iris":
        clip = f"{wid}i"
        return (f'<defs><clipPath id="{clip}"><circle data-anim="iris" data-ease="out" data-delay="{t_in:.4f}" '
                f'data-dur="0.7" data-r0="0" data-r1="{math.hypot(w, h):.1f}" cx="{x + w / 2:g}" cy="{y + h / 2:g}" '
                f'r="0"/></clipPath></defs><g clip-path="url(#{clip})">{body}</g>')
    return B.anim("fade-up", t_in, 0.55, body, ' data-shift="80"')


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


def tree(ctx, el):
    """分派树：一个节点按念到往下分出子节点，一层层拆开；结果沿连线流回顶上，顶上只收最后的结果。
    节点 {at, label?, logo?, children?}；`return_at` 结果点从最底层逐层往上流，`fold_at` 中间层变淡，
    `result: {text, at}` 在根节点旁弹出结果卡。"""
    root = el["tree"]
    x, y, w = el.get("x", 2000), el.get("y", 700), el.get("w", 1600)
    gap = el.get("level_gap", 330)
    radii = el.get("node_r", [120, 92, 56, 36])
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    nodes, edges = [], []

    def leaves(n):
        return max(1, sum(leaves(c) for c in n.get("children", [])))

    def place(n, depth, left, span, parent):
        nx, ny = left + span / 2, y + depth * gap
        nr = radii[min(depth, len(radii) - 1)]
        at = ctx.at(n["at"])
        nodes.append((n, depth, nx, ny, nr, at))
        if parent is not None:
            px, py, pr = parent
            edges.append((depth, at, f'M{px:g},{py + pr:g} C{px:g},{(py + ny) / 2:g} {nx:g},{(py + ny) / 2:g} '
                                     f'{nx:g},{ny - nr:g}',
                          f'M{nx:g},{ny - nr:g} C{nx:g},{(py + ny) / 2:g} {px:g},{(py + ny) / 2:g} '
                          f'{px:g},{py + pr:g}'))
        cs = n.get("children", [])
        total = sum(leaves(c) for c in cs)
        cur = left
        for c in cs:
            cw = span * leaves(c) / total
            place(c, depth + 1, cur, cw, (nx, ny, nr))
            cur += cw

    place(root, 0, x, w, None)
    deepest = max(d for _, d, *_ in nodes)
    fold = ctx.at(el["fold_at"]) if el.get("fold_at") else None
    back = ctx.at(el["return_at"]) if el.get("return_at") else None
    step = el.get("return_step", 0.45)
    lower, upper = [], []
    for depth, at, d, rev in edges:
        seg = line(ctx, d, at, .35, color="rule", sw=6 if depth > 1 else 8)
        (lower if depth > 1 else upper).append(seg)
        if back is not None:     # 结果从最底层先走，逐层往上
            ta = back + (deepest - depth) * step
            dot = travelling_dot(ctx, rev, ta, step, r=13 if depth > 1 else 18)
            upper.append(B.out_at(ta + step + .27, dot, .15))   # 到达后停一下再消失
    for n, depth, nx, ny, nr, at in nodes:
        logo = n.get("logo")
        if logo:
            body = B.brand_mark(ctx, logo, nx, ny, nr, ring="accent" if depth == 0 else "rule",
                                sw=max(4, nr * .06))
        else:
            body = circle(nx, ny, nr, ink if depth == 0 else "#FFFFFF", stroke=ink if depth else "none",
                          sw=max(4, nr * .1))
        svg = B.anim("pop", at + .2, .35, body)
        if n.get("label"):
            fs = n.get("size", 76 if depth < 2 else 60)
            svg += label(ctx, n["label"], n.get("label_at") or n["at"], nx, ny + nr + fs * 1.15, fs,
                         anchor="middle", font="sans", weight=800 if depth == 0 else 700, settle=False)
        (upper if depth <= 1 else lower).append(svg)
        if depth == 0:
            upper.append(pulse(ctx, nx, ny, nr * 1.35, at + .55))
    low = "".join(lower)
    if fold is not None:     # 中间过程变淡：顶上只看结果
        low = B.keys([[0, 0, 0, 1, 1], [fold, 0, 0, 1, 1], [fold + .4, 0, 0, 1, .3]], low)
    out = [low, "".join(upper)]
    res = el.get("result")
    if res:
        _, _, rx, ry, rr, _ = nodes[0]
        ra = ctx.at(res["at"])
        fs = res.get("size", 72)
        cw = ctx.width(res["text"], fs) + 200
        bx, by = rx + rr + 70, ry - 70
        chip = rect(bx, by, cw, 140, "#FFFFFF", radius=70, stroke=a, sw=6) + B.text(
            ctx, res["text"], bx + 130, by + 70 + fs * .36, fs, ctx.glyphs(res["text"], res["at"]),
            font="sans", weight=800, settle=False)
        out.append(B.anim("fade-right", ra, .4, chip, ' data-shift="50"'))
        out.append(B.anim("pop", ra + .1, .3, circle(bx + 70, by + 70, 34, a, extra=' fill-opacity="0.15"'))
                   + line(ctx, f'M{bx + 52:g},{by + 70:g} L{bx + 66:g},{by + 86:g} L{bx + 92:g},{by + 54:g}',
                          ra + .2, .3, sw=9))
    return "".join(out)


def _party(ctx, node, cx, cy, r, at, *, ring="ink"):
    """代表某一方的圆：有 logo 放标志，没有就画白底黑圈加绿芯（以后换标志不改版式）。"""
    if node.get("logo"):
        return B.anim("pop", at, .45, B.brand_mark(ctx, node["logo"], cx, cy, r, ring=ring, sw=max(5, r * .06)))
    return B.anim("pop", at, .45, circle(cx, cy, r, "#FFFFFF", stroke=ctx.col(ring), sw=max(6, r * .07))
                  + circle(cx, cy, r * .34, ctx.col("accent")))


def _doc(ctx, w, h):
    """一份交付物（局部坐标 0,0 起）：白纸、折角、三行字线。"""
    ink, block = ctx.col("ink"), ctx.col("block")
    f = w * .28
    out = (f'<path d="M0,0 L{w - f:g},0 L{w:g},{f:g} L{w:g},{h:g} L0,{h:g} Z" fill="#FFFFFF" stroke="{ink}" '
           f'stroke-width="6" stroke-linejoin="round"/>'
           f'<path d="M{w - f:g},0 L{w - f:g},{f:g} L{w:g},{f:g}" fill="{block}" stroke="{ink}" stroke-width="5" '
           f'stroke-linejoin="round"/>')
    for k, lw in enumerate((.62, .7, .46)):
        out += rect(w * .16, h * (.42 + k * .17), w * lw, h * .07, ink if k == 0 else ctx.col("faint"), radius=h * .035)
    return out


def handoff(ctx, el):
    """一方做、另一方审：每行左边做的、右边审的，交付物沿箭头递过去，审的一方到点打勾。
    同一方在上一行审、下一行做时，可用 chain 画一道虚线把两次身份连起来。"""
    cfg = el["handoff"]
    x, y, w = el.get("x", 600), el.get("y", 1150), el.get("w", 2500)
    gap, r = el.get("row_gap", 420), el.get("r", 120)
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    x0, x1 = x, x + w
    out, nodes = [], []
    for k, hd in enumerate(cfg.get("heads", [])[:2]):
        hx = x0 if k == 0 else x1
        out.append(label(ctx, hd["text"], hd["at"], hx, y - r - el.get("head_gap", 90), hd.get("size", 110),
                         anchor="middle", fill="accent" if k else "ink"))
    for k, row in enumerate(cfg["rows"]):
        ry = y + k * gap
        fr, to = row["from"], row["to"]
        tf, tt = ctx.at(fr["at"]), ctx.at(to["at"])
        if tt <= tf:
            raise ValueError("handoff: to.at must follow from.at")
        ls = el.get("label_size", 96)
        out.append(_party(ctx, fr, x0, ry, r, tf))
        out.append(label(ctx, fr["label"], fr.get("label_at") or fr["at"], x0, ry + r + ls + 20, ls, anchor="middle"))
        # 箭头从做的一方画向审的一方，画完正好轮到念审的一方
        sx, ex = x0 + r + 40, x1 - r - 40
        d = f'M{sx:g},{ry:g} L{ex:g},{ry:g}'
        ld = max(.3, tt - tf - .25)
        out.append(line(ctx, d, tf + .2, ld, color="faint", sw=12, extra=' data-ease="in-out"'))
        head = (f'M{ex - 52:g},{ry - 40:g} L{ex:g},{ry:g} L{ex - 52:g},{ry + 40:g}')
        out.append(line(ctx, head, tf + .2 + ld - .05, .25, color="faint", sw=12))
        # 交付物：从做的一方身边出发，沿箭头走到审的一方跟前
        dw, dh = r * 1.05, r * 1.3
        sx_doc, ex_doc = sx + 20, ex - dw - 90
        track = [[0, sx_doc, ry - dh / 2, .6, 0], [tf + .2, sx_doc, ry - dh / 2, .6, 0],
                 [tf + .45, sx_doc, ry - dh / 2 - 40, 1, 1], [tt, ex_doc, ry - dh / 2 - 40, 1, 1]]
        out.append(B.keys(track, _doc(ctx, dw, dh)))
        out.append(_party(ctx, to, x1, ry, r, tt, ring="accent"))
        out.append(label(ctx, to["label"], to.get("label_at") or to["at"], x1, ry + r + ls + 20, ls,
                         anchor="middle", fill="accent"))
        if row.get("check_at"):
            ct = ctx.at(row["check_at"])
            cx_, cy_, br = x1 + r * .78, ry - r * .78, r * .42
            out.append(B.anim("pop", ct, .3, circle(cx_, cy_, br, a) + circle(cx_, cy_, br, "none", stroke="#FFFFFF", sw=6)))
            out.append(f'<path data-anim="draw" data-delay="{ct + .08:.4f}" data-dur="0.22" '
                       f'd="M{cx_ - br * .44:g},{cy_ + br * .02:g} L{cx_ - br * .12:g},{cy_ + br * .34:g} '
                       f'L{cx_ + br * .48:g},{cy_ - br * .3:g}" fill="none" '
                       f'stroke="#FFFFFF" stroke-width="{br * .22:g}" stroke-linecap="round" stroke-linejoin="round"/>')
            out.append(pulse(ctx, x1, ry, r * 1.35, ct + .1))
        nodes.append((row, ry))
    # chain：上一行审的一方 = 下一行做的一方（同一个名字），虚线连起两次出场
    if cfg.get("chain"):
        for (ra, ya), (rb, yb) in zip(nodes, nodes[1:]):
            if ra["to"]["label"] != rb["from"]["label"]:
                continue
            tb = ctx.at(rb["from"]["at"])
            d = (f'M{x1 - r * .7:g},{ya + r * .7:g} C{x1 - 300:g},{ya + gap * .55:g} '
                 f'{x0 + 300:g},{yb - gap * .55:g} {x0 + r * .7:g},{yb - r * .7:g}')
            out.insert(0, dashed(ctx, d, tb - .15, .45, color="faint", sw=8, dash="2 22", direction="right"))
    return "".join(out)


def layers(ctx, el):
    """几层把关（瑞士奶酪）：每层板上有洞，问题点从左飞来，穿过洞就漏过这一层，撞上实心处就被拦下；
    align 让后一层的洞挪到和前一层对齐（看的是同一份东西，盲区重合），之后的问题点一路穿过。"""
    cfg = el["layers"]
    x, y, w, h = el.get("x", 1900), el.get("y", 560), el.get("w", 1700), el.get("h", 1100)
    a, ink, rule, block, page = (ctx.col(k) for k in ("accent", "ink", "rule", "block", "page"))
    slabs = cfg["slabs"]
    n = len(slabs)
    sw = el.get("slab_w", 150)
    hole_ry = el.get("hole_h", h * .12) / 2
    hole_rx = sw * .36
    xs = [x + w * (k + 1) / (n + 1) for k in range(n)]
    align = cfg.get("align")
    al_t = ctx.at(align["at"]) if align else None
    al_d = align.get("dur", .7) if align else 0
    hits = {k: [] for k in range(n)}
    shots = cfg.get("shots", [])
    plans = []
    x_start, x_end = x - el.get("lead", 40), x + w - el.get("tail", 60)
    for s in shots:
        t0 = ctx.at(s["at"])
        lane = y + h * s["lane"]
        stop = s.get("stop")
        if stop is None:
            xe, t_end = x_end, ctx.at(s["end_at"]) if s.get("end_at") else t0 + s.get("dur", 1.1)
        else:
            xe = xs[stop] - sw / 2 - s.get("r", 44) - 6
            t_end = ctx.at(s["hit_at"]) if s.get("hit_at") else t0 + s.get("dur", .9)
            hits[stop].append(t_end)
        if t_end <= t0 + .2:
            raise ValueError("layers: shot needs at least 0.2s to travel")
        plans.append((s, t0, lane, xe, t_end))
    out = []
    for k, sl in enumerate(slabs):
        cx, at = xs[k], ctx.at(sl["at"])
        depth = sw * .32
        body = (rect(cx - sw / 2 + depth, y - depth, sw, h, block, radius=26, stroke=ink, sw=5)
                + f'<path d="M{cx - sw / 2 + 10:g},{y + 4:g} L{cx - sw / 2 + depth + 10:g},{y - depth + 4:g}" stroke="{ink}" stroke-width="5"/>'
                + rect(cx - sw / 2, y, sw, h, "#FFFFFF", radius=26, stroke=ink, sw=6))
        for j, f in enumerate(sl["holes"]):
            hy = y + h * f
            hole = (f'<ellipse cx="{cx:g}" cy="{hy:g}" rx="{hole_rx:g}" ry="{hole_ry:g}" fill="{page}" stroke="{ink}" stroke-width="5"/>'
                    f'<ellipse cx="{cx + hole_rx * .18:g}" cy="{hy - hole_ry * .2:g}" rx="{hole_rx * .72:g}" ry="{hole_ry * .62:g}" '
                    f'fill="{block}"/>')
            if align and align.get("slab") == k:
                dy = h * align["to"][j] - h * f
                hole = B.keys([[0, 0, 0, 1, 1], [al_t, 0, 0, 1, 1], [al_t + al_d, 0, dy, 1, 1]], hole)
            body += hole
        for ht in hits[k]:
            body = f'<g data-anim="shake" data-delay="{ht:.4f}" data-amp="14">{body}</g>'
        out.append(B.anim("fade-up", at, .5, body, ' data-shift="60"'))
        if sl.get("label"):
            out.append(label(ctx, sl["label"], sl.get("label_at") or sl["at"], cx, y + h + 150,
                             sl.get("size", 100), anchor="middle"))
        if sl.get("logo"):
            out.append(B.anim("pop", ctx.at(sl.get("label_at") or sl["at"]), .4,
                              B.brand_mark(ctx, sl["logo"], cx, y - depth - 110, 70)))
    if align and align.get("label"):
        out.append(label(ctx, align["label"], align.get("label_at") or align["at"], (xs[0] + xs[-1]) / 2,
                         y - 150, align.get("size", 80), anchor="middle", font="sans", weight=800, fill="accent"))
        if n > 1:
            for f in align["to"]:
                hy = y + h * f
                out.append(dashed(ctx, f'M{xs[0]:g},{hy:g} L{xs[-1]:g},{hy:g}', al_t + al_d, .4, color="accent", sw=6,
                                  dash="14 18"))
    for s, t0, lane, xe, t_end in plans:
        r = s.get("r", 44)
        if s.get("glyph") == "image":   # 一组图（3×3 小方块）代替圆点，用来指认“那九张图”
            cell, g = r * .56, r * .14
            dot = rect(-r, -r, 2 * r, 2 * r, "#FFFFFF", radius=14, stroke=ink, sw=5)
            for q in range(9):
                dot += rect(-r + g * 1.3 + (q % 3) * (cell + g * .5), -r + g * 1.3 + (q // 3) * (cell + g * .5),
                            cell, cell, a, radius=4)
        else:
            dot = circle(0, 0, r, ink) + circle(-r * .3, -r * .3, r * .28, "#FFFFFF", extra=' fill-opacity="0.35"')
        pid = B._id("shot")
        path = f'<path id="{pid}" d="M{x_start:g},{lane:g} L{xe:g},{lane:g}" fill="none" stroke="none"/>'
        mover = (f'<g data-anim="move-along" data-ease="linear" data-delay="{t0:.4f}" data-dur="{t_end - t0:.4f}" '
                 f'data-path="#{pid}" data-x0="0" data-y0="0">{dot}</g>')
        trail = line(ctx, f'M{x_start:g},{lane:g} L{xe:g},{lane:g}', t0, t_end - t0, color="rule", sw=8,
                     extra=' data-ease="linear"')
        stop = s.get("stop")
        group = [path + trail + mover]
        speed = (xe - x_start) / (t_end - t0)
        for k, cx in enumerate(xs):     # 穿过的每一层，洞口闪一下
            if (stop is None or k < stop) and x_start < cx < xe:
                tp = t0 + (cx - x_start) / speed
                ring = (f'<ellipse cx="{cx:g}" cy="{lane:g}" rx="{hole_rx + 18:g}" ry="{hole_ry + 18:g}" fill="none" '
                        f'stroke="{a}" stroke-width="8"/>')
                group.append(B.anim("pop", tp - .05, .3, ring))
        if stop is not None:
            hx = xs[stop] - sw / 2
            group.append(f'<g transform="translate({hx:g},{lane:g})"><circle data-anim="shockwave" data-delay="{t_end:.4f}" '
                         f'data-dur="0.6" data-max="3.2" r="{r * 1.1:g}" fill="none" stroke="{a}" stroke-width="8"/></g>')
        if s.get("label"):
            lt = s.get("label_at") or s["at"]
            ls = s.get("size", 92)
            if stop is None:     # 漏过去的：名字写在停下的点上方
                group.append(label(ctx, s["label"], lt, xe, lane - r - 44, ls, anchor="middle", fill="ink"))
            else:                # 被拦下的：名字写在这一层右侧
                group.append(label(ctx, s["label"], lt, xs[stop] + sw / 2 + 60, lane + ls * .36, ls, fill="accent"))
        # 被拦下的点到 clear_at（默认洞对齐时）淡出，免得卡在挪过来的洞口
        clear = s.get("clear_at") or (align["at"] if (align and stop is not None) else None)
        body = "".join(group)
        out.append(B.anim("fade-out", ctx.at(clear), .3, body) if clear else body)
    return "".join(out)


def gate(ctx, el):
    """只把挑定的几样递给接收方：几张签条在左边按念到出现，依次飞进右边的空位；
    被挡下的那张在半路撞上闸门弹回、变淡划掉。"""
    cfg = el["gate"]
    x, y, w = el.get("x", 240), el.get("y", 620), el.get("w", 3360)
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    items = cfg["items"]
    ch, cgap = el.get("chip_h", 170), el.get("chip_gap", 60)
    size = el.get("size", 92)
    cw = el.get("chip_w", 900)
    rcv = cfg["receiver"]
    rx, rw = x + w - el.get("receiver_w", 1300), el.get("receiver_w", 1300)
    passing = [k for k, it in enumerate(items) if not it.get("block_at")]
    rh = el.get("receiver_h", 220 + len(passing) * (ch + 40) + 60)
    ry = y
    bx = el.get("barrier_x", (x + cw + rx) / 2)
    out = []
    # 接收方：卡片、小标签、眼睛图标、几个虚线空位
    ra = ctx.at(rcv["at"])
    sid = B._id("gate")
    box = (f'<defs><filter id="{sid}" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="18" '
           f'stdDeviation="30" flood-color="#1A1A17" flood-opacity="0.07"/></filter></defs>'
           + rect(rx, ry, rw, rh, "#FFFFFF", radius=36, stroke=rule, extra=f' filter="url(#{sid})"'))
    out.append(B.anim("fade-up", ra, .5, box, ' data-shift="70"'))
    out.append(label(ctx, rcv["label"], rcv.get("label_at") or rcv["at"], rx + 80, ry + 150, rcv.get("size", 110)))
    if rcv.get("logo"):
        out.append(B.anim("pop", ra + .2, .4, B.brand_mark(ctx, rcv["logo"], rx + rw - 150, ry + 110, 70)))
    else:
        out.append(B.icon(ctx, rcv.get("icon", "eye"), rx + rw - 150, ry + 110, 130, ra + .2))
    slots = []
    st = ctx.at(rcv["slots_at"]) if rcv.get("slots_at") else ra + .3
    for j, k in enumerate(passing):
        sx, sy = rx + 80, ry + 250 + j * (ch + 40)
        slots.append((sx, sy))
        out.append(B.anim("pop", st + j * .12, .35, rect(sx, sy, rw - 160, ch, ctx.col("page"), radius=ch / 2,
                                                       stroke=ctx.col("faint"), sw=5, extra=' stroke-dasharray="20 16"')))
    # 闸门：被挡的那张来时落下
    blocked = [it for it in items if it.get("block_at")]
    if blocked:
        gt = ctx.at(cfg["barrier_at"]) if cfg.get("barrier_at") else ctx.at(blocked[0]["block_at"])
        gy0, gy1 = y + el.get("barrier_top", 0), y + el.get("barrier_h", rh)
        out.append(line(ctx, f'M{bx:g},{gy0:g} L{bx:g},{gy1:g}', gt, .35, color="ink", sw=14))
        out.append(B.icon(ctx, "lock", bx, gy0 - 90, 120, gt + .15))
    slot_i = 0
    for k, it in enumerate(items):
        cy = y + k * (ch + cgap) + el.get("chip_top", 60)
        at = ctx.at(it["at"])
        g = ctx.glyphs(B.plain_of(it["text"]), it.get("text_at") or it["at"])
        tw = ctx.width(B.plain_of(it["text"]), size)
        cwk = max(cw * .55, min(cw, tw + 200))
        chip = (rect(0, 0, cwk, ch, "#FFFFFF", radius=ch / 2, stroke=ink if not it.get("block_at") else rule, sw=5)
                + rect(40, ch / 2 - 30, 60, 60, a if not it.get("block_at") else ctx.col("faint"), radius=30))
        body = chip + B.text(ctx, it["text"], 130, ch / 2 + size * .36, size, g, settle=False)
        if it.get("block_at"):
            bt = ctx.at(it["block_at"])
            reach = bx - x - cwk - 18
            track = [[0, 0, 0, 1, 1], [bt, 0, 0, 1, 1], [bt + .3, reach, 0, 1, 1], [bt + .55, reach - 90, 0, 1, 1]]
            if it.get("dim_at"):
                dt = ctx.at(it["dim_at"])
                if dt < bt + .55:
                    raise ValueError("gate: dim_at must come after the bounce")
                track += [[dt, reach - 90, 0, 1, 1], [dt + .35, reach - 90, 0, 1, .38]]
                body += (f'<path data-anim="draw" data-delay="{dt:.4f}" data-dur="0.3" d="M110,{ch / 2:g} L{cwk - 50:g},{ch / 2:g}" '
                         f'stroke="{ink}" stroke-width="10" stroke-linecap="round"/>')
            inner = B.keys(track, body)
            out.append(f'<g transform="translate({x:g},{cy:g})">' + B.anim("fade-up", at, .4, inner, ' data-shift="40"') + '</g>')
            out.append(f'<g transform="translate({bx:g},{cy + ch / 2:g})"><circle data-anim="shockwave" '
                       f'data-delay="{bt + .3:.4f}" data-dur="0.6" data-max="2.6" r="70" fill="none" stroke="{ink}" '
                       f'stroke-width="7"/></g>')
            continue
        sx, sy = slots[slot_i]
        slot_i += 1
        mt = ctx.at(it["move_at"]) if it.get("move_at") else max(g) + it.get("wait", .3)
        s = min(1.0, (rw - 160) / cwk)
        track = [[0, 0, 0, 1, 1], [mt, 0, 0, 1, 1], [mt + .55, sx - x, sy - cy, s, 1]]
        inner = B.keys(track, body)
        out.append(f'<g transform="translate({x:g},{cy:g})">' + B.anim("fade-up", at, .4, inner, ' data-shift="40"') + '</g>')
        out.append(B.anim("pop", mt + .5, .3, rect(sx - 10, sy - 10, rw - 140, ch + 20, "none", radius=(ch + 20) / 2,
                                                  stroke=a, sw=8)))
    return "".join(out)


def verdict(ctx, el):
    """一句交回来的结论（如“做完了”）：带勾的胶囊弹出；到 doubt_at 勾变灰、盖上黑色问号、胶囊一震。"""
    cfg = el["verdict"]
    x, y = el.get("x", 2200), el.get("y", 1500)
    size = cfg.get("size", 120)
    a, ink = ctx.col("accent"), ctx.col("ink")
    at = ctx.at(el["at"])
    txt = cfg["text"]
    g = ctx.glyphs(B.plain_of(txt), cfg.get("text_at") or el["at"])
    h = size * 1.9
    tw = ctx.width(B.plain_of(txt), size)
    w = tw + h + 120
    sid = B._id("vd")
    pill = (f'<defs><filter id="{sid}" x="-10%" y="-20%" width="120%" height="160%"><feDropShadow dx="0" dy="16" '
            f'stdDeviation="24" flood-color="#1A1A17" flood-opacity="0.12"/></filter></defs>'
            + rect(0, 0, w, h, "#FFFFFF", radius=h / 2, stroke=ctx.col("rule"), extra=f' filter="url(#{sid})"'))
    cx, cy = h / 2, h / 2
    disc = circle(cx, cy, h * .33, a)
    tick = (f'<path data-anim="draw" data-delay="{at + .25:.4f}" data-dur="0.3" '
            f'd="M{cx - h * .14:g},{cy + h * .01:g} L{cx - h * .04:g},{cy + h * .11:g} L{cx + h * .15:g},{cy - h * .1:g}" '
            f'fill="none" stroke="#FFFFFF" stroke-width="{h * .06:g}" stroke-linecap="round" stroke-linejoin="round"/>')
    body = pill + B.anim("pop", at + .1, .3, disc) + tick
    body += B.text(ctx, txt, h * .9, h / 2 + size * .36, size, g, settle=False)
    if cfg.get("doubt_at"):
        dt = ctx.at(cfg["doubt_at"])
        body += B.anim("fade", dt, .3, circle(cx, cy, h * .36, ctx.col("faint")))
        qx, qy, qr = w - h * .12, -h * .08, h * .36
        q = (circle(qx, qy, qr, ink) + f'<text x="{qx:g}" y="{qy + qr * .42:g}" text-anchor="middle" '
             f'font-family="{B.esc(ctx.font("heavy"))}" font-size="{qr * 1.25:g}" font-weight="900" fill="#FFFFFF">?</text>')
        body += B.anim("stamp", dt + .05, .35, q)
        body = f'<g data-anim="shake" data-delay="{dt + .3:.4f}" data-amp="18">{body}</g>'
    out = [f'<g transform="translate({x:g},{y:g})">{B.anim("pop", at, .45, body)}</g>']
    if cfg.get("label"):
        out.append(label(ctx, cfg["label"], cfg.get("label_at") or el["at"], x + 20, y - 50, 60,
                         font="mono", weight=700, fill="muted", settle=False))
    return "".join(out)


KINDS = {"screenshot": screenshot_stamp, "repeat_flow": repeat_flow, "focus_network": focus_network,
         "time_stretch": time_stretch, "scan_grid": scan_grid, "capacity_gauges": capacity_gauges,
         "device_flow": device_flow, "condense": condense, "cross_check": cross_check, "lanes": lanes,
         "rail": rail, "screen": screen, "desc_links": desc_links, "sanlian": sanlian, "tree": tree, "handoff": handoff, "layers": layers, "gate": gate, "verdict": verdict}
