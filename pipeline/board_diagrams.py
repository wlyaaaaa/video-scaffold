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


def _track(points, what):
    """keys 关键帧要按时间递增；绑词顺序写反时直接报错，不让动画倒着走。"""
    for p, q in zip(points, points[1:]):
        if q[0] < p[0] - 1e-6:
            raise ValueError(f"{what}: cue times go backwards ({p[0]:.2f}s → {q[0]:.2f}s)")
    return points


def _spines(ctx, xs, top, sw_, sh_, labels, current, *, size=76):
    """一排书脊（卷宗）。返回每本的 SVG（局部坐标，按书脊左上角摆好），最后一本（current）绿色。"""
    a, rule = ctx.col("accent"), ctx.col("rule")
    out = []
    for k, (sx, lab) in enumerate(zip(xs, labels)):
        cur = k == current
        body = rect(sx, top, sw_, sh_, a if cur else "#FFFFFF", radius=22, stroke=a if cur else rule, sw=5)
        body += rect(sx + sw_ * 0.2, top + 70, sw_ * 0.6, 110, "#FFFFFF" if cur else ctx.col("block"), radius=14,
                     extra=f' fill-opacity="{0.9 if cur else 1}"')
        body += (f'<text x="{sx + sw_ / 2:g}" y="{top + 125 + size * 0.36:g}" text-anchor="middle" '
                 f'font-family="{B.esc(ctx.font("mono"))}" font-size="{size}" font-weight="700" '
                 f'fill="{a if cur else ctx.col("muted")}">{B.esc(lab)}</text>')
        for j in range(3):      # 书脊下部几道细纹，像装订线
            yy = top + sh_ - 150 + j * 34
            body += rect(sx + 26, yy, sw_ - 52, 8, "#FFFFFF" if cur else rule, radius=4,
                         extra=f' fill-opacity="{0.55 if cur else 1}"')
        out.append(body)
    return out


