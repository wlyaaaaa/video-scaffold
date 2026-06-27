# -*- coding: utf-8 -*-
"""
游戏王 MD 视频生成 · 主业务脚本（v2 起步骨架 / clean MD skeleton）。

上一期《游戏王MD氪金指南》已发布；它的完整 build_v2、文案/数据、实拍图、配音、成片
都已归档到  E:\\video-archive\\md-krijin-v1\\（要抄分镜/数据口径去那里翻，别污染 token）。
本文件只留 4 个**可直接 build/preview 的示例场景**（不依赖 assets/）。开新一期就：
  1) 改 TITLE；2) 把实拍图丢进 assets/（尺寸自动探测）；3) 重写下面 SCENES：每个场景
     写旁白 + 用 L.* 组件拼前景，cue="旁白真词" 做词级踩点，多用高级 FX；4) 改 CHAPTER_GROUPS/COVERS。
动效/组件/CLI/纠偏 全部只读 docs/AI_GUIDE.md（+ docs/ADVANCED_FX.md），不要通读源码。

用法： python build_v2.py [doctor|scripts|tts|timing|build|lint|preview|cover|chapters|render|merge|verify|cleanup|ship|reset|all]
  doctor   渲染前体检：ffmpeg/ffprobe/背景/Fish key/playwright/assets 是否就绪
  build    片段嵌底板 -> scene_html/（改了文案/分镜先跑这个）
  lint     越界自检：自动找出离开画布的文字(HARD,必修)/离开毛玻璃的元素(soft,看情况)
  preview  生成 output/preview.html，浏览器里逐场景「动态」自检（渲染前必看）
  render   逐帧抓取叠背景 -> video_track.mp4，并自动接 merge 出带声音的成片
  cover    渲染封面（骨架里 COVERS 为空，做好封面模板后再填）
  chapters 生成 output/chapters.txt 与 章节管理.txt（B站章节）
  verify   核对成片/封面已生成且非空（就绪自检）
  cleanup  清理临时分片/中间产物，回收 NVMe
  ship     verify 通过则 cleanup，一键收尾
  reset    清空可再生工作区（scripts/raw_audio/srt/scene_html/output/durations）为下期腾位
  all      端到端（tts/timing 已幂等：配音/转写齐全会自动跳过，不再覆盖审过的配音）
注意：tts/timing 现已幂等——raw_audio/ 配音齐全时 `all` 会自动跳过合成与转写
（要强制重配音：`python build_v2.py tts force`）。日常迭代用 `build`→`lint`→`preview`→（满意再）`render`。
"""
import os, sys, glob, json, pathlib, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, v2lib as L
from pipeline import fish_tts, durations as dur_mod, transcribe, build_scene, render, merge
from pipeline import chapters as chapters_mod, preview as preview_mod, cleanup as cleanup_mod, lint as lint_mod

INK, ACCENT, RED, GOLD = L.INK, L.ACCENT, L.RED, L.GOLD
M, CX, CY, COL = L.M, L.CX, L.CY, L.COL

TITLE = "游戏王 MD · 待定标题"     # 章节管理.txt 抬头 + 封面用，改成本期标题


# ============================================================================
#  示例场景（照着改/加；这 4 个不依赖 assets/，能直接 build/preview 看动效）
#  - 每个场景 = 一个返回静态 SVG 片段的函数 + 一段旁白字符串
#  - cue="旁白真词" 在有 srt 后做词级踩点；没 srt 时自动退回 data-delay
#  - 高级 FX 速查：docs/ADVANCED_FX.md（holo_panel/gauge/convert/morph_path/
#    num_burst/discount_seal/pulse_badge/card_flip/coin_fountain/gooey_flow/ambient_motes）
# ============================================================================
def s00_open():
    """冷启动钩子：先勾人。TODO 换成本期真实开场。"""
    return (
        L.kicker("游戏王 MASTER DUEL · 待定副标题", M, 480, delay=0.2, anim="kicker-zoom")
        + L.type_in("一句话钩子放这里", M, 800, lvl=1, cue="钩子", delay=0.2)
        + L.rule(M + 4, 858, 1500, delay=0.6)
        + L.pop("把核心卖点摆明白", M, 1120, lvl=2, cue="卖点", delay=0.0, fill=GOLD)
        + L.ambient_motes(n=18)                       # 氛围浮尘（高级感、不抢戏）
        + L.text("电子雪貂饲养员 · 亲测", M, 1860, lvl=4, delay=2.0, opacity=1, fill=ACCENT)
    )
