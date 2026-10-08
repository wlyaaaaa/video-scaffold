"""Independent command line; the older SVG line keeps its existing entry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .common import chrome_path, new_output, tool, write_json


def parser():
    root = argparse.ArgumentParser(description="把自包含网页逐帧制作成视频；不发布任何内容。")
    tasks = root.add_subparsers(dest="command", required=True)
    tasks.add_parser("doctor", help="只读检查工具位置，不开浏览器、不读密钥")
    discovery = tasks.add_parser("discover", help="只读识别原样文件夹中的网页、视频和素材")
    discovery.add_argument("folder")
    demo = tasks.add_parser("demo", help="在全新隔离目录生成制作彩排素材")
    demo.add_argument("destination")
    check = tasks.add_parser("check", help="静态规则和素材清单；运行期规则由完整渲染验证")
    check.add_argument("work")
    check.add_argument("--output")
    check.add_argument("--max-duration", type=float, default=120)
    render = tasks.add_parser("render", help="逐帧渲染与离线程序音乐，可选绝对时间片段")
    render.add_argument("work")
    render.add_argument("output")
    render.add_argument("--1080p", action="store_true")
    render.add_argument("--actions")
    render.add_argument("--max-duration", type=float, default=120)
    render.add_argument("--start", type=float, default=0, help="源作品起点秒数，包含，须在60fps帧边界")
    render.add_argument("--end", type=float, help="源作品终点秒数，不包含，默认作品末尾")
    stills = tasks.add_parser("stills", help="直接采样作品关键帧，并生成带秒数的小拼图")
    stills.add_argument("work")
    stills.add_argument("output")
    stills.add_argument("--at", nargs="+", type=float, required=True, help="源作品绝对秒数，须在60fps帧边界")
    stills.add_argument("--1080p", action="store_true")
    stills.add_argument("--actions")
    capture = tasks.add_parser("capture", help="从外部驱动普通网页，无需修改源码或使用本工具接口")
    capture.add_argument("folder")
    capture.add_argument("output")
    capture.add_argument("--entry")
    capture.add_argument("--duration", type=float, default=20)
    capture.add_argument("--seed", type=int, default=829)
    capture.add_argument("--1080p", action="store_true")
    capture.add_argument("--actions")
    capture.add_argument("--max-duration", type=float, default=120)
    compare = tasks.add_parser("compare", help="比较两次完整渲染的每帧像素和离线音频")
    compare.add_argument("left")
    compare.add_argument("right")
    compare.add_argument("--output")
    review = tasks.add_parser("review", help="回看包：抽帧拼图、整片、声音概览")
    review.add_argument("video")
    review.add_argument("output")
    compose = tasks.add_parser("compose", help="按时间线接片、并排、旁白字幕与整片响度")
    compose.add_argument("timeline")
    compose.add_argument("output")
    compose.add_argument("--1080p", action="store_true")
    cover = tasks.add_parser("cover", help="同一个网页渲染16:9及4:3封面")
    cover.add_argument("work")
    cover.add_argument("output")
    cover.add_argument("--at", type=float, default=0)
    package = tasks.add_parser("package", help="生成静态展示页文件夹，不写网站")
    package.add_argument("manifest")
    package.add_argument("output")
    upload = tasks.add_parser("upload-template", help="上传文字清单格式和示例")
    upload.add_argument("output")
    narration = tasks.add_parser("narrate", help="显式调用现有Fish生产配音；不另取密码中心凭据")
    narration.add_argument("text")
    narration.add_argument("output")
    narration.add_argument("--legacy-root", required=True)
    return root


def main(argv=None):
    arguments = parser().parse_args(argv)
    command = arguments.command
    try:
        if command == "doctor":
            tools = {}
            for name, resolve in (("Chrome", chrome_path), ("FFmpeg", lambda: tool("ffmpeg")), ("FFprobe", lambda: tool("ffprobe"))):
                try:
                    tools[name] = {"available": True, "path": resolve()}
                except FileNotFoundError as error:
                    tools[name] = {"available": False, "error": str(error)}
            try:
                import playwright.sync_api
                import PIL
                tools["Python libraries"] = {"available": True, "Pillow": PIL.__version__}
            except ImportError as error:
                tools["Python libraries"] = {"available": False, "error": str(error)}
            result = {"schema": "webfilm.doctor.v1", "pass": all(v["available"] for v in tools.values()), "scope": "static", "tools": tools}
        elif command == "discover":
            from .input import discover
            result = discover(arguments.folder)
        elif command == "demo":
            from .demo import create_demo
            result = create_demo(arguments.destination)
        elif command == "check":
            from .check import check_work
            result = check_work(arguments.work, max_duration=arguments.max_duration)
            if arguments.output:
                write_json(new_output(arguments.output), result)
        elif command in ("render", "capture"):
            from .render import render_work
            width, height = (1920, 1080) if arguments.__dict__["1080p"] else (3840, 2160)
            extra = ({"generic": True, "entry": arguments.entry, "duration": arguments.duration, "seed": arguments.seed}
                     if command == "capture" else {"start": arguments.start, "end": arguments.end})
            result = render_work(arguments.folder if command == "capture" else arguments.work, arguments.output, width=width, height=height,
                                 actions_path=arguments.actions, max_duration=arguments.max_duration, **extra)
            # The complete inventory and 1200 hashes stay in the sidecars.
            result = {key: result[key] for key in ("schema", "width", "height", "fps", "duration", "source_duration", "source_range", "frame_count", "elapsed_seconds", "output_sha256")}
        elif command == "stills":
            from .render import render_stills
            width, height = (1920, 1080) if arguments.__dict__["1080p"] else (3840, 2160)
            result = render_stills(arguments.work, arguments.output, at=arguments.at, width=width, height=height,
                                   actions_path=arguments.actions)
            result = {key: result[key] for key in ("schema", "source_duration", "sample_times", "width", "height", "files", "contact_sheet")}
        elif command == "compare":
            from .render import compare_renders
            result = compare_renders(arguments.left, arguments.right)
            if arguments.output:
                write_json(new_output(arguments.output), result)
        elif command == "review":
            from .media import review
            result = review(arguments.video, arguments.output)
        elif command == "compose":
            from .media import compose
            width, height = (1920, 1080) if arguments.__dict__["1080p"] else (3840, 2160)
            result = compose(arguments.timeline, arguments.output, width=width, height=height)
        elif command == "cover":
            from .render import render_cover
            result = render_cover(arguments.work, arguments.output, at=arguments.at)
        elif command == "package":
            from .package import package_site
            result = package_site(arguments.manifest, arguments.output)
        elif command == "upload-template":
            from .package import upload_template
            result = {"path": str(upload_template(arguments.output))}
        else:
            from .narration import narrate
            result = narrate(arguments.text, arguments.output, legacy_root=arguments.legacy_root)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), flush=True)
        return 1 if result.get("pass") is False else 0
    except Exception as error:
        print(f"webfilm failed: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