def archive(ctx, el):
    """原话档案：原话一条条接在账页末尾（只往后加）；到点上锁（不改一个字）；
    整页合进最新一卷、和前几个月的书脊排成一排（按月分卷）；之后可抽出某一卷（出了问题再翻）。"""
    cfg = el["archive"]
    x, y, w, h = el.get("x", 2000), el.get("y", 540), el.get("w", 1600), el.get("h", 1240)
    a, ink = ctx.col("accent"), ctx.col("ink")
    t0 = ctx.at(el["at"])
    entries = cfg["entries"]
    rh, gap, head_h = cfg.get("row_h", 120), cfg.get("gap", 28), cfg.get("head_h", 190)
    pw = cfg.get("page_w", w)
    ph = min(h, head_h + len(entries) * (rh + gap) + 60)
    page = [rect(0, 0, pw, ph, "#FFFFFF", radius=36, stroke=ctx.col("rule"), sw=4),
            rect(0, 40, 18, ph - 80, a, radius=9)]
    lab = []
    if cfg.get("page_label"):
        lab.append(label(ctx, cfg["page_label"], cfg.get("page_label_at") or el["at"], 80, 120, 84))
    rows = []
    for k, en in enumerate(entries):
        at = ctx.at(en["at"])
        ry = head_h + k * (rh + gap)
        bub = _bubble(ctx, pw - 160, rh, True, en.get("lines", 1))
        track = _track([[at, 0, 90, 1, 0], [at + 0.45, 0, 0, 1, 1]], "archive entry")
        rows.append(f'<g transform="translate(80,{ry:g})">{B.keys(track, bub)}</g>')
    lock = ""
    if cfg.get("lock_at"):
        la = ctx.at(cfg["lock_at"])
        lock = (rect(-10, -10, pw + 20, ph + 20, "none", radius=44, stroke=a, sw=8,
                     extra=f' data-anim="draw" data-delay="{la:.4f}" data-dur="0.5"')
                + B.icon(ctx, "lock", pw - 120, 100, 120, la))
    inner = B.anim("fade-up", t0, .5, "".join(page), ' data-shift="60"') + "".join(lab) + "".join(rows) + lock
    labels = cfg.get("volumes", [])
    nv = len(labels)
    out = []
    if nv:
        va = ctx.at(cfg["volumes_at"])
        sw_, sh_ = cfg.get("spine_w", 260), cfg.get("spine_h", min(860, h - 240))
        sgap = cfg.get("spine_gap", 70)
        total = nv * sw_ + (nv - 1) * sgap
        x0 = x + (w - total) / 2
        top = y + h - sh_ - 90
        xs = [x0 + k * (sw_ + sgap) for k in range(nv)]
        spines = _spines(ctx, xs, top, sw_, sh_, labels, nv - 1)
        shelf = line(ctx, f"M{x:g},{top + sh_ + 30:g} L{x + w:g},{top + sh_ + 30:g}", va, .5, color="rule", sw=14)
        pull = cfg.get("pull")
        pk, pt = (pull.get("index", 0), ctx.at(pull["at"])) if pull else (None, None)
        for k, sp in enumerate(spines):
            d = va + 0.12 * k if k < nv - 1 else va + 0.45
            if k == pk and pt < d + 0.45:
                raise ValueError("archive pull must come after the volume is on the shelf")
            body = (f'<rect data-anim="grow-bar" data-grow="y" data-delay="{d:.4f}" data-dur="0.45" x="{xs[k]:g}" '
                    f'y="{top:g}" width="{sw_:g}" height="{sh_:g}" rx="22" fill="{a if k == nv - 1 else ctx.col("rule")}"/>'
                    + B.anim("fade", d + 0.3, 0.25, sp))
            if k == pk:
                body = B.keys([[0, 0, 0, 1, 1], [pt, 0, 0, 1, 1], [pt + 0.45, 0, -150, 1, 1]], body)
                body += rect(xs[k] - 16, top - 166, sw_ + 32, sh_ + 32, "none", radius=30, stroke=a, sw=9,
                             extra=f' data-anim="draw" data-delay="{pt + 0.2:.4f}" data-dur="0.4"')
            out.append(body)
        # 账页合进最新一卷：缩到书脊位置并淡去，书脊接着长出来
        s = sw_ / pw
        cx_last = xs[-1]
        track = _track([[0, 0, 0, 1, 1], [va + 0.05, 0, 0, 1, 1],
                        [va + 0.5, cx_last - x, top - y, s, 0]], "archive close")
        out.insert(0, shelf)
        page_g = f'<g transform="translate({x:g},{y:g})">{B.keys(track, inner)}</g>'
        return page_g + "".join(out)
    return f'<g transform="translate({x:g},{y:g})">{inner}</g>'


