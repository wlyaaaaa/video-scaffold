# -*- coding: utf-8 -*-
"""图文页通用版式（动态图形）：页眉、说法堆叠、右侧卡片组、时间线、带图标清单、数字条形。

每个版式是分镜表里的一种元素（见 docs/AUTHORING.md“图文页版式”），由 pipeline.pages 调用。
画法统一：米白底、黑字、单一强调绿、等宽小标签、细线、白色圆角卡片。所有文字按词轴逐字出现
（原文里找得到的字用各自被念到的时刻；找不到的概括字样从绑定的词开始快速打出），动作全部
走 templates/scene_base.html 里的原语，只依赖时间 t。坐标是 4K 画布像素，都有默认值，可在表里覆盖。
"""
from __future__ import annotations

import html
import json
import math

import config

TYPE_STEP = 0.035      # 非原文字样的逐字间隔
GLYPH_FADE = 0.14
CARD_IN, CARD_OUT = 0.5, 0.3
_ids = [0]


def _id(prefix):
    _ids[0] += 1
    return f"{prefix}{_ids[0]}"


def esc(s):
    return html.escape(str(s), quote=True)


def J(v):
    return esc(json.dumps(v, separators=(",", ":")))


def _r(v):
    return f"{v:.3f}".rstrip("0").rstrip(".")


class Ctx:
    """把 PageBuilder 的词轴、主题和字宽估算交给版式函数。"""

    def __init__(self, builder):
        import v2lib as L
        self.b, self.L, self.th = builder, L, L.theme()
        self.motion = config.PAGE_MOTION

    # ---- 时间 ----
    def at(self, cue, default=None):
        return self.b.at(cue, default)

    def cue_pos(self, cue):
        from pipeline.pages import cue_time
        return cue_time(self.b.tl, cue, self.b.pos)[1]

    def glyphs(self, plain, cue=None, start=None, search=True, summary=False):
        """plain 每个字的本页出现时刻。原文里找得到：各字被念到的时刻；找不到：从 start/cue 起逐字打出。
        search=False：已讲过的字样重现，不在后文里找，直接从 start/cue 起打出。"""
        tl, b = self.b.tl, self.b
        summary = summary or b.options.get("summary", False)
        def finish(times):
            record = getattr(b, 'record_glyphs', None)
            return record(plain, cue, start, summary or not search, times) if record else times
        t0 = start if start is not None else self.at(cue)
        idx = -1
        core = plain.strip("“”\"「」 ")
        if core and search and not summary:
            frm = b.pos
            if cue:
                frm = max(b.pos, self.cue_pos(cue) - len(core))
            idx = tl.text.find(core, frm)
            if idx < 0:
                idx = tl.text.find(core, b.pos)
            if cue and b.options.get("hold_check") != "warn":
                anchor = self.cue_pos(cue)
                containing = tl.text.rfind(core, max(0, anchor - len(core) + 1), anchor + len(core))
                if containing >= 0 and containing <= anchor < containing + len(core):
                    idx = containing
        if idx < 0:
            out, k = [], 0
            for ch in plain:
                out.append(round(t0 + k * TYPE_STEP, 4))
                k += 0 if ch.isspace() else 1
            return finish(out)
        times, last = [], None
        lead = plain.find(core)
        spoken = []
        for p in range(idx, idx + len(core)):
            ct = tl.char_time(p)
            if ct is not None:
                last = max(0.0, ct - b.start)
            spoken.append(last)
        first = next((v for v in spoken if v is not None), t0)
        spoken = [first if v is None else v for v in spoken]
        times = [first] * lead + spoken + [spoken[-1]] * (len(plain) - lead - len(core))
        return finish([round(max(v, t0 if start is not None else 0.0), 4) for v in times])

    # ---- 品牌标志 ----
    def logo_href(self, logo):
        """logo 写分镜表顶层 `brands` 里的名字（如 "claude"），或直接写图片路径（相对分镜表）。"""
        from pipeline.pages import _resolve
        brands = getattr(self.b, "brands", None) or {}
        path = brands.get(logo, logo)
        full = _resolve(self.b.base, path) if self.b.base is not None else __import__("pathlib").Path(path)
        if not full.exists():
            raise FileNotFoundError(f"logo {logo!r}: 找不到图片 {full}")
        return self.L.FU(str(full))

    # ---- 字 ----
    def width(self, s, size):
        return self.L._text_w(s, size)

    def col(self, role):
        return self.th.get(role, role)

    def font(self, role):
        return self.th[role]


def markup_spans(s):
    from pipeline.pages import markup
    return markup(s)


def plain_of(s):
    return "".join(t for t, _ in markup_spans(s))


def text(ctx, s, x, y, size, times, *, font="heavy", weight=900, fill="ink", anchor="start", ls=0,
         settle=True, tid=None, opacity=None, roles=None, fade=GLYPH_FADE, follow=None, gap=24):
    """一行逐字出现的字。s 可带 *强调* / ~灰~ 标记；times 与可见字一一对应。"""
    spans = markup_spans(s) if roles is None else roles
    fill_c = ctx.col(fill)
    body = ""
    for part, role in spans:
        c = ctx.col("accent" if role == "accent" else "muted" if role == "muted" else fill)
        body += f'<tspan fill="{c}">{esc(part)}</tspan>' if c != fill_c else esc(part)
    assert len(times) == sum(len(p) for p, _ in spans), (s, len(times))
    tid_a = f' id="{tid}"' if tid else ""
    settle_a = f' data-glyph-from="{ctx.col("faint")}"' if settle else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    if follow:
        op += f' data-follow="#{follow}" data-gap="{gap}"'
    svg = (f'<text{tid_a} data-anim="type" data-delay="{_r(min(times))}" data-dur="0.3" '
            f'data-glyph-times="{J(times)}" data-glyph-fade="{fade}"{settle_a} x="{_r(x)}" y="{_r(y)}" '
            f'font-family="{esc(ctx.font(font))}" font-size="{size}" font-weight="{weight}" fill="{fill_c}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}"{op}>{body}</text>')
    record = getattr(ctx.b, 'record_glyph_svg', None)
    return record(svg, times) if record else svg


def anim(kind, delay, dur, inner, extra=""):
    return f'<g data-anim="{kind}" data-delay="{_r(delay)}" data-dur="{_r(dur)}"{extra}>{inner}</g>'


def keys(track, inner):
    return f'<g data-anim="keys" data-keys="{J([[round(v, 4) for v in k] for k in track])}">{inner}</g>'


def out_at(when, inner, dur=CARD_OUT):
    return inner if when is None else anim("fade-out", when, dur, inner)


def recolor(ctx, s, x, y, size, t0, dur, which, color, *, font="heavy", weight=900, anchor="start", glyphs=None):
    """覆盖层：把 which（字下标集合）从左到右依次染成 color（划绿、变灰都用它）。"""
    plain = plain_of(s)
    idx = [i for i in range(len(plain)) if i in which]
    n = max(1, len(idx))
    times = [9999.0] * len(plain)
    for k, i in enumerate(idx):
        times[i] = round(t0 + dur * k / n, 4)
        if glyphs is not None and ctx.b.options.get("hold_check") != "warn":
            times[i] = max(times[i], glyphs[i])
    roles = [(ch, None) for ch in plain]
    return text(ctx, plain, x, y, size, times, font=font, weight=weight, fill=color, anchor=anchor,
                settle=False, roles=roles, fade=0.16)


def mark_rect(tid, c0, c1, t0, dur, color, mode="band", opacity=1.0, pad=0.08):
    return (f'<rect data-anim="mark" data-mode="{mode}" data-text="#{tid}" data-c0="{c0}" data-c1="{c1}" '
            f'data-pad="{pad}" data-delay="{_r(t0)}" data-dur="{_r(dur)}" data-ease="in-out" x="0" y="0" '
            f'width="0" height="0" rx="6" fill="{color}" fill-opacity="{opacity}"/>')


