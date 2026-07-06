from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .common import ForwardArg


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "research").exists():
            return parent
    return Path.cwd()

def run_script(args: argparse.Namespace) -> int:
    script = args.repo_root.joinpath(*args.script_parts)
    if not script.exists():
        return missing_script(script)
    command = [str(args.python), str(script)]
    append_forwarded_args(command, args, args.forward_args)
    return run_command(command, args.repo_root)

def append_forwarded_args(
    command: list[str],
    args: argparse.Namespace,
    specs: list[ForwardArg],
) -> None:
    for spec in specs:
        value = getattr(args, spec.name)
        if spec.mode == "flag":
            if value:
                command.append(spec.flag)
            continue
        if spec.mode == "optional" and value is None:
            continue
        if spec.mode == "non_empty" and (value is None or value == ""):
            continue
        command.extend([spec.flag, str(value)])

def run_command(command: list[str], cwd: Path) -> int:
    print(">>> " + " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=cwd)
    return completed.returncode

def missing_script(script: Path) -> int:
    print(
        f"缺少脚本：{script}\n"
        "请在 EDP 仓库根目录运行，或传入 --repo-root C:\\path\\to\\EDP。",
        file=sys.stderr,
    )
    return 2
