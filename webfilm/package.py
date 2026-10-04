"""Portable local showcase packages and editable upload copy, never publication."""

from __future__ import annotations

import html
import json
from pathlib import Path
import shutil

from .common import read_json, sha256, temp_workspace, write_json


def _name(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _free_directory(path):
    target = Path(path).resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FileExistsError(f"refusing to overwrite existing deliverables: {target}")
    return target


def _work_tree(source):
    return sorted((item for item in source.rglob("*") if item.is_file()), key=lambda p: p.as_posix())


def _fingerprints(source):
    files = _work_tree(source) if source.is_dir() else [source]
    return [{"path": str(path), "relative": path.relative_to(source).as_posix() if source.is_dir() else path.name,
             "bytes": path.stat().st_size, "sha256": sha256(path)} for path in files]


_PAGE = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · 网页作品展示</title>
<style>
:root{color-scheme:light;font-family:system-ui,"Microsoft YaHei",sans-serif;color:#21382e;background:#f5f8f6}
*{box-sizing:border-box}body{margin:0}header{background:#fff;border-bottom:1px solid #dce7df;padding:24px 4vw}
h1{font-size:clamp(24px,3vw,36px);margin:0 0 8px}p{line-height:1.7;margin:0;color:#60756a}main{max-width:1600px;margin:auto;padding:24px 4vw}
.toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:16px}.toolbar label{display:flex;align-items:center;gap:8px}
select,button{font:inherit;border:1px solid #b8ccbf;border-radius:7px;padding:9px 14px;background:#fff;color:#234533}
button{cursor:pointer}button:hover{background:#eaf4ed}a{color:#187846}iframe{display:block;border:1px solid #cbdcd0;border-radius:10px;width:100%;height:min(75vh,900px);background:#fff}
.card{margin-top:24px;background:#fff;border:1px solid #dce7df;border-radius:10px;padding:20px}h2{font-size:20px;margin:0 0 16px}
textarea{display:block;width:100%;min-height:150px;resize:vertical;font:15px/1.7 system-ui,sans-serif;border:1px solid #cadbce;border-radius:7px;padding:12px;color:#243f2f;background:#fbfdfb}
pre{overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.7 ui-monospace,Consolas,monospace;background:#f5f8f6;padding:16px;max-height:65vh;border-radius:7px}
.note{font-size:13px}#status{min-height:1.5em;margin-top:8px}.links{margin-left:auto;display:flex;gap:14px}@media(max-width:700px){main{padding:16px}header{padding:20px 16px}.links{margin-left:0}iframe{height:65vh}.card{padding:16px}}
</style></head><body><header><h1>__TITLE__</h1><p>切换作品与版本，直接运行页面，也可以阅读源码和复制给模型的提示词。</p></header>
<main><div class="toolbar"><label>作品 <select id="entry" aria-label="选择作品"></select></label>
<label>版本 <select id="version" aria-label="选择版本"></select></label><div class="links"><a id="open" target="_blank" rel="noopener">单独打开作品</a><a href="package.json">来源记录</a></div></div>
<iframe id="work" title="网页作品运行预览" allow="autoplay; fullscreen"></iframe>
<section class="card"><h2>给模型的提示词</h2><textarea id="prompt" readonly aria-label="给模型的提示词"></textarea><button id="copy" style="margin-top:12px">复制提示词</button><p id="status" role="status"></p></section>
<section class="card"><h2>阅读源码</h2><div class="toolbar"><label>文件 <select id="source" aria-label="选择源码文件"></select></label><a id="download" target="_blank" rel="noopener">打开原文件</a></div><pre id="code">请选择源码文件。</pre></section>
<section class="card"><p class="note">作品文件按原始字节复制。目录作品包含其素材；单个 HTML 适用于自包含页面。需要 fetch、模块脚本或同源资源的作品，请通过本地 HTTP 服务打开此目录。外部字体与 CDN 等依赖仍按作品原设置加载。此包仅供本地展示，没有部署、投稿或发布。</p></section>
</main><script id="manifest" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.getElementById('manifest').textContent);
const entry=document.getElementById('entry'),version=document.getElementById('version'),source=document.getElementById('source');
const preview=document.getElementById('work'),code=document.getElementById('code');let selection=0;
const urlFor=path=>path.split('/').map(encodeURIComponent).join('/');
const addOption=(select,text,value)=>{const option=document.createElement('option');option.textContent=text;option.value=value;select.appendChild(option)};
data.entries.forEach((item,index)=>addOption(entry,item.name,index));document.getElementById('prompt').value=data.prompt;
function selected(){return data.entries[Number(entry.value)].versions[Number(version.value)]}
async function showSource(){const token=++selection;const item=selected(),file=item.sources[Number(source.value)];
 if(!file){code.textContent='此作品没有可浏览的文本源码。';document.getElementById('download').removeAttribute('href');return}
 const path=urlFor(item.directory+'/'+file);document.getElementById('download').href=path;code.textContent='正在读取…';
 try{const response=await fetch(path);if(!response.ok)throw new Error('HTTP '+response.status);const text=await response.text();if(token===selection)code.textContent=text}
 catch(error){if(token===selection)code.textContent='浏览器未能读取源码。请通过本地 HTTP 服务打开此展示目录，或点击“打开原文件”。\n'+error.message}}
function showVersion(){const item=selected();preview.src=urlFor(item.entrypoint);document.getElementById('open').href=urlFor(item.entrypoint);source.replaceChildren();
 item.sources.forEach((file,index)=>addOption(source,file,index));showSource()}
function showEntry(){version.replaceChildren();data.entries[Number(entry.value)].versions.forEach((item,index)=>addOption(version,item.name,index));showVersion()}
entry.addEventListener('change',showEntry);version.addEventListener('change',showVersion);source.addEventListener('change',showSource);
document.getElementById('copy').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(data.prompt);document.getElementById('status').textContent='提示词已复制。'}
 catch(error){document.getElementById('prompt').focus();document.getElementById('prompt').select();document.getElementById('status').textContent='已选中提示词，请复制。'}});showEntry();
</script></body></html>'''


def package_site(manifest_path, output_dir):
    """Copy a manifest's works into a static local gallery; do not deploy it."""
    manifest_file = Path(manifest_path).resolve()
    manifest_hash = sha256(manifest_file)
    manifest = read_json(manifest_file)
    if not isinstance(manifest, dict):
        raise ValueError("showcase manifest must be an object")
    prompt = _name(manifest.get("prompt"), "manifest.prompt")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest.entries must be a nonempty list")
    output = _free_directory(output_dir)
    prepared = []
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError("each manifest entry must be an object")
        name = _name(entry.get("name"), "entry.name")
        versions = entry.get("versions")
        if not isinstance(versions, list) or not versions:
            raise ValueError("entry.versions must be a nonempty list")
        prepared_versions = []
        for version_index, version in enumerate(versions):
            if not isinstance(version, dict):
                raise ValueError("each version must be an object")
            version_name = _name(version.get("name"), "version.name")
            work = Path(_name(version.get("work"), "version.work"))
            if work.is_absolute():
                raise ValueError("version.work must be relative to the manifest")
            source = (manifest_file.parent / work).resolve()
            if not source.exists():
                raise FileNotFoundError(source)
            if source.is_dir():
                if output.parent.is_relative_to(source):
                    raise ValueError("showcase output parent must be outside each source work directory")
                specified_entry = version.get("entry")
                if specified_entry is not None:
                    entry_path = Path(_name(specified_entry, "version.entry"))
                    if entry_path.is_absolute():
                        raise ValueError("version.entry must be relative to its work directory")
                    resolved_entry = (source / entry_path).resolve()
                    if not resolved_entry.is_relative_to(source) or not resolved_entry.is_file():
                        raise ValueError(f"version.entry is not a file inside its work directory: {specified_entry}")
                    if resolved_entry.suffix.lower() not in (".html", ".htm"):
                        raise ValueError("version.entry must name an HTML file")
                    entrypoint = resolved_entry.relative_to(source).as_posix()
                else:
                    candidates = [path.relative_to(source).as_posix() for path in _work_tree(source)
                                  if path.suffix.lower() in (".html", ".htm")]
                    if not candidates:
                        raise ValueError(f"directory work contains no HTML entry: {source}")
                    if len(candidates) != 1:
                        raise ValueError("directory work has multiple HTML entries; set version.entry: " + ", ".join(candidates))
                    entrypoint = candidates[0]
            elif source.is_file() and source.suffix.lower() in (".html", ".htm"):
                entrypoint = source.name
                if version.get("entry") is not None and version["entry"] != source.name:
                    raise ValueError("version.entry for a single HTML work must name that file")
            else:
                raise ValueError(f"work must be a directory or an HTML file: {source}")
            prepared_versions.append({"name": version_name, "source": source, "entrypoint": entrypoint,
                                      "directory": f"works/{entry_index + 1:02d}/{version_index + 1:02d}",
                                      "fingerprints": _fingerprints(source)})
        prepared.append({"name": name, "versions": prepared_versions})
    text_extensions = {".html", ".htm", ".css", ".js", ".mjs", ".cjs", ".json", ".svg", ".txt", ".md"}
    with temp_workspace(output.parent, ".webfilm-package-") as workspace:
        staged = Path(workspace) / "delivery"
        staged.mkdir()
        public_entries, source_records = [], []
        for entry in prepared:
            public_versions = []
            for version in entry["versions"]:
                target = staged / version["directory"]
                source = version["source"]
                if source.is_dir():
                    if staged.resolve().is_relative_to(source):
                        raise ValueError("configured temporary workspace must be outside each source work directory")
                    shutil.copytree(source, target)
                else:
                    target.mkdir(parents=True)
                    shutil.copy2(source, target / source.name)
                copied_files = _work_tree(target)
                for fingerprint in version["fingerprints"]:
                    copied = target / fingerprint["relative"]
                    if sha256(copied) != fingerprint["sha256"] or sha256(Path(fingerprint["path"])) != fingerprint["sha256"]:
                        raise RuntimeError(f"work changed during packaging: {fingerprint['path']}")
                public_versions.append({"name": version["name"], "directory": version["directory"],
                                        "entrypoint": version["directory"] + "/" + version["entrypoint"],
                                        "sources": [path.relative_to(target).as_posix() for path in copied_files
                                                    if path.suffix.lower() in text_extensions]})
                source_records.append({"entry": entry["name"], "version": version["name"],
                                       "work": str(source), "files": version["fingerprints"]})
            public_entries.append({"name": entry["name"], "versions": public_versions})
        gallery = {"prompt": prompt, "entries": public_entries}
        embedded = json.dumps(gallery, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        title = html.escape(manifest.get("title", "网页作品展示") if isinstance(manifest.get("title", "网页作品展示"), str) else "网页作品展示")
        page = _PAGE.replace("__TITLE__", title).replace("__DATA__", embedded)
        (staged / "index.html").write_text(page, encoding="utf-8")
        (staged / "README.md").write_text(
            "# 网页作品展示包\n\n打开 index.html 可切换作品与版本。需要源码 fetch、模块脚本或同源资源时，"
            "在本目录运行 `python -m http.server 8000 --bind 127.0.0.1`，再访问 `http://127.0.0.1:8000/`。\n\n"
            "works/ 保留作品原始字节；package.json 记录输入和复制文件哈希。给模型的提示词显示在主页上。\n\n"
            "该目录只生成本地交付包，没有部署、投稿或发布。\n", encoding="utf-8")
        record = {"schema": "webfilm.package.v1", "manifest": {"path": str(manifest_file), "sha256": manifest_hash},
                  "gallery": gallery, "sources": source_records,
                  "outputs": [{"path": path.relative_to(staged).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}
                              for path in _work_tree(staged)]}
        write_json(staged / "package.json", record)
        if sha256(manifest_file) != manifest_hash:
            raise RuntimeError("showcase manifest changed during packaging")
        _free_directory(output)
        output.mkdir(parents=True, exist_ok=True)
        for path in staged.iterdir():
            path.rename(output / path.name)
    return {"output_dir": str(output), "index": str(output / "index.html"), "identity": record}


def upload_template(output_path):
    """Write an editable upload format with illustrative copy and no platform rules."""
    output = Path(output_path).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing upload copy: {output}")
    text = """# 投稿文案模板

这是文案格式，示例均为虚构示意，请用实际作品信息替换。文件没有发布，未引用或推定 B 站的平台规则。

## 标题

占位：〈主题〉｜〈作品特点〉

格式示例：让一张网页动起来｜三种交互设计对比

## 简介

占位：这期展示〈实际主题〉。使用〈真实工具与版本〉制作，比较〈真实版本差异〉。

补充〈作品入口、源码地址或说明〉、〈实际素材来源与授权〉、〈实际使用的 AI 工具与用途〉。

格式示例：这期展示一个虚构网页练习的三个版本，比较布局、动效和操作方式。源码与演示地址：〈填写〉。

## 标签

占位：〈主题〉、〈实际工具〉、〈作品类型〉

格式示例：网页设计、前端、创作过程

## 置顶评论

占位：你最喜欢〈实际选项〉中的哪一个？〈实际作品地址或补充说明〉。

格式示例：你更喜欢这个虚构练习的第一版还是第三版？版本区别与源码：〈填写〉。

## 投稿声明

请按实际情况填写：

- 作者与参与者：〈填写真实信息〉。
- 作品、声音、图片与代码来源：〈填写实际来源及授权〉。
- AI 参与范围：〈如实填写生成、修改、配音或辅助环节〉。
- 引用与改编：〈填写实际引用内容、原作者与链接；没有则写无〉。
- 本文案与成片的最终检查：〈填写真实检查结果〉。

格式示例：本片为虚构练习示意。页面代码由〈工具〉辅助生成，作者完成〈实际修改〉；旁白来源为〈填写〉；外部素材及授权为〈填写〉。
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(text)
    return output