# ================================================================================================
# 页眉：粗体小标题 + 绿色小标签 + 一行灰色小字（可分段出现）
# ================================================================================================
def head(ctx, el):
    x, y, size = el.get("x", 240), el.get("y", 330), el.get("size", 150)
    t0 = ctx.at(el.get("at"))
    out = []
    if el.get("kicker"):
        kt = ctx.glyphs(el["kicker"], el.get("kicker_at"))
        out.append(text(ctx, el["kicker"], x, y - size * 1.05, 60, kt, font="mono", weight=700, fill="muted", ls=4))
    title = el["head"]
    tt = ctx.glyphs(plain_of(title), el.get("at"))
    out.append(text(ctx, title, x, y, size, tt))
    if el.get("tag"):
        tg = el["tag"]
        ta = ctx.at(el["tag_at"]) if el.get("tag_at") else max(tt) + 0.15
        fs = 54
        w = ctx.width(tg, fs) + 64
        h = fs * 1.7
        tx = x + ctx.width(plain_of(title), size) + 56
        ty = y - size * 0.40 - h / 2
        out.append(anim("pop", ta, 0.45,
                        f'<rect x="{_r(tx)}" y="{_r(ty)}" width="{_r(w)}" height="{_r(h)}" rx="{_r(h / 2)}" '
                        f'fill="{ctx.col("accent")}" fill-opacity="0.12"/>'
                        f'<text x="{_r(tx + w / 2)}" y="{_r(ty + h / 2 + fs * 0.36)}" text-anchor="middle" '
                        f'font-family="{esc(ctx.font("mono"))}" font-size="{fs}" font-weight="700" '
                        f'fill="{ctx.col("accent")}">{esc(tg)}</text>'))
    sub = el.get("sub")
    if sub:
        pieces = [[sub, el.get("sub_at")]] if isinstance(sub, str) else sub
        line, times = "", []
        for k, (piece, cue) in enumerate(pieces):
            if k:
                line += " · "
            seg = piece
            gt = ctx.glyphs(seg, cue) if cue else ctx.glyphs(seg, start=max(tt) + 0.2)
            if k:
                times += [gt[0]] * 3
            line += seg
            times += gt
            if hasattr(ctx.b, 'record_glyph_join'):
                ctx.b.record_glyph_join(times, gt)
        out.append(text(ctx, line, x, y + 118, 64, times, font="sans", weight=500, fill="muted", settle=False))
    return "".join(out)


# ================================================================================================
# 说法堆叠：当前说法大字逐字出现；下一句来时旧说法缩小上移成一摞；到点变灰划线；重点被绿色划过
# ================================================================================================
def claims(ctx, el):
    x, y, size = el.get("x", 240), el.get("y", 1130), el.get("size", 170)
    sy, ss, sg = el.get("stack_y", 640), el.get("stack_size", 66), el.get("stack_gap", 100)
    items = el["claims"]
    accent, muted, ink = ctx.col("accent"), ctx.col("muted"), ctx.col("ink")
    out = []
    starts = []
    for it in items:
        s = it["text"]
        p = plain_of(s)
        shown = ("“" + p + "”") if it.get("quote") else p
        g = ctx.glyphs(shown, it.get("at"))
        starts.append((s, p, shown, g))
    slot = 0
    for i, (s, p, shown, g) in enumerate(starts):
        it = items[i]
        size = it.get("size", el.get("size", 170))
        tid = _id("claim")
        roles = markup_spans(s)
        if it.get("quote"):
            roles = [("“", "accent")] + roles + [("”", "accent")]
        layers = []
        mark = it.get("mark")
        strike_t = ctx.at(it["strike"]) if it.get("strike") else None
        if mark:
            c0 = shown.find(mark)
            if c0 < 0:
                raise ValueError(f"mark {mark!r} not in claim {shown!r}")
            mt = ctx.at(it["mark_at"]) if it.get("mark_at") else max(g[c0:c0 + len(mark)]) + 0.08
            md = it.get("mark_dur", 0.55)
            band = mark_rect(tid, c0, c0 + len(mark), mt, md, accent, "band", 0.16, pad=0.06)
            layers.append(out_at(strike_t, band, 0.25))
        layers.append(text(ctx, shown, 0, 0, size, g, tid=tid, roles=roles))
        if mark:
            layers.append(recolor(ctx, shown, 0, 0, size, mt, md, set(range(c0, c0 + len(mark))), "accent", glyphs=g))
        if strike_t is not None:
            sd = it.get("strike_dur", 0.45)
            layers.append(recolor(ctx, shown, 0, 0, size, strike_t, sd, set(range(len(shown))), "muted", glyphs=g))
            layers.append(mark_rect(tid, 0, len(shown), strike_t, sd, muted, "strike", 1.0, pad=0.04))
        # 进场后何时退到上面那一摞：下一句开始前，或者被划掉的时刻
        nxt = starts[i + 1][3][0] if i + 1 < len(starts) else None
        leave = None
        if nxt is not None:
            leave = nxt - 0.42
        if strike_t is not None and (leave is None or strike_t < leave):
            leave = strike_t - 0.5
        track = [[0, 0, 0, 1, 1]]
        if leave is not None and not it.get("stay"):
            k = ss / size
            dy = (sy + slot * sg) - y
            track = [[0, 0, 0, 1, 1], [leave, 0, 0, 1, 1], [leave + 0.4, 0, dy, k, 1]]
            slot += 1
        inner = keys(track, "".join(layers))
        out.append(f'<g transform="translate({x},{y})">{inner}</g>')
    return "".join(out)


# ================================================================================================
# 小图标：会动的线条图标（画在 cx, cy 处，边长约 size）
# ================================================================================================
def brand_mark(ctx, logo, cx, cy, r, *, ring="rule", sw=None, scale=1.45):
    """代表某一方的圆点换成标志：白底圆里放 logo。logo 方图按圆裁切，白底图也能融进白圆。
    返回静态 SVG，入场由调用方套（pop 等）；不填 logo 的地方照旧画圆点。"""
    href = ctx.logo_href(logo)
    sw = max(3.0, r * 0.07) if sw is None else sw
    clip = _id("logo")
    s = r * scale
    return (f'<defs><clipPath id="{clip}"><circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(r - sw / 2)}"/></clipPath></defs>'
            f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(r)}" fill="#FFFFFF"/>'
            f'<g clip-path="url(#{clip})"><image href="{href}" x="{_r(cx - s / 2)}" y="{_r(cy - s / 2)}" '
            f'width="{_r(s)}" height="{_r(s)}" preserveAspectRatio="xMidYMid meet"/></g>'
            f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(r)}" fill="none" stroke="{ctx.col(ring)}" '
            f'stroke-width="{_r(sw)}"/>')


