from __future__ import annotations

import argparse

from ..common import ChineseArgumentParser, ForwardArg, add_python_arg, set_script_runner


def add_strategy_area(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    strategy = subparsers.add_parser(
        "strategy",
        help="EDP 策略层回测命令。",
    )
    commands = strategy.add_subparsers(
        dest="command",
        metavar="commands",
        required=True,
        parser_class=ChineseArgumentParser,
    )
    add_strategy_backtest_parser(commands)

def add_strategy_backtest_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "backtest",
        help="按研究配置运行 EDP 分歧转向策略回测。",
    )
    add_python_arg(parser)
    set_script_runner(
        parser,
        ["research", "edp_turning_strategy", "run_edp_turning_strategy_backtest.py"],
        [ForwardArg("python", "--python")],
    )