S00 = "[excited]开场钩子的旁白放这里。TODO：换成本期真实开场白，记得 cue 用旁白真词。"


def s01_dashboard():
    """演示：3D 全息看板 + 风险/力度仪表盘。"""
    return (
        L.title("数据看板示例", cue="数据", kick="ADVANCED FX")
        + L.holo_panel("核心数据", [("指标一", 9.5, 0.95, ""), ("指标二", 8.0, 0.80, ""),
                                   ("整体折扣", 74.8, 0.748, "%")], x=M, y=760, w=1640, cue="核心")
        + L.gauge(82, zones=[(0.4, ACCENT), (0.7, GOLD), (1.0, RED)], x=2900, y=1200, r=360,
                  title="代充封号风险", unit="%", cue="风险")
    )
S01 = "这一段演示全息数据看板和风险仪表盘。TODO：换成本期真实数据与口径。"


def s02_money():
    """演示：币种换算 + 折扣印章 + 数字粒子炸裂。"""
    return (
        L.title("算账示例", cue="算账", kick="MONEY")
        + L.convert(495.32, "RMB", 11770, "日元", x=M, y=940, cue="换算")
        + L.discount_seal("74.8折", x=2950, y=820, cue="折")
        + L.num_burst(74.8, 2950, 1480, lvl=0, suffix="%", dec=1, cue="七四八")
    )
S02 = "这一段演示币种换算、折扣印章和数字粒子炸裂。TODO：换成本期真实金额。"


def s03_cta():
    """结尾 CTA + 金币喷泉。"""
    return (
        L.coin_fountain(x=CX, y=1500, cue="收益")
        + L.end_card("一键三连 + 关注", "下期见", cue="三连", delay=0.3)
    )
S03 = "结尾：觉得有用就一键三连加关注，我们下期见。"


# (name, build_fn, narration) —— 顺序即成片顺序，名字用于 preview/章节对照
SCENES = [
    ("s00", s00_open,      S00),
    ("s01", s01_dashboard, S01),
    ("s02", s02_money,     S02),
    ("s03", s03_cta,       S03),
]

# ---- 章节(B站): (0-based 起始场景下标, 章节标题) —— 一个清晰主题一章，短到手机能看 ----
CHAPTER_GROUPS = [
    (0, "开场钩子"),
    (1, "核心数据"),
    (3, "结尾三连"),
]

# ---- 封面：骨架留空。做好本期封面模板(templates/)后按下面格式填：
#   ("模板.html", "cover.png", {占位符: 文件路径}, (宽,高), 缩放)
#   注意 render_covers 把 repl 的值都当**文件路径**转成 file URI（只能填图片，不能填文字）。
COVERS = []


def render_covers():
    """Screenshot each bespoke cover template to output/. Vector + one image, so
    the result is razor sharp (no video frame-grab softness)."""
    if not COVERS:
        print("[cover] no covers configured (skeleton) - add an entry to COVERS when ready")
        return
    import asyncio
    from playwright.async_api import async_playwright
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    async def run():
        async with async_playwright() as p:
            try: b = await p.chromium.launch(headless=True, channel="chrome")
            except Exception: b = await p.chromium.launch(headless=True)
            for tpl, outname, repl, (vw, vh), scale in COVERS:
                html = pathlib.Path(os.path.join(config.ROOT, "templates", tpl)).read_text(encoding="utf-8")
                for ph, path in repl.items():
                    html = html.replace(ph, pathlib.Path(path).as_uri())
                tmp = os.path.join(config.DIR_SCENE, f"_cover_{outname}.html")
                pathlib.Path(tmp).write_text(html, encoding="utf-8")
                ctx = await b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=scale)
                pg = await ctx.new_page(); await pg.goto(pathlib.Path(tmp).as_uri())
                out = os.path.join(config.DIR_OUTPUT, outname)
                await pg.screenshot(path=out, type="png"); await ctx.close()
                os.remove(tmp); print(f"[cover] -> {out}  ({vw}x{vh}@{scale}x)")
            await b.close()
    config.ensure_dirs()
    asyncio.run(run())


