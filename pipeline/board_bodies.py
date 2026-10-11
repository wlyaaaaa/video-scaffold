# -*- coding: utf-8 -*-
"""卡片里的会动内容块（boards.card 的 body），以及一排并列卡片 `cards`。

每块签名 fn(ctx, part, x, top, w, room, pad, t0) -> (svg, 用掉的高度)；字仍按词轴逐字出现，
动作仍只用 scene_base 的原语。新块登记在 BODIES，boards.body_part 找不到内置块时来这里找。
"""
from __future__ import annotations

import math

from pipeline import boards as B

_r = B._r


def _t(ctx, part, key, default):
    return ctx.at(part[key]) if part.get(key) else default


# ---- 终端：几行代码条依次写出，末尾光标闪动 -----------------------------------------------------
def terminal(ctx, part, x, top, w, room, pad, t0):
    a, block, rule = ctx.col("accent"), ctx.col("block"), ctx.col("rule")
    at = _t(ctx, part, "at", t0 + 0.2)
    n = part.get("lines", 5)
    widths = part.get("widths") or [0.62, 0.84, 0.48, 0.73, 0.38, 0.66, 0.55][:n]
    lh, bar = part.get("line_h", 74), part.get("bar", 26)
    x0, inner = x + pad, w - 2 * pad - 70
    out = [f'<rect x="{_r(x0 - 30)}" y="{_r(top)}" width="{_r(w - 2 * pad + 60)}" height="{_r(n * lh + 70)}" rx="22" '
           f'fill="{ctx.col("page")}" stroke="{rule}" stroke-width="3"/>']
    step = part.get("step", 0.16)
    for k, wf in enumerate(widths):
        ly = top + 50 + k * lh
        d = at + k * step
        color = a if k == part.get("accent_line", 1) else block
        out.append(B.anim("fade", d, 0.2, f'<text x="{_r(x0)}" y="{_r(ly + bar)}" font-family="{B.esc(ctx.font("mono"))}" '
                                         f'font-size="44" font-weight="700" fill="{a}">›</text>'))
        out.append(f'<rect data-anim="wipe" data-dir="left" data-delay="{_r(d)}" data-dur="0.32" x="{_r(x0 + 60)}" '
                   f'y="{_r(ly)}" width="{_r(inner * wf)}" height="{bar}" rx="{bar / 2}" fill="{color}"/>')
    cy = top + 50 + (n - 1) * lh
    cx = x0 + 60 + inner * widths[-1] + 24
    out.append(f'<g data-anim="pulse" data-delay="{_r(at + n * step)}" data-dur="0.2" data-amp="0" data-spd="9" '
               f'data-opmin="0"><rect x="{_r(cx)}" y="{_r(cy - 6)}" width="22" height="{bar + 12}" fill="{a}"/></g>')
    return "".join(out), n * lh + 110


# ---- 对话：气泡逐条出现；可到点描绿框、加小注、变淡 ------------------------------------------------
def chat(ctx, part, x, top, w, room, pad, t0):
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    size = part.get("size", 68)
    bh, gap = size * 1.9, part.get("gap", 34)
    out, y = [], top + 10
    for it in part["items"]:
        user = it.get("side", "user") == "user"
        at = ctx.at(it["at"])
        s = it.get("text")
        if s:
            bw = ctx.width(B.plain_of(s), size) + size * 1.4
        else:
            bw = (w - 2 * pad) * it.get("width", 0.55)
        bw = min(bw, w - 2 * pad - 140)
        bx = x + w - pad - bw if user else x + pad + 110
        if it.get("note"):
            y += 66
        parts = []
        fill = "#E6F4EF" if user else "#FFFFFF"
        parts.append(f'<rect x="{_r(bx)}" y="{_r(y)}" width="{_r(bw)}" height="{_r(bh)}" rx="{_r(bh / 2)}" '
                     f'fill="{fill}" stroke="{rule if not user else fill}" stroke-width="3"/>')
        if not user:
            parts.append(f'<circle cx="{_r(x + pad + 46)}" cy="{_r(y + bh / 2)}" r="44" fill="{ink}"/>'
                         f'<text x="{_r(x + pad + 46)}" y="{_r(y + bh / 2 + 15)}" text-anchor="middle" '
                         f'font-family="{B.esc(ctx.font("mono"))}" font-size="40" font-weight="700" fill="#FFFFFF">AI</text>')
        body = ""
        if s:
            g = ctx.glyphs(B.plain_of(s), it["at"])
            body = B.text(ctx, s, bx + size * 0.7, y + bh / 2 + size * 0.36, size, g, font="sans", weight=600)
        else:
            for k in range(it.get("lines", 1)):
                lw = (bw - size * 1.4) * (0.92 if k == 0 else 0.6)
                ly = y + bh / 2 - (it.get("lines", 1) - 1) * 18 + k * 36 - 9
                parts.append(f'<rect x="{_r(bx + size * 0.7)}" y="{_r(ly)}" width="{_r(lw)}" height="18" rx="9" '
                             f'fill="{ctx.col("faint")}" fill-opacity="0.7"/>')
        if it.get("badge"):
            bx2 = bx - 150 if user else bx + bw + 30
            parts.append(f'<rect x="{_r(bx2)}" y="{_r(y + bh / 2 - 36)}" width="120" height="72" rx="36" fill="{a}"/>'
                         f'<text x="{_r(bx2 + 60)}" y="{_r(y + bh / 2 + 16)}" text-anchor="middle" '
                         f'font-family="{B.esc(ctx.font("mono"))}" font-size="44" font-weight="700" fill="#FFFFFF">'
                         f'{B.esc(it["badge"])}</text>')
        group = B.anim("fade-up", at, 0.4, "".join(parts), ' data-shift="40"') + body
        if it.get("ring_at"):
            ra = ctx.at(it["ring_at"])
            m = 14
            per = 2 * (bw + bh) + 2 * m * 4
            group += (f'<rect data-anim="draw" data-delay="{_r(ra)}" data-dur="0.45" x="{_r(bx - m)}" y="{_r(y - m)}" '
                      f'width="{_r(bw + 2 * m)}" height="{_r(bh + 2 * m)}" rx="{_r(bh / 2 + m)}" fill="none" '
                      f'stroke="{a}" stroke-width="7"/>')
        if it.get("note"):
            nt = ctx.glyphs(it["note"], it.get("note_at"))
            nx = bx + (bw if user else 0)
            group += B.text(ctx, it["note"], nx, y - 26, 50, nt, font="mono", weight=700, fill="accent",
                            anchor="end" if user else "start", settle=False)
        if it.get("dim_at"):
            da = ctx.at(it["dim_at"])
            group = B.keys([[0, 0, 0, 1, 1], [da, 0, 0, 1, 1], [da + 0.35, 0, 0, 1, 0.35]], group)
        out.append(group)
        y += bh + gap
    return "".join(out), y - top


