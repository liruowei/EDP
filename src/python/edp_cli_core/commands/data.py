from __future__ import annotations

import argparse
from pathlib import Path

from ..common import ChineseArgumentParser, ForwardArg, add_python_arg, set_script_runner


def add_data_area(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    data = subparsers.add_parser("data", help="统一行情数据维护命令。")
    commands = data.add_subparsers(
        dest="command",
        metavar="commands",
        required=True,
        parser_class=ChineseArgumentParser,
    )
    add_data_update_parser(commands)
    add_data_update_factors_parser(commands)

def add_data_update_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("update", help="补齐 EDP DuckDB 未复权日线行情。")
    add_python_arg(parser)
    parser.add_argument("--end-date", default="", help="结束日期 YYYYMMDD；留空使用今天。")
    parser.add_argument("--start-date", default="", help="开始日期 YYYYMMDD；留空使用数据配置。")
    parser.add_argument("--max-stocks", type=int, default=None, help="调试用；留空表示全市场。")
    parser.add_argument("--refresh-universe", action="store_true", help="刷新股票池。")
    parser.add_argument("--config", type=Path, default=None, help="数据配置文件；留空使用默认全市场配置。")
    parser.add_argument("--progress-every", type=int, default=None, help="每批处理多少只股票打印一次进度。")
    set_script_runner(
        parser,
        ["research", "market_data", "update_market_data.py"],
        [
            ForwardArg("end_date", "--end-date", "non_empty"),
            ForwardArg("start_date", "--start-date", "non_empty"),
            ForwardArg("max_stocks", "--max-stocks", "optional"),
            ForwardArg("refresh_universe", "--refresh-universe", "flag"),
            ForwardArg("config", "--config", "optional"),
            ForwardArg("progress_every", "--progress-every", "optional"),
        ],
    )

def add_data_update_factors_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("update-factors", help="更新 EDP DuckDB 复权因子。")
    add_python_arg(parser)
    parser.add_argument("--end-date", default="", help="结束日期 YYYYMMDD；留空使用今天。")
    parser.add_argument("--factor-types", default="", help="逗号分隔 qfq/hfq；留空使用配置。")
    parser.add_argument("--max-stocks", type=int, default=None, help="调试用；留空表示全市场。")
    parser.add_argument("--refresh-universe", action="store_true", help="刷新股票池。")
    parser.add_argument("--config", type=Path, default=None, help="数据配置文件；留空使用默认全市场配置。")
    parser.add_argument("--progress-every", type=int, default=None, help="每批处理多少只股票打印一次进度。")
    set_script_runner(
        parser,
        ["research", "market_data", "update_market_factors.py"],
        [
            ForwardArg("end_date", "--end-date", "non_empty"),
            ForwardArg("factor_types", "--factor-types", "non_empty"),
            ForwardArg("max_stocks", "--max-stocks", "optional"),
            ForwardArg("refresh_universe", "--refresh-universe", "flag"),
            ForwardArg("config", "--config", "optional"),
            ForwardArg("progress_every", "--progress-every", "optional"),
        ],
    )
