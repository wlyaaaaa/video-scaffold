# -*- coding: utf-8 -*-
"""
Reusable scene components.

Each function returns a static SVG fragment string (with data-anim / data-cue)
ready to drop inside the base board, so scenes look consistent and premium and
the AI can compose a scene from a few calls instead of hand-laying every node.
All components obey the design contract: celadon ink, accent lines, NO cards /
borders / shadows. Pass `cue="旁白里的词"` to fire on the narrated word, else a
`delay` (seconds) is used.

Convention: position with the OUTER <g transform> these return; animate via the
inner nodes' data-anim (no transform attribute on animated nodes).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

INK, ACCENT = config.INK, config.ACCENT
SERIF = "'Source Han Serif CN','Georgia',serif"
SANS = "-apple-system,sans-serif"


def _timing(cue, delay):
    """data-cue beats data-delay; returns the attribute snippet."""
    return f'data-cue="{cue}"' if cue else f'data-delay="{delay}"'


def title_block(main, kicker="", sub="", x=280, y=520, cue=None, delay=0.3, size=200):
    """Big 逐字 headline + optional kicker + subtitle + drawn underline."""
    parts = [f'<g transform="translate({x},{y})">']
    if kicker:
        parts.append(
            f'<text data-anim="fade-up" data-delay="{max(delay-0.2,0):.2f}" data-dur="0.9" '
            f'x="6" y="-70" font-family="{SANS}" font-size="56" fill="{ACCENT}" '
            f'letter-spacing="20" font-weight="700" opacity="0">{kicker}</text>')
    parts.append(
        f'<text data-anim="type" {_timing(cue, delay)} data-dur="1.4" '
        f'font-family="{SERIF}" font-size="{size}" font-weight="bold" '
        f'fill="{INK}" letter-spacing="6">{main}</text>')
    parts.append(
        f'<line data-anim="draw" data-delay="{delay+0.3:.2f}" data-dur="1.1" '
        f'x1="6" y1="{size*0.18:.0f}" x2="{x+1200}" y2="{size*0.18:.0f}" '
        f'stroke="url(#accent-grad)" stroke-width="10"/>')
    if sub:
        parts.append(
            f'<text data-anim="fade-up" data-delay="{delay+0.6:.2f}" data-dur="1.0" '
            f'x="8" y="{size*0.18+90:.0f}" font-family="{SANS}" font-size="58" '
            f'fill="{INK}" opacity="0" letter-spacing="6">{sub}</text>')
    parts.append("</g>")
    return "\n".join(parts)


def lower_third(title, sub="", x=240, y=1820, cue=None, delay=0.3):
    """Borderless name strip: accent tick + title sliding in + subtitle."""
    return f"""
<g transform="translate({x},{y})">
  <rect data-anim="fade" {_timing(cue, delay)} data-dur="0.5" x="0" y="-58" width="12" height="96" rx="6" fill="{ACCENT}" opacity="0"/>
  <text data-anim="fade-left" {_timing(cue, delay)} data-dur="0.7" x="40" y="0" font-family="{SANS}" font-size="64" font-weight="bold" fill="{INK}" opacity="0">{title}</text>
  <text data-anim="fade-left" data-delay="{delay+0.15:.2f}" data-dur="0.7" x="42" y="56" font-family="{SANS}" font-size="38" fill="{INK}" opacity="0">{sub}</text>
</g>"""


def stat_bar(label, value, frac, y=0, cue=None, delay=0.0, x=0, width=1500, decimals=1):
    """Labelled progress bar with a count-up value, all cued to one phrase."""
    full = width * max(0.0, min(1.0, frac))
    t = _timing(cue, delay)
    return f"""