# ---- 表盘：先亮一小段（说好的时长），再一路拖满一圈；圈心的字到点替换 --------------------------------
def _arc(cx, cy, r, a0, a1):
    p0 = (cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
    p1 = (cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1)))
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{_r(p0[0])},{_r(p0[1])} A{_r(r)},{_r(r)} 0 {large} 1 {_r(p1[0])},{_r(p1[1])}"


def dial(ctx, part, x, top, w, room, pad, t0):
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    r = part.get("r", min(300, (room - 80) / 2))
    cx, cy = x + w / 2, top + r + 50
    sw = part.get("stroke", 34)
    at = _t(ctx, part, "at", t0 + 0.2)
    out = [f'<circle data-anim="draw" data-delay="{_r(t0 + 0.15)}" data-dur="0.5" cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(r)}" '
           f'fill="none" stroke="{rule}" stroke-width="{sw}"/>']
    for k in range(24):
        ang = math.radians(-90 + k * 15)
        r0, r1 = r - sw * 1.3, r - sw * (2.1 if k % 6 == 0 else 1.7)
        out.append(B.anim("fade", t0 + 0.2 + 0.015 * k, 0.2,
                          f'<line x1="{_r(cx + r0 * math.cos(ang))}" y1="{_r(cy + r0 * math.sin(ang))}" '
                          f'x2="{_r(cx + r1 * math.cos(ang))}" y2="{_r(cy + r1 * math.sin(ang))}" stroke="{ctx.col("faint")}" '
                          f'stroke-width="5" stroke-linecap="round"/>'))
    first = part.get("first", 15)
    out.append(f'<path data-anim="draw" data-delay="{_r(at)}" data-dur="0.4" d="{_arc(cx, cy, r, -90, -90 + first)}" '
               f'fill="none" stroke="{a}" stroke-width="{sw}" stroke-linecap="round"/>')
    ga, gd = ctx.at(part["grow_at"]), part.get("grow_dur", 1.2)
    rest = _arc(cx, cy, r, -90 + first, 269.9)
    out.append(f'<path data-anim="draw" data-ease="in-out" data-delay="{_r(ga)}" data-dur="{_r(gd)}" d="{rest}" '
               f'fill="none" stroke="{ink}" stroke-width="{sw}" stroke-linecap="round"/>')
    l1 = part["label"]
    g1 = ctx.glyphs(l1, part.get("label_at"))
    swap = ctx.at(part["label2_at"]) if part.get("label2") else None
    t1 = B.text(ctx, l1, cx, cy + 40, part.get("label_size", 110), g1, anchor="middle")
    out.append(B.out_at(swap - 0.3 if swap else None, t1, 0.25))
    if swap is not None:
        g2 = ctx.glyphs(part["label2"], part["label2_at"])
        out.append(B.text(ctx, part["label2"], cx, cy + 40, part.get("label_size", 110), g2, anchor="middle"))
    return "".join(out), 2 * r + 100


