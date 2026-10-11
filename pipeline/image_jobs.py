"""从 JSON 清单原样写生图派单；不调用模型。看过回图后显式登记验收。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path, PureWindowsPath


def literal(value):
    if not isinstance(value, str) or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in value):
        raise ValueError("路径必须为无控制字符的字符串；用 JSON 序列化写清单，不用手拼转义")
    if re.search(r"\$(?:\w+|\{[^}]+\})|\{\w+\}", value):
        raise ValueError(f"路径有未展开变量：{value}")
    if not Path(value).is_absolute() and not PureWindowsPath(value).is_absolute():
        raise ValueError(f"派单路径必须为绝对路径：{value}")
    return value


def generate(manifest, destination):
    spec = json.loads(Path(manifest).read_text(encoding="utf-8-sig"))
    destination = Path(destination)
    jobs = []
    for item in spec["images"]:
        name = item["name"]
        if not re.fullmatch(r"[\w.-]+", name) or name in (".", ".."):
            raise ValueError(f"无效派单名：{name}")
        output = literal(item["output"])
        references = [literal(p) for p in item.get("references", [])]
        header = {"任务": f"生成图片：{name}", "出处": spec["source"], "方案": "已定",
                  "仓库": literal(spec["repository"]), "基线": spec.get("base_ref", "HEAD"),
                  "工作树": "使用已给路径，仅生成图片", "范围": output,
                  "代码上限": 0, "测试上限": 0, "时限分钟": spec.get("minutes", 15),
                  "预计收益": item["purpose"], "预计花费": "一轮图片生成", "验证方式": "实测"}
        text = "---\n" + "\n".join(f"{k}: {v}" for k, v in header.items()) + "\n---\n\n"
        text += ("使用 Codex 内置图片生成能力；派出生图交 Luna low。\n"
                 "公开范围与个人资料按核验后的活动约法 L18、L20 和《个人资料与数据处理》原文。\n\n"
                 f"用途：{item['purpose']}\n\n提示词：\n{item['prompt']}\n\n"
                 f"参考图（路径原样）：\n" + ("\n".join(references) or "无") +
                 f"\n\n输出文件（绝对路径，按版本命名，不覆盖已有图）：\n{output}\n")
        jobs.append((destination / f"{name}.md", text, {"copied_to": output,
                     "source": "Codex 内置图片生成", "synthetic": True, "status": "planned", "reviewed": False}))
    paths = [p for p, _, _ in jobs]
    outputs = [r["copied_to"].casefold() for _, _, r in jobs]
    if len(set(paths)) != len(paths) or len(set(outputs)) != len(outputs):
        raise ValueError("派单名或输出图片重复")
    if any(p.exists() or p.with_suffix(".result.json").exists() for p in paths):
        raise FileExistsError("派单已存在，请使用新版本目录")
    destination.mkdir(parents=True, exist_ok=True)
    for path, text, result in jobs:
        path.write_text(text, encoding="utf-8")
        path.with_suffix(".result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths


def accept(path, saved_path, run_dir, note):
    from PIL import Image
    path = Path(path)
    result = json.loads(path.read_text(encoding="utf-8"))
    output = Path(result["copied_to"])
    with Image.open(output) as image:
        image.load()
        width, height = image.size
    if not Path(saved_path).is_file() or not Path(run_dir).is_dir():
        raise FileNotFoundError("需要实际生成源文件与任务回执目录")
    result.update(saved_path=str(saved_path), run_dir=str(run_dir), width=width, height=height,
                  sha256=hashlib.sha256(output.read_bytes()).hexdigest(), status="accepted", reviewed=True,
                  review_note=note, reviewed_at=datetime.now(timezone(timedelta(hours=8))).isoformat())
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate"); gen.add_argument("manifest"); gen.add_argument("destination")
    review = sub.add_parser("accept"); review.add_argument("result")
    for key in ("saved-path", "run-dir", "note"):
        review.add_argument("--" + key, required=True)
    args = parser.parse_args(argv)
    if args.command == "generate":
        for path in generate(args.manifest, args.destination):
            print(path)
    else:
        accept(args.result, args.saved_path, args.run_dir, args.note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
