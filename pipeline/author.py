# -*- coding: utf-8 -*-
"""
Stage 3.1 - foreground prompt assembly.

Builds the exact prompt that asks an LLM for ONE scene fragment (static SVG +
data-anim/data-cue) to drop into the base board. The whole point of the board is
that the model returns a small fragment, not a full animated document - fast and
on-spec. The script + word timeline + asset name are injected so the model can
cue animations to the narration.

This module assembles + saves the prompt. Wire `generate()` to your LLM of
choice (e.g. the Anthropic API) to close the loop into scene_html/scene_NN.html.
"""

import os
import sys
import json
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

DESIGN_RULES = f"""设计契约（必须遵守）：
- 画布 3840x2160，<svg id="stage"> 内只写静态 SVG 片段，不要写 <html>/<style>/<script>。
- 背景全透明；文字深黛绿 {config.INK}；强调线/箭头浅绿 {config.ACCENT}（或 url(#accent-grad)）。
- 禁止：边框、卡片、阴影、毛玻璃。版式留白克制，体现高级感。
- 定位用「外层 <g transform="translate(x,y)"> 属性」；动画放在「内层 <g data-anim>」（无 transform 属性）。
"""

ANIMATION_GUIDE = """可用动画（data-anim + data-delay/data-dur 秒）：
  type(逐字) / fade / fade-up / fade-left / fade-right / zoom /
  draw(描边生长，箭头用 marker-end="url(#arrow)") / count(数字滚动: data-to,data-decimals) /
  float(无重力悬浮，持续)
音画同步：用 data-cue="旁白里的原词" 代替 data-delay，元素会在念到该词的那一帧才动。
只能 cue 旁白里真实说出的词（不是屏幕上的数字）。"""


def _transcript(srt_path):
    if not os.path.exists(srt_path):
        return ""
    words = json.load(open(srt_path, encoding="utf-8"))
    return "".join(w["word"] for w in words)


def build_prompt(script_text, srt_path, asset_name):
    transcript = _transcript(srt_path)
    return f"""你是顶级动态信息图设计师。请为下面这一段旁白设计「一个场景」的前景 SVG 片段。

【旁白文案】
{script_text}

【旁白词级时间轴可 cue 的词】（用于 data-cue 精确对齐）
{transcript or "（无，回退到 data-delay 估时）"}

【本场景可用素材】assets/{asset_name}
（用 <image href="file:///绝对路径/{asset_name}"> 引入，建议配 data-anim="float"）

{DESIGN_RULES}
{ANIMATION_GUIDE}

只输出 <svg id="stage"> 内部的片段内容，不要任何解释或代码块标记。"""


def assemble_all(scripts_dir=config.DIR_SCRIPTS, srt_dir=config.DIR_SRT,
                 assets=None, out_dir=config.DIR_SCENE):
    """Write scene_html/prompt_NN.txt for every script. Returns the prompt list."""
    config.ensure_dirs()
    scripts = sorted(glob.glob(os.path.join(scripts_dir, "script_*.txt")))
    assets = assets or sorted(glob.glob(os.path.join(config.DIR_ASSETS, "*.png")))
    prompts = []
    for i, script in enumerate(scripts, 1):
        idx = f"{i:02d}"
        text = open(script, encoding="utf-8").read().strip()
        srt = os.path.join(srt_dir, f"srt_{idx}.json")
        asset = os.path.basename(assets[(i - 1) % len(assets)]) if assets else "weapon_01.png"
        prompt = build_prompt(text, srt, asset)
        with open(os.path.join(out_dir, f"prompt_{idx}.txt"), "w", encoding="utf-8") as f:
            f.write(prompt)
        prompts.append(prompt)
    print(f"[author] assembled {len(prompts)} scene prompts -> {out_dir}/prompt_NN.txt")
    return prompts


def generate(prompt):
    """HOOK: send `prompt` to your LLM and return the raw SVG fragment string.
    Left unwired so the scaffold runs offline; plug in the Anthropic API here."""
    raise NotImplementedError("Wire an LLM here to auto-generate scene fragments.")


if __name__ == "__main__":
    assemble_all()
