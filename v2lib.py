# -*- coding: utf-8 -*-
"""
回形针式组件库 (v2)。每个函数返回一段合规静态 SVG 片段，挂 data-cue 实现"先音后画面"。
设计规格见 paperclip-design-spec。坐标恒为 viewBox 0 0 3840 2160。

约定：
- 定位用"外层 <g transform> 属性"；动画用"内层无 transform 的元素 data-anim"。
- 时间用 cue(旁白真词) 优先，并永远附一个 data-delay 兜底（cue 未命中时仍按兜底出现）。
- 颜色语义：INK 文字主色 / ACCENT 好·结论 / RED 代价·坏 / GOLD 钱。
"""
import os, sys, math, pathlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

INK, ACCENT = config.INK, config.ACCENT
RED, GOLD = "#C0392B", "#B8862F"
DIM = "#0C2B1B"
SERIF = "'Source Han Serif CN','Microsoft YaHei',serif"
SANS = "'Microsoft YaHei','PingFang SC',-apple-system,sans-serif"

# ---- grid & type ----------------------------------------------------------
W, H, CX, CY = 3840, 2160, 1920, 1080
M = 240                                  # margin / strong left edge
COL = [240,540,840,1140,1440,1740,2040,2340,2640,2940,3240,3540]
ROW = 120
# six type levels (size, weight, fill, opacity)
T = {0:(220,700,INK,1), 1:(150,700,INK,1), 2:(100,700,INK,1),
     3:(64,600,INK,1), 4:(44,500,INK,0.62), 5:(32,400,INK,0.45)}

ASSETS = config.DIR_ASSETS
def FU(name): return pathlib.Path(os.path.join(ASSETS, name)).as_uri()


def _probe_img_header(path):
    """Read pixel (width,height) straight from a PNG/JPEG header — no Pillow needed.
    Lets a new project drop fresh art in assets/ without hand-filling DIMS."""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":           # PNG: IHDR at byte 16
                import struct
                w, h = struct.unpack(">II", head[16:24])
                return int(w), int(h)
            if head[:2] == b"\xff\xd8":                    # JPEG: scan SOF markers
                f.seek(2)
                while True:
                    b = f.read(1)
                    while b and b != b"\xff":
                        b = f.read(1)
                    marker = f.read(1)
                    while marker == b"\xff":
                        marker = f.read(1)
                    if not marker:
                        break
                    if 0xC0 <= marker[0] <= 0xCF and marker[0] not in (0xC4, 0xC8, 0xCC):
                        f.read(3)                          # length(2) + precision(1)
                        h = int.from_bytes(f.read(2), "big")
                        w = int.from_bytes(f.read(2), "big")
                        return w, h
                    seg = int.from_bytes(f.read(2), "big")
                    f.seek(seg - 2, 1)
    except Exception:
        pass
    return None


def img_dims(name):
    """Pixel size of an asset. Hand-tuned DIMS (EXIF-corrected) win; otherwise the
    size is probed from the file header automatically, so swapping in a new
    project's assets needs zero DIMS edits."""
    if name in DIMS:
        return DIMS[name]
    dims = _probe_img_header(os.path.join(ASSETS, name))
    if dims:
        return dims
    try:
        from PIL import Image
        with Image.open(os.path.join(ASSETS, name)) as im:
            return im.size
    except Exception:
        pass
    raise KeyError(f"unknown image dims for {name!r}; add it to v2lib.DIMS")

# Optional per-project EXIF/special-format overrides. Normal PNG/JPEG assets are
# probed automatically; keep the reusable scaffold topic-neutral.
DIMS = {}

# ---- timing helper: cue first, data-delay fallback ------------------------
def _t(cue, delay, dur=None, offset=None, index=None):
    import html
    cue = html.escape(str(cue), quote=True) if cue else cue
    a = f'data-cue="{cue}" data-delay="{delay:.2f}"' if cue else f'data-delay="{delay:.2f}"'
    if cue and index and index != 1: a += f' data-cue-index="{int(index)}"'
    if cue and offset: a += f' data-cue-offset="{offset:.3f}"'
    if dur is not None: a += f' data-dur="{dur}"'
    return a

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# ---- atoms ----------------------------------------------------------------
def text(s, x, y, lvl=3, cue=None, delay=0.3, dur=0.7, anim="fade-up", fill=None,
         anchor="start", weight=None, serif=False, opacity=None, ls=0):
    sz, wt, fl, op = T[lvl]
    fill = fill or fl; weight = weight or wt; opacity = op if opacity is None else opacity
    fam = SERIF if serif else SANS
    return (f'<text data-anim="{anim}" {_t(cue,delay,dur)} x="{x}" y="{y}" '
            f'font-family="{fam}" font-size="{sz}" font-weight="{weight}" fill="{fill}" '
            f'fill-opacity="{opacity}" text-anchor="{anchor}" letter-spacing="{ls}">{esc(s)}</text>')

def type_in(s, x, y, lvl=1, cue=None, delay=0.3, dur=1.2, fill=None, serif=True, anchor="start", ls=4):
    sz, wt, fl, op = T[lvl]; fill = fill or fl; fam = SERIF if serif else SANS
    return (f'<text data-anim="type" {_t(cue,delay,dur)} x="{x}" y="{y}" font-family="{fam}" '
            f'font-size="{sz}" font-weight="{wt}" fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}">{esc(s)}</text>')

def num(value, x, y, lvl=1, cue=None, delay=0.3, dur=1.0, prefix="", suffix="", dec=0,
        comma=False, fill=None, anchor="start", weight=None):
    sz, wt, fl, op = T[lvl]; fill = fill or fl; weight = weight or wt
    return (f'<text data-anim="count" {_t(cue,delay,dur)} data-to="{value}" data-decimals="{dec}" '
            f'data-prefix="{prefix}" data-suffix="{suffix}" data-comma="{1 if comma else 0}" '
            f'x="{x}" y="{y}" font-family="{SANS}" font-size="{sz}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}">0</text>')

def pop(s, x, y, lvl=1, cue=None, delay=0.4, dur=0.6, fill=None, anchor="start", serif=False, weight=None):
    sz, wt, fl, op = T[lvl]; fill = fill or fl; weight = weight or wt; fam = SERIF if serif else SANS
    return (f'<g transform="translate({x},{y})"><text data-anim="pop" {_t(cue,delay,dur)} x="0" y="0" '
            f'font-family="{fam}" font-size="{sz}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(s)}</text></g>')

def fade_out(frag_id_x, y, w, h, delay, dur=0.5):  # not used directly; see clear()
    pass

def rule(x, y, w, cue=None, delay=0.5, dur=0.9, color=None):
    color = color or "url(#accent-grad)"
    return (f'<line data-anim="draw" {_t(cue,delay,dur)} x1="{x}" y1="{y}" x2="{x+w}" y2="{y}" '
            f'stroke="{color}" stroke-width="8"/>')

def kicker(s, x, y, cue=None, delay=0.2, color=None, anim="fade-up"):
    color = color or ACCENT
    return text(s, x, y, lvl=4, cue=cue, delay=delay, anim=anim, fill=color, opacity=1, weight=700, ls=10)

def title(main, x=M, y=470, lvl=1, kick=None, cue=None, delay=0.3, serif=True, under=True):
    out = []
    if kick:
        sz = T[lvl][0]
        out.append(kicker(kick, x+4, y - int(sz*0.80) - 30, delay=max(delay-0.1,0)))
    out.append(type_in(main, x, y, lvl=lvl, cue=cue, delay=delay, serif=serif))
    if under:
        out.append(rule(x+4, y + int(T[lvl][0]*0.20), 1100, delay=delay+0.3))
    return "".join(out)

def chip(s, x, y, lvl=3, cue=None, delay=0.4, color=None, fill=None, opacity=1):
    color = color or ACCENT
    return (f'<g transform="translate({x},{y})">'
            f'<rect data-anim="fade" {_t(cue,delay,0.4)} x="0" y="-46" width="11" height="64" rx="5" fill="{color}"/>'
            f'{text(s, 30, 0, lvl=lvl, cue=cue, delay=delay+0.02, anim="fade-left", fill=fill, opacity=opacity)}</g>')

def clear(x, y, w, h, delay, dur=0.5):
    """invisible block that simply fades OUT a region marker; use a covering rect over content to clear.
    In practice we 'clear' by giving the to-be-removed elements data-anim='fade-out' directly."""
    return ""

def sweep(x, y, w, h, cue=None, delay=0.5, dur=0.7, color=None):
    color = color or ACCENT
    return (f'<rect data-anim="highlight-sweep" data-mode="stay" {_t(cue,delay,dur)} x="{x}" y="{y}" '
            f'width="{w}" height="{h}" rx="10" fill="{color}"/>')

def strike(x, y, w, cue=None, delay=0.6, dur=0.5, color=None):
    color = color or RED
    return (f'<line data-anim="draw" {_t(cue,delay,dur)} x1="{x}" y1="{y}" x2="{x+w}" y2="{y}" '
            f'stroke="{color}" stroke-width="9"/>')

# ---- image (big, with gentle ken-burns push) ------------------------------
def image(name, x, y, w=None, h=None, anim="wipe", cue=None, delay=0.4, dur=1.0, dir="left"):
    iw, ih = img_dims(name); ar = iw/ih
    if h and not w: w = int(h*ar)
    elif w and not h: h = int(w/ar)
    if anim == "wipe":
        return (f'<g transform="translate({x},{y})"><image data-anim="wipe" data-dir="{dir}" {_t(cue,delay,dur)} '
                f'href="{FU(name)}" xlink:href="{FU(name)}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid meet"/></g>')
    return (f'<g transform="translate({x},{y})"><g data-anim="{anim}" {_t(cue,delay,dur)}>'
            f'<image href="{FU(name)}" xlink:href="{FU(name)}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid meet"/></g></g>')

