"""逐页生成确定性的 SVG 片段并比较；不出片、不写影片目录。

python -m pipeline.page_compare snapshot <pages目录> <快照.json> [表名.json ...]
python -m pipeline.page_compare compare <基准.json> <当前.json> <差异.json>
基线不认识的元素单独报告为 unavailable，不冒充通过。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pipeline import boards, pages
import v2lib as L
import config


def snapshot(directory, names=None):
    result = {}
    paths = [Path(directory) / n for n in names] if names else sorted(Path(directory).glob("*.json"))
    for path in paths:
        spec = pages._read_json(path)
        if not isinstance(spec, dict) or "pages" not in spec or "narration" not in spec:
            continue
        L.use_theme(spec.get("theme", "white-green"))
        tl = pages.load_timeline(spec, path.parent)
        records = []
        for page, (start, end, pos) in zip(spec["pages"], pages.plan_pages(spec, tl)):
            def make(value):
                boards._ids[0] = 0
                try:
                    fragment = pages.PageBuilder(tl, value, start, pos, path.parent,
                        value.get("progress", spec.get("progress")), end, spec.get("brands")).build()
                    return {"svg": fragment}
                except (ValueError, KeyError) as exc:
                    return {"unavailable": str(exc)}
            record = make(page)
            record["elements"] = [dict(index=i + 1, keys=list(el), **make(dict(page, elements=[el])))
                                  for i, el in enumerate(page["elements"])]
            records.append(record)
        result[path.name] = records
    if not result:
        raise ValueError("没有找到图文页分镜表")
    return result


def compare(before, after):
    changes, unavailable, added = [], [], []
    for name, old_pages in before.items():
        new_pages = after.get(name, [])
        if len(old_pages) != len(new_pages):
            changes.append({"table": name, "reason": "page count", "before": len(old_pages), "after": len(new_pages)})
        for i, (old, new) in enumerate(zip(old_pages, new_pages), 1):
            elements = []
            if len(old["elements"]) != len(new["elements"]):
                changes.append({"table": name, "page": i, "reason": "element count"})
            for a, b in zip(old["elements"], new["elements"]):
                where = {"table": name, "page": i, "element": a["index"], "keys": a["keys"]}
                if "unavailable" in a or "unavailable" in b:
                    unavailable.append(dict(where, before=a.get("unavailable"), after=b.get("unavailable")))
                elif a["svg"].encode() != b["svg"].encode():
                    elements.append(a["index"])
            if "svg" in old and "svg" in new:
                if old["svg"].encode() != new["svg"].encode():
                    changes.append({"table": name, "page": i, "elements": elements})
            elif "svg" not in old and "svg" in new:
                added.append({"table": name, "page": i})
                if elements:
                    changes.append({"table": name, "page": i, "elements": elements})
            elif elements:
                changes.append({"table": name, "page": i, "elements": elements})
    return {"equal": not changes and not unavailable, "changes": changes,
            "unavailable": unavailable, "newly_supported_pages": added}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(__doc__)
        return 2
    if args[0] == "snapshot":
        output = Path(args[2]).resolve()
        config.DIR_ASSETS = str(output.parent / "compare-assets")
        data = snapshot(args[1], args[3:] or None)
    elif args[0] == "compare":
        data = compare(pages._read_json(args[1]), pages._read_json(args[2]))
        output = Path(args[3])
        print(json.dumps({k: v for k, v in data.items() if k != "unavailable"}, ensure_ascii=False))
        print(f"unavailable elements: {len(data['unavailable'])}")
    else:
        raise ValueError(__doc__)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return int(data.get("equal") is False)


if __name__ == "__main__":
    raise SystemExit(main())
