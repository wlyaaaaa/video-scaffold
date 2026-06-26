# -*- coding: utf-8 -*-
"""
Scaffold a fresh video project from this universal template.

    python init_project.py <target_dir>

Copies the reusable parts (config, pipeline, templates, docs, background system,
examples, runner) into <target_dir>, creates the empty per-project workspace
folders, and drops a secret_local.py stub for the API key. The shared 4K
background is copied so the new project renders out of the box.
"""

import os
import sys
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))

UNIVERSAL = ["config.py", "run_demo.py", "init_project.py", "requirements.txt",
             "README.md", ".gitignore", "pipeline", "templates", "docs",
             "background", "examples"]
WORKSPACE = ["assets", "scripts", "raw_audio", "srt_data",
             "scene_html", "rendered", "output"]


def init(target):
    target = os.path.abspath(target)
    if os.path.exists(target) and os.listdir(target):
        print(f"[init] refusing: {target} exists and is not empty")
        sys.exit(1)
    os.makedirs(target, exist_ok=True)

    for item in UNIVERSAL:
        src = os.path.join(HERE, item)
        if not os.path.exists(src):
            continue
        dst = os.path.join(target, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, dst)

    for d in WORKSPACE:
        os.makedirs(os.path.join(target, d), exist_ok=True)

    with open(os.path.join(target, "secret_local.py"), "w", encoding="utf-8") as f:
        f.write('# GIT-IGNORED. Put your key here.\nFISH_API_KEY = ""\n')

    print(f"[init] new project ready at {target}")
    print("       next: set secret_local.py, drop art in assets/, run python run_demo.py")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python init_project.py <target_dir>")
        sys.exit(1)
    init(sys.argv[1])