def fork(ctx, el):
    """同一句回答，接在不同问题后面，意思不同：每行“问题 → 回答 → 意思”，回答从第一行复制到后面几行。"""
    cfg = el["fork"]
    x, y, w = el.get("x", 1960), el.get("y", 620), el.get("w", 1640)
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    rows = cfg["branches"]
    rh, rgap = cfg.get("row_h", 190), cfg.get("row_gap", 330)
    qw, aw = cfg.get("question_w", 640), cfg.get("answer_w", 440)
    rw = w - qw - aw - 2 * cfg.get("link", 110)
    ax = x + qw + cfg.get("link", 110)
    rx = ax + aw + cfg.get("link", 110)
    ans = cfg["answer"]
    a_at = ctx.at(cfg["answer_at"])
    a_glyphs = ctx.glyphs(B.plain_of(ans), cfg["answer_at"])
    fs = cfg.get("size", round(rh * 0.5))
    out = []
    first_y = y
    for k, br in enumerate(rows):
        ry = y + k * (rh + rgap)
        qt = ctx.at(br["at"])
        q = rect(0, 0, qw, rh, "#FFFFFF", radius=rh / 2, stroke=rule)
        q += circle(rh / 2, rh / 2, rh * 0.32, ink)
        q += (f'<text x="{rh / 2:g}" y="{rh / 2 + rh * 0.11:g}" text-anchor="middle" font-family="{B.esc(ctx.font("mono"))}" '
              f'font-size="{rh * 0.3:g}" font-weight="700" fill="#FFFFFF">AI</text>')
        for j, f in enumerate((0.52, 0.34)):
            q += rect(rh + 10, rh / 2 - 30 + j * 44, (qw - rh - 150) * f / 0.52, 18, ctx.col("faint"), radius=9,
                      extra=' fill-opacity="0.6"')
        q += (f'<text x="{qw - 80:g}" y="{rh / 2 + rh * 0.22:g}" text-anchor="middle" font-family="{B.esc(ctx.font("heavy"))}" '
              f'font-size="{rh * 0.62:g}" font-weight="900" fill="{a}">？</text>')
        out.append(f'<g transform="translate({x:g},{ry:g})">' + B.anim("fade-right", qt, .45, q, ' data-shift="60"') + '</g>')
        if br.get("label"):
            out.append(label(ctx, br["label"], br.get("label_at") or br["at"], x + 10, ry - 34, 60, font="mono",
                             weight=700, fill="muted", settle=False))
        # 回答：第一行在 answer_at 出现；后面几行从第一行复制下来
        show = max(a_at, qt) if k == 0 else max(qt, a_at) + 0.1
        chip = rect(0, 0, aw, rh, "#E6F4EF", radius=rh / 2, stroke=a, sw=5)
        if k == 0:
            txt = B.text(ctx, ans, aw / 2, rh / 2 + fs * 0.36, fs, a_glyphs, anchor="middle")
            body = B.anim("pop", show, .4, chip) + txt
            out.append(f'<g transform="translate({ax:g},{ry:g})">{body}</g>')
        else:
            txt = (f'<text x="{aw / 2:g}" y="{rh / 2 + fs * 0.36:g}" text-anchor="middle" font-family="{B.esc(ctx.font("heavy"))}" '
                   f'font-size="{fs:g}" font-weight="900" fill="{ink}">{B.esc(B.plain_of(ans))}</text>')
            track = _track([[show, 0, first_y - ry, 1, 0], [show + 0.05, 0, first_y - ry, 1, 1],
                            [show + 0.6, 0, 0, 1, 1]], "fork answer")
            out.append(f'<g transform="translate({ax:g},{ry:g})">{B.keys(track, chip + txt)}</g>')
        lq = f"M{x + qw + 14:g},{ry + rh / 2:g} L{ax - 14:g},{ry + rh / 2:g}"
        out.insert(0, line(ctx, lq, show + (0 if k == 0 else 0.5), .3, color="rule", sw=8))
        # 意思
        if br.get("result"):
            rt = ctx.at(br["result_at"])
            hot = br.get("accent", False)
            res = rect(0, 0, rw, rh, a if hot else "#FFFFFF", radius=28, stroke=a if hot else ctx.col("faint"), sw=5)
            rs = br.get("size", fs)
            res += (f'<text x="{rw / 2:g}" y="{rh / 2 + rs * 0.36:g}" text-anchor="middle" font-family="{B.esc(ctx.font("heavy"))}" '
                    f'font-size="{rs:g}" font-weight="900" fill="{"#FFFFFF" if hot else ink}">'
                    f'{B.esc(br["result"])}</text>')
            out.append(line(ctx, f"M{ax + aw + 14:g},{ry + rh / 2:g} L{rx - 24:g},{ry + rh / 2:g}", rt, .3,
                            color="accent" if hot else "faint", sw=8,
                            extra=' marker-end="url(#arrow)"' if cfg.get("arrows") else ""))
            out.append(f'<g transform="translate({rx:g},{ry:g})">' + B.anim("pop", rt + 0.2, .4, res) + '</g>')
    return "".join(out)


