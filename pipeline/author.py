# -*- coding: utf-8 -*-
"""
Stage 3.1 - foreground prompt assembly.

Builds the exact prompt that asks an LLM for ONE scene fragment (static SVG +
data-anim/data-cue) to drop into the base board. The whole point of the board is
that the model returns a small fragment, not a full animated document - fast and
on-spec. The script + word timeline + asset name are injected so the model can
cue animations to the narration.

This module assembles and saves the prompt. The current AI or a person writes
the fragment; no separate model service is needed for this workflow.
"""

import os
import sys
import json
import glob
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.io_utils import safe_print as print
from pipeline.indexed_files import indexed_basename, indexed_files
from pipeline.recycle import recycle_generated

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
音画同步：用 data-cue="旁白里的原词" 绑定现有词轴中的估计时间，再通过有声预览检查。
只能 cue 旁白里真实说出的词（不是屏幕上的数字）。完整动画与参数见 docs/AUTHORING.md 和 docs/ADVANCED_FX.md。"""


def _transcript(srt_path):
    if not os.path.exists(srt_path):
        return ""
    with open(srt_path, encoding="utf-8") as source:
        words = json.load(source)
    return "".join(w["word"] for w in words)


def build_prompt(script_text, srt_path, asset_path=None):
    transcript = _transcript(srt_path)
    if asset_path:
        asset = Path(asset_path)
        if not asset.is_absolute():
            asset = Path(config.DIR_ASSETS) / asset
        asset_uri = asset.resolve().as_uri()
        asset_guide = f"""【本场景可用素材】{asset_uri}
（用 <image href=\"{asset_uri}\"> 引入，建议配 data-anim=\"float\"）"""
    else:
        asset_guide = "【本场景可用素材】无（不要虚构素材路径）"
    return f"""你是顶级动态信息图设计师。请为下面这一段旁白设计「一个场景」的前景 SVG 片段。

先结合本工程 docs/AUTHORING.md 选择能讲清内容的画面：让明确的主体发生有意义的变化，
按内容选流程、结构、比例或关系等表达；文字服务于画面，不把整段旁白搬上屏幕。

【旁白文案】
{script_text}

【旁白词级时间轴可 cue 的词】（用于 data-cue 精确对齐）
{transcript or "（无，回退到 data-delay 估时）"}

{asset_guide}

{DESIGN_RULES}
{ANIMATION_GUIDE}

只输出 <svg id="stage"> 内部的片段内容，不要任何解释或代码块标记。"""


def assemble_all(
    scripts_dir=config.DIR_SCRIPTS,
    srt_dir=config.DIR_SRT,
    assets=None,
    out_dir=config.DIR_SCENE,
):
    """Write scene_html/prompt_NN.txt for every script. Returns the prompt list."""
    scripts = indexed_files(os.path.join(scripts_dir, "script_*.txt"))
    assets = assets or sorted(glob.glob(os.path.join(config.DIR_ASSETS, "*.png")))
    prepared = []
    for position, (index, script) in enumerate(scripts.items()):
        with open(script, encoding="utf-8") as source:
            text = source.read().strip()
        srt = os.path.join(srt_dir, indexed_basename("srt", index, ".json"))
        asset = assets[position % len(assets)] if assets else None
        prompt = build_prompt(text, srt, asset)
        output = os.path.join(out_dir, indexed_basename("prompt", index, ".txt"))
        prepared.append((output, prompt))

    expected = {os.path.basename(output) for output, _prompt in prepared}
    existing = indexed_files(
        os.path.join(out_dir, "prompt_*.txt"),
        ignore_noncanonical=True,
    )

    os.makedirs(out_dir, exist_ok=True)
    for path in existing.values():
        if os.path.basename(path) not in expected:
            recycle_generated(path, out_dir)
    for output, prompt in prepared:
        with open(output, "w", encoding="utf-8") as f:
            f.write(prompt)
    print(
        f"[author] assembled {len(prepared)} scene prompts -> {out_dir}/prompt_NN.txt"
    )
    return [prompt for _output, prompt in prepared]


def generate(prompt):
    """Reserved compatibility entry; the active workflow uses AI-authored SVG."""
    raise NotImplementedError("Use the current AI or a person to author the scene SVG fragment.")


if __name__ == "__main__":
    assemble_all()