def push_image(name, x, y, w=None, h=None, cue=None, delay=0.0, dur=8.0, zoom=1.10, dx=-80, dy=-40, origin=None):
    """big screenshot with a slow ken-burns push over the scene."""
    iw, ih = img_dims(name); ar = iw/ih
    if h and not w: w = int(h*ar)
    elif w and not h: h = int(w/ar)
    ox = origin[0] if origin else x + w//2; oy = origin[1] if origin else y + h//2
    return (f'<g transform="translate({x},{y})"><g data-anim="push" {_t(cue,delay,dur)} '
            f'data-sc0="1" data-sc1="{zoom}" data-tx1="{dx}" data-ty1="{dy}" data-origin="{ox-x}px {oy-y}px">'
            f'<image href="{FU(name)}" xlink:href="{FU(name)}" width="{w}" height="{h}" '
            f'preserveAspectRatio="xMidYMid meet" image-rendering="optimizeQuality"/></g></g>')

def hero_feather(name, x, y, w, h, cue=None, delay=0.4, dur=1.2, scrim=0.30,
                 sat=0.92, drift=15.0, push=1.06, idp=None):
    """A 'premium' hero image that melts INTO the frosted-glass background instead
    of sitting in a hard rectangle (which would read as a forbidden card):
      * a radial alpha-feather softens all four edges into the glass,
      * a celadon scrim (heavier on the left / text side) harmonises vivid art
        with the celadon palette,
      * a gentle desaturate calms loud colours,
      * a slow ken-burns push gives it life over the scene; it fades in on `cue`.
    The image is cover-fit (slice) into the w×h region, so any aspect ratio fills
    cleanly and the feather hides the crop. Stays inside the glass if x,y,w,h do."""
    idp = idp or "hero%d" % (abs(hash((name, x, y, w, h))) % 100000)
    cxp, oy = w / 2.0, h * 0.45
    defs = (
        f'<defs>'
        f'<radialGradient id="{idp}f" cx="50%" cy="46%" r="63%">'
        f'<stop offset="0" stop-color="#fff" stop-opacity="1"/>'
        f'<stop offset="0.52" stop-color="#fff" stop-opacity="1"/>'
        f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="{idp}m"><rect x="0" y="0" width="{w}" height="{h}" fill="url(#{idp}f)"/></mask>'
        f'<linearGradient id="{idp}s" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="#EAF3EE" stop-opacity="{min(scrim+0.24,1):.2f}"/>'
        f'<stop offset="0.40" stop-color="#EAF3EE" stop-opacity="{scrim:.2f}"/>'
        f'<stop offset="1" stop-color="#EAF3EE" stop-opacity="0"/></linearGradient>'
        f'<filter id="{idp}d" x="0" y="0" width="100%" height="100%">'
        f'<feColorMatrix type="saturate" values="{sat}"/></filter>'
        f'</defs>'
    )
    inner = (
        f'<g mask="url(#{idp}m)">'
        f'<image href="{FU(name)}" xlink:href="{FU(name)}" x="0" y="0" width="{w}" height="{h}" '
        f'preserveAspectRatio="xMidYMid slice" filter="url(#{idp}d)" image-rendering="optimizeQuality"/>'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="url(#{idp}s)"/></g>'
    )
    pushg = (f'<g data-anim="push" data-delay="0" data-dur="{drift}" data-sc0="1" data-sc1="{push}" '
             f'data-tx1="-24" data-ty1="-14" data-origin="{cxp:.0f}px {oy:.0f}px">{inner}</g>')
    return (f'<g transform="translate({x},{y})">{defs}'
            f'<g data-anim="fade" {_t(cue,delay,dur)}>{pushg}</g></g>')


def hl_box(x, y, w, h, cue=None, delay=0.6, dur=0.6, color=None, sw=7):
    color = color or ACCENT
    return (f'<rect data-anim="draw" {_t(cue,delay,dur)} x="{x}" y="{y}" width="{w}" height="{h}" rx="14" '
            f'fill="none" stroke="{color}" stroke-width="{sw}"/>')

def arrow(x1, y1, x2, y2, cue=None, delay=0.7, dur=0.5, color=None):
    color = color or ACCENT
    return (f'<line data-anim="draw" {_t(cue,delay,dur)} x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="7" marker-end="url(#arrow)"/>')

def callout(label_lines, x, y, cue=None, delay=0.7, lvl=2, fill=None, anchor="start"):
    """big overlay number/label beside a highlight box (so viewer reads it, not the tiny screenshot)."""
    out=[]
    for i, ln in enumerate(label_lines):
        L = lvl if i==0 else 4
        out.append(pop(ln, x, y+i*88, lvl=L, cue=cue,   # all lines ride the same cued word
                       delay=delay+i*0.12, fill=fill, anchor=anchor))
    return "".join(out)

# ---- devices --------------------------------------------------------------
def bar_race(rows, x=M, y=720, track=2400, row_h=200, base_cue=None, delay=1.0, maxv=None,
             label_lvl=3, unit=""):
    """rows: [(label, value, color, cue, val_suffix)]. shared scale; grow-bar + count."""
    maxv = maxv or max(r[1] for r in rows)
    out=[]
    for i, r in enumerate(rows):
        label, val, color, cue, vs = (list(r)+[None,""])[:5]
        color = color or ACCENT
        ry = y + i*row_h
        d = delay + i*0.5
        bw = int(track * (val/maxv))
        out.append(text(label, x, ry-20, lvl=label_lvl, cue=cue, delay=d, anim="fade-left"))
        # ghost track
        out.append(f'<rect x="{x}" y="{ry+20}" width="{track}" height="70" rx="14" fill="{INK}" fill-opacity="0.08"/>')
        # grown bar
        out.append(f'<g transform="translate({x},{ry+20})"><rect data-anim="grow-bar" data-grow="x" {_t(cue,d+0.05,0.9)} '
                   f'x="0" y="0" width="{bw}" height="70" rx="14" fill="{color}"/></g>')
        out.append(num(val, x+bw+40, ry+78, lvl=label_lvl, cue=cue, delay=d+0.1, dur=0.9,
                       suffix=vs or unit, fill=color, dec=(1 if isinstance(val,float) else 0)))
    return "".join(out)