# ---- 扫描：一格有毛病；人一眼圈出来，AI 的扫描带扫过去却没停 ------------------------------------------
def scan(ctx, part, x, top, w, room, pad, t0):
    a, ink, block = ctx.col("accent"), ctx.col("ink"), ctx.col("block")
    cols, rows = part.get("cols", 8), part.get("rows", 4)
    gap = 22
    cell = min((w - 2 * pad - gap * (cols - 1)) / cols, (room - 120 - gap * (rows - 1)) / rows, 150)
    gw = cols * cell + (cols - 1) * gap
    x0 = x + (w - gw) / 2
    y0 = top + 30
    bad = part.get("anomaly", cols + 5)
    out = []
    for k in range(cols * rows):
        cx_, cy_ = x0 + (k % cols) * (cell + gap), y0 + (k // cols) * (cell + gap)
        d = t0 + 0.15 + 0.012 * k
        if k == bad:
            s = cell * 0.36
            mx, my = cx_ + cell / 2, cy_ + cell / 2
            sq = (f'<rect x="{_r(cx_)}" y="{_r(cy_)}" width="{_r(cell)}" height="{_r(cell)}" rx="14" fill="{block}"/>'
                  f'<path d="M{_r(mx)},{_r(my - s)} L{_r(mx + s)},{_r(my)} L{_r(mx)},{_r(my + s)} L{_r(mx - s)},{_r(my)} Z" '
                  f'fill="{ink}"/>')
        else:
            sq = f'<rect x="{_r(cx_)}" y="{_r(cy_)}" width="{_r(cell)}" height="{_r(cell)}" rx="14" fill="{block}"/>'
        out.append(B.anim("pop", d, 0.3, sq))
    bx, by = x0 + (bad % cols) * (cell + gap) + cell / 2, y0 + (bad // cols) * (cell + gap) + cell / 2
    if part.get("circle_at"):
        ca = ctx.at(part["circle_at"])
        rr = cell * 0.78
        out.append(f'<circle data-anim="draw" data-delay="{_r(ca)}" data-dur="0.45" cx="{_r(bx)}" cy="{_r(by)}" '
                   f'r="{_r(rr)}" fill="none" stroke="{a}" stroke-width="9" stroke-linecap="round"/>')
        if part.get("who"):
            wt = ctx.glyphs(part["who"], part.get("who_at"), start=None if part.get("who_at") else ca + 0.2)
            lab = B.text(ctx, part["who"], bx, by - rr - 34, 60, wt, font="mono", weight=700, fill="accent",
                         anchor="middle", settle=False)
            # 白色描边垫底，压在格子上也清楚
            out.append(lab.replace(' font-family=', ' stroke="#FFFFFF" stroke-width="22" stroke-linejoin="round" '
                                   'paint-order="stroke" font-family=', 1))
    if part.get("scan_at"):
        sa, sd = ctx.at(part["scan_at"]), part.get("scan_dur", 0.7)
        bw = cell * 0.9
        h = rows * (cell + gap) + 40
        band = (f'<rect x="{_r(x0 - bw)}" y="{_r(y0 - 20)}" width="{_r(bw)}" height="{_r(h)}" rx="16" fill="{a}" '
                f'fill-opacity="0.16"/><rect x="{_r(x0 - 10)}" y="{_r(y0 - 20)}" width="8" height="{_r(h)}" fill="{a}"/>')
        out.append(B.keys([[0, 0, 0, 1, 0], [sa, 0, 0, 1, 0], [sa + 0.08, 0, 0, 1, 1],
                           [sa + sd, gw + bw, 0, 1, 1], [sa + sd + 0.15, gw + bw, 0, 1, 0]], band))
    return "".join(out), rows * (cell + gap) + 60


# ---- 容量槽：按念到依次涨到七成，“全打满”时一齐顶满变黑并一震 ----------------------------------------
def gauges(ctx, part, x, top, w, room, pad, t0):
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    items = part["items"]
    n = len(items)
    tw = part.get("tank_w", 230)
    th = part.get("tank_h", min(520, room - 170))
    span = (w - 2 * pad - tw) / max(1, n - 1)
    full = ctx.at(part["full_at"]) if part.get("full_at") else None
    low = part.get("level", 0.62)
    tanks = []
    for k, it in enumerate(items):
        tx, ty = x + pad + k * span, top + 20
        at = ctx.at(it["at"])
        g = [f'<rect x="{_r(tx)}" y="{_r(ty)}" width="{tw}" height="{_r(th)}" rx="28" fill="#FFFFFF" '
             f'stroke="{rule}" stroke-width="5"/>']
        inset = 16
        ih = th - 2 * inset
        g.append(f'<rect data-anim="grow-bar" data-grow="y" data-delay="{_r(at)}" data-dur="0.5" x="{_r(tx + inset)}" '
                 f'y="{_r(ty + inset + ih * (1 - low))}" width="{tw - 2 * inset}" height="{_r(ih * low)}" rx="16" fill="{a}"/>')
        if full is not None:
            g.append(f'<rect data-anim="grow-bar" data-grow="y" data-delay="{_r(full + 0.05 * k)}" data-dur="0.3" '
                     f'x="{_r(tx + inset)}" y="{_r(ty + inset)}" width="{tw - 2 * inset}" height="{_r(ih * (1 - low) + 2)}" '
                     f'rx="16" fill="{ink}"/>')
        lt = ctx.glyphs(it["label"], it["at"])
        g.append(B.text(ctx, it["label"], tx + tw / 2, ty + th + 100, 76, lt, font="sans", weight=700,
                        anchor="middle"))
        tanks.append("".join(g))
    body = "".join(tanks)
    if full is not None:
        body = f'<g data-anim="shake" data-delay="{_r(full + 0.2)}" data-amp="18">{body}</g>'
    return body, th + 150


# ---- 注意力环：一圈问题点；先只照到一点，再一路扫满整圈、点逐个点亮 ----------------------------------
def ring(ctx, part, x, top, w, room, pad, t0):
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    n = part.get("n", 8)
    R = part.get("r", min(380, (room - 100) / 2))
    cx, cy = x + w / 2, top + R + 60
    na = _t(ctx, part, "nodes_at", t0)
    out = [f'<circle data-anim="draw" data-delay="{_r(na)}" data-dur="0.6" cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(R)}" '
           f'fill="none" stroke="{rule}" stroke-width="4" stroke-dasharray="1 0"/>']
    angs = [-90 + 360 * k / n for k in range(n)]
    pts = [(cx + R * math.cos(math.radians(t)), cy + R * math.sin(math.radians(t))) for t in angs]
    for k, (px, py) in enumerate(pts):
        out.append(f'<g transform="translate({_r(px)},{_r(py)})">' +
                   B.anim("pop", na + 0.05 * k, 0.3, f'<circle r="40" fill="#FFFFFF" stroke="{ctx.col("faint")}" '
                                                     f'stroke-width="6"/>') + '</g>')
    core = (f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="110" fill="{ink}"/><text x="{_r(cx)}" y="{_r(cy + 26)}" '
            f'text-anchor="middle" font-family="{B.esc(ctx.font("mono"))}" font-size="76" font-weight="700" '
            f'fill="#FFFFFF">AI</text>')
    out.append(B.anim("pop", na, 0.4, core))
    if part.get("narrow_at"):
        nt = ctx.at(part["narrow_at"])
        beam = (f'<path d="M{_r(cx)},{_r(cy)} L{_r(cx + (R + 70) * math.cos(math.radians(-90 - 14)))},'
                f'{_r(cy + (R + 70) * math.sin(math.radians(-90 - 14)))} A{_r(R + 70)},{_r(R + 70)} 0 0 1 '
                f'{_r(cx + (R + 70) * math.cos(math.radians(-90 + 14)))},{_r(cy + (R + 70) * math.sin(math.radians(-90 + 14)))} Z" '
                f'fill="{a}" fill-opacity="0.18"/>')
        wide = ctx.at(part["wide_at"]) if part.get("wide_at") else None
        out.append(B.out_at(wide, B.anim("fade", nt, 0.12, beam), 0.3))
        lit0 = f'<g transform="translate({_r(pts[0][0])},{_r(pts[0][1])})">' + \
            B.anim("pop", nt + 0.1, 0.3, f'<circle r="40" fill="{a}"/>') + '</g>'
        out.append(lit0)
    if part.get("wide_at"):
        wa, wd = ctx.at(part["wide_at"]), part.get("wide_dur", 0.5)
        # 旋转放在外层：带 data-anim 的元素会被 CSS 改变变换原点
        out.append(f'<g transform="rotate(-90 {_r(cx)} {_r(cy)})"><circle data-anim="draw" data-ease="in-out" '
                   f'data-delay="{_r(wa)}" data-dur="{_r(wd)}" cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(R)}" fill="none" '
                   f'stroke="{a}" stroke-width="150" stroke-opacity="0.16"/></g>')
        for k, (px, py) in enumerate(pts[1:], start=1):
            f = k / n
            q = (f / 4) ** (1 / 3) if f < 0.5 else 1 - (2 * (1 - f)) ** (1 / 3) / 2
            out.append(f'<g transform="translate({_r(px)},{_r(py)})">' +
                       B.anim("pop", wa + wd * q, 0.25, f'<circle r="40" fill="{a}"/>') + '</g>')
    return "".join(out), 2 * R + 140


# ---- 进度条：先涨到 from，再到点退到 to（清理）或涨到 to --------------------------------------------
def bar(ctx, part, x, top, w, room, pad, t0):
    a, block = ctx.col("accent"), ctx.col("block")
    bw, bh = w - 2 * pad, part.get("h", 56)
    x0, y0 = x + pad, top + 70
    at = _t(ctx, part, "at", t0 + 0.2)
    f0, f1 = part.get("from", 0.9), part.get("to", 0.3)
    out = []
    if part.get("label"):
        lt = ctx.glyphs(part["label"], part.get("label_at"), start=None if part.get("label_at") else at)
        out.append(B.text(ctx, part["label"], x0, top + 40, 50, lt, font="mono", weight=700, fill="muted",
                          settle=False))
    out.append(f'<rect x="{_r(x0)}" y="{_r(y0)}" width="{_r(bw)}" height="{bh}" rx="{bh / 2}" fill="{block}"/>')
    out.append(f'<rect data-anim="grow-bar" data-delay="{_r(at)}" data-dur="0.6" x="{_r(x0)}" y="{_r(y0)}" '
               f'width="{_r(bw * f0)}" height="{bh}" rx="{bh / 2}" fill="{ctx.col(part.get("color", "ink"))}"/>')
    if part.get("change_at"):
        ca = ctx.at(part["change_at"])
        if f1 < f0:     # 从右往左退回：用底色条盖住退掉的部分
            out.append(f'<rect data-anim="wipe" data-dir="right" data-delay="{_r(ca)}" data-dur="0.7" '
                       f'x="{_r(x0 + bw * f1)}" y="{_r(y0 - 2)}" width="{_r(bw * (f0 - f1) + 2)}" height="{bh + 4}" '
                       f'fill="{block}"/>'
                       f'<rect data-anim="fade" data-delay="{_r(ca + 0.6)}" data-dur="0.2" x="{_r(x0 + bw * f1 - bh / 2)}" '
                       f'y="{_r(y0)}" width="{bh}" height="{bh}" rx="{bh / 2}" fill="{a}"/>')
        else:
            out.append(f'<rect data-anim="grow-bar" data-delay="{_r(ca)}" data-dur="0.7" x="{_r(x0 + bw * f0)}" '
                       f'y="{_r(y0)}" width="{_r(bw * (f1 - f0))}" height="{bh}" rx="{bh / 2}" fill="{a}"/>')
    return "".join(out), bh + 110


# ---- 搬运：一串点从左框流到右框（持续），右框逐格填上 --------------------------------------------------
def flow(ctx, part, x, top, w, room, pad, t0):
    a, ink, rule, block = ctx.col("accent"), ctx.col("ink"), ctx.col("rule"), ctx.col("block")
    at = _t(ctx, part, "at", t0 + 0.2)
    bw, bh = part.get("box", (260, 200))
    lx, rx = x + pad, x + w - pad - bw
    yy = top + 30
    out = []
    for k, bx in enumerate((lx, rx)):
        out.append(B.anim("pop", at + 0.15 * k, 0.35,
                          f'<rect x="{_r(bx)}" y="{_r(yy)}" width="{bw}" height="{bh}" rx="22" fill="#FFFFFF" '
                          f'stroke="{ink if k else rule}" stroke-width="6"/>'))
    for k in range(6):
        cs = (bw - 60) / 3
        cx_, cy_ = rx + 30 + (k % 3) * cs, yy + (bh - 2 * cs) / 2 + (k // 3) * cs
        out.append(B.anim("pop", at + 0.6 + 0.18 * k, 0.25,
                          f'<rect x="{_r(cx_)}" y="{_r(cy_)}" width="{_r(cs - 16)}" height="{_r(cs - 16)}" rx="10" fill="{a}"/>'))
        cx2 = lx + 30 + (k % 3) * cs
        out.append(f'<rect x="{_r(cx2)}" y="{_r(cy_)}" width="{_r(cs - 16)}" height="{_r(cs - 16)}" rx="10" fill="{block}"/>')
    pid = B._id("flow")
    d = f"M{_r(lx + bw + 30)},{_r(yy + bh / 2)} L{_r(rx - 30)},{_r(yy + bh / 2)}"
    out.append(f'<path id="{pid}" d="{d}" fill="none" stroke="{rule}" stroke-width="6" stroke-dasharray="4 18" '
               f'stroke-linecap="round"/>')
    for k in range(3):
        out.append(f'<circle data-anim="flow-blob" data-delay="{_r(at + 0.35)}" data-path="#{pid}" data-speed="0.9" '
                   f'data-phase="{k / 3:.3f}" data-x0="0" data-y0="0" cx="0" cy="0" r="16" fill="{a}"/>')
    return "".join(out), bh + 70


def context_stack(ctx, part, x, top, w, room, pad, t0):
    """固定窗口里的对话条；较早条目可按词轴淡去、聚拢，保留最近一条。"""
    items = part["items"]
    h = part.get("h", min(room - 60, 1050))
    inner_w, x0 = w - 2 * pad, x + pad
    step = h / len(items)
    row_h = step * 0.73
    parts = []
    collapse = _t(ctx, part, "collapse_at", None)
    for k, it in enumerate(items):
        at = ctx.at(it["at"])
        last = k == len(items) - 1
        bx = x0 + (60 if k % 2 else 0)
        by = top + k * step + 26
        bw = inner_w - 60
        bg = ctx.col("accent") if last else "#FFFFFF"
        body = f'<rect x="{bx}" y="{by}" width="{bw}" height="{row_h}" rx="24" fill="{bg}" '
        body += f'stroke="{ctx.col("rule")}" stroke-width="{0 if last else 3}"/>'
        if it.get("text"):
            s = it["text"]
            size = it.get("size", 100)
            gt = ctx.glyphs(B.plain_of(s), it.get("text_at", it["at"]))
            body += B.text(ctx, s, bx + 44, by + row_h / 2 + size * 0.36, size, gt,
                           fill="#FFFFFF" if last else "muted", settle=False)
        else:
            for j, frac in enumerate((0.68, 0.43)):
                body += f'<rect x="{bx + 44}" y="{by + row_h * (0.33 + j * 0.3)}" width="{bw * frac}" '
                body += f'height="18" rx="9" fill="{ctx.col("rule")}"/>'
        if it.get("dim_at"):
            dt = ctx.at(it["dim_at"])
            body = B.keys([[0, 0, 0, 1, 1], [dt, 0, 0, 1, 1], [dt + 0.35, 0, 0, 1, 0.2]], body)
        if collapse is not None and not last:
            target_y = top + (len(items) - 1) * step + 26
            body = B.keys([[0, 0, 0, 1, 1], [collapse, 0, 0, 1, 1],
                           [collapse + 0.6, 0, target_y - by, 1, 0]], body)
        parts.append(B.anim("fade-up", at, 0.4, body, ' data-shift="35"'))
    if part.get("window_at"):
        at = ctx.at(part["window_at"])
        yy = top + (len(items) - 1) * step + 8
        parts.append(f'<rect data-anim="draw" data-delay="{_r(at)}" data-dur="0.6" x="{x0 - 18}" y="{yy}" '
                     f'width="{inner_w + 36}" height="{row_h + 36}" rx="36" fill="none" '
                     f'stroke="{ctx.col("accent")}" stroke-width="8"/>')
    return "".join(parts), h + 50


def _tick(ctx, cx, cy, s, at, dur=0.3, sw=12):
    d = f"M{_r(cx - s * 0.45)},{_r(cy)} L{_r(cx - s * 0.12)},{_r(cy + s * 0.32)} L{_r(cx + s * 0.5)},{_r(cy - s * 0.36)}"
    return (f'<path data-anim="draw" data-delay="{_r(at)}" data-dur="{_r(dur)}" d="{d}" fill="none" '
            f'stroke="{ctx.col("accent")}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')


def _cross(ctx, cx, cy, s, at, sw=12):
    a, b = (f"M{_r(cx - s / 2)},{_r(cy - s / 2)} L{_r(cx + s / 2)},{_r(cy + s / 2)}",
            f"M{_r(cx + s / 2)},{_r(cy - s / 2)} L{_r(cx - s / 2)},{_r(cy + s / 2)}")
    return "".join(f'<path data-anim="draw" data-delay="{_r(at + k * 0.12)}" data-dur="0.2" d="{d}" fill="none" '
                   f'stroke="{ctx.col("ink")}" stroke-width="{sw}" stroke-linecap="round"/>' for k, d in enumerate((a, b)))


# ---- 细看：一排排看着都对（逐行打勾），放大镜移到其中一行，那一行原来不对 -------------------------------
def inspect(ctx, part, x, top, w, room, pad, t0):
    block, ink = ctx.col("block"), ctx.col("ink")
    n = part.get("rows", 5)
    rh, gap = part.get("row_h", 44), part.get("gap", 46)
    widths = part.get("widths") or [0.88, 0.72, 0.94, 0.62, 0.82, 0.7][:n]
    x0, iw = x + pad, w - 2 * pad - 150
    at = _t(ctx, part, "at", t0 + 0.2)
    tick_at = _t(ctx, part, "tick_at", None)
    wrong_at = _t(ctx, part, "wrong_at", None)
    k_bad = part.get("target", 2)
    rows, bad_layer, bad_strike = [], "", ""
    for k, wf in enumerate(widths):
        ry = top + 40 + k * (rh + gap)
        bar_ = (f'<rect data-anim="wipe" data-dir="left" data-delay="{_r(at + 0.07 * k)}" data-dur="0.35" '
                f'x="{_r(x0)}" y="{_r(ry)}" width="{_r(iw * wf)}" height="{rh}" rx="{rh / 2}" fill="{block}"/>')
        tick = _tick(ctx, x0 + iw + 80, ry + rh / 2, rh * 1.2, tick_at + 0.09 * k) if tick_at is not None else ""
        if k == k_bad and wrong_at is not None:
            tick = B.out_at(wrong_at, tick, 0.2)
            bad_strike = (f'<path data-anim="draw" data-delay="{_r(wrong_at + 0.1)}" data-dur="0.3" '
                          f'd="M{_r(x0 - 10)},{_r(ry + rh / 2)} L{_r(x0 + iw * wf + 10)},{_r(ry + rh / 2)}" '
                          f'stroke="{ink}" stroke-width="10" stroke-linecap="round"/>')
            bad_layer = bad_strike + _cross(ctx, x0 + iw + 80, ry + rh / 2, rh * 1.1, wrong_at + 0.15)
        if k == k_bad:
            bad_bar = f'<rect x="{_r(x0)}" y="{_r(ry)}" width="{_r(iw * wf)}" height="{rh}" rx="{rh / 2}" fill="{block}"/>'
        rows.append(bar_ + tick)
    out = rows + [bad_layer]
    lens_at = _t(ctx, part, "lens_at", None)
    if lens_at is not None:
        ry = top + 40 + k_bad * (rh + gap) + rh / 2
        lx, R = x0 + iw * part.get("lens_x", 0.55), part.get("lens_r", 150)
        clip = B._id("lens")
        zoom = part.get("zoom", 1.7)
        mag = (f'<defs><clipPath id="{clip}"><circle cx="{_r(lx)}" cy="{_r(ry)}" r="{R - 6}"/></clipPath></defs>'
               f'<g clip-path="url(#{clip})">' + B.anim(
                   "fade", lens_at + 0.5, 0.2,
                   f'<circle cx="{_r(lx)}" cy="{_r(ry)}" r="{R}" fill="#FFFFFF"/>'
                   f'<g transform="translate({_r(lx)},{_r(ry)}) scale({zoom}) translate({_r(-lx)},{_r(-ry)})">'
                   f'{bad_bar}{bad_strike}</g>') + '</g>')    # 镜里只放大那一行，右侧的叉不进镜（放大后会出画）
        glass = (f'<circle cx="{_r(lx)}" cy="{_r(ry)}" r="{R}" fill="none" stroke="{ink}" stroke-width="16"/>'
                 f'<path d="M{_r(lx + R * 0.72)},{_r(ry + R * 0.72)} L{_r(lx + R * 1.45)},{_r(ry + R * 1.45)}" '
                 f'stroke="{ink}" stroke-width="34" stroke-linecap="round"/>')
        track = [[0, 520, 260, 1, 0], [lens_at, 520, 260, 1, 0], [lens_at + 0.1, 470, 230, 1, 1],
                 [lens_at + 0.55, 0, 0, 1, 1]]
        out.append(B.keys(track, mag + glass))
        if part.get("lens_label"):
            g = ctx.glyphs(part["lens_label"], part.get("lens_label_at"), start=None if part.get("lens_label_at") else lens_at + 0.3)
            out.append(B.text(ctx, part["lens_label"], lx - R - 40, ry + 26, 76, g, font="sans", weight=800,
                              fill="ink", anchor="end", settle=False))
    if part.get("wrong_label") and wrong_at is not None:
        g = ctx.glyphs(B.plain_of(part["wrong_label"]), part.get("wrong_label_at"), start=None if part.get("wrong_label_at") else wrong_at)
        yy = top + 40 + k_bad * (rh + gap) + rh / 2 + part.get("lens_r", 150) + 150
        out.append(B.text(ctx, part["wrong_label"], x0 + iw * part.get("lens_x", 0.55), yy, part.get("label_size", 110),
                          g, anchor="middle"))
    return "".join(out), n * (rh + gap) + 80


# ---- 任务单：逐条列出、打勾；某条到点被划掉并消失；空位可出现虚线并补回 -----------------------------------
def todo(ctx, part, x, top, w, room, pad, t0):
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    items = part["items"]
    size = part.get("size", 72)
    rh, gap = part.get("row_h", size * 1.9), part.get("gap", 24)
    x0, iw = x + pad, w - 2 * pad
    bs = size * 0.95
    n = len(items)
    sa = _t(ctx, part, "scan_at", None)
    sd = part.get("scan_dur", 0.22 * n)
    out = []
    for k, it in enumerate(items):
        ry = top + 20 + k * (rh + gap)
        at = ctx.at(it["at"]) if it.get("at") else t0 + 0.2 + 0.08 * k
        box_x, cy = x0 + 26, ry + rh / 2
        row = [f'<rect x="{_r(x0)}" y="{_r(ry)}" width="{_r(iw)}" height="{_r(rh)}" rx="22" fill="#FFFFFF" '
               f'stroke="{rule}" stroke-width="3"/>',
               f'<rect x="{_r(box_x)}" y="{_r(cy - bs / 2)}" width="{_r(bs)}" height="{_r(bs)}" rx="12" fill="none" '
               f'stroke="{ctx.col("faint")}" stroke-width="6"/>']
        tx = box_x + bs + 40
        if it.get("text"):
            g = ctx.glyphs(B.plain_of(it["text"]), it.get("text_at") or it.get("at"),
                           start=None if (it.get("text_at") or it.get("at")) else at)
            row.append(B.text(ctx, it["text"], tx, cy + size * 0.36, size, g, font="sans", weight=700))
            tw = ctx.width(B.plain_of(it["text"]), size)
        else:
            tw = (iw - (tx - x0) - 60) * it.get("w", 0.6)
            row.append(f'<rect x="{_r(tx)}" y="{_r(cy - 14)}" width="{_r(tw)}" height="28" rx="14" fill="{ctx.col("block")}"/>')
        drop = ctx.at(it["drop_at"]) if it.get("drop_at") else None
        tick_t = ctx.at(it["tick_at"]) if it.get("tick_at") else None
        if tick_t is None and sa is not None and (drop is None or drop > sa + sd):
            tick_t = sa + sd * (k + 0.6) / n
        if tick_t is not None:
            row.append(_tick(ctx, box_x + bs / 2, cy, bs * 0.8, tick_t, 0.25, 10))
        body = "".join(row)
        if drop is not None:
            body += (f'<path data-anim="draw" data-delay="{_r(drop)}" data-dur="0.3" d="M{_r(tx - 10)},{_r(cy)} '
                     f'L{_r(tx + tw + 10)},{_r(cy)}" stroke="{ink}" stroke-width="9" stroke-linecap="round"/>')
            body = B.keys([[0, 0, 0, 1, 1], [drop + 0.45, 0, 0, 1, 1], [drop + 0.85, 30, 0, 1, 0]], body)
        if not it.get("absent"):     # absent：这一条一开始就不在，只留虚线空位或之后补回
            out.append(B.anim("fade-up", at, 0.35, body, ' data-shift="30"'))
        if it.get("ghost_at"):
            gt = ctx.at(it["ghost_at"])
            ghost = (f'<rect x="{_r(x0)}" y="{_r(ry)}" width="{_r(iw)}" height="{_r(rh)}" rx="22" fill="{a}" '
                     f'fill-opacity="0.06" stroke="{a}" stroke-width="6" stroke-dasharray="22 16"/>')
            out.append(B.anim("pop", gt, 0.35, ghost))
            if it.get("ghost_label"):
                g = ctx.glyphs(it["ghost_label"], it.get("ghost_label_at"), start=None if it.get("ghost_label_at") else gt + 0.1)
                out.append(B.text(ctx, it["ghost_label"], x0 + iw / 2, cy + size * 0.36, size, g, font="sans",
                                  weight=800, fill="accent", anchor="middle", settle=False))
        if it.get("restore_at"):
            rt = ctx.at(it["restore_at"])
            rest = (f'<rect x="{_r(x0)}" y="{_r(ry)}" width="{_r(iw)}" height="{_r(rh)}" rx="22" fill="{a}" '
                    f'fill-opacity="0.14" stroke="{a}" stroke-width="5"/>'
                    f'<rect x="{_r(box_x)}" y="{_r(cy - bs / 2)}" width="{_r(bs)}" height="{_r(bs)}" rx="12" fill="#FFFFFF" '
                    f'stroke="{a}" stroke-width="6"/>')
            if it.get("text"):
                rest += (f'<text x="{_r(tx)}" y="{_r(cy + size * 0.36)}" font-family="{B.esc(ctx.font("sans"))}" '
                         f'font-size="{size}" font-weight="700" fill="{ink}">{B.esc(B.plain_of(it["text"]))}</text>')
            out.append(B.anim("fade-left", rt, 0.4, rest, ' data-shift="40"') + _tick(ctx, box_x + bs / 2, cy, bs * 0.8, rt + 0.3, 0.25, 10))
    if sa is not None:
        span = n * (rh + gap)
        band = (f'<rect x="{_r(x0 - 16)}" y="{_r(top + 10)}" width="{_r(iw + 32)}" height="{_r(rh * 0.5)}" rx="14" '
                f'fill="{a}" fill-opacity="0.18"/><rect x="{_r(x0 - 16)}" y="{_r(top + 10 + rh * 0.5 - 4)}" '
                f'width="{_r(iw + 32)}" height="8" fill="{a}"/>')
        out.append(B.keys([[0, 0, 0, 1, 0], [sa, 0, 0, 1, 0], [sa + 0.1, 0, 0, 1, 1],
                           [sa + sd, 0, span - rh * 0.4, 1, 1], [sa + sd + 0.15, 0, span - rh * 0.4, 1, 0]], band))
    return "".join(out), n * (rh + gap) + 40


# ---- 水位条：按念到一段段涨，碰到虚线（阈值）时一震；可被“看不见”的磨砂盖住 ---------------------------------
def level(ctx, part, x, top, w, room, pad, t0):
    a, ink, block = ctx.col("accent"), ctx.col("ink"), ctx.col("block")
    bw, bh = w - 2 * pad, part.get("h", 96)
    x0, y0 = x + pad, top + 90
    out = []
    if part.get("label"):
        lt = ctx.glyphs(part["label"], part.get("label_at"), start=None if part.get("label_at") else t0 + 0.15)
        out.append(B.text(ctx, part["label"], x0, top + 50, 52, lt, font="mono", weight=700, fill="muted", ls=4, settle=False))
    clip = B._id("lvl")
    meter = [f'<defs><clipPath id="{clip}"><rect x="{_r(x0)}" y="{_r(y0)}" width="{_r(bw)}" height="{bh}" '
             f'rx="{bh / 2}"/></clipPath></defs>'
             f'<rect x="{_r(x0)}" y="{_r(y0)}" width="{_r(bw)}" height="{bh}" rx="{bh / 2}" fill="{block}"/>']
    prev, segs = 0.0, []
    for cue, frac, *rest in part.get("steps", []):    # 每段从上一段的末端接着涨，整条按圆角裁齐
        st = ctx.at(cue)
        dur = rest[0] if rest else 0.7
        color = ctx.col(rest[1]) if len(rest) > 1 else a
        segs.append(f'<rect data-anim="grow-bar" data-ease="in-out" data-delay="{_r(st)}" data-dur="{_r(dur)}" '
                    f'x="{_r(x0 + bw * prev - 1)}" y="{_r(y0)}" width="{_r(bw * (frac - prev) + 1)}" height="{bh}" '
                    f'fill="{color}"/>')
        prev = frac
    meter.append(f'<g clip-path="url(#{clip})">{"".join(segs)}</g>')
    if part.get("limit") is not None:
        lx = x0 + bw * part["limit"]
        la = _t(ctx, part, "limit_at", t0 + 0.2)
        meter.append(B.anim("fade", la, 0.3, f'<path d="M{_r(lx)},{_r(y0 - 34)} L{_r(lx)},{_r(y0 + bh + 34)}" '
                                              f'stroke="{ink}" stroke-width="8" stroke-dasharray="16 12"/>'))
        if part.get("limit_label"):
            g = ctx.glyphs(part["limit_label"], part.get("limit_label_at"), start=None if part.get("limit_label_at") else la)
            meter.append(B.text(ctx, part["limit_label"], lx, y0 + bh + 110, 60, g, font="sans", weight=700,
                                anchor="middle", settle=False))
    body = "".join(meter)
    if part.get("hit_at"):
        ht = ctx.at(part["hit_at"])
        body = f'<g data-anim="shake" data-delay="{_r(ht)}" data-amp="20">{body}</g>'
        if part.get("limit") is not None:
            lx = x0 + bw * part["limit"]
            body += (f'<g transform="translate({_r(lx)},{_r(y0 + bh / 2)})"><circle data-anim="shockwave" '
                     f'data-delay="{_r(ht)}" data-dur="0.7" data-max="3" r="{bh * 0.6}" fill="none" stroke="{a}" '
                     f'stroke-width="8"/></g>')
    out.append(body)
    if part.get("blind_at"):
        bt = ctx.at(part["blind_at"])
        cx, cy = x0 + bw / 2, y0 + bh / 2
        veil = (f'<rect x="{_r(x0 - 24)}" y="{_r(y0 - 26)}" width="{_r(bw + 48)}" height="{_r(bh + 52)}" rx="30" '
                f'fill="{ctx.col("page")}" fill-opacity="0.94" stroke="{ctx.col("rule")}" stroke-width="3"/>')
        s = bh * 0.8
        eye = (f'<path d="M{_r(cx - s)},{_r(cy)} Q{_r(cx)},{_r(cy - s * 0.9)} {_r(cx + s)},{_r(cy)} '
               f'Q{_r(cx)},{_r(cy + s * 0.9)} {_r(cx - s)},{_r(cy)} Z" fill="none" stroke="{ctx.col("muted")}" stroke-width="9"/>'
               f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(s * 0.28)}" fill="{ctx.col("muted")}"/>')
        slash = (f'<path data-anim="draw" data-delay="{_r(bt + 0.25)}" data-dur="0.3" d="M{_r(cx - s * 0.9)},{_r(cy + s * 0.8)} '
                 f'L{_r(cx + s * 0.9)},{_r(cy - s * 0.8)}" stroke="{ink}" stroke-width="12" stroke-linecap="round"/>')
        out.append(B.anim("fade", bt, 0.3, veil + eye) + slash)
    return "".join(out), bh + 220


BODIES = {"terminal": terminal, "chat": chat, "dial": dial, "scan": scan, "gauges": gauges, "ring": ring,
          "bar": bar, "flow": flow, "context_stack": context_stack, "inspect": inspect, "todo": todo,
          "level": level}


# ---- 一排并列卡片（各自到点升起、一直留着） -------------------------------------------------------
def cards(ctx, el):
    items = el["cards"]
    n = len(items)
    x, y = el.get("x", 240), el.get("y", 620)
    gap = el.get("gap", 80)
    w = el.get("w", (3600 - x - gap * (n - 1)) / n)
    h = el.get("h", 1000)
    out = []
    for k, cd in enumerate(items):
        out.append(B.card(ctx, cd, x + k * (w + gap), y, w, h, ctx.at(cd["at"])))
    return "".join(out)