def recall(ctx, el):
    """动手之前自动翻档案：AI 要做的事一出来，就去原话档案里找同一件事的原话，飞到它眼前排好，
    带着分类和出处；项目规矩也一起带上；禁令排到最前，不算数的划掉掉出去。"""
    cfg = el["recall"]
    a, ink, rule, muted = ctx.col("accent"), ctx.col("ink"), ctx.col("rule"), ctx.col("muted")
    out = []
    # ---- 左：做事的 AI 和它要做的事 --------------------------------------------------------------
    ag = cfg.get("agent", {})
    ax, ay = ag.get("x", 240), ag.get("y", 560)
    aw_ = ag.get("w", 900)
    t_agent = ctx.at(ag.get("at") or el["at"])
    nx, ny, nr = ax + 110, ay + 110, 100
    node = circle(nx, ny, nr, ink) + (f'<text x="{nx:g}" y="{ny + 26:g}" text-anchor="middle" '
                                      f'font-family="{B.esc(ctx.font("mono"))}" font-size="72" font-weight="700" '
                                      f'fill="#FFFFFF">AI</text>')
    out.append(B.anim("pop", t_agent, .45, node))
    if ag.get("label"):
        out.append(label(ctx, ag["label"], ag.get("label_at") or ag.get("at") or el["at"], nx + nr + 50, ny + 30,
                         ag.get("label_size", 84), font="sans", weight=800))
    acts = cfg.get("actions", [])
    ph, pgap = cfg.get("action_h", 150), cfg.get("action_gap", 36)
    py0 = ay + 2 * nr + 120
    times = [ctx.at(it["at"]) for it in acts]
    for k, it in enumerate(acts):
        py = py0 + k * (ph + pgap)
        pw = aw_ - 60
        t = times[k]
        nxt = times[k + 1] if k + 1 < len(times) else None
        pill = rect(ax + 30, py, pw, ph, "#FFFFFF", radius=ph / 2, stroke=rule, sw=4)
        hot = rect(ax + 30, py, pw, ph, a, radius=ph / 2, extra=' fill-opacity="0.14"')
        hot += rect(ax + 30, py, pw, ph, "none", radius=ph / 2, stroke=a, sw=6)
        out.append(B.anim("fade-up", t, .4, pill, ' data-shift="40"'))
        out.append(B.out_at(nxt, B.anim("fade", t, .25, hot), .3))
        txt = it["text"]
        out.append(B.text(ctx, txt, ax + 30 + 90, py + ph / 2 + 36, it.get("size", 100),
                          ctx.glyphs(B.plain_of(txt), it["at"])))
    task = cfg.get("task")
    if task:
        tt = ctx.at(task["at"])
        fy = py0 - 90
        fh = len(acts) * (ph + pgap) - pgap + 130
        out.append(rect(ax, fy, aw_, fh, "none", radius=40, stroke=a, sw=8,
                        extra=f' data-anim="draw" data-delay="{tt:.4f}" data-dur="0.5"'))
        out.append(label(ctx, task["label"], task.get("label_at") or task["at"], ax + 30, fy + fh + 90, 72,
                         font="mono", weight=700, fill="accent", settle=False))
    # ---- 右：原话档案（按月的几卷） ----------------------------------------------------------------
    ar = cfg["archive"]
    zx, zy, zw = ar.get("x", 2700), ar.get("y", 560), ar.get("w", 900)
    vols = ar.get("volumes", ["8月", "9月", "10月"])
    nv = len(vols)
    sw_, sgap = ar.get("spine_w", 240), ar.get("spine_gap", 50)
    sh_ = ar.get("spine_h", 820)
    x0 = zx + (zw - (nv * sw_ + (nv - 1) * sgap)) / 2
    top = zy + 170
    xs = [x0 + k * (sw_ + sgap) for k in range(nv)]
    t_ar = ctx.at(ar["at"])
    arch = [label(ctx, ar.get("label", "原话档案"), ar.get("label_at") or ar["at"], zx + zw / 2, zy + 84, 92,
                  anchor="middle")]
    arch.append(line(ctx, f"M{zx:g},{top + sh_ + 30:g} L{zx + zw:g},{top + sh_ + 30:g}", t_ar, .4, color="rule", sw=14))
    for k, sp in enumerate(_spines(ctx, xs, top, sw_, sh_, vols, nv - 1, size=72)):
        arch.append(B.anim("fade-up", t_ar + 0.1 * k, .4, sp, ' data-shift="60"'))
    if ar.get("match_at"):       # 找到同一件事的原话：几卷依次亮一下
        mt = ctx.at(ar["match_at"])
        for k in range(nv):
            arch.append(B.anim("pulse", mt + 0.12 * k, .4,
                               rect(xs[k] - 14, top - 14, sw_ + 28, sh_ + 28, "none", radius=30, stroke=a, sw=8),
                               ' data-amp="0.02" data-spd="5" data-opmin="0.35"'))
    archive_g = "".join(arch)
    # ---- 中：摆到眼前的原话 -------------------------------------------------------------------------
    st = cfg.get("stack", {})
    sx, sy0 = st.get("x", 1300), st.get("y", 560)
    cw, ch, cgap = st.get("w", 1220), st.get("h", 190), st.get("gap", 34)
    q = cfg.get("query")
    if q:
        qa = ctx.at(q["at"])
        qy = q.get("y", sy0 + 2 * (ch + cgap) + ch / 2)
        d = f"M{ax + aw_ + 20:g},{qy:g} L{zx - 30:g},{qy:g}"
        beam = (f'<path d="{d}" fill="none" stroke="{a}" stroke-width="8" stroke-dasharray="6 26" stroke-linecap="round" '
                f'data-anim="draw" data-delay="{qa:.4f}" data-dur="0.5"/>' + travelling_dot(ctx, d, qa + .3, 1.0, r=20, loop=True))
        until = ctx.at(q["until"]) if q.get("until") else None
        out.append(B.out_at(until, beam, .3))
    items = cfg["items"]
    arrivals = sorted(range(len(items)), key=lambda k: ctx.at(items[k]["at"]))
    arr_slot = {k: n for n, k in enumerate(arrivals)}
    ranks = cfg.get("order") or list(range(len(items)))
    sort_t = ctx.at(cfg["sort_at"]) if cfg.get("sort_at") else None
    drop_t = ctx.at(cfg["drop_at"]) if cfg.get("drop_at") else None
    kept = [k for k in ranks if not items[k].get("strike_at")]
    slot_y = lambda n: sy0 + n * (ch + cgap)  # noqa: E731
    stack_layers = []
    for k, it in enumerate(items):
        t = ctx.at(it["at"])
        y_arr = slot_y(arr_slot[k])
        rule_card = it.get("kind") == "rules"
        body = [rect(0, 0, cw, ch, "#FFFFFF", radius=30, stroke=ink if rule_card else rule, sw=5 if rule_card else 4)]
        if rule_card:     # 项目规矩：文件夹图标 + 名字
            body.append(f'<path d="M50,{ch * 0.3:g} h70 l20,22 h90 v{ch * 0.42:g} h-180 Z" fill="none" stroke="{ink}" '
                        f'stroke-width="9" stroke-linejoin="round"/>')
            body.append(B.text(ctx, it["text"], 280, ch / 2 + 36, it.get("size", 96),
                               ctx.glyphs(B.plain_of(it["text"]), it.get("text_at") or it["at"])))
        else:
            body.append(rect(0, 30, 14, ch - 60, a, radius=7))
            body.append(f'<text x="44" y="{ch * 0.66:g}" font-family="{B.esc(ctx.font("heavy"))}" font-size="{ch * 0.7:g}" '
                        f'font-weight="900" fill="{a}">“</text>')
            body.append(rect(150, ch * 0.3, (cw - 600) * it.get("w", 0.8), 26, a, radius=13, extra=' fill-opacity="0.38"'))
            if it.get("src"):
                body.append(B.text(ctx, it["src"], 150, ch * 0.8, st.get("src_size", 58),
                                   ctx.glyphs(it["src"], it.get("src_at"), start=None if it.get("src_at") else t + .3),
                                   font="mono", weight=700, fill="muted", settle=False))
            if it.get("tag"):
                ta = ctx.at(it["tag_at"]) if it.get("tag_at") else t + .4
                hot = it.get("accent", False)
                tw, th_ = st.get("tag_w", 280), st.get("tag_h", 124)
                chip = rect(cw - tw - 50, ch / 2 - th_ / 2, tw, th_, a if hot else "#FFFFFF", radius=th_ / 2,
                            stroke=a if hot else ctx.col("faint"), sw=5)
                ts = st.get("tag_size", 84)
                chip += (f'<text x="{cw - tw / 2 - 50:g}" y="{ch / 2 + ts * 0.36:g}" text-anchor="middle" '
                         f'font-family="{B.esc(ctx.font("heavy"))}" font-size="{ts}" font-weight="900" '
                         f'fill="{"#FFFFFF" if hot else ink}">{B.esc(it["tag"])}</text>')
                body.append(B.anim("pop", ta, .35, chip))
        strike = it.get("strike_at")
        if strike:
            s_t = ctx.at(strike)
            body.append(line(ctx, f"M40,{ch / 2:g} L{cw - 40:g},{ch / 2:g}", s_t, .3, color="ink", sw=12))
        inner = "".join(body)
        # 轨迹：从档案里那一卷（或从下方）飞来 → 到点按排名换位 → 划掉的变淡、掉出；其余往上并拢
        if rule_card:
            track = [[t, 0, 160, 1, 0], [t + 0.5, 0, 0, 1, 1]]
        else:
            v = it.get("volume", nv - 1)
            vx = xs[v] + sw_ / 2 - cw * 0.12 - sx
            vy = top + sh_ * 0.35 - y_arr
            track = [[t, vx, vy, 0.24, 0], [t + 0.12, vx, vy, 0.24, 1], [t + 0.75, 0, 0, 1, 1]]
        cur = 0
        if sort_t is not None:
            dy = slot_y(ranks.index(k)) - y_arr
            track += [[sort_t, 0, cur, 1, 1], [sort_t + 0.55, 0, dy, 1, 1]]
            cur = dy
        if strike:
            track += [[s_t, 0, cur, 1, 1], [s_t + 0.35, 0, cur, 1, 0.45]]
            if drop_t is not None:
                track += [[drop_t, 0, cur, 1, 0.45], [drop_t + 0.5, 0, cur + 140, 1, 0]]
        elif drop_t is not None:
            dy = slot_y(kept.index(k)) - y_arr
            track += [[drop_t + 0.1, 0, cur, 1, 1], [drop_t + 0.6, 0, dy, 1, 1]]
        track = _track(track, f"recall item {k}")
        stack_layers.append(f'<g transform="translate({sx:g},{y_arr:g})">{B.keys(track, inner)}</g>')
    if ar.get("exit_at"):
        archive_g = B.out_at(ctx.at(ar["exit_at"]), archive_g, .35)
    out.append(archive_g)
    out.extend(stack_layers)
    if cfg.get("seen_at"):
        se = ctx.at(cfg["seen_at"])
        out.append(B.icon(ctx, "eye", nx + nr + 200, ny, 170, se))
        n_kept = len(kept) if drop_t is not None else len(items)
        hh = n_kept * (ch + cgap) - cgap
        out.append(rect(sx - 30, sy0 - 30, cw + 60, hh + 60, "none", radius=46, stroke=a, sw=8,
                        extra=f' data-anim="draw" data-delay="{se:.4f}" data-dur="0.5"'))
    return "".join(out)


KINDS = {"screenshot": screenshot_stamp, "repeat_flow": repeat_flow, "focus_network": focus_network,
         "time_stretch": time_stretch, "scan_grid": scan_grid, "capacity_gauges": capacity_gauges,
         "device_flow": device_flow, "condense": condense, "cross_check": cross_check, "lanes": lanes,
         "rail": rail, "archive": archive, "fork": fork, "recall": recall}