def icon(ctx, name, cx, cy, size, t0):
    a, ink = ctx.col("accent"), ctx.col("ink")
    r = size / 2
    sw = max(6, size / 22)
    pid = _id("ip")

    def draw(d, delay, dur=0.55, color=a, w=sw, extra=""):
        return (f'<path data-anim="draw" data-delay="{_r(delay)}" data-dur="{_r(dur)}" d="{d}" fill="none" '
                f'stroke="{color}" stroke-width="{_r(w)}" stroke-linecap="round" stroke-linejoin="round"{extra}/>')

    ring = (f'<circle data-anim="draw" data-delay="{_r(t0)}" data-dur="0.5" cx="{_r(cx)}" cy="{_r(cy)}" '
            f'r="{_r(r)}" fill="none" stroke="{ctx.col("rule")}" stroke-width="{_r(sw * 0.7)}"/>')
    if name == "bolt":
        s = r * 0.62
        d = (f"M{_r(cx + s * 0.15)},{_r(cy - s)} L{_r(cx - s * 0.45)},{_r(cy + s * 0.12)} "
             f"L{_r(cx + s * 0.05)},{_r(cy + s * 0.12)} L{_r(cx - s * 0.15)},{_r(cy + s)} "
             f"L{_r(cx + s * 0.45)},{_r(cy - s * 0.12)} L{_r(cx - s * 0.05)},{_r(cy - s * 0.12)} Z")
        halo = (f'<g transform="translate({_r(cx)},{_r(cy)})"><g data-anim="pulse" data-delay="{_r(t0 + 0.5)}" '
                f'data-dur="0.4" data-amp="0.10" data-spd="7" data-opmin="0.25">'
                f'<circle r="{_r(r * 1.12)}" fill="{a}" fill-opacity="0.10" stroke="{a}" stroke-width="{_r(sw * 0.5)}"/>'
                f'</g></g>')
        fillb = anim("fade", t0 + 0.45, 0.3, f'<path d="{d}" fill="{a}"/>')
        return halo + ring + draw(d, t0 + 0.05, 0.45) + fillb
    if name == "wander":
        s = r * 0.78
        d = (f"M{_r(cx - s)},{_r(cy + s * 0.55)} C{_r(cx - s * 0.6)},{_r(cy - s * 1.1)} {_r(cx - s * 0.05)},"
             f"{_r(cy + s * 1.05)} {_r(cx + s * 0.25)},{_r(cy - s * 0.15)} S{_r(cx + s * 0.95)},{_r(cy - s * 0.95)} "
             f"{_r(cx + s)},{_r(cy - s * 0.2)}")
        dot = (f'<circle data-anim="flow-blob" data-delay="{_r(t0 + 0.45)}" data-path="#{pid}" data-speed="0.8" '
               f'data-x0="0" data-y0="0" cx="0" cy="0" r="{_r(sw * 1.6)}" fill="{a}"/>')
        return (ring + f'<path id="{pid}" d="{d}" fill="none" stroke="none"/>'
                + draw(d, t0, 0.6, color=ink, w=sw * 0.6, extra=' stroke-dasharray="1 0"') + dot)
    if name == "burst":
        lines = []
        for k in range(8):
            ang = math.pi * 2 * k / 8 + 0.2
            r0, r1 = r * 0.22, r * (0.62 if k % 2 else 0.8)
            lines.append(f"M{_r(cx + r0 * math.cos(ang))},{_r(cy + r0 * math.sin(ang))} "
                         f"L{_r(cx + r1 * math.cos(ang))},{_r(cy + r1 * math.sin(ang))}")
        rays = "".join(draw(d, t0 + 0.04 * k, 0.25) for k, d in enumerate(lines))
        waves = "".join(
            f'<g transform="translate({_r(cx)},{_r(cy)})"><circle data-anim="shockwave" data-delay="{_r(t0 + dt)}" '
            f'data-dur="0.8" data-max="2.6" r="{_r(r * 0.5)}" fill="none" stroke="{a}" stroke-width="{_r(sw * 0.6)}"/></g>'
            for dt in (0.0, 0.22, 0.44))
        core = anim("pop", t0, 0.35, f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(r * 0.16)}" fill="{a}"/>')
        return waves + f'<g data-anim="shake" data-delay="{_r(t0)}" data-amp="{_r(size * 0.06)}">{rays}{core}</g>'
    if name == "math":     # 几何证明草图：圆、内接三角形、角弧、求和号
        s = r
        tri = (f"M{_r(cx - s * 0.78)},{_r(cy + s * 0.45)} L{_r(cx + s * 0.78)},{_r(cy + s * 0.45)} "
               f"L{_r(cx + s * 0.18)},{_r(cy - s * 0.86)} Z")
        circ = (f"M{_r(cx + s * 0.9)},{_r(cy)} A{_r(s * 0.9)},{_r(s * 0.9)} 0 1 1 {_r(cx + s * 0.9 - 0.01)},"
                f"{_r(cy - 0.5)}")
        arc = (f"M{_r(cx - s * 0.48)},{_r(cy + s * 0.45)} A{_r(s * 0.3)},{_r(s * 0.3)} 0 0 0 "
               f"{_r(cx - s * 0.6)},{_r(cy + s * 0.18)}")
        sig = (f"M{_r(cx + s * 1.55)},{_r(cy - s * 0.5)} L{_r(cx + s * 1.15)},{_r(cy - s * 0.5)} "
               f"L{_r(cx + s * 1.4)},{_r(cy)} L{_r(cx + s * 1.15)},{_r(cy + s * 0.5)} L{_r(cx + s * 1.55)},{_r(cy + s * 0.5)}")
        return (draw(circ, t0, 0.7, color=ink, w=sw * 0.6) + draw(tri, t0 + 0.25, 0.6) + draw(arc, t0 + 0.75, 0.3)
                + draw(sig, t0 + 0.55, 0.5, color=ink, w=sw * 0.8))
    if name == "phone":
        w_, h_ = r * 0.95, r * 1.6
        body = (f"M{_r(cx - w_ / 2 + 18)},{_r(cy - h_ / 2)} L{_r(cx + w_ / 2 - 18)},{_r(cy - h_ / 2)} "
                f"Q{_r(cx + w_ / 2)},{_r(cy - h_ / 2)} {_r(cx + w_ / 2)},{_r(cy - h_ / 2 + 18)} "
                f"L{_r(cx + w_ / 2)},{_r(cy + h_ / 2 - 18)} Q{_r(cx + w_ / 2)},{_r(cy + h_ / 2)} "
                f"{_r(cx + w_ / 2 - 18)},{_r(cy + h_ / 2)} L{_r(cx - w_ / 2 + 18)},{_r(cy + h_ / 2)} "
                f"Q{_r(cx - w_ / 2)},{_r(cy + h_ / 2)} {_r(cx - w_ / 2)},{_r(cy + h_ / 2 - 18)} "
                f"L{_r(cx - w_ / 2)},{_r(cy - h_ / 2 + 18)} Q{_r(cx - w_ / 2)},{_r(cy - h_ / 2)} "
                f"{_r(cx - w_ / 2 + 18)},{_r(cy - h_ / 2)} Z")
        btn = f"M{_r(cx - r * 0.15)},{_r(cy + h_ / 2 - r * 0.2)} L{_r(cx + r * 0.15)},{_r(cy + h_ / 2 - r * 0.2)}"
        return draw(body, t0, 0.55, color=ink, w=sw * 0.8) + draw(btn, t0 + 0.45, 0.2)
    if name == "laptop":
        w_, h_ = r * 1.5, r * 0.95
        scr = (f"M{_r(cx - w_ / 2)},{_r(cy + h_ / 2 - 10)} L{_r(cx - w_ / 2)},{_r(cy - h_ / 2)} "
               f"L{_r(cx + w_ / 2)},{_r(cy - h_ / 2)} L{_r(cx + w_ / 2)},{_r(cy + h_ / 2 - 10)}")
        base = f"M{_r(cx - w_ / 2 - r * 0.25)},{_r(cy + h_ / 2)} L{_r(cx + w_ / 2 + r * 0.25)},{_r(cy + h_ / 2)}"
        return draw(scr, t0, 0.5, color=ink, w=sw * 0.8) + draw(base, t0 + 0.35, 0.3)
    if name == "quote":
        return anim("pop", t0, 0.45,
                    f'<text x="{_r(cx)}" y="{_r(cy + size * 0.42)}" text-anchor="middle" font-size="{_r(size * 1.3)}" '
                    f'font-family="{esc(ctx.font("heavy"))}" font-weight="900" fill="{a}">“</text>')
    if name == "check":    # 打勾：绿圈里描出一笔勾
        tick = (f"M{_r(cx - r * 0.42)},{_r(cy + r * 0.02)} L{_r(cx - r * 0.1)},{_r(cy + r * 0.34)} "
                f"L{_r(cx + r * 0.46)},{_r(cy - r * 0.32)}")
        disc = anim("pop", t0, 0.35, f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(r * 0.92)}" fill="{a}" fill-opacity="0.14"/>')
        return disc + draw(tick, t0 + 0.12, 0.35, w=sw * 1.3)
    if name == "hook":     # 挂钩：钉座弹出，钩身一笔描出
        s = r * 0.9
        d = (f"M{_r(cx)},{_r(cy - s)} L{_r(cx)},{_r(cy + s * 0.35)} A{_r(s * 0.42)},{_r(s * 0.42)} 0 1 1 "
             f"{_r(cx - s * 0.84)},{_r(cy + s * 0.35)} L{_r(cx - s * 0.84)},{_r(cy + s * 0.12)}")
        mount = anim("pop", t0, 0.3, f'<circle cx="{_r(cx)}" cy="{_r(cy - s)}" r="{_r(sw * 1.6)}" fill="{ink}"/>')
        return mount + draw(d, t0 + 0.1, 0.5, color=ink, w=sw * 1.2)
    if name == "eye":      # 眼睛：轮廓描出，瞳孔弹出
        s = r * 0.95
        d = (f"M{_r(cx - s)},{_r(cy)} Q{_r(cx)},{_r(cy - s * 0.95)} {_r(cx + s)},{_r(cy)} "
             f"Q{_r(cx)},{_r(cy + s * 0.95)} {_r(cx - s)},{_r(cy)} Z")
        pupil = anim("pop", t0 + 0.35, 0.3, f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(s * 0.3)}" fill="{a}"/>')
        return draw(d, t0, 0.45, color=ink, w=sw) + pupil
    if name == "lock":     # 锁：锁身弹出，锁梁描出
        bw_, bh_ = r * 1.25, r * 0.95
        body = anim("pop", t0, 0.3, f'<rect x="{_r(cx - bw_ / 2)}" y="{_r(cy - bh_ * 0.2)}" width="{_r(bw_)}" '
                                    f'height="{_r(bh_)}" rx="{_r(r * 0.16)}" fill="{a}"/>')
        d = (f"M{_r(cx - bw_ * 0.32)},{_r(cy - bh_ * 0.2)} L{_r(cx - bw_ * 0.32)},{_r(cy - r * 0.45)} "
             f"A{_r(bw_ * 0.32)},{_r(bw_ * 0.32)} 0 0 1 {_r(cx + bw_ * 0.32)},{_r(cy - r * 0.45)} "
             f"L{_r(cx + bw_ * 0.32)},{_r(cy - bh_ * 0.2)}")
        return draw(d, t0 + 0.15, 0.35, color=a, w=sw * 1.3) + body
    if name == "swap":     # 换一家：上箭头向右（绿）、下箭头向左（黑），依次描出
        s = r * 0.6
        top = (f"M{_r(cx - s)},{_r(cy - s * 0.4)} L{_r(cx + s)},{_r(cy - s * 0.4)} "
               f"M{_r(cx + s * 0.5)},{_r(cy - s * 0.85)} L{_r(cx + s)},{_r(cy - s * 0.4)} "
               f"L{_r(cx + s * 0.5)},{_r(cy + s * 0.05)}")
        bot = (f"M{_r(cx + s)},{_r(cy + s * 0.4)} L{_r(cx - s)},{_r(cy + s * 0.4)} "
               f"M{_r(cx - s * 0.5)},{_r(cy - s * 0.05)} L{_r(cx - s)},{_r(cy + s * 0.4)} "
               f"L{_r(cx - s * 0.5)},{_r(cy + s * 0.85)}")
        return ring + draw(top, t0 + 0.1, 0.4) + draw(bot, t0 + 0.35, 0.4, color=ink)
    if name == "clip":     # 回形针（附上证据）：一笔描出
        s = r * 0.9
        d = (f"M{_r(cx + s * 0.28)},{_r(cy - s * 0.35)} L{_r(cx + s * 0.28)},{_r(cy + s * 0.55)} "
             f"A{_r(s * 0.28)},{_r(s * 0.28)} 0 0 1 {_r(cx - s * 0.28)},{_r(cy + s * 0.55)} "
             f"L{_r(cx - s * 0.28)},{_r(cy - s * 0.62)} A{_r(s * 0.2)},{_r(s * 0.2)} 0 0 1 {_r(cx + s * 0.12)},"
             f"{_r(cy - s * 0.62)} L{_r(cx + s * 0.12)},{_r(cy + s * 0.4)}")
        return ring + draw(d, t0 + 0.1, 0.55, color=ink, w=sw * 1.1)
    if name == "noloop":   # 循环箭头（再来一轮）描出后被一道斜线划掉
        s = r * 0.62
        arc = (f"M{_r(cx + s)},{_r(cy)} A{_r(s)},{_r(s)} 0 1 1 {_r(cx + s * 0.5)},{_r(cy - s * 0.87)}")
        tip = (f"M{_r(cx + s * 0.18)},{_r(cy - s * 1.12)} L{_r(cx + s * 0.55)},{_r(cy - s * 0.85)} "
               f"L{_r(cx + s * 0.22)},{_r(cy - s * 0.5)}")
        slash = f"M{_r(cx - r * 0.72)},{_r(cy + r * 0.72)} L{_r(cx + r * 0.72)},{_r(cy - r * 0.72)}"
        return (ring + draw(arc, t0, 0.45, color=ink, w=sw) + draw(tip, t0 + 0.4, 0.15, color=ink, w=sw)
                + draw(slash, t0 + 0.5, 0.25, color=a, w=sw * 1.3))
    if name == "plus":     # 往后加：一条横线接一个加号，加号弹出
        s = r * 0.62
        rows = "".join(draw(f"M{_r(cx - s)},{_r(cy - s * 0.55 + k * s * 0.45)} L{_r(cx + s * 0.2)},"
                            f"{_r(cy - s * 0.55 + k * s * 0.45)}", t0 + 0.08 * k, 0.3, color=ink, w=sw * 0.8)
                       for k in range(2))
        px_, py_ = cx + s * 0.55, cy + s * 0.55
        plus = (f'<path d="M{_r(px_ - s * 0.42)},{_r(py_)} L{_r(px_ + s * 0.42)},{_r(py_)} M{_r(px_)},{_r(py_ - s * 0.42)} '
                f'L{_r(px_)},{_r(py_ + s * 0.42)}" stroke="{a}" stroke-width="{_r(sw * 1.4)}" stroke-linecap="round"/>')
        return ring + rows + anim("pop", t0 + 0.25, 0.35, plus)
    if name == "books":    # 按月分卷：三本书脊依次立起，最新一本绿色
        bw_, bh_ = r * 0.36, r * 1.15
        out_ = [ring]
        for k in range(3):
            bx_ = cx - bw_ * 1.6 + k * bw_ * 1.1
            fill = a if k == 2 else ink
            out_.append(f'<rect data-anim="grow-bar" data-grow="y" data-delay="{_r(t0 + 0.1 * k)}" data-dur="0.35" '
                        f'x="{_r(bx_)}" y="{_r(cy - bh_ / 2)}" width="{_r(bw_)}" height="{_r(bh_)}" rx="{_r(bw_ * 0.18)}" '
                        f'fill="{fill}"/>')
        return "".join(out_)
    raise ValueError(f"unknown icon {name!r}")


