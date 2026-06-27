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

# real pixel sizes (EXIF-corrected)
DIMS = {
 "1249日元某宝截图.jpg":(1440,844), "Google大师决斗-1美刀优惠券.jpg":(1440,461),
 "steam手机确认和小号交易.jpg":(1440,3200), "五大适合出售的箱子.jpg":(1440,2195),
 "和小号交易请求.png":(1623,1922), "官方常住10000日元=4950.png":(797,1175),
 "小号同意交易礼物.png":(1647,1165), "小号的“交易 URL.png":(1854,1739),
 "无痕窗口.png":(602,244), "日语区官方价格.png":(3840,2023), "消费价格.jpg":(1440,2280),
 "热潮武器箱出售6.18.png":(1792,1194), "网易buff一键设置steam账号管理界面.jpg":(1440,3200),
 "网易buff热潮武器箱200库存4.07.jpg":(1440,3200), "美区价格 (2).jpg":(3200,1440),
 "美区价格.jpg":(1440,1754), "购买成功.jpg":(1440,3200),
}

# ---- timing helper: cue first, data-delay fallback ------------------------
def _t(cue, delay, dur=None):
    a = f'data-cue="{cue}" data-delay="{delay:.2f}"' if cue else f'data-delay="{delay:.2f}"'
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
    弧长重采样插值，无需 GSAP MorphSVG）。两段 d 写在同一 translate(x,y) 局部坐标里。"""
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


# ---- MD-genre advanced devices (币种/折扣/卡牌/锁/金币/氛围) -------------------
def convert(a_val, a_unit, b_val, b_unit, x=M, y=1000, cue=None, delay=0.3,
            factor="÷0.04207", lvl=1, a_fill=None, b_fill=None, comma=True):
    """币种换算条：左值(人民币¥) —[factor]→ 右值(日元¥)，两个数字滚动 + 中间换算箭头。
    专治本系列"币种铁律"——截图标人民币、旁白讲日元，观众要看得见换算。"""
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
    """游戏王卡牌翻转揭示：inner_svg 像一张卡从立边翻到正面（本系列主题契合）。
    inner_svg 用以(x,y)为原点的局部坐标书写。"""
    return (f'<g transform="translate({x},{y})">'
            f'<g data-anim="flip" data-ry0="{ry0}" {_t(cue,delay,dur)}>{inner_svg}</g></g>')


def coin_fountain(x=CX, y=1500, cue=None, delay=0.0, n=70, token="¥"):
    """金币喷泉：偏上抛、慢重力的金色"硬币"喷出（充值/到账/收益的金钱感）。
    复用确定性 burst 引擎，只是调参更"币"。"""
    return particle_burst(x, y, cue=cue, delay=delay, n=n, colors=[GOLD, "#E8C46A", "#F2D98A"],
                          rmin=14, rmax=30, vmin=700, vmax=1700, life=1.6, g=1100, up_bias=0.62,
                          seed=abs(hash((x, y, token))) & 0xffff)


# closed-padlock and open-padlock outlines (same node budget) for market unlock
_LOCK_SHUT = "M-70,-10 L70,-10 L70,120 L-70,120 Z M-46,-10 L-46,-58 A46,46 0 0 1 46,-58 L46,-10"
_LOCK_OPEN = "M-70,-10 L70,-10 L70,120 L-70,120 Z M-46,-10 L-46,-58 A46,46 0 0 1 46,-58 L46,-92"
def lock_unlock(x=CX, y=CY, cue=None, delay=0.4, dur=1.0, color=None):
    """令牌/市场解锁：闭锁的锁梁顺滑morph成开锁（15天解锁市场、绑令牌→可交易）。"""
    color = color or ACCENT
    return morph_path(_LOCK_SHUT, _LOCK_OPEN, x=x, y=y, cue=cue, delay=delay, dur=dur,
                      stroke=color, sw=12, samples=80)


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