def compare_table(headers, rows, x=M, y=620, colw=None, row_h=170, delay=0.6, hi_col=None,
                  size_lvl=3, hi_color=None):
    """headers list; rows list of lists (strings). cue per row via rows meta not here -> caller cues."""
    hi_color = hi_color or ACCENT
    colw = colw or [620]+[ (3360-620)//(len(headers)-1) ]*(len(headers)-1)
    out=[f'<g transform="translate({x},{y})">']
    cx=0
    for j,h in enumerate(headers):
        col = hi_color if (hi_col is not None and j==hi_col) else ACCENT
        out.append(text(h, cx, 0, lvl=4, delay=delay+j*0.08, anim="fade", fill=col, opacity=1, weight=700))
        cx+=colw[j]
    out.append(rule(0, 34, sum(colw), delay=delay+0.15))
    for i,row in enumerate(rows):
        ry=40+(i+1)*row_h; rd=delay+0.3+i*0.22
        cx=0
        for j,cell in enumerate(row):
            is_hi=(hi_col is not None and j==hi_col)
            fill = hi_color if is_hi else INK
            w = 700 if is_hi else None
            out.append(text(cell, cx, ry, lvl=size_lvl, delay=rd, anim="fade-up", fill=fill, weight=w))
            cx+=colw[j]
    # our column highlight stripe
    if hi_col is not None:
        cx=sum(colw[:hi_col])
        out.append(f'<rect data-anim="grow-bar" data-grow="y" data-delay="{delay+0.2:.2f}" data-dur="0.8" '
                   f'x="{cx-30}" y="-70" width="{colw[hi_col]-20}" height="{40+(len(rows)+1)*row_h}" rx="16" '
                   f'fill="{hi_color}" fill-opacity="0.08"/>')
    out.append("</g>")
    return "".join(out)

def ledger(title_s, items, total, x=M, y=560, w=2400, delay=0.6, total_label="总计", money="¥"):
    """逐行填充账本：每行 (label, amount, cue). 右对齐金额成列, 末尾分隔线+总计 pop."""
    out=[text(title_s, x, y, lvl=4, delay=delay, fill=ACCENT, opacity=1, weight=700)]
    out.append(rule(x, y+30, w, delay=delay+0.1))
    ry=y+30
    for i,(label, amt, cue) in enumerate(items):
        ry += 150; d=delay+0.3+i*0.0  # cue drives timing
        out.append(text(label, x, ry, lvl=3, cue=cue, delay=delay+0.4+i*0.3, anim="fade-left"))
        out.append(num(amt, x+w, ry, lvl=3, cue=cue, delay=delay+0.5+i*0.3, dur=0.6,
                       prefix=money, anchor="end", fill=GOLD, comma=True))
    ry+=150
    out.append(rule(x, ry-60, w, delay=delay+0.4+len(items)*0.3, color=INK))
    out.append(text(total_label, x, ry, lvl=2, cue=None, delay=delay+0.6+len(items)*0.3))
    out.append(num(total, x+w, ry, lvl=1, delay=delay+0.7+len(items)*0.3, dur=1.0,
                   prefix=money, anchor="end", fill=GOLD, comma=True))
    return "".join(out)

def timeline_scrub(nodes, x=M, y=1080, w=3200, delay=0.8, head=True):
    """nodes: [(frac, top_label, bottom_label, cue, accent)]. main axis draws; play-head scrubs; nodes pop."""
    out=[f'<line x1="{x}" y1="{y}" x2="{x+w}" y2="{y}" stroke="{INK}" stroke-opacity="0.14" stroke-width="8"/>']
    out.append(f'<line data-anim="draw" {_t(None,delay,1.6)} x1="{x}" y1="{y}" x2="{x+w}" y2="{y}" stroke="url(#accent-grad)" stroke-width="8"/>')
    n = len(nodes)
    for i,nd in enumerate(nodes):
        frac, top, bot, cue, acc = (list(nd)+[None,True])[:5]
        px=x+int(w*frac); d=delay+0.5+i*0.5; col=ACCENT if acc else INK
        # End nodes anchor their captions inward (start/end) so a long label on the
        # first/last node can't spill past the timeline ends (= outside the glass).
        anc = "start" if i == 0 else ("end" if i == n-1 else "middle")
        out.append(f'<g transform="translate({px},{y})"><circle data-anim="pop" {_t(cue,d,0.5)} cx="0" cy="0" r="20" fill="{col}"/></g>')
        if top: out.append(text(top, px, y-58, lvl=3, cue=cue, delay=d+0.05, anim="fade-up", fill=col, anchor=anc, weight=700))
        if bot: out.append(text(bot, px, y+92, lvl=4, cue=cue, delay=d+0.12, anim="fade-up", anchor=anc, opacity=1))
    if head:
        out.append(f'<g transform="translate({x},{y})"><circle data-anim="play-head" data-span="{w}" {_t(None,delay,1.6)} cx="0" cy="0" r="14" fill="{GOLD}"/></g>')
    return "".join(out)

def _text_w(s, fs):
    """Rough rendered width of a mixed CJK / Latin label at font-size fs.
    Used to size boxes so text never spills outside its border."""
    w = 0.0
    for ch in s:
        o = ord(ch)
        if ch == ' ' or ch in '·.,:;\'!|·': w += 0.30 * fs
        elif ch in 'iIlrtf(){}[]': w += 0.34 * fs
        elif ch in 'mMW': w += 0.84 * fs
        elif o < 0x2E80: w += 0.56 * fs          # latin letters / digits / %
        else: w += 1.0 * fs                      # CJK & full-width glyphs
    return w

def flow_token(nodes, x=M, y=1100, gap=560, delay=0.8, token_label="¥"):
    """nodes: [(label, cue, accent)]. Each box auto-sizes to its label (so the
    text never spills), links draw between the actual box edges, a token rides
    the chain at the end."""
    fs = T[3][0]                                 # label font size (lvl 3)
    out=[]; pts=[]; halfs=[]; cues=[]
    for i,nd in enumerate(nodes):
        label, cue, acc = (list(nd)+[None,False])[:3]
        nx=x+i*gap; pts.append(nx); cues.append(cue); col=ACCENT if acc else INK; d=delay+i*0.5
        bw = max(400, int(_text_w(label, fs)) + 96)    # >=48px breathing room each side
        hw = bw//2; halfs.append(hw)
        out.append(f'<g transform="translate({nx},{y})">'
                   f'<rect data-anim="pop" {_t(cue,d,0.6)} x="{-hw}" y="-72" width="{bw}" height="144" rx="22" fill="none" stroke="{col}" stroke-width="5"/>'
                   f'{text(label, 0, 16, lvl=3, cue=cue, delay=d+0.08, anim="fade", fill=col, anchor="middle", weight=700)}</g>')
    for i in range(len(nodes)-1):
        a = pts[i]+halfs[i]+18; b = pts[i+1]-halfs[i+1]-18
        if b > a:
            out.append(arrow(a, y, b, y, cue=cues[i], delay=delay+i*0.5+0.45, dur=0.35))
    # token rides an invisible straight path across the chain
    x0, x1 = pts[0], pts[-1]
    out.append(f'<path id="ftpath" d="M{x0},{y-160} L{x1},{y-160}" fill="none" stroke="{INK}" stroke-opacity="0.0"/>')
    last_cue = cues[-1]
    out.append(f'<g transform="translate({x0},{y-160})"><g data-anim="move-along" data-path="#ftpath" data-x0="{x0}" data-y0="{y-160}" {_t(last_cue,0.5,2.0)}>'
               f'<circle cx="0" cy="0" r="46" fill="{GOLD}"/>'
               f'<text x="0" y="20" font-family="{SANS}" font-size="46" font-weight="700" fill="#fff" text-anchor="middle">{token_label}</text></g></g>')
    return "".join(out)

def checklist(title_s, items, x=M, y=560, delay=0.6, lvl=3):
    out=[text(title_s, x, y, lvl=4, delay=delay, fill=ACCENT, opacity=1, weight=700)]
    for i,(s, cue) in enumerate(items):
        ry=y+120+i*150; d=delay+0.3+i*0.0
        # check mark (two-seg polyline) draws on cue
        out.append(f'<polyline data-anim="draw" {_t(cue, d+0.3 if not cue else 0.3, 0.4)} points="{x},{ry-18} {x+26},{ry+8} {x+74},{ry-44}" fill="none" stroke="{ACCENT}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>')
        out.append(text(s, x+120, ry, lvl=lvl, cue=cue, delay=0.3, anim="fade-left"))
    return "".join(out)

def balance(left_label, left_items, right_label, right_items, tilt_to=8, x=CX, y=1240,
            beam=2400, delay=0.8, left_color=None, right_color=None):
    """A scale whose beam tilts toward the heavier side. Each side's text hangs in
    a pan suspended (straight down) from the *tilted* beam end, so the labels
    always track the beam instead of floating at fixed coordinates."""
    left_color = left_color or RED; right_color = right_color or ACCENT
    th = math.radians(tilt_to); half = beam/2.0; pivot_y = y-30
    # tilt_to > 0 => beam rotates clockwise => right end drops, left end rises
    lex, ley = x-half*math.cos(th), pivot_y-half*math.sin(th)
    rex, rey = x+half*math.cos(th), pivot_y+half*math.sin(th)
    HANG, PW = 120, 150
    out=[]
    # fulcrum
    out.append(f'<path data-anim="fade" {_t(None,delay,0.5)} d="M{x-70},{y+90} L{x+70},{y+90} L{x},{pivot_y} Z" fill="{ACCENT}"/>')
    # beam (tilts toward the heavier side)
    out.append(f'<g transform="translate({x},{pivot_y})"><g data-anim="tilt" data-to="{tilt_to}" {_t(None,delay+0.2,1.0)}>'
               f'<line x1="{-half:.0f}" y1="0" x2="{half:.0f}" y2="0" stroke="{INK}" stroke-width="12" stroke-linecap="round"/></g></g>')
    # a pan hangs straight down from each (tilted) beam end
    def pan(ex, ey, color):
        return (f'<g data-anim="fade" {_t(None,delay+0.5,0.6)}>'
                f'<line x1="{ex:.0f}" y1="{ey:.0f}" x2="{ex:.0f}" y2="{ey+HANG:.0f}" stroke="{INK}" stroke-opacity="0.45" stroke-width="5"/>'
                f'<line x1="{ex-PW:.0f}" y1="{ey+HANG:.0f}" x2="{ex+PW:.0f}" y2="{ey+HANG:.0f}" stroke="{color}" stroke-width="10" stroke-linecap="round"/></g>')
    out.append(pan(lex, ley, left_color)); out.append(pan(rex, rey, right_color))
    # text sits on / below each pan plate, centred on the end
    lpy, rpy = ley+HANG, rey+HANG
    out.append(text(left_label, lex, lpy+96, lvl=2, cue=None, delay=delay+0.7, anchor="middle", fill=left_color, weight=700))
    for i,(s,cue) in enumerate(left_items):
        out.append(text(s, lex, lpy+96+86+i*78, lvl=3, cue=cue, delay=delay+0.9+i*0.2, anchor="middle", anim="fade-up"))
    out.append(text(right_label, rex, rpy+96, lvl=2, cue=None, delay=delay+1.0, anchor="middle", fill=right_color, weight=700))
    for i,(s,cue) in enumerate(right_items):
        out.append(text(s, rex, rpy+96+86+i*78, lvl=3, cue=cue, delay=delay+1.2+i*0.2, anchor="middle", anim="fade-up"))
    return "".join(out)

def stamp(s, x=CX, y=CY, lvl=1, cue=None, delay=0.5, fill=None):
    fill = fill or ACCENT
    return (f'<g transform="translate({x},{y})"><text data-anim="stamp" {_t(cue,delay,0.8)} x="0" y="0" '
            f'font-family="{SERIF}" font-size="{T[lvl][0]}" font-weight="700" fill="{fill}" '
            f'text-anchor="middle" letter-spacing="6">{esc(s)}</text></g>')

def end_card(main, sub, cue=None, delay=0.4):
    return (f'<g transform="translate({CX},{CY-40})">'
            f'<text data-anim="type" {_t(cue,delay,1.3)} x="0" y="0" text-anchor="middle" font-family="{SERIF}" '
            f'font-size="{T[0][0]}" font-weight="700" fill="{INK}" letter-spacing="10">{esc(main)}</text>'
            f'<line data-anim="draw" data-delay="{delay+0.5:.2f}" data-dur="1.0" x1="-340" y1="130" x2="340" y2="130" stroke="url(#accent-grad)" stroke-width="10"/>'
            f'<text data-anim="fade-up" data-delay="{delay+0.9:.2f}" data-dur="1.0" x="0" y="250" text-anchor="middle" '
            f'font-family="{SANS}" font-size="{T[3][0]}" fill="{INK}" letter-spacing="6">{esc(sub)}</text></g>')


# ============================================================================
#  ADVANCED FX (AE 级硬核动效) · 全部是 t 的纯函数，零 rAF/随机/Date.now —— 渲染
#  时 render.py 每帧 seekTime(t) 抓图，掉帧不可能发生。运行时实现见
#  templates/scene_base.html 的 holo-3d / morph / flow-blob / burst 四个 case。
#  这套是 OPT-IN 的"科技/全息"风格，允许半透明边框+辉光（区别于默认回形针极简契约）。
#  详见 docs/ADVANCED_FX.md。
# ============================================================================
import random as _rng_mod


def holo(inner_svg, cue=None, delay=0.3, dur=1.1, rx=18, ry=-14, settle=True):
    """① 3D 全息数据看板：把任意 SVG 片段当成一块平面，带空间纵深感翻转滑入镜头。
    settle=True 落定为正面可读；settle=False 停在轻微倾角(更"全息"但牺牲可读性)。
    inner_svg 用绝对 viewBox 坐标书写；绕其外接盒中心做 3D 旋转。"""
    rx1, ry1 = (0, 0) if settle else (round(rx * 0.4, 1), round(ry * 0.4, 1))
    return (f'<g data-anim="holo-3d" {_t(cue,delay,dur)} '
            f'data-rx0="{rx}" data-ry0="{ry}" data-rx1="{rx1}" data-ry1="{ry1}">{inner_svg}</g>')


def holo_panel(title, items, x=M, y=560, w=2400, cue=None, delay=0.4,
               rx=16, ry=-12, settle=True, accent=None):
    """① 现成的全息看板：半透明青瓷框 + 发光数据条，整块带纵深翻入。
    items: [(label, value, frac, suffix)]。frac∈[0,1] 决定条长。"""
    accent = accent or ACCENT
    rows = len(items); h = 250 + rows * 150; track = w - 760
    parts = [
        f'<rect x="{x}" y="{y-130}" width="{w}" height="{h}" rx="30" '
        f'fill="{accent}" fill-opacity="0.05" stroke="{accent}" stroke-opacity="0.34" stroke-width="3"/>',
        text(title, x + 56, y - 34, lvl=3, delay=delay + 0.1, anim="fade", fill=accent, opacity=1, weight=700),
        rule(x + 56, y + 12, w - 112, delay=delay + 0.2),
    ]
    for i, (label, val, frac, suf) in enumerate(items):
        ry_ = y + 140 + i * 150; d = delay + 0.3 + i * 0.12; bw = int(track * max(0.0, min(1.0, frac)))
        parts.append(text(label, x + 56, ry_, lvl=3, delay=d, anim="fade-left"))
        parts.append(f'<rect x="{x+520}" y="{ry_-56}" width="{track}" height="66" rx="14" fill="{INK}" fill-opacity="0.08"/>')
        parts.append(f'<g transform="translate({x+520},{ry_-56})"><rect data-anim="grow-bar" data-grow="x" '
                     f'data-delay="{d+0.1:.2f}" data-dur="0.9" x="0" y="0" width="{bw}" height="66" rx="14" fill="{accent}"/></g>')
        parts.append(num(val, x + 520 + track + 34, ry_, lvl=3, delay=d + 0.2, dur=0.9, suffix=suf,
                         fill=accent, anchor="start", dec=(1 if isinstance(val, float) else 0)))
    return holo("".join(parts), cue=cue, delay=delay, dur=1.1, rx=rx, ry=ry, settle=settle)


def morph_path(from_d, to_d, x=CX, y=CY, cue=None, delay=0.4, dur=1.2,
               stroke=None, sw=10, fill="none", close=False, samples=120):
    """② 矢量路径顺滑形变：from_d 流体般扭曲重组成 to_d（节点数可不同，运行时按
    弧长重采样插值，无需 GSAP MorphSVG）。两段 d 写在同一 translate(x,y) 局部坐标里。
    ⚠️ 形变的路径要用**单段子路径**（一个 M，其余 L/A/C…）；多子路径(多个 M)重采样后会
    被连成一条线、出现跨接直线——多部件图形请把"会动的那部分"单独 morph、其余静态画
    （参考 lock_unlock：锁体静止、只 morph 锁梁）。"""
    stroke = stroke or ACCENT
    tid = "morphT%d" % (abs(hash((from_d, to_d, x, y))) % 100000)
    closeattr = ' data-close="1"' if close else ''
    return (f'<g transform="translate({x},{y})">'
            f'<path id="{tid}" d="{to_d}" style="opacity:0" fill="{fill}" stroke="none"/>'
            f'<path data-anim="morph" data-to="#{tid}" data-samples="{samples}"{closeattr} '
            f'{_t(cue,delay,dur)} d="{from_d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/></g>')


def gooey_flow(pts, cue=None, delay=0.5, n=5, r=46, color=None, speed=0.22,
               pipe=True, pipe_op=0.12):
    """③ 资金流向·流体融合：n 个金球在管道(pts 折线)里流动，靠近彼此时像水银互相
    吸引拉伸融合(goo 滤镜)。pts: [(x,y), ...] 描述管线；强化"资金流转/闭环"观感。"""
    color = color or GOLD
    pid = "goo%d" % (abs(hash(tuple(map(tuple, pts)))) % 100000)
    d = "M" + " L".join(f"{px},{py}" for px, py in pts)
    out = []
    if pipe:
        out.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-opacity="{pipe_op}" '
                   f'stroke-width="{int(r*1.7)}" stroke-linecap="round" stroke-linejoin="round"/>')
    out.append(f'<path id="{pid}" d="{d}" fill="none" stroke="none"/>')
    out.append('<g filter="url(#goo)">')
    x0, y0 = pts[0]
    for i in range(n):
        out.append(f'<circle data-anim="flow-blob" data-path="#{pid}" data-phase="{i/float(n):.3f}" '
                   f'data-speed="{speed}" data-x0="{x0}" data-y0="{y0}" {_t(cue,delay,0.5)} '
                   f'cx="{x0}" cy="{y0}" r="{r}" fill="{color}"/>')
    out.append('</g>')
    return "".join(out)