# ================================================================================================
# 右侧卡片组：一张接一张替换（旧卡淡出上移、新卡升起），卡内依次是小标签、标题和会动的内容
# ================================================================================================
def deck(ctx, el):
    x, y, w, h = el.get("x", 2380), el.get("y", 580), el.get("w", 1220), el.get("h", 860)
    cards = el["deck"]
    out = []
    for i, cd in enumerate(cards):
        t0 = ctx.at(cd["at"])
        nxt = ctx.at(cards[i + 1]["at"]) if i + 1 < len(cards) else None
        if cd.get("until"):
            nxt = ctx.at(cd["until"])
        out.append(out_at(nxt, card(ctx, cd, x, y, w, h, t0), CARD_OUT))
    return "".join(out)


def card(ctx, cd, x, y, w, h, t0):
    th = ctx.th
    pad = cd.get("pad", 80)
    frame = cd.get("frame", True)
    parts = []
    cid = _id("card")
    if frame:
        sh = f"{cid}s"
        parts.append(f'<defs><filter id="{sh}" x="-10%" y="-10%" width="120%" height="130%">'
                     f'<feDropShadow dx="0" dy="18" stdDeviation="30" flood-color="#1A1A17" flood-opacity="0.07"/>'
                     f'</filter></defs>'
                     f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="36" fill="#FFFFFF" '
                     f'stroke="{ctx.col("rule")}" stroke-width="3" filter="url(#{sh})"/>')
    cy = y + pad
    inner = []
    if not cd.get("label") and not cd.get("title"):
        cy = y
    if cd.get("label"):
        lt = ctx.glyphs(cd["label"], cd.get("label_at"), start=None if cd.get("label_at") else t0 + 0.1)
        cy += 50
        inner.append(text(ctx, cd["label"], x + pad, cy, 50, lt, font="mono", weight=700, fill="muted", ls=4,
                          settle=False))
        cy += 40
    if cd.get("title"):
        tt = ctx.glyphs(plain_of(cd["title"]), cd.get("title_at"),
                        start=None if cd.get("title_at") else t0 + 0.15)
        size = cd.get("title_size", 110)
        cy += size
        inner.append(text(ctx, cd["title"], x + pad, cy, size, tt))
        if cd.get("logo"):       # 卡片代表某一方：标题右侧放标志（和 icon 二选一）
            ia = ctx.at(cd["icon_at"]) if cd.get("icon_at") else max(tt) + 0.1
            isz = cd.get("icon_size", 150)
            inner.append(anim("pop", ia, 0.4, brand_mark(ctx, cd["logo"], x + w - pad - isz * 0.6,
                                                         cy - size * 0.38, isz * 0.55)))
        elif cd.get("icon"):
            ia = ctx.at(cd["icon_at"]) if cd.get("icon_at") else max(tt) + 0.1
            isz = cd.get("icon_size", 150)
            inner.append(icon(ctx, cd["icon"], x + w - pad - isz * (1.6 if cd["icon"] == "math" else 0.6),
                              cy - size * 0.38, isz, ia))
        cy += 40
    for part in cd.get("body", []):
        frag, used = body_part(ctx, part, x, cy, w, y + h - cy, pad, t0, cid)
        inner.append(frag)
        cy += used
    content = "".join(parts) + "".join(inner)
    enter = cd.get("enter", "rise")
    if enter == "rise":
        return (f'<g data-anim="fade-up" data-delay="{_r(t0)}" data-dur="{CARD_IN}" data-shift="70">'
                f'{content}</g>')
    if enter == "pop":
        return anim("pop", t0, 0.5, content)
    if enter == "drop":
        return (f'<g data-anim="drop" data-delay="{_r(t0)}" data-dur="0.45" data-shift="90" data-spin="-2.5">'
                f'<g data-anim="shake" data-delay="{_r(t0 + 0.42)}" data-amp="22">{content}</g></g>')
    if enter == "iris":
        clip = f"{cid}i"
        return (f'<defs><clipPath id="{clip}"><circle data-anim="iris" data-ease="out" data-delay="{_r(t0)}" data-dur="0.7" '
                f'data-r0="0" data-r1="{_r(math.hypot(w, h))}" cx="{_r(x + w * 0.5)}" cy="{_r(y + h * 0.5)}" r="0"/>'
                f'</clipPath></defs><g clip-path="url(#{clip})">{content}</g>')
    raise ValueError(f"unknown card enter {enter!r}")


