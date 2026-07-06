from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ForwardArg:
    name: str
    flag: str
    mode: str = "value"


class ChineseArgumentParser(argparse.ArgumentParser):
    def format_usage(self) -> str:
        return chinese_argparse_text(super().format_usage())

    def format_help(self) -> str:
        return chinese_argparse_text(super().format_help())


def chinese_argparse_text(text: str) -> str:
    replacements = {
        "usage:": "用法:",
        "positional arguments:": "位置参数:",
        "options:": "选项:",
        "commands:": "命令:",
        "show this help message and exit": "显示帮助信息并退出",
        "show program's version number and exit": "显示版本号并退出",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def add_python_arg(parser: argparse.ArgumentParser, purpose: str = "执行研究脚本") -> None:
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help=f"用于{purpose}的 Python 解释器。",
    )


def set_script_runner(
    parser: argparse.ArgumentParser,
    script_parts: list[str],
    forward_args: list[ForwardArg],
) -> None:
    from .runtime import run_script

    parser.set_defaults(
        func=run_script,
        script_parts=script_parts,
        forward_args=forward_args,
    )