def write_chapters():
    """Bilibili chapter markers: output/chapters.txt (paste-ready) + a richer
    章节管理.txt (markers + per-scene reference for manual tweaking)."""
    durs = _durs()
    chs = chapters_mod.from_scene_groups(durs, CHAPTER_GROUPS)
    chapters_mod.write(chs)  # -> output/chapters.txt
    offs, acc = [], 0.0
    for d in durs:
        offs.append(acc); acc += d
    lines = [f"{TITLE} · 章节管理",
             f"全片 {chapters_mod.fmt_ts(acc)} · {len(SCENES)} 场景 · {len(CHAPTER_GROUPS)} 章节",
             "用法：复制下面【章节标记】整块，粘进 B 站投稿页「章节文本编辑器」一键生成。",
             "格式 MM:SS 标题；首行须 00:00；相邻章节间隔 ≥5 秒。", "",
             "──────── 章节标记（复制这块）────────"]
    lines += [f"{chapters_mod.fmt_ts(t)} {title}" for t, title in chs]
    lines += ["", "──────── 场景对照（自己定位用，不用粘）────────"]
    for i, (name, _, _) in enumerate(SCENES):
        lines.append(f"#{i+1:02d}  {chapters_mod.fmt_ts(offs[i])}  {name:5s}  {durs[i]:5.1f}s")
    out = os.path.join(config.ROOT, "章节管理.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[chapters] -> {out}")


# ====================================================================== driver
def write_scripts():
    config.ensure_dirs()
    for i, (_, _, text) in enumerate(SCENES, 1):
        with open(os.path.join(config.DIR_SCRIPTS, f"script_{i:02d}.txt"), "w", encoding="utf-8") as f:
            f.write(text)
    print(f"[v2] wrote {len(SCENES)} scripts")


def build_all():
    config.ensure_dirs()
    paths = []
    for i, (name, fn, _) in enumerate(SCENES, 1):
        srt = os.path.join(config.DIR_SRT, f"srt_{i:02d}.json")
        out = os.path.join(config.DIR_SCENE, f"scene_{i:02d}.html")
        paths.append(build_scene.build(fn(), out, srt=srt if os.path.exists(srt) else None))
    return paths


