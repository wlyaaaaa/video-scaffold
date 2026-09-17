"""Create a clean video project transactionally; never copy source workspaces/secrets."""

from pathlib import Path
import os
import shutil
import sys
import tempfile
from pipeline.io_utils import safe_print as print

HERE = str(Path(__file__).resolve().parent)
UNIVERSAL = [
    "config.py",
    "run.ps1",
    "run_demo.py",
    "init_project.py",
    "requirements.txt",
    "requirements.lock.txt",
    "README.md",
    "AGENTS.md",
    ".gitignore",
    "pipeline",
    "templates",
    "docs",
    "background",
    "examples",
    "tests",
    "v2lib.py",
]
WORKSPACE = [
    "assets",
    "scripts",
    "raw_audio",
    "srt_data",
    "scene_html",
    "rendered",
    "output",
]


def init(target):
    target = Path(target).resolve()
    source = Path(HERE)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise RuntimeError(f"refusing nonempty project target: {target}")
    missing = [name for name in UNIVERSAL if not (source / name).exists()]
    if missing:
        raise RuntimeError("incomplete scaffold source: " + ", ".join(missing))
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".video-init-", dir=target.parent
    ) as temporary:
        staged = Path(temporary) / "project"
        staged.mkdir()
        for name in UNIVERSAL:
            src = source / name
            dst = staged / name
            if src.is_dir():
                ignored = ["__pycache__", ".pytest_cache", "*.pyc"]
                if name == "templates":
                    ignored += ["cover_md.html", "cover_md_43.html"]
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*ignored))
            else:
                shutil.copy2(src, dst)
        for name in WORKSPACE:
            (staged / name).mkdir(exist_ok=True)
        (staged / "secret_local.py").write_text(
            '# GIT-IGNORED. Empty does not override an environment key.\nFISH_API_KEY = ""\n',
            encoding="utf-8",
        )
        if target.exists():
            target.rmdir()  # Fails safely if a concurrent writer filled it.
        os.replace(staged, target)
    print(f"[init] new project ready at {target}")
    print(r"       next: run: pwsh -File .\run.ps1 test")
    print(r"       then: run: pwsh -File .\run.ps1 doctor")
    print(r"       optional later: pwsh -File .\run.ps1 doctor-local / doctor-live")
    return str(target)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    args = parser.parse_args()
    init(args.target)
