from __future__ import annotations

import argparse

from ..common import ChineseArgumentParser, ForwardArg, add_python_arg, set_script_runner


def add_low_buy_area(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    low_buy = subparsers.add_parser(
        "low-buy",
        help="强势股分歧后次日低吸策略。",
    )
    commands = low_buy.add_subparsers(
        dest="command",
        metavar="commands",
        required=True,
        parser_class=ChineseArgumentParser,
    )
    add_low_buy_daily_parser(commands)
    add_low_buy_backtest_parser(commands)
    add_low_buy_full_backtest_parser(commands)
    add_low_buy_monitor_parser(commands)

def add_low_buy_daily_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("daily", help="生成次日低吸候选和买点计划。")
    add_python_arg(parser)
    parser.add_argument("--codes", default="", help="逗号分隔股票代码；留空使用配置筛选。")
    parser.add_argument("--end-date", default="", help="结束日期 YYYYMMDD；留空使用配置或最新。")
    set_script_runner(
        parser,
        ["research", "second_day_low_buy", "run_second_day_low_buy.py"],
        [
            ForwardArg("codes", "--codes", "non_empty"),
            ForwardArg("end_date", "--end-date", "non_empty"),
        ],
    )

def add_low_buy_backtest_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("backtest", help="回测次日低吸触发和短线收益。")
    add_python_arg(parser)
    parser.add_argument("--codes", default="", help="逗号分隔股票代码；留空使用配置筛选。")
    parser.add_argument("--end-date", default="", help="结束日期 YYYYMMDD；留空使用配置或最新。")
    set_script_runner(
        parser,
        ["research", "second_day_low_buy", "run_second_day_low_buy.py"],
        [
            ForwardArg("mode", "--mode"),
            ForwardArg("codes", "--codes", "non_empty"),
            ForwardArg("end_date", "--end-date", "non_empty"),
        ],
    )
    parser.set_defaults(mode="backtest")

def add_low_buy_full_backtest_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("full-backtest", help="全市场跨日期样本外回测。")
    add_python_arg(parser)
    parser.add_argument("--max-stocks", type=int, default=None, help="调试用；留空表示配置中的全市场。")
    parser.add_argument("--refresh-universe", action="store_true")
    set_script_runner(
        parser,
        ["research", "second_day_low_buy", "run_full_market_oos_backtest.py"],
        [
            ForwardArg("max_stocks", "--max-stocks", "optional"),
            ForwardArg("refresh_universe", "--refresh-universe", "flag"),
        ],
    )

def add_low_buy_monitor_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("monitor", help="监控全市场次日低吸信号。")
    add_python_arg(parser)
    parser.add_argument("--end-date", default="", help="结束日期 YYYYMMDD；留空使用配置或今天。")
    parser.add_argument("--max-stocks", type=int, default=None, help="调试用；留空表示配置中的全市场。")
    parser.add_argument("--iterations", type=int, default=None, help="循环次数；留空使用配置。")
    parser.add_argument("--interval-seconds", type=int, default=None, help="循环间隔秒数；留空使用配置。")
    parser.add_argument("--refresh-universe", action="store_true")
    set_script_runner(
        parser,
        ["research", "second_day_low_buy", "run_low_buy_monitor.py"],
        [
            ForwardArg("end_date", "--end-date", "non_empty"),
            ForwardArg("max_stocks", "--max-stocks", "optional"),
            ForwardArg("iterations", "--iterations", "optional"),
            ForwardArg("interval_seconds", "--interval-seconds", "optional"),
            ForwardArg("refresh_universe", "--refresh-universe", "flag"),
        ],
    )