def particle_burst(x, y, cue=None, delay=0.0, n=110, colors=None, rmin=6, rmax=20,
                   vmin=900, vmax=2300, life=1.25, g=1500, up_bias=0.35, seed=None):
    """④ 多巴胺终结·粒子炸裂：以(x,y)为中心爆发上百颗带重力抛物线的金色微粒。
    所有随机量在 Python 端用固定种子生成 => 运行时零随机 => 逐帧抓图完全确定。"""
    colors = colors or [GOLD, "#E8C46A", ACCENT, "#FFFFFF"]
    rng = _rng_mod.Random(seed if seed is not None else (abs(hash((x, y, n))) & 0xffffffff))
    out = [f'<g transform="translate({x},{y})">']
    for _ in range(n):
        ang = rng.uniform(0, 2 * math.pi); spd = rng.uniform(vmin, vmax)
        vx = math.cos(ang) * spd; vy = math.sin(ang) * spd - up_bias * spd
        r = rng.uniform(rmin, rmax); col = rng.choice(colors)
        lf = life * rng.uniform(0.7, 1.1); spin = rng.uniform(-220, 220)
        out.append(f'<circle data-anim="burst" {_t(cue, delay + rng.uniform(0,0.04), lf)} '
                   f'data-vx="{vx:.0f}" data-vy="{vy:.0f}" data-g="{g}" data-life="{lf:.2f}" '
                   f'data-spin="{spin:.0f}" cx="0" cy="0" r="{r:.1f}" fill="{col}"/>')
    out.append('</g>')
    return "".join(out)


def num_burst(value, x, y, lvl=0, cue=None, delay=0.1, dur=1.0, prefix="", suffix="",
              dec=0, comma=False, fill=None, anchor="middle", n=120, burst_color=None):
    """④ 组合糖：核心数字滚动到位的刹那，在数字坐标爆出粒子。把 num + particle_burst
    挂同一个 cue，粒子在数字 count 结束(delay+dur)瞬间引爆。"""
    fill = fill or GOLD
    number = num(value, x, y, lvl=lvl, cue=cue, delay=delay, dur=dur, prefix=prefix,
                 suffix=suffix, dec=dec, comma=comma, fill=fill, anchor=anchor)
    burst = particle_burst(x, y - int(T[lvl][0] * 0.30), cue=cue, delay=delay + dur * 0.92,
                           n=n, colors=([burst_color] if burst_color else None))
    return number + burst


# ---- advanced devices (币种/折扣/卡片/锁/粒子/氛围) ---------------------------
def convert(a_val, a_unit, b_val, b_unit, x=M, y=1000, cue=None, delay=0.3,
            factor="÷0.04207", lvl=1, a_fill=None, b_fill=None, comma=True):
    """币种/单位换算条：左值 —[factor]→ 右值，两个数字滚动 + 中间换算箭头。"""
    a_fill = a_fill or INK; b_fill = b_fill or GOLD
    aw = 760; gap = 560
    return (
        num(a_val, x, y, lvl=lvl, cue=cue, delay=delay, dur=0.8, prefix="¥",
            dec=(2 if isinstance(a_val, float) else 0), comma=comma, fill=a_fill)
        + text(factor, x + aw, y - 70, lvl=4, cue=cue, delay=delay + 0.25, anim="fade", fill=ACCENT, opacity=1, weight=700, anchor="middle")
        + arrow(x + aw - 150, y - 26, x + aw + 150, y - 26, cue=cue, delay=delay + 0.35, dur=0.4)
        + text("≈", x + aw + 200, y, lvl=lvl, cue=cue, delay=delay + 0.45, anim="fade", fill=b_fill)
        + num(b_val, x + aw + gap, y, lvl=lvl, cue=cue, delay=delay + 0.5, dur=0.9, prefix="¥",
              suffix=" " + b_unit, dec=(2 if isinstance(b_val, float) else 0), comma=comma, fill=b_fill)
    )


def discount_seal(s, x=CX, y=CY, cue=None, delay=0.4, fill=None, lvl=1, rings=3):
    """折扣大印章：印章盖下的同时炸出几圈冲击波环（"74.8折""7.27折"砸出冲击力）。"""
    fill = fill or RED
    out = []
    for i in range(rings):
        out.append(f'<g transform="translate({x},{y})"><circle data-anim="shockwave" data-max="9" '
                   f'{_t(cue, delay + 0.18 + i*0.12, 0.9)} cx="0" cy="0" r="120" fill="none" '
                   f'stroke="{fill}" stroke-width="{10-i*2}" stroke-opacity="0.7"/></g>')
    out.append(stamp(s, x, y, lvl=lvl, cue=cue, delay=delay, fill=fill))
    return "".join(out)


def pulse_badge(s, x=CX, y=CY, cue=None, delay=0.4, lvl=2, fill=None, glow=None):
    """脉冲高亮徽章：一圈呼吸辉光 + 文字，适合标"当前最优/最划算/亲测可行"。"""
    fill = fill or ACCENT; glow = glow or fill
    halfw = int(_text_w(s, T[lvl][0]) / 2) + 70
    return (f'<g transform="translate({x},{y})">'
            f'<rect data-anim="pulse" data-amp="0.05" data-spd="3.2" data-opmin="0.18" {_t(cue,delay,0.6)} '
            f'x="{-halfw}" y="-86" width="{halfw*2}" height="150" rx="74" fill="{glow}" fill-opacity="0.16"/>'
            f'<rect data-anim="fade" {_t(cue,delay+0.05,0.5)} x="{-halfw}" y="-86" width="{halfw*2}" height="150" rx="74" '
            f'fill="none" stroke="{fill}" stroke-width="4"/>'
            f'{text(s, 0, 18, lvl=lvl, cue=cue, delay=delay+0.1, anim="fade", fill=fill, anchor="middle", weight=700)}</g>')