<g transform="translate({x},{y})">
  <text data-anim="fade-up" {t} data-dur="0.6" x="0" y="0" font-family="{SANS}" font-size="56" fill="{INK}" opacity="0">{label}</text>
  <line x1="0" y1="40" x2="{width}" y2="40" stroke="{INK}" stroke-width="10" stroke-linecap="round" opacity="0.12"/>
  <line data-anim="draw" {t} data-dur="1.0" x1="0" y1="40" x2="{full:.0f}" y2="40" stroke="url(#accent-grad)" stroke-width="10" stroke-linecap="round"/>
  <text data-anim="count" {t} data-dur="1.0" data-to="{value}" data-decimals="{decimals}" x="{width}" y="0" font-family="{SANS}" font-size="56" font-weight="bold" fill="{ACCENT}" text-anchor="end" opacity="0">0.0</text>
</g>"""


def stat_panel(items, x=330, y=900, gap=220, width=1500):
    """items: list of (label, value, frac, cue). Stacks stat_bars."""
    rows = "".join(
        stat_bar(lbl, val, frac, y=i * gap, cue=cue, x=0, width=width)
        for i, (lbl, val, frac, cue) in enumerate(items))
    return f'<g transform="translate({x},{y})">{rows}</g>'


def quote(lines, x=300, y=900, cue=None, delay=0.3, size=64):
    """Pull-quote: big quotation glyph + accent tick + stacked lines."""
    body = "".join(
        f'<text data-anim="fade-up" data-delay="{delay + 0.25*i:.2f}" data-dur="0.8" '
        f'x="80" y="{i*size*1.5:.0f}" font-family="{SANS}" font-size="{size}" '
        f'font-weight="bold" fill="{INK}" opacity="0">{ln}</text>'
        for i, ln in enumerate(lines))
    return f"""
<g transform="translate({x},{y})">
  <text data-anim="fade" {_timing(cue, delay)} data-dur="0.6" x="-30" y="40" font-family="'Times New Roman',serif" font-size="320" fill="{ACCENT}" opacity="0">“</text>
  <line data-anim="draw" {_timing(cue, delay)} data-dur="0.9" x1="0" y1="-50" x2="0" y2="{len(lines)*size*1.5:.0f}" stroke="url(#accent-grad)" stroke-width="8"/>
  {body}
</g>"""


def pointer(x1, y1, x2, y2, label, cue=None, delay=1.0, anchor="end"):
    """Annotation arrow that grows to the target, then a label fades in."""
    lx = x1 - 30 if anchor == "end" else x1 + 30
    return f"""
<line data-anim="draw" {_timing(cue, delay)} data-dur="0.9" fill="none" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ACCENT}" stroke-width="7" marker-end="url(#arrow)"/>
<text data-anim="fade" data-delay="{delay+0.5:.2f}" data-dur="0.6" x="{lx}" y="{y1-5}" font-family="{SANS}" font-size="46" fill="{INK}" opacity="0" text-anchor="{anchor}">{label}</text>"""


def hero(image_uri, x=2500, y=560, w=980, h=1400, cue=None, delay=0.6, floaty=True):
    """Game art that floats weightlessly (or just fades in)."""
    anim = 'data-anim="float"' if floaty else 'data-anim="zoom"'
    return f"""
<g transform="translate({x},{y})">
  <g {anim} {_timing(cue, delay)} data-dur="1.5">
    <image href="{image_uri}" xlink:href="{image_uri}" width="{w}" height="{h}"/>
  </g>
</g>"""


def end_card(main, sub="", cue=None, delay=0.4):
    """Centered closing screen."""
    return f"""
<g transform="translate(1920,980)">
  <text data-anim="type" {_timing(cue, delay)} data-dur="1.3" x="0" y="0" text-anchor="middle" font-family="{SERIF}" font-size="200" font-weight="bold" fill="{INK}" letter-spacing="10">{main}</text>
  <line data-anim="draw" data-delay="{delay+0.4:.2f}" data-dur="1.0" x1="-300" y1="120" x2="300" y2="120" stroke="url(#accent-grad)" stroke-width="10"/>
  <text data-anim="fade-up" data-delay="{delay+0.8:.2f}" data-dur="1.0" x="0" y="240" text-anchor="middle" font-family="{SANS}" font-size="64" fill="{INK}" opacity="0" letter-spacing="8">{sub}</text>
</g>"""