def body_part(ctx, part, x, top, w, room, pad, t0, cid):
    """卡片里的一块内容，返回 (svg, 用掉的高度)。"""
    kind = part["kind"]
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    if kind == "photo":
        ph = part.get("h", room - pad)
        bleed = part.get("bleed", False)
        px, py, pw = (x, top, w) if bleed else (x + pad, top + 20, w - 2 * pad)
        if bleed:
            ph = part.get("h", room)
        clip = _id("pc")
        dur = max(0.5, ctx.at(part["until"]) - t0) if part.get("until") else part.get("push", 6.0)
        zoom = part.get("zoom", 1.08)
        from pipeline.pages import _resolve
        img = ctx.L.FU(str(_resolve(ctx.b.base, part["photo"])))
        rx = 36 if bleed else 22
        return (f'<defs><clipPath id="{clip}"><rect x="{_r(px)}" y="{_r(py)}" width="{_r(pw)}" height="{_r(ph)}" '
                f'rx="{rx}"/></clipPath></defs><g clip-path="url(#{clip})">'
                f'<g data-anim="push" data-ease="linear" data-delay="{_r(t0)}" data-dur="{_r(dur)}" data-sc0="1" '
                f'data-sc1="{zoom}" data-origin="{_r(part.get("fx", 0.5) * 100)}% {_r(part.get("fy", 0.5) * 100)}%">'
                f'<image href="{img}" x="{_r(px)}" y="{_r(py)}" width="{_r(pw)}" height="{_r(ph)}" '
                f'preserveAspectRatio="{part.get("align", "xMidYMid")} slice"/></g></g>'), ph + 40
    if kind == "wave":
        n, hh = part.get("bars", 30), part.get("h", 170)
        on, until = ctx.at(part["at"]), ctx.at(part["until"])
        bw = (w - 2 * pad) / n
        bars = []
        for k in range(n):
            bx = x + pad + k * bw + bw * 0.22
            env = 0.45 + 0.55 * math.sin(math.pi * (k + 0.5) / n)
            bars.append(f'<rect data-anim="wave" data-delay="{_r(on)}" data-dur="{_r(until - on)}" '
                        f'data-amp="{_r(env)}" data-phase="{_r(k * 1.7 % 6.28)}" data-spd="{_r(9 + (k * 37 % 7))}" '
                        f'x="{_r(bx)}" y="{_r(top + 20)}" width="{_r(bw * 0.56)}" height="{hh}" rx="{_r(bw * 0.28)}" '
                        f'fill="{a if k % 5 else ink}"/>')
        label = ""
        if part.get("label"):
            lt = ctx.glyphs(part["label"], part.get("label_at"), start=None if part.get("label_at") else on)
            label = text(ctx, part["label"], x + pad, top + hh + 110, 50, lt, font="mono", weight=700, fill="muted",
                         ls=4, settle=False)
        return anim("fade", t0 + 0.2, 0.4, "".join(bars)) + label, hh + 140
    if kind == "grid":
        cols, n = part.get("cols", 7), part.get("n", 35)
        gap = 18
        cell = min((w - 2 * pad - gap * (cols - 1)) / cols, part.get("cell", 120))
        on = ctx.at(part["at"])
        flips = set(part.get("flip", []))
        flip_at = ctx.at(part["flip_at"]) if part.get("flip_at") else None
        cells = []
        order = sorted(flips)
        rings = list(part.get("ring", []))
        ring_at = ctx.at(part["ring_at"]) if part.get("ring_at") else None
        dims = set(part.get("dim", []))
        dim_at = ctx.at(part["dim_at"]) if part.get("dim_at") else None
        gx = x + pad + ((w - 2 * pad - cols * cell - (cols - 1) * gap) / 2 if part.get("center") else 0)
        for k in range(n):
            cx_ = gx + (k % cols) * (cell + gap)
            cy_ = top + 20 + (k // cols) * (cell + gap)
            sq = (f'<rect x="{_r(cx_)}" y="{_r(cy_)}" width="{_r(cell)}" height="{_r(cell)}" rx="10" '
                  f'fill="{a}" fill-opacity="0.22"/>')
            if part.get("glyph") == "image":     # 图片占位：小太阳 + 两座山
                s = cell
                sq += (f'<circle cx="{_r(cx_ + s * 0.7)}" cy="{_r(cy_ + s * 0.3)}" r="{_r(s * 0.09)}" fill="#FFFFFF"/>'
                       f'<path d="M{_r(cx_ + s * 0.12)},{_r(cy_ + s * 0.8)} L{_r(cx_ + s * 0.38)},{_r(cy_ + s * 0.45)} '
                       f'L{_r(cx_ + s * 0.55)},{_r(cy_ + s * 0.66)} L{_r(cx_ + s * 0.68)},{_r(cy_ + s * 0.52)} '
                       f'L{_r(cx_ + s * 0.88)},{_r(cy_ + s * 0.8)} Z" fill="{a}" fill-opacity="0.75"/>')
            cell_svg = anim("pop", on + k * part.get("step", 0.018), 0.3, sq)
            if k in dims and dim_at is not None:     # 到点变淡（例如被筛掉的那几张）
                cell_svg = keys([[0, 0, 0, 1, 1], [dim_at, 0, 0, 1, 1], [dim_at + 0.35, 0, 0, 1, 0.22]], cell_svg)
            cells.append(cell_svg)
            if k in rings and ring_at is not None:   # 到点圈出（例如抽出来让人核对的几张）
                rk = ring_at + rings.index(k) * part.get("ring_step", 0.12)
                cells.append(f'<rect data-anim="draw" data-delay="{_r(rk)}" data-dur="0.35" x="{_r(cx_ - 9)}" '
                             f'y="{_r(cy_ - 9)}" width="{_r(cell + 18)}" height="{_r(cell + 18)}" rx="16" fill="none" '
                             f'stroke="{a}" stroke-width="8"/>')
            if k in flips and flip_at is not None:
                dk = flip_at + order.index(k) * part.get("flip_step", 0.07)
                ins = cell * 0.2
                cells.append(anim("pop", dk, 0.32,
                                  f'<rect x="{_r(cx_ + ins)}" y="{_r(cy_ + ins)}" width="{_r(cell - 2 * ins)}" '
                                  f'height="{_r(cell - 2 * ins)}" rx="8" fill="{ink}"/>'))
        rows = math.ceil(n / cols)
        return "".join(cells), rows * (cell + gap) + 40
    if kind == "comments":
        out = []
        size = part.get("size", 64)
        rowh = size * 2.6
        for k, item in enumerate(part["items"]):
            logo = None
            if isinstance(item, str):
                s, cue = item, None
            elif isinstance(item, dict):
                s, cue, logo = item["text"], item.get("at"), item.get("logo")
            else:
                s, cue, logo = (list(item) + [None])[:3]
            ta = ctx.at(cue) if cue else t0 + k * part.get("step", 0.55)
            ox = x + pad + (k % 2) * part.get("jog", 60)
            oy = top + k * (rowh + 28)
            cw = min(w - 2 * pad - 60, ctx.width(s, size) + size * 3.4)
            rot = (-1.2, 0.9, -0.6, 1.1)[k % 4]
            bub = (f'<rect x="{_r(ox)}" y="{_r(oy)}" width="{_r(cw)}" height="{_r(rowh)}" rx="{_r(rowh / 2)}" '
                   f'fill="#FFFFFF" stroke="{rule}" stroke-width="3"/>'
                   + (brand_mark(ctx, logo, ox + rowh / 2, oy + rowh / 2, rowh * 0.34, sw=3) if logo else
                      f'<circle cx="{_r(ox + rowh / 2)}" cy="{_r(oy + rowh / 2)}" r="{_r(rowh * 0.28)}" '
                      f'fill="{a if k == 1 else ctx.col("block")}"/>') +
                   f'<text x="{_r(ox + rowh * 0.95)}" y="{_r(oy + rowh / 2 + size * 0.36)}" font-family="'
                   f'{esc(ctx.font("sans"))}" font-size="{size}" font-weight="600" fill="{ink}">{esc(s)}</text>')
            out.append(f'<g transform="rotate({rot} {_r(ox + cw / 2)} {_r(oy + rowh / 2)})">'
                       f'{anim("pop", ta, 0.45, bub)}</g>')
        return "".join(out), len(part["items"]) * (rowh + 28)
    from pipeline.board_bodies import BODIES
    if kind in BODIES:
        return BODIES[kind](ctx, part, x, top, w, room, pad, t0)
    raise ValueError(f"unknown card body kind {kind!r}")


# ================================================================================================
# 时间线：细轴画出、刻度依次弹出；节点按念到弹出，最新节点绿色并呼吸；可选一个点沿轴走过去
# ================================================================================================
def timeline(ctx, el):
    x0, x1, y = el.get("x0", 240), el.get("x1", 3600), el.get("y", 1660)
    nodes = el["timeline"]
    a, ink, rule = ctx.col("accent"), ctx.col("ink"), ctx.col("rule")
    t_axis = ctx.at(el["at"]) if el.get("at") else min(ctx.at(n["at"]) for n in nodes)
    out = [f'<line data-anim="draw" data-delay="{_r(t_axis)}" data-dur="0.7" x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" '
           f'stroke="{rule}" stroke-width="5" stroke-linecap="round"/>']
    nt = el.get("ticks", 28)
    ticks_x = [x0 + (x1 - x0) * (k + 0.5) / nt for k in range(nt)]
    for k, tx in enumerate(ticks_x):
        out.append(anim("pop", t_axis + 0.02 * k, 0.25,
                        f'<rect x="{_r(tx - 3)}" y="{y - 18}" width="6" height="36" rx="3" fill="{rule}"/>'))
    times = [ctx.at(n["at"]) for n in nodes]
    xs = [x0 + (x1 - x0) * n.get("x", (k + 1) / (len(nodes) + 1)) for k, n in enumerate(nodes)]
    order = sorted(range(len(nodes)), key=lambda k: times[k])
    tr = el.get("trace")
    if tr:
        ta, tb = ctx.at(tr["at"]), ctx.at(tr["until"])
        xa, xb = xs[tr.get("from", 0)], xs[tr.get("to", len(nodes) - 1)]
        dot = _id("tdot")
        out.append(f'<path data-anim="trace-dot" data-dot="#{dot}" data-delay="{_r(ta)}" data-dur="{_r(tb - ta)}" '
                   f'data-ease="in-out" d="M{_r(xa)},{y} L{_r(xb)},{y}" fill="none" stroke="{a}" stroke-width="10" '
                   f'stroke-linecap="round"/>'
                   f'<circle id="{dot}" cx="0" cy="0" r="22" fill="{a}" stroke="#FFFFFF" stroke-width="6" '
                   f'style="opacity:0"/>')
        for k, tx in enumerate(ticks_x):
            if min(xa, xb) < tx < max(xa, xb):
                f = abs(tx - xa) / abs(xb - xa)
                # trace-dot 用三次 in-out 缓动：求点走到这一格的时刻
                q = (f / 4) ** (1 / 3) if f < 0.5 else 1 - (2 * (1 - f)) ** (1 / 3) / 2
                out.append(anim("fade", ta + (tb - ta) * q, 0.12,
                                f'<rect x="{_r(tx - 3)}" y="{y - 18}" width="6" height="36" rx="3" fill="{a}"/>'))
    for k, n in enumerate(nodes):
        t = times[k]
        nxt = [times[j] for j in order if times[j] > t]
        later = min(nxt) if nxt else None
        nx = xs[k]
        up = n.get("side", "up") == "up"
        ly = y - 92 if up else y + 130
        lab = n["label"]
        lt = ctx.glyphs(lab, n["at"])
        anchor = n.get("anchor", "middle")
        out.append(f'<line data-anim="draw" data-delay="{_r(t)}" data-dur="0.3" x1="{_r(nx)}" y1="{y}" x2="{_r(nx)}" '
                   f'y2="{y - 52 if up else y + 52}" stroke="{ink}" stroke-width="4"/>')
        out.append(text(ctx, lab, nx, ly, n.get("size", 68), lt, font="sans", weight=700, anchor=anchor))
        if n.get("sub"):
            st = ctx.glyphs(n["sub"], n.get("sub_at"), start=None if n.get("sub_at") else max(lt) + 0.1)
            out.append(text(ctx, n["sub"], nx, ly - 84 if up else ly + 72, 48, st, font="mono", weight=700,
                            fill="muted", anchor=anchor, settle=False))
        lr = n.get("logo_r", 52)
        halo = (f'<g transform="translate({_r(nx)},{y})"><g data-anim="pulse" data-delay="{_r(t + 0.3)}" data-dur="0.3" '
                f'data-amp="0.18" data-spd="6" data-opmin="0.2"><circle r="{_r(lr * 1.45 if n.get("logo") else 44)}" '
                f'fill="{a}" fill-opacity="0.16"/></g></g>')
        out.append(out_at(later, halo, 0.3))
        if n.get("logo"):    # 节点代表某一方：圆点换成标志，最新节点描绿圈
            dot_ink = anim("pop", t, 0.4, brand_mark(ctx, n["logo"], 0, 0, lr, ring="rule", sw=5))
            dot_green = anim("pop", t, 0.4, f'<circle r="{_r(lr)}" fill="none" stroke="{a}" stroke-width="7"/>')
        else:
            dot_ink = anim("pop", t, 0.4, f'<circle r="22" fill="{ink}"/>')
            dot_green = anim("pop", t, 0.4, f'<circle r="22" fill="{a}"/>')
        out.append(f'<g transform="translate({_r(nx)},{y})">{dot_ink}</g>')
        green = f'<g transform="translate({_r(nx)},{y})">{dot_green}</g>'
        out.append(out_at(later, green, 0.3))
    return "".join(out)


# ================================================================================================
# 带图标清单：逐条出现，每条配会动的图标；左侧绿色指示条跟着念到的那条走，旧条目变淡
# ================================================================================================
def checklist(ctx, el):
    x, y, gap, size = el.get("x", 240), el.get("y", 780), el.get("gap", 300), el.get("size", 120)
    items = el["checklist"]
    a = ctx.col("accent")
    isz = el.get("icon_size", 170)
    tx = x + isz + 90
    out = []
    focus = [ctx.at(c) for c in el["focus"]] if el.get("focus") else \
        [ctx.at(it.get("pre_at") or it["at"]) for it in items]
    for k, it in enumerate(items):
        ry = y + k * gap
        t = ctx.at(it["at"])
        row = []
        if it.get("icon"):
            row.append(icon(ctx, it["icon"], x + isz / 2, ry - size * 0.36, isz, t))
        elif el.get("index"):        # 编号代替图标：轮到这一条时先出编号，字按念到出现
            num = f"{k + 1:02d}"
            row.append(text(ctx, num, x, ry, round(size * 0.62), [round(focus[k] + 0.05 * i, 3) for i in range(2)],
                            font="mono", weight=700, fill="accent", settle=False))
        g = ctx.glyphs(plain_of(it["text"]), it["at"])
        row.append(text(ctx, it["text"], tx, ry, size, g))
        if it.get("pre"):
            pg = ctx.glyphs(it["pre"], it.get("pre_at"))
            row.append(text(ctx, it["pre"], tx, ry - size * 1.05, 58, pg, font="sans", weight=500, fill="muted",
                            settle=False))
        dim = focus[k + 1] if k + 1 < len(focus) else None
        track = [[0, 0, 0, 1, 1]] if dim is None else [[0, 0, 0, 1, 1], [dim, 0, 0, 1, 1], [dim + 0.35, 0, 0, 1, 0.38]]
        if el.get("all_at") and dim is not None:     # 最后一齐点亮（例如“这些”）
            back = ctx.at(el["all_at"]) + 0.04 * k
            track += [[back, 0, 0, 1, 0.38], [back + 0.35, 0, 0, 1, 1]]
        out.append(keys(track, "".join(row)))
    # 指示条
    bar_h = size * 1.25
    track = []
    for k, f in enumerate(focus):
        yy = y + k * gap - size * 0.36 - bar_h / 2
        if not track:
            track.append([0, 0, yy, 1, 0])
            track.append([f, 0, yy, 1, 0])
            track.append([f + 0.25, 0, yy, 1, 1])
        else:
            track.append([f, 0, track[-1][2], 1, 1])
            track.append([f + 0.35, 0, yy, 1, 1])
    out.append(keys(track, f'<rect x="{x - 70}" y="0" width="14" height="{_r(bar_h)}" rx="7" fill="{a}"/>'))
    return "".join(out)


# ================================================================================================
# 数字条形：每行条从左长出、数字滚动；“合计”时后面的条移到第一行接上，总数滚动
# ================================================================================================
def tally(ctx, el):
    x, y, gap, bh = el.get("x", 240), el.get("y", 1250), el.get("gap", 260), el.get("h", 150)
    lw = el.get("label_w", 440)
    rows = el["tally"]
    total = el.get("total")
    a, ink = ctx.col("accent"), ctx.col("ink")
    vmax = el.get("max", sum(float(r["value"]) for r in rows) if total else max(float(r["value"]) for r in rows))
    W = el.get("w", 3600 - x - lw)
    merge = ctx.at(total["at"]) if total else None
    out = []
    acc = 0.0
    nsize = el.get("number_size", 150)
    for k, r in enumerate(rows):
        ry = y + k * gap
        bw = W * float(r["value"]) / vmax
        t = ctx.at(r["at"])
        dur = r.get("dur", 1.0)
        color = ctx.col(r.get("color", "ink" if k == 0 else "accent"))
        lab_t = ctx.glyphs(r["label"], r.get("label_at") or r["at"])
        lx = x
        lab = ""
        if r.get("logo"):    # 这一行代表某一方：名字前放标志，名字右移
            lr = bh * 0.5
            lab = anim("pop", lab_t[0], 0.4, brand_mark(ctx, r["logo"], x + lr, ry + bh * 0.5, lr))
            lx = x + lr * 2 + 30
        lab += text(ctx, r["label"], lx, ry + bh * 0.5 + 30, 84, lab_t, font="sans", weight=700)
        out.append(out_at(merge, lab, 0.3))
        bar = (f'<rect data-anim="grow-bar" data-delay="{_r(t)}" data-dur="{_r(dur)}" x="{x + lw}" y="{ry}" '
               f'width="{_r(bw)}" height="{bh}" rx="12" fill="{color}"/>')
        if merge is not None and k:
            dx, dy = W * acc / vmax, -k * gap
            bar = keys([[0, 0, 0, 1, 1], [merge, 0, 0, 1, 1], [merge + 0.55, dx, dy, 1, 1]], bar)
        out.append(bar)
        if r.get("number", True):
            v = float(r["value"])
            dec = r.get("decimals", 0 if v.is_integer() else 1)
            nx = x + lw + bw + 50
            ny = ry + bh * 0.5 + nsize * 0.36
            nid = _id("num")
            comma = ' data-comma="1"' if r.get("comma") else ""
            num = (f'<text id="{nid}" data-anim="count" data-delay="{_r(t)}" data-dur="{_r(dur)}" data-to="{v}" '
                   f'data-decimals="{dec}"{comma} x="{_r(nx)}" y="{_r(ny)}" font-family="{esc(ctx.font("heavy"))}" '
                   f'font-size="{nsize}" font-weight="900" fill="{color}">0</text>')
            if r.get("unit"):
                ut = ctx.glyphs(r["unit"], r.get("unit_at"), start=None if r.get("unit_at") else t + dur)
                num += text(ctx, r["unit"], nx, ny, 72, ut, font="sans", weight=700, fill="muted",
                            follow=nid, gap=28)
            out.append(out_at(merge, num, 0.3))
        if merge is not None:
            seg = text(ctx, r["label"], x + lw + W * acc / vmax + 6, y + bh + 78, 56,
                       [round(merge + 0.5 + 0.03 * i, 3) for i in range(len(r["label"]))],
                       font="mono", weight=700, fill="muted", settle=False)
            out.append(seg)
        acc += float(r["value"])
    if total:
        ct = ctx.at(total["count_at"]) if total.get("count_at") else merge + 0.4
        dur = total.get("dur", 1.5)
        v = float(total["value"])
        dec = total.get("decimals", 0 if v.is_integer() else 1)
        size = total.get("size", 230)
        ny = y - 70                                   # 总数基线：压在合并后的整条上方
        nx = x + lw
        lt = ctx.glyphs(total["label"], total["at"])
        out.append(text(ctx, total["label"], nx, ny - size * 0.86, 60, lt, font="mono", weight=700, fill="muted",
                        ls=6, settle=False))
        tid = _id("total")
        out.append(f'<text id="{tid}" data-anim="count" data-delay="{_r(ct)}" data-dur="{_r(dur)}" data-to="{v}" '
                   f'data-decimals="{dec}" x="{nx}" y="{ny}" font-family="{esc(ctx.font("heavy"))}" '
                   f'font-size="{size}" font-weight="900" fill="{a}">0</text>')
        if total.get("unit"):
            ut = ctx.glyphs(total["unit"], total.get("unit_at"), start=None if total.get("unit_at") else ct + dur)
            out.append(text(ctx, total["unit"], nx, ny, round(size * 0.5), ut, font="heavy", weight=900,
                            fill="accent", follow=tid, gap=30))
    return "".join(out)


# ================================================================================================
# 圆形擦除：页面底色的圆从一点扩大盖住整页（边上一圈细绿线），常用在换段落前
# ================================================================================================
def wipe(ctx, el):
    t = ctx.at(el["wipe"])
    cx, cy = el.get("x", 1920), el.get("y", 1080)
    dur = el.get("dur", 0.4)
    r1 = math.hypot(max(cx, config.WIDTH - cx), max(cy, config.HEIGHT - cy)) + 40
    return (f'<circle data-anim="iris" data-cover="1" data-delay="{_r(t)}" data-dur="{_r(dur)}" data-r0="0" data-r1="{_r(r1)}" '
            f'cx="{cx}" cy="{cy}" r="0" fill="{ctx.col("page")}" fill-opacity="0.99" stroke="{ctx.col("accent")}" '
            f'stroke-width="10"/>')   # 0.99：盖满整页时截图仍带透明通道，编码不换格式


def tiles(ctx, el):
    """词轴卡片网格：分类、对照、动作清单；同一卡片可移位、变淡、划线或加锁。"""
    items = el["tiles"]
    cols = el.get("cols", len(items))
    if cols < 1:
        raise ValueError("tiles cols must be positive")
    x, y = el.get("x", 240), el.get("y", 640)
    w, h, gap = el.get("w", 1000), el.get("h", 380), el.get("gap", 48)
    out = []
    for k, it in enumerate(items):
        tx, ty = x + (k % cols) * (w + gap), y + (k // cols) * (h + gap)
        at = ctx.at(it["at"])
        dark = it.get("dark", False)
        fg, bg = ("#FFFFFF", ctx.col("ink")) if dark else ("ink", "#FFFFFF")
        border = ctx.col("accent" if it.get("accent") else "rule")
        parts = [f'<rect width="{w}" height="{h}" rx="28" fill="{bg}" stroke="{border}" stroke-width="3"/>']
        parts.append(f'<rect x="0" y="32" width="10" height="{h - 64}" rx="5" '
                     f'fill="{ctx.col("accent")}" fill-opacity="{1 if it.get("accent") or dark else 0.22}"/>')
        size = it.get("size", el.get("size", 140))
        title = it.get("title", "")
        pad = it.get("pad", 64)
        lines = it.get("lines", [])
        baseline = pad + size if lines else h / 2 + size * 0.36
        if title:
            tid = _id("tile")
            if it.get("replay") or el.get("replay"):    # 前面已讲过的字样重现：从 at 起直接打出，不等后文再念到
                tt = ctx.glyphs(plain_of(title), start=ctx.at(it.get("title_at", it["at"])), search=False)
            else:
                tt = ctx.glyphs(plain_of(title), it.get("title_at", it["at"]))
            parts.append(text(ctx, title, pad, baseline, size, tt, fill=fg, tid=tid,
                              settle=not dark, fade=it.get("fade", GLYPH_FADE)))
            if it.get("strike_at"):
                st = ctx.at(it["strike_at"])
                parts.append(mark_rect(tid, 0, len(plain_of(title)), st, it.get("strike_dur", 0.28),
                                       ctx.col("muted"), "strike"))
            if it.get("logo"):   # 卡片代表某一方：标题右侧放标志，和标题一起出现
                lr = it.get("logo_r", size * 0.5)
                la = ctx.at(it["logo_at"]) if it.get("logo_at") else min(tt)
                parts.append(anim("pop", la, 0.4, brand_mark(ctx, it["logo"], w - pad * 0.7 - lr,
                                                             baseline - size * 0.36, lr)))
        ly = baseline
        for line in lines:
            fs = line.get("size", 100)
            ly += line.get("gap", fs * 1.5)
            gt = ctx.glyphs(plain_of(line["text"]), line["at"])
            lid = _id("tline") if line.get("strike_at") else None
            parts.append(text(ctx, line["text"], pad, ly, fs, gt,
                              fill=line.get("color", "#FFFFFF" if dark else "muted"),
                              font="sans", weight=600, settle=False, tid=lid))
            if lid:      # 这一行到点划掉（如“写死的数”）
                parts.append(mark_rect(lid, 0, len(plain_of(line["text"])), ctx.at(line["strike_at"]),
                                       line.get("strike_dur", 0.3), ctx.col("ink"), "strike"))
        if it.get("focus_at"):
            ft = ctx.at(it["focus_at"])
            parts.append(f'<rect data-anim="draw" data-delay="{_r(ft)}" data-dur="0.4" '
                         f'x="-8" y="-8" width="{w + 16}" height="{h + 16}" rx="34" fill="none" '
                         f'stroke="{ctx.col("accent")}" stroke-width="8"/>')
        if it.get("lock_at"):
            lt = ctx.at(it["lock_at"])
            lx, ly = w - 136, 56
            lock = (f'<path d="M{lx + 12},{ly + 38} v-15 a26,26 0 0 1 52,0 v15" fill="none" '
                    f'stroke="{ctx.col("accent")}" stroke-width="9"/>'
                    f'<rect x="{lx}" y="{ly + 35}" width="76" height="62" rx="10" fill="{ctx.col("accent")}"/>'
                    f'<circle cx="{lx + 38}" cy="{ly + 60}" r="7" fill="#FFFFFF"/>')
            parts.append(anim("pop", lt, it.get("lock_dur", 0.35), lock))
        inner = "".join(parts)
        if it.get("dim_at"):
            dt = ctx.at(it["dim_at"])
            low = it.get("opacity", 0.25)
            track = [[0, 0, 0, 1, 1], [dt, 0, 0, 1, 1], [dt + it.get("dim_dur", 0.3), 0, 0, 1, low]]
            if it.get("undim_at"):       # 变淡后再点亮（例如先只看禁令，再回到要求和建议）
                ut = ctx.at(it["undim_at"])
                if ut < track[-1][0]:
                    raise ValueError(f"tile undim_at {it['undim_at']!r} comes before its dimming finishes")
                track += [[ut, 0, 0, 1, low], [ut + 0.3, 0, 0, 1, 1]]
            inner = keys(track, inner)
        if it.get("move_at"):
            mt, dest = ctx.at(it["move_at"]), it["move_to"]
            inner = keys([[0, 0, 0, 1, 1], [mt, 0, 0, 1, 1],
                          [mt + it.get("move_dur", 0.55), dest[0] - tx, dest[1] - ty, 1, 1]], inner)
        inner = out_at(ctx.at(it["exit_at"]) if it.get("exit_at") else None, inner, it.get("exit_dur", 0.25))
        entrance = anim("fade-up", at, it.get("dur", 0.35), inner, ' data-shift="55"')
        out.append(f'<g transform="translate({_r(tx)},{_r(ty)})">{entrance}</g>')
    return "".join(out)


KINDS = {"head": head, "claims": claims, "deck": deck, "timeline": timeline, "checklist": checklist,
         "tally": tally, "wipe": wipe, "tiles": tiles}

from pipeline.board_diagrams import KINDS as DIAGRAM_KINDS  # noqa: E402
from pipeline.board_bodies import cards as _cards  # noqa: E402
KINDS.update(DIAGRAM_KINDS)
KINDS["cards"] = _cards