def card_flip(inner_svg, x=CX, y=CY, cue=None, delay=0.4, dur=0.9, ry0=-105):
    """卡片翻转揭示：inner_svg 从立边翻到正面，以(x,y)为局部原点。"""
    return (f'<g transform="translate({x},{y})">'
            f'<g data-anim="flip" data-ry0="{ry0}" {_t(cue,delay,dur)}>{inner_svg}</g></g>')


def coin_fountain(x=CX, y=1500, cue=None, delay=0.0, n=70, token="¥"):
    """金色令牌喷泉：偏上抛、慢重力，复用确定性 burst 引擎。"""
    return particle_burst(x, y, cue=cue, delay=delay, n=n, colors=[GOLD, "#E8C46A", "#F2D98A"],
                          rmin=14, rmax=30, vmin=700, vmax=1700, life=1.6, g=1100, up_bias=0.62,
                          seed=int(x) * 131 + int(y) * 17 + len(token))   # stable, no str-hash


# Only the SHACKLE morphs (single open subpath M-L-A-L, same node budget); the
# body is a static rect. morph resamples one subpath cleanly — a multi-subpath
# outline would draw a stray join line, so keep the moving part single-subpath.
_SHACKLE_SHUT = "M-46,-6 L-46,-58 A46,46 0 0 1 46,-58 L46,-6"
_SHACKLE_OPEN = "M-46,-6 L-46,-58 A46,46 0 0 1 46,-58 L46,-92"
def lock_unlock(x=CX, y=CY, cue=None, delay=0.4, dur=1.0, color=None):
    """解锁图示：锁梁顺滑 morph 成开锁；锁体静止，只有锁梁右脚抬起。"""
    color = color or ACCENT
    body = (f'<rect data-anim="pop" {_t(cue,delay,0.5)} x="-70" y="-6" width="140" height="120" rx="20" '
            f'fill="none" stroke="{color}" stroke-width="12"/>')
    keyhole = f'<circle data-anim="fade" {_t(cue,delay+0.2,0.4)} cx="0" cy="48" r="13" fill="{color}"/>'
    shackle = morph_path(_SHACKLE_SHUT, _SHACKLE_OPEN, x=0, y=0, cue=cue, delay=delay + 0.25,
                         dur=dur, stroke=color, sw=12, samples=64)
    return f'<g transform="translate({x},{y})">{body}{keyhole}{shackle}</g>'


def ambient_motes(n=26, cue=None, delay=0.0, color=None, area=None, seed=7):
    """背景氛围浮尘：n 颗缓慢游走的光点，给场景加"高级氛围"而不抢戏（全 t 纯函数）。
    area=(x0,y0,x1,y1) 限定范围，默认右侧空域，避开左侧文字。"""
    color = color or ACCENT
    x0, y0, x1, y1 = area or (2200, 300, 3680, 1900)
    rng = _rng_mod.Random(seed)
    out = []
    for _ in range(n):
        cx = rng.uniform(x0, x1); cy = rng.uniform(y0, y1); r = rng.uniform(3, 11)
        ax = rng.uniform(18, 46); ay = rng.uniform(22, 60)
        fx = rng.uniform(0.18, 0.55); fy = rng.uniform(0.15, 0.5)
        px = rng.uniform(0, 6.28); py = rng.uniform(0, 6.28); op = rng.uniform(0.18, 0.5)
        out.append(f'<g transform="translate({cx:.0f},{cy:.0f})"><circle data-anim="drift" '
                   f'data-ax="{ax:.0f}" data-ay="{ay:.0f}" data-fx="{fx:.2f}" data-fy="{fy:.2f}" '
                   f'data-px="{px:.2f}" data-py="{py:.2f}" data-op="{op:.2f}" {_t(cue,delay,0.8)} '
                   f'cx="0" cy="0" r="{r:.1f}" fill="{color}"/></g>')
    return "".join(out)


def gauge(value, lo=0, hi=100, x=CX, y=1240, r=420, cue=None, delay=0.4, title="",
          unit="", zones=None, needle_color=None, dec=0):
    """风险/力度/收益 半圆仪表盘：彩色区段 + 指针从 lo 扫到 value。指针复用 `tilt` 原语
    （纯函数of t），绕表盘中心旋转。zones: [(frac_end, color), ...] 从左(lo)到右(hi)依次上色，
    如 [(0.5,ACCENT),(0.8,GOLD),(1.0,RED)]。本系列用于"代充封号风险/折扣力度/收益率"。"""
    needle_color = needle_color or INK
    frac = 0.0 if hi == lo else max(0.0, min(1.0, (value - lo) / float(hi - lo)))
    def pt(fr):
        a = math.radians(180 * (1 - fr))
        return (x + r * math.cos(a), y - r * math.sin(a))
    def _arc(fa, fb, stroke, sw, op, d, dur, cap="butt"):
        # sample the exact circle centered at the hub (no SVG arc-flag ambiguity).
        n = max(2, int(abs(fb - fa) * 48) + 2)
        pts = []
        for k in range(n + 1):
            ax, ay = pt(fa + (fb - fa) * k / n); pts.append(f"{ax:.1f},{ay:.1f}")
        return (f'<path data-anim="draw" {_t(cue,d,dur)} d="M{" L".join(pts)}" fill="none" '
                f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}" stroke-linejoin="round" stroke-opacity="{op}"/>')
    lx, ly = pt(0.0); rx, ry = pt(1.0)
    out = [_arc(0.0, 1.0, INK, 34, 0.14, delay, 1.0, cap="round")]   # light track
    if zones:
        fa = 0.0
        for i, (fb, col) in enumerate(zones):
            out.append(_arc(fa, min(fb, 1.0), col, 34, 0.9, delay + 0.1 + i * 0.12, 0.7))
            fa = fb
    out.append(text(f"{lo}{unit}", lx, ly + 72, lvl=4, delay=delay + 0.3, anchor="middle", opacity=1))
    out.append(text(f"{hi}{unit}", rx, ry + 72, lvl=4, delay=delay + 0.3, anchor="middle", opacity=1))
    out.append(num(value, x, y + 180, lvl=1, cue=cue, delay=delay + 0.5, dur=1.0, suffix=unit,
                   dec=dec, anchor="middle", fill=needle_color))
    if title:
        out.append(text(title, x, y + 280, lvl=3, delay=delay + 0.6, anchor="middle", opacity=1))
    Ln = int(r * 0.82)                                  # needle pivots at hub: a 0-opacity
    out.append(f'<g transform="translate({x},{y})">'   # counter-dot balances the bbox so
               f'<g data-anim="tilt" data-to="{frac*180:.1f}" {_t(cue,delay+0.4,1.1)}>'  # tilt's
               f'<line x1="0" y1="0" x2="{-Ln}" y2="0" stroke="{needle_color}" stroke-width="14" stroke-linecap="round"/>'  # center == hub
               f'<circle cx="{Ln}" cy="0" r="2" fill="{needle_color}" fill-opacity="0"/></g>'
               f'<circle cx="0" cy="0" r="24" fill="{needle_color}"/></g>')
    return "".join(out)


# ---- 图文页（page）：一张页上，元素按念到的词一个个进来、进来就停住 -------------------
# 颜色、字体、间距和字幕样式只在 config.PAGE_THEMES 一处定义；这里每次调用时读当前主题，
# 换主题（config.PAGE_THEME 或 use_theme）不改组件。颜色参数可写主题角色名
# （page/ink/accent/muted/faint/rule/block/pen）或 #RRGGBB；字体参数可写 heavy/sans/mono/hand
# 或完整 font-family。文字参数可传字符串，或 [("普通", None), ("重点", "accent")] 分段上色。
# 时刻参数 timings 每项是 (cue, offset) 或数字 delay。用法见 docs/AUTHORING.md“图文页”。
_ROLES = ("page", "ink", "accent", "muted", "faint", "rule", "block", "pen", "shadow")
_FONTS = ("heavy", "sans", "mono", "hand")
# “正”字计数的五笔（100×100 方格，按书写顺序）
ZHENG_STROKES = (
    "M12 10 C40 7 66 8 90 9",
    "M51 10 C51 38 50 66 51 92",
    "M52 50 C62 49 72 49 82 50",
    "M24 42 C24 58 24 76 25 92",
    "M4 93 C36 91 66 91 97 92",
)


def theme(name=None):
    """当前（或指定）图文页主题 dict，来自 config.PAGE_THEMES。"""
    t = config.PAGE_THEME if name is None else name
    if isinstance(t, dict):
        return t
    try:
        return config.PAGE_THEMES[t]
    except KeyError:
        raise KeyError(f"unknown page theme {t!r}; known: {', '.join(config.PAGE_THEMES)}") from None


def use_theme(name_or_dict):
    """切换当前主题；传 dict 时登记为 "custom"（可先 dict(theme("white-green"), accent=...) 再改几项）。"""
    if isinstance(name_or_dict, dict):
        config.PAGE_THEMES["custom"] = name_or_dict
        config.PAGE_THEME = "custom"
    else:
        theme(name_or_dict)
        config.PAGE_THEME = name_or_dict
    return theme()


def _col(v, default):
    v = default if v is None else v
    return theme()[v] if v in _ROLES else v


def _font(v, default):
    v = default if v is None else v
    return theme()[v] if v in _FONTS else v


def _plain(s):
    return s if isinstance(s, str) else "".join(p if isinstance(p, str) else p[0] for p in s)