def _durs():
    with open(config.DURATIONS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _count(dir_, pat):
    return len(glob.glob(os.path.join(dir_, pat)))


def doctor():
    """Preflight: confirm the toolchain + inputs are ready BEFORE a long render,
    so a missing ffmpeg / background fails in 1s instead of 80min in. Only the
    render-critical tools are fatal; FISH key / BGM / assets are advisory (they
    matter only for tts / music / real screenshots, not for a skeleton build)."""
    import shutil as _sh
    req_ok = []
    def chk(name, cond, hint="", required=True):
        mark = "OK" if cond else ("XX" if required else "--")
        print(f"  [{mark}] {name}" + ("" if cond else f"   -> {hint}"))
        if required:
            req_ok.append(cond)
    try:
        import playwright  # noqa: F401
        pw = True
    except Exception:
        pw = False
    chk("ffmpeg",         _sh.which("ffmpeg") is not None,  "install ffmpeg and add to PATH")
    chk("ffprobe",        _sh.which("ffprobe") is not None, "ships with ffmpeg")
    chk("background mp4",  os.path.exists(config.BG_VIDEO), "background/background_4k.mp4 missing")
    chk("playwright",      pw, "pip install playwright && playwright install chrome")
    n_assets = _count(config.DIR_ASSETS, "*") if os.path.exists(config.DIR_ASSETS) else 0
    chk("FISH_API_KEY",    bool(config.FISH_API_KEY), "set secret_local.py / env (needed only for tts)", required=False)
    chk("BGM",             os.path.exists(config.BGM_PATH), "drop bgm.mp3 for ducked music (optional)", required=False)
    chk("assets/",         n_assets > 0, "drop screenshots into assets/ (skeleton scenes need none)", required=False)
    ok = all(req_ok)
    print("[doctor] READY" if ok else "[doctor] NOT READY - fix the XX rows above")
    return ok


def reset_workspace(confirm):
    """Wipe the regenerable per-project workspace so THIS FOLDER can host the next
    video. Keeps assets/ (you swap art by hand) and the committed scaffold/code.
    scripts/ IS cleared: it is regenerated from SCENES by the `scripts` stage, and
    leaving stale script_NN.txt would let tts/durations pick up phantom scenes."""
    targets = [config.DIR_SCRIPTS, config.DIR_AUDIO, config.DIR_SRT,
               config.DIR_SCENE, config.DIR_RENDERED, config.DIR_OUTPUT]
    if confirm != "yes":
        print("[reset] DRY-RUN. Would DELETE: scripts/ raw_audio/ srt_data/ scene_html/ "
              "rendered/ output/ + durations.json")
        print("[reset] (kept: assets/ and all committed code).  Confirm with:")
        print("[reset]   python build_v2.py reset yes")
        return
    import shutil as _sh
    for d in targets:
        _sh.rmtree(d, ignore_errors=True)
    try: os.remove(config.DURATIONS_JSON)
    except OSError: pass
    config.ensure_dirs()
    print("[reset] workspace cleared. Next: swap assets/, edit SCENES in build_v2.py, "
          "then `python build_v2.py doctor` -> `all`.")


VALID = {"doctor", "scripts", "tts", "timing", "build", "lint", "preview", "cover",
         "chapters", "render", "merge", "verify", "cleanup", "ship", "reset", "all"}


def main():
    argv = sys.argv[1:]
    stage = argv[0] if argv else "all"
    rest = argv[1:]
    force = "force" in rest

    if stage not in VALID:
        print(__doc__)
        sys.exit(f"[v2] unknown stage {stage!r}. valid: {', '.join(sorted(VALID))}")
    if stage == "doctor":
        sys.exit(0 if doctor() else 1)
    if stage == "reset":
        return reset_workspace(rest[0] if rest else "")

    if stage in ("scripts", "all"):
        write_scripts()
    if stage in ("tts", "all"):
        # Idempotent: approved narration is precious. Skip if every clip exists
        # (this is the fix for the old "don't re-run tts/all, it overwrites" footgun).
        if _count(config.DIR_AUDIO, "audio_*.mp3") >= len(SCENES) and not force:
            print(f"[v2] tts: {len(SCENES)} clips already in raw_audio/ - skipping "
                  f"(pass 'force' to re-synthesize the voice).")
        else:
            outs = fish_tts.synth_batch()
            if len(outs) != len(SCENES):
                sys.exit(f"[v2] TTS produced {len(outs)}/{len(SCENES)}")
    if stage in ("timing", "all"):
        dur_mod.build()                       # durations are cheap + must track audio
        if stage == "all" and _count(config.DIR_SRT, "srt_*.json") >= len(SCENES) and not force:
            print(f"[v2] timing: {len(SCENES)} srt present - skipping whisper (pass 'force' to redo).")
        else:
            transcribe.transcribe_batch()
    scenes = build_all() if stage in ("build", "all") else sorted(glob.glob(os.path.join(config.DIR_SCENE, "scene_*.html")))
    if stage in ("lint", "all"):        # catch off-canvas text BEFORE the long render
        durs = _durs() if os.path.exists(config.DURATIONS_JSON) else [6.0] * len(scenes)
        lint_mod.lint(scenes, durs, names=[s[0] for s in SCENES])
    if stage in ("preview", "all"):
        preview_mod.build(names=[s[0] for s in SCENES])
    if stage in ("cover", "all"):
        render_covers()
    if stage in ("chapters", "all"):
        write_chapters()
    if stage in ("render", "all"):
        workers = int(rest[0]) if rest and rest[0].isdigit() else None  # e.g. python build_v2.py render 2
        render.render_timeline(scenes, _durs(), num_workers=workers)
    # NOTE: render writes a SILENT video track (output/video_track.mp4, -an by
    # design). The sound lives in output/final_output.mp4, produced by muxing
    # narration + ducked BGM here. `render` now falls through to merge too, so a
    # render run never leaves you with a soundless file.
    if stage in ("merge", "render", "all"):
        audio = merge.concat_audio()
        merge.mux(os.path.join(config.DIR_OUTPUT, "video_track.mp4"), audio)  # BGM auto (config.BGM_PATH exists)
        print("[v2] DONE -> output/final_output.mp4 (with narration + BGM)")
    if stage in ("verify", "all"):
        cleanup_mod.verify()
    if stage == "cleanup":
        cleanup_mod.cleanup()
    if stage == "ship":
        if cleanup_mod.verify():
            cleanup_mod.cleanup()
            print("[v2] shipped: deliverables verified, temps cleaned.")
        else:
            sys.exit("[v2] ship aborted: deliverables not ready (run render/merge first).")


if __name__ == "__main__":
    main()