def _spans(s, fill):
    """字符串原样转义；分段 [(文字, 颜色角色)] 输出带 fill 的 <tspan>（逐字 type 也保留颜色）。"""
    if isinstance(s, str):
        return esc(s)
    out = []
    for part in s:
        txt, role = (part, None) if isinstance(part, str) else part
        out.append(f'<tspan fill="{_col(role, fill)}">{esc(txt)}</tspan>' if role else esc(txt))
    return "".join(out)


def _tm(tm, dur):
    """timings 的一项 → 时刻属性：(cue, offset) 或数字 delay。"""
    if isinstance(tm, tuple):
        cue, off = (tm + (None,))[:2]
        return _t(cue, 0.0, dur, off)
    return _t(None, float(tm), dur)


def step_fps(fps=12):
    """整场按 fps 定格推进（元素按字进来、停住的节奏）；放进片段任意位置一次即可。"""
    return f'<g data-step-fps="{fps:g}"/>'


def page_background(path, color=None, size=None):
    """把主题底色写成一张整画布 PNG，供 config.BG_VIDEO 使用（render 铺满画布且不动）。"""
    from PIL import Image
    w, h = size or (config.WIDTH, config.HEIGHT)
    c = _col(color, "page").lstrip("#")
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))).save(p)
    return str(p)


def _uid(prefix, *parts):
    import hashlib
    return prefix + hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()[:8]


def _shadow(idp, blur=26, dy=14, opacity=0.28, dx=0, color=None):
    color = _col(color, "shadow")
    return (f'<filter id="{idp}" x="-15%" y="-15%" width="130%" height="135%">'
            f'<feDropShadow dx="{dx}" dy="{dy}" stdDeviation="{blur}" flood-color="{color}" '
            f'flood-opacity="{opacity}"/></filter>')


# ---- 文字 --------------------------------------------------------------------------
def page_text(s, x, y, size, cue=None, delay=0.3, dur=0.33, anim="fade-up", fill=None,
              font=None, weight=900, anchor="start", ls=0, shift=None, offset=None, index=None):
    """页上的一行字（标题、正文、标签都用它）。默认粗体墨色；s 可分段上色。"""
    fill = _col(fill, "ink"); font = _font(font, "heavy")
    sh = f' data-shift="{shift}"' if shift is not None else ""
    return (f'<text data-anim="{anim}"{sh} {_t(cue,delay,dur,offset,index)} x="{x}" y="{y}" '
            f'font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}">{_spans(s, fill)}</text>')


def page_title(title, kicker=None, sub=None, x=None, y=None, size=180, cue=None, kicker_cue=None,
               sub_cue=None, delay=0.3, dur=0.33, offset=None):
    """页眉：等宽小标（灰）→ 大标题（黑色粗字，可分段上色）→ 副标题（灰）。各自可绑词。"""
    th = theme(); x = th["margin"] if x is None else x; y = th["top"] + size if y is None else y
    out = []
    if kicker:
        out.append(page_text(kicker, x + 4, y - size - 50, 44, cue=kicker_cue or cue, delay=delay, dur=dur,
                             fill="muted", font="mono", weight=700, ls=6, shift=20))
    out.append(page_text(title, x, y, size, cue=cue, delay=delay, dur=dur, shift=30, offset=offset))
    if sub:
        out.append(page_text(sub, x + 4, y + int(size * 0.55), 60, cue=sub_cue or cue, delay=delay, dur=dur,
                             fill="muted", font="sans", weight=400, shift=20))
    return "".join(out)


def tag(s, x, y, size=40, color=None, cue=None, delay=0.4, dur=1/12, filled=False, offset=None, index=None):
    """等宽小标签（胶囊框，如 CONFIRMED）；(x, y) 是框左上角。filled=True 时实底白字。"""
    color = _col(color, "accent"); mono = _font(None, "mono")
    w = _text_w(s, size) * 1.05 + size * 1.6 + len(s) * size * 0.08; h = size * 1.9
    bg = f'fill="{color}"' if filled else f'fill="none" stroke="{color}" stroke-width="{max(3, size // 12)}"'
    txt = _col("page", None) if filled else color
    return (f'<g transform="translate({x},{y})"><g data-anim="fade" {_t(cue,delay,dur,offset,index)}>'
            f'<rect x="0" y="0" width="{w:.0f}" height="{h:.0f}" rx="{h/2:.0f}" {bg}/>'
            f'<text x="{w/2:.0f}" y="{h/2 + size*0.36:.0f}" text-anchor="middle" font-family="{mono}" '
            f'font-size="{size}" font-weight="700" letter-spacing="{size*0.08:.1f}" fill="{txt}">{esc(s)}</text>'
            f'</g></g>')


def old_text(s, x, y, size, cue=None, delay=0.3, strike_cue=None, strike_delay=None, strike_offset=None,
             fill=None, font=None, weight=700, offset=None):
    """旧说法：灰字；给 strike_cue/strike_delay 时到点划上删除线，否则一出现就带删除线。"""
    fill = _col(fill, "muted"); w = _text_w(_plain(s), size)
    line_t = (_t(strike_cue, strike_delay or 0.0, 1/6, strike_offset) if (strike_cue or strike_delay is not None)
              else _t(cue, delay, 0.01, offset))
    return (page_text(s, x, y, size, cue=cue, delay=delay, fill=fill, font=font or "heavy", weight=weight,
                      anim="fade", dur=1/12, offset=offset)
            + f'<line data-anim="draw" {line_t} x1="{x - size*0.1:.0f}" y1="{y - size*0.32:.0f}" '
              f'x2="{x + w + size*0.1:.0f}" y2="{y - size*0.36:.0f}" stroke="{fill}" '
              f'stroke-width="{max(4, size // 14)}" stroke-linecap="round"/>')


def hand_line(s, x, y, size=88, cue=None, delay=0.4, dur=0.25, color=None, font=None,
              rotate=0, weight=400, offset=None, index=None):
    """一行从左往右写出（wipe），写完不动；主题 hand 字体（纸页红是楷体，白底绿是黑体）。"""
    color = _col(color, "ink"); font = _font(font, "hand")
    rot = f" rotate({rotate})" if rotate else ""
    return (f'<g transform="translate({x},{y}){rot}"><text data-anim="wipe" data-dir="left" '
            f'{_t(cue,delay,dur,offset,index)} x="0" y="0" font-family="{font}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}">{_spans(s, color)}</text></g>')


# ---- 编号、清单、数字、引语 -------------------------------------------------------------
def number_row(labels, x, y, gap=220, size=88, cue=None, delay=0.4, step=1/12,
               fill=None, font=None, offset=0.0, index=None):
    """一行空编号（01 02 03 …），每 step 秒出现一个。"""
    return "".join(page_text(s, x + i * gap, y, size, cue=cue, delay=delay + i * step, dur=step,
                             anim="fade", fill=fill or "faint", font=font or "mono", weight=400,
                             offset=(offset + i * step) if cue else None, index=index)
                   for i, s in enumerate(labels))


def mark_label(s, x, y, size=88, cue=None, delay=0.4, color=None, bar=None, font=None, offset=None, index=None):
    """点亮一个编号：同位置叠一层粗体并加一条下划线，一拍出现后不动。"""
    color = _col(color, "ink"); bar = _col(bar, "accent"); font = _font(font, "mono")
    w = int(_text_w(s, size) * 1.05)
    return (f'<g data-anim="fade" {_t(cue,delay,0.05,offset,index)}>'
            f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="900" fill="{color}">{esc(s)}</text>'
            f'<rect x="{x}" y="{y + int(size*0.22)}" width="{w}" height="{max(4, size//11)}" fill="{bar}"/></g>')


def nav_list(items, x=None, y=640, gap=130, size=60, active=None, cue=None, delay=0.4, step=1/12,
             active_cue=None, active_delay=None, active_offset=None, offset=0.0, numbered=True):
    """左侧目录：各项按 step 依次出现（浅灰），active 那项到 active_cue 时变黑、左侧出一条竖线。"""
    th = theme(); x = th["margin"] if x is None else x
    out = []
    for i, s in enumerate(items):
        yy = y + i * gap
        t_kw = dict(cue=cue, delay=delay + i * step, dur=step, offset=(offset + i * step) if cue else None)
        if numbered:
            out.append(page_text(f"{i + 1:02d}", x, yy, size * 0.7, anim="fade", fill="faint", font="mono",
                                 weight=700, **t_kw))
        out.append(page_text(s, x + (size * 1.6 if numbered else 0), yy, size, anim="fade", fill="faint",
                             font="sans", weight=500, **t_kw))
    if active is not None:
        yy = y + active * gap; at = _t(active_cue, active_delay if active_delay is not None else delay, 0.05,
                                       active_offset)
        num = (f'<text x="{x}" y="{yy}" font-family="{th["mono"]}" font-size="{size*0.7:.0f}" font-weight="700" '
               f'fill="{th["ink"]}">{active + 1:02d}</text>' if numbered else "")
        out.append(f'<g data-anim="fade" {at}>'
                   f'<rect x="{x - 50}" y="{yy - size*0.95:.0f}" width="{max(5, size//10)}" height="{size*1.25:.0f}" fill="{th["ink"]}"/>'
                   f'{num}<text x="{x + (size * 1.6 if numbered else 0):.0f}" y="{yy}" font-family="{th["sans"]}" '
                   f'font-size="{size}" font-weight="700" fill="{th["ink"]}">{_spans(items[active], th["ink"])}</text></g>')
    return "".join(out)


def bullets(items, x=None, y=900, size=60, gap=None, dash=True, fill=None):
    """短横线清单。items 每项 (文字或分段, timing)；timing 同 timings：(cue, offset) 或 delay。"""
    th = theme(); x = th["margin"] if x is None else x; gap = gap or int(size * 1.75)
    out = []
    for i, (s, tm) in enumerate(items):
        yy = y + i * gap
        body = (f'<text x="0" y="0" font-family="{th["sans"]}" font-size="{size}" fill="{th["muted"]}">–</text>'
                if dash else "")
        out.append(f'<g transform="translate({x},{yy})"><g data-anim="fade" {_tm(tm, 1/12)}>{body}'
                   f'<text x="{size*1.0 if dash else 0:.0f}" y="0" font-family="{th["sans"]}" font-size="{size}" '
                   f'font-weight="500" fill="{_col(fill, "ink")}">{_spans(s, _col(fill, "ink"))}</text></g></g>')
    return "".join(out)


def figure(value, x, y, size=220, label=None, unit=None, cue=None, delay=0.4, fill=None, offset=None):
    """一个大数字：上方等宽小标签，数字黑色粗体（可 fill="accent"），后面跟灰色单位。一拍出现。"""
    th = theme(); fill = _col(fill, "ink")
    lab = (f'<text x="{x}" y="{y - size*0.95:.0f}" font-family="{th["mono"]}" font-size="{max(36, size//5)}" '
           f'font-weight="700" letter-spacing="4" fill="{th["muted"]}">{esc(label)}</text>' if label else "")
    un = (f'<text x="{x + _text_w(str(value), size) + size*0.12:.0f}" y="{y}" font-family="{th["sans"]}" '
          f'font-size="{size*0.36:.0f}" font-weight="700" fill="{th["muted"]}">{esc(unit)}</text>' if unit else "")
    return (f'<g data-anim="fade" {_t(cue,delay,1/12,offset)}>{lab}'
            f'<text x="{x}" y="{y}" font-family="{th["heavy"]}" font-size="{size}" font-weight="900" '
            f'fill="{fill}">{esc(value)}</text>{un}</g>')


def quote_block(lines, x=None, y=900, size=76, source=None, cue=None, delay=0.4, step=1/12, offset=0.0):
    """引语：绿色引号 + 各行依次出现 + 等宽灰色出处。"""
    th = theme(); x = th["margin"] if x is None else x
    out = [page_text("“", x - size * 0.1, y + size * 0.15, size * 2.2, cue=cue, delay=delay, dur=step, anim="fade",
                     fill="accent", offset=offset if cue else None)]
    for i, ln in enumerate(lines):
        out.append(page_text(ln, x + size * 1.3, y + i * size * 1.5, size, cue=cue, delay=delay + (i + 1) * step,
                             dur=step, anim="fade", font="sans", weight=700,
                             offset=(offset + (i + 1) * step) if cue else None))
    if source:
        out.append(page_text(source, x + size * 1.3, y + len(lines) * size * 1.5 + size * 0.2, size * 0.55,
                             cue=cue, delay=delay + (len(lines) + 1) * step, dur=step, anim="fade", fill="muted",
                             font="mono", weight=700, offset=(offset + (len(lines) + 1) * step) if cue else None))
    return "".join(out)


def meter(n, x, y, timings=(), cell=40, gap=14, fill=None, empty=None, cue=None, delay=0.3, offset=None):
    """方块计量（■■■□）：n 个空格先在 cue 出现；timings 每项点亮一格，停住不动。"""
    fill = _col(fill, "ink"); empty = _col(empty, "rule")
    out = [f'<g data-anim="fade" {_t(cue,delay,1/12,offset)}>']
    out += [f'<rect x="{x + i*(cell+gap)}" y="{y - cell}" width="{cell}" height="{cell}" fill="{empty}"/>' for i in range(n)]
    out.append('</g>')
    for i, tm in enumerate(list(timings)[:n]):
        out.append(f'<rect data-anim="fade" {_tm(tm, 1/24)} x="{x + i*(cell+gap)}" y="{y - cell}" '
                   f'width="{cell}" height="{cell}" fill="{fill}"/>')
    return "".join(out)


# ---- 时间轴与条形时间表 -------------------------------------------------------------------
def time_axis(x, y, w, ticks=(), cue=None, delay=0.3, size=40, color=None, offset=None):
    """细线时间轴：一条墨线 + 刻度 + 等宽灰色刻度字，一拍出现。ticks 每项 (位置0—1, 文字)。"""
    th = theme(); color = _col(color, "ink"); lw = th["line_width"]
    out = [f'<g data-anim="fade" {_t(cue,delay,1/12,offset)}>'
           f'<line x1="{x}" y1="{y}" x2="{x + w}" y2="{y}" stroke="{color}" stroke-width="{lw}"/>']
    for frac, label in ticks:
        px = x + w * frac
        out.append(f'<line x1="{px:.0f}" y1="{y}" x2="{px:.0f}" y2="{y + size*0.4:.0f}" stroke="{color}" stroke-width="{lw}"/>')
        if label:
            out.append(f'<text x="{px:.0f}" y="{y + size*1.6:.0f}" text-anchor="middle" font-family="{th["mono"]}" '
                       f'font-size="{size}" fill="{th["muted"]}">{esc(label)}</text>')
    out.append('</g>')
    return "".join(out)


def time_block(x, w, axis_y, h, style="ink", label=None, sub=None, cue=None, delay=0.4, dur=1/6, offset=None,
               index=None, size=44):
    """坐在时间轴上的一段（x 起、宽 w、高 h），从轴向上长出后停住。
    style：ink 实黑 / accent 实绿 / block 浅灰 / hatch 斜线；label 粗体、sub 等宽灰字标在上方。"""
    th = theme(); top = axis_y - h; lw = th["line_width"]; defs = ""
    if style == "hatch":
        pid = _uid("hatch", x, w, axis_y, h)
        defs = (f'<defs><pattern id="{pid}" width="22" height="22" patternUnits="userSpaceOnUse" '
                f'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="22" stroke="{th["ink"]}" '
                f'stroke-width="{lw}"/></pattern></defs>')
        paint = f'fill="url(#{pid})" stroke="{th["ink"]}" stroke-width="{lw}"'
    elif style == "block":
        paint = f'fill="{th["block"]}" stroke="{th["faint"]}" stroke-width="{lw/2:g}"'
    else:
        paint = f'fill="{_col(style, "ink")}"'
    at = _t(cue, delay, dur, offset, index)
    out = [defs, f'<rect data-anim="wipe" data-dir="down" {at} x="{x}" y="{top}" width="{w}" height="{h}" {paint}/>']
    if label or sub:
        lab = (f'<text x="0" y="0" font-family="{th["sans"]}" font-size="{size}" font-weight="700" '
               f'fill="{th["ink"]}">{_spans(label, th["ink"])}</text>' if label else "")
        sx = _text_w(_plain(label), size) + size * 0.5 if label else 0
        sb = (f'<text x="{sx:.0f}" y="0" font-family="{th["mono"]}" font-size="{size*0.9:.0f}" '
              f'fill="{th["muted"]}">{esc(sub)}</text>' if sub else "")
        out.append(f'<g transform="translate({x},{top - size*0.6:.0f})"><g data-anim="fade" '
                   f'{_t(cue, delay + dur, 1/12, (offset or 0) + dur if cue else None, index)}>{lab}{sb}</g></g>')
    return "".join(out)


def progress(n, current, frac=1.0, x=None, w=None, y=None, h=4):
    """底部分段进度条：n 段浅灰细线，第 current 段（从 0 数）黑色、前 frac 部分绿色。静态，整场不动。"""
    th = theme(); x = th["margin"] if x is None else x
    w = (config.WIDTH - 2 * th["margin"]) if w is None else w
    y = th["progress"]["y"] if y is None else y; gap = th["progress"]["gap"]
    seg = (w - gap * (n - 1)) / n
    out = ['<g>']
    for i in range(n):
        sx = x + i * (seg + gap)
        color = th["ink"] if i == current else th["rule"]
        out.append(f'<rect x="{sx:.1f}" y="{y}" width="{seg:.1f}" height="{h}" fill="{color}"/>')
        if i == current and frac > 0:
            out.append(f'<rect x="{sx:.1f}" y="{y}" width="{seg*min(1.0, frac):.1f}" height="{h}" fill="{th["accent"]}"/>')
    out.append('</g>')
    return "".join(out)


# ---- 卡片、照片、抠图、气泡、圈 ------------------------------------------------------------
def card(x, y, w, h, inner="", cue=None, delay=0.4, dur=0.25, anim="fade-up", shift=30, offset=None, index=None):
    """白色圆角卡片（主题的填充、细边、圆角、软投影）；inner 是卡片内坐标的 SVG，随卡片一起进来。"""
    th = theme(); c = th["card"]; idp = _uid("crd", x, y, w, h)
    sb, sdy, sop = c["shadow"]
    line = f' stroke="{c["line"]}" stroke-width="{th["line_width"]/2:g}"' if c.get("line") else ""
    return (f'<defs>{_shadow(idp, blur=sb, dy=sdy, opacity=sop)}</defs>'
            f'<g transform="translate({x},{y})"><g data-anim="{anim}" data-shift="{shift}" {_t(cue,delay,dur,offset,index)}>'
            f'<rect x="0" y="0" width="{w}" height="{h}" rx="{c["radius"]}" fill="{c["fill"]}"{line} filter="url(#{idp})"/>'
            f'{inner}</g></g>')


def photo_card(name, cx, cy, w, h=None, rotate=None, cue=None, delay=0.4, dur=0.33, anim=None, shift=None,
               spin=2.5, tape=None, align="xMidYMid", offset=None, index=None):
    """写实照片卡：主题决定白边、圆角、细边、投影、倾斜和胶带；(cx, cy) 是卡片中心，w 是照片宽。
    h 给定时按 w×h 裁切（align 选保留哪边，如 "xMinYMid"）。默认动作：倾斜主题“落到纸上”(drop)，
    不倾斜主题短距上移淡入(fade-up)；进来就停住。"""
    th = theme(); c = th["card"]
    iw, ih = img_dims(name); h = w * ih / iw if h is None else h
    pad, radius = c["pad"], c["radius"]
    rotate = c["tilt"] if rotate is None else rotate
    tape = c["tape"] if tape is None else tape
    anim = anim or ("drop" if rotate else "fade-up")
    shift = (110 if anim == "drop" else 40) if shift is None else shift
    cw, ch = w + 2 * pad, h + 2 * pad
    idp = _uid("card", name, cx, cy, w, h)
    sb, sdy, sop = c["shadow"]
    clip = (f'<clipPath id="{idp}c"><rect x="{-w/2:.1f}" y="{-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{max(0, radius - pad)}"/></clipPath>')
    tw, tth = min(360, cw * 0.28), 92
    tape_svg = (f'<g transform="translate(0,{-ch/2:.1f}) rotate(4)">'
                f'<rect x="{-tw/2:.1f}" y="{-tth/2:.1f}" width="{tw:.1f}" height="{tth}" fill="#ECE0C4" fill-opacity="0.74"/>'
                f'<rect x="{-tw/2:.1f}" y="{-tth/2:.1f}" width="{tw:.1f}" height="14" fill="#FFFFFF" fill-opacity="0.22"/></g>'
                if tape else "")
    line = (f'<rect x="{-cw/2:.1f}" y="{-ch/2:.1f}" width="{cw:.1f}" height="{ch:.1f}" rx="{radius}" fill="none" '
            f'stroke="{c["line"]}" stroke-width="{th["line_width"]/2:g}"/>' if c.get("line") else
            f'<rect x="{-w/2:.1f}" y="{-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" fill="none" stroke="#000" '
            f'stroke-opacity="0.08" stroke-width="2"/>')
    extra = f' data-spin="{spin}"' if anim == "drop" else ""
    return (f'<defs>{_shadow(idp, blur=sb, dy=sdy, opacity=sop)}{clip}</defs>'
            f'<g transform="translate({cx},{cy}) rotate({rotate})">'
            f'<g data-anim="{anim}" data-shift="{shift}"{extra} {_t(cue,delay,dur,offset,index)}>'
            f'<rect x="{-cw/2:.1f}" y="{-ch/2:.1f}" width="{cw:.1f}" height="{ch:.1f}" rx="{radius}" fill="{c["fill"]}" filter="url(#{idp})"/>'
            f'<image href="{FU(name)}" xlink:href="{FU(name)}" x="{-w/2:.1f}" y="{-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'preserveAspectRatio="{align} slice" clip-path="url(#{idp}c)"/>'
            f'{line}{tape_svg}</g></g>')


def cutout(name, x, y, h, cue=None, delay=0.4, dur=0.33, shift=260, shadow=True, offset=None, index=None):
    """抠好的主体（透明底 PNG）压在卡片前面：从下方冒出来后停住。(x, y) 是图片左上角。"""
    iw, ih = img_dims(name); w = h * iw / ih
    idp = _uid("cut", name, x, y, h)
    filt = f' filter="url(#{idp})"' if shadow else ""
    defs = f'<defs>{_shadow(idp, blur=22, dy=16, opacity=0.22, dx=-10)}</defs>' if shadow else ""
    return (f'{defs}<g transform="translate({x},{y})"><g data-anim="fade-up" data-shift="{shift}" '
            f'{_t(cue,delay,dur,offset,index)}><image href="{FU(name)}" xlink:href="{FU(name)}" '
            f'width="{w:.1f}" height="{h:.1f}" preserveAspectRatio="xMidYMid meet"{filt}/></g></g>')


def image_point(name, x, y, h, fx, fy):
    """图片内相对位置 (fx, fy) 在画布上的坐标，例如抠图的嘴，用来对准气泡尾巴。"""
    iw, ih = img_dims(name); w = h * iw / ih
    return x + fx * w, y + fy * h


def bubble_bounds(s, tip_x, tip_y, size=80, side="left", tail=130, lift=70, pad=68):
    """speech_bubble 的外框 (x, y, w, h)，给圈、标签等后续零件定位。"""
    bw = len(s) * size * 0.6 + 2 * pad; bh = size + pad * 1.6
    bx = tip_x - tail - bw if side == "left" else tip_x + tail
    return bx, tip_y - lift - bh / 2, bw, bh


def speech_bubble(s, tip_x, tip_y, size=80, side="left", tail=130, lift=70, pad=68,
                  cue=None, delay=0.4, dur=1/6, type_cue=None, type_delay=None, type_dur=0.25,
                  offset=None, type_offset=None, font=None):
    """对话气泡：尾巴尖落在 (tip_x, tip_y)（对准说话者的嘴），框先弹出，再打字机打出文字。
    side="left" 时气泡在嘴的左边。填充、描边、圆角取主题；默认等宽字，宽度按等宽字估算。"""
    th = theme(); b = th["bubble"]; font = _font(font, "mono")
    bx, by, bw, bh = bubble_bounds(s, tip_x, tip_y, size, side, tail, lift, pad)
    r, ty = b["radius"], by + bh * 0.62
    top = f"M{bx+r:.1f},{by:.1f} L{bx+bw-r:.1f},{by:.1f} Q{bx+bw:.1f},{by:.1f} {bx+bw:.1f},{by+r:.1f} "
    bottom_left = (f"L{bx+r:.1f},{by+bh:.1f} Q{bx:.1f},{by+bh:.1f} {bx:.1f},{by+bh-r:.1f} ")
    corner_br = f"L{bx+bw:.1f},{by+bh-r:.1f} Q{bx+bw:.1f},{by+bh:.1f} {bx+bw-r:.1f},{by+bh:.1f} "
    close = f"L{bx:.1f},{by+r:.1f} Q{bx:.1f},{by:.1f} {bx+r:.1f},{by:.1f} Z"
    if side == "left":
        e = bx + bw
        d = (top + f"L{e:.1f},{ty-34:.1f} L{tip_x:.1f},{tip_y:.1f} L{e:.1f},{ty+8:.1f} "
             + corner_br + bottom_left + close)
    else:
        d = (top + corner_br + bottom_left
             + f"L{bx:.1f},{ty+8:.1f} L{tip_x:.1f},{tip_y:.1f} L{bx:.1f},{ty-34:.1f} " + close)
    idp = _uid("bub", s, tip_x, tip_y)
    if type_cue is None and type_delay is None:
        type_cue, type_delay, type_offset = cue, delay + dur, (offset or 0) + dur
    return (f'<defs>{_shadow(idp, blur=12, dy=8, opacity=0.14)}</defs>'
            f'<g data-anim="pop" {_t(cue,delay,dur,offset)}>'
            f'<path d="{d}" fill="{b["fill"]}" stroke="{b["line"]}" stroke-width="{b["line_width"]}" '
            f'stroke-linejoin="round" filter="url(#{idp})"/>'
            f'<text data-anim="type" {_t(type_cue,type_delay or 0.0,type_dur,type_offset)} x="{bx+pad:.1f}" '
            f'y="{by+bh/2+size*0.34:.1f}" font-family="{font}" font-size="{size}" font-weight="700" '
            f'fill="{th["ink"]}">{esc(s)}</text></g>')


def pen_strokes(paths, x, y, size=300, timings=(), dur=1/12, color=None, width=18, rotate=0):
    """一笔笔写（主题笔色）。paths 是 100×100 方格内的路径；timings 每笔一项；项数少于 paths 时只写前几笔。"""
    color = _col(color, "pen"); k = size / 100.0
    rot = f" rotate({rotate})" if rotate else ""
    out = [f'<g transform="translate({x},{y}){rot} scale({k:.4f})">']
    for d, tm in zip(paths, timings):
        out.append(f'<path data-anim="draw" {_tm(tm, dur)} d="{d}" fill="none" stroke="{color}" '
                   f'stroke-width="{width / k:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
    out.append('</g>')
    return "".join(out)


def tally(n, x, y, size=300, timings=(), **kw):
    """“正”字计数：写前 n 笔（n ≤ 5），每笔各自的时刻见 pen_strokes。"""
    return pen_strokes(ZHENG_STROKES[:n], x, y, size=size, timings=timings, **kw)


def pen_circle(cx, cy, rx, ry, cue=None, delay=0.4, dur=0.25, color=None, width=14,
               start=200, sweep=385, spiral=0.05, rotate=-3, square=2.0, offset=None, index=None):
    """手画圈（主题笔色）：一笔画的圈，收笔略越过起点，画完不动。
    square=2 是椭圆；圈长条文字（气泡、一行字）用 3—4，更贴近矩形、角上不切字。
    干净版式要规整的框时用 hl_box(..., color=theme()["accent"])。"""
    color = _col(color, "pen")
    a0, n, e = math.radians(start), 120, 2.0 / square
    pts = []
    for i in range(n + 1):
        a = a0 + math.radians(sweep) * i / n; g = 1 + spiral * i / n
        c, s = math.cos(a), math.sin(a)
        x = math.copysign(abs(c) ** e, c) * rx * g; y = math.copysign(abs(s) ** e, s) * ry * g
        pts.append(f"{x:.1f},{y:.1f}")
    return (f'<g transform="translate({cx:.1f},{cy:.1f}) rotate({rotate})">'
            f'<path data-anim="draw" {_t(cue,delay,dur,offset,index)} d="M{" L".join(pts)}" fill="none" '
            f'stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/></g>')


def hbar(label, value, frac, x, y, w=1600, h=56, cue=None, delay=0.4, dur=1/6, fill=None, size=44, offset=None):
    """横条对比：上方等宽小标签，条从左长出后停住，数值跟在条尾。frac 是 0—1 的长度。"""
    th = theme(); fill = _col(fill, "ink"); bw = max(h, w * max(0.0, min(1.0, frac)))
    at = _t(cue, delay, dur, offset)
    return (f'<text data-anim="fade" {_t(cue,delay,1/12,offset)} x="{x}" y="{y - h*0.5:.0f}" font-family="{th["mono"]}" '
            f'font-size="{size}" font-weight="700" letter-spacing="4" fill="{th["muted"]}">{esc(label)}</text>'
            f'<rect data-anim="wipe" data-dir="left" {at} x="{x}" y="{y}" width="{bw:.0f}" height="{h}" fill="{fill}"/>'
            f'<text data-anim="fade" {_t(cue, delay + dur, 1/12, (offset or 0) + dur if cue else None)} '
            f'x="{x + bw + size*0.6:.0f}" y="{y + h*0.5 + size*0.95:.0f}" font-family="{th["heavy"]}" '
            f'font-size="{size*2.4:.0f}" font-weight="900" fill="{fill}">{esc(value)}</text>')
