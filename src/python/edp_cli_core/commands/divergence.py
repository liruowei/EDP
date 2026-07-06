from __future__ import annotations

import argparse
from pathlib import Path

from ..common import ChineseArgumentParser, ForwardArg, add_python_arg, set_script_runner
from .shared import common_rank_forward_args


def add_divergence_area(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    divergence = subparsers.add_parser(
        "divergence",
        help="分歧转向点研究命令。",
    )
    commands = divergence.add_subparsers(
        dest="command",
        metavar="commands",
        required=True,
        parser_class=ChineseArgumentParser,
    )
    add_divergence_daily_parser(commands)
    add_divergence_build_parser(commands)
    add_divergence_rank_parser(commands)
    add_divergence_breadth_parser(commands)
    add_divergence_dashboard_parser(commands)
    add_divergence_intraday_parser(commands)

def add_divergence_daily_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "daily",
        help="生成每日分歧转向点 EDP 看板。",
    )
    add_python_arg(parser)
    set_script_runner(
        parser,
        ["research", "divergence_turning_point", "run_daily_divergence_turning.py"],
        [ForwardArg("python", "--python")],
    )

def add_divergence_build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("build", help="构建分歧转向点特征面板。")
    add_python_arg(parser)
    parser.add_argument("--input", type=Path, default=None, help="已有题材面板 CSV；设置后跳过远程拉取。")
    parser.add_argument("--theme-source", default="concept_ths")
    parser.add_argument("--start-date", default="20240101")
    parser.add_argument("--end-date", default="", help="结束日期，留空使用脚本默认值。")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--horizons", default="", help="逗号分隔的多个窗口，会覆盖 --horizon。")
    parser.add_argument("--top-quantile", type=float, default=0.8)
    parser.add_argument("--min-forward-runup", type=float, default=0.04)
    parser.add_argument("--max-entry-ret-5d-rank-pct", type=float, default=0.70)
    parser.add_argument("--min-history-rows", type=int, default=160)
    parser.add_argument("--min-amount", type=float, default=0.0)
    parser.add_argument("--max-themes", type=int, default=0)
    parser.add_argument("--theme-names", default="")
    parser.add_argument("--theme-filter", default="")
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--refresh-list", action="store_true")
    parser.add_argument("--refresh-history", action="store_true")
    parser.add_argument("--keep-unlabeled-tail", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    set_script_runner(
        parser,
        ["research", "divergence_turning_point", "build_divergence_turning_dataset.py"],
        [
            ForwardArg("input", "--input", "optional"),
            ForwardArg("theme_source", "--theme-source"),
            ForwardArg("start_date", "--start-date"),
            ForwardArg("end_date", "--end-date", "non_empty"),
            ForwardArg("horizon", "--horizon"),
            ForwardArg("horizons", "--horizons", "non_empty"),
            ForwardArg("top_quantile", "--top-quantile"),
            ForwardArg("min_forward_runup", "--min-forward-runup"),
            ForwardArg("max_entry_ret_5d_rank_pct", "--max-entry-ret-5d-rank-pct"),
            ForwardArg("min_history_rows", "--min-history-rows"),
            ForwardArg("min_amount", "--min-amount"),
            ForwardArg("max_themes", "--max-themes"),
            ForwardArg("theme_names", "--theme-names", "non_empty"),
            ForwardArg("theme_filter", "--theme-filter", "non_empty"),
            ForwardArg("cache_dir", "--cache-dir", "optional"),
            ForwardArg("output", "--output", "optional"),
            ForwardArg("refresh_list", "--refresh-list", "flag"),
            ForwardArg("refresh_history", "--refresh-history", "flag"),
            ForwardArg("keep_unlabeled_tail", "--keep-unlabeled-tail", "flag"),
            ForwardArg("sleep_seconds", "--sleep-seconds"),
        ],
    )

def add_divergence_rank_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("rank", help="分歧转向点 walk-forward 排名。")
    add_python_arg(parser)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--initial-train-days", type=int, default=252)
    parser.add_argument("--refit-every-days", type=int, default=1)
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--model", choices=["logistic", "hgb"], default="logistic")
    parser.add_argument("--flow-low-pp", type=float, default=5.0)
    parser.add_argument("--flow-high-pp", type=float, default=10.0)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--latest-output", type=Path, default=None)
    parser.add_argument("--latest-output-limit", type=int, default=0, help="latest 输出行数，0 表示输出全部最新候选。")
    parser.add_argument("--summary-output", type=Path, default=None)
    set_script_runner(
        parser,
        ["research", "divergence_turning_point", "walk_forward_turning_rank.py"],
        [
            ForwardArg("input", "--input", "optional"),
            ForwardArg("horizon", "--horizon"),
            ForwardArg("initial_train_days", "--initial-train-days"),
            ForwardArg("refit_every_days", "--refit-every-days"),
            ForwardArg("top_n", "--top-n"),
            ForwardArg("model", "--model"),
            ForwardArg("flow_low_pp", "--flow-low-pp"),
            ForwardArg("flow_high_pp", "--flow-high-pp"),
            ForwardArg("output", "--output", "optional"),
            ForwardArg("latest_output", "--latest-output", "optional"),
            ForwardArg("latest_output_limit", "--latest-output-limit"),
            ForwardArg("summary_output", "--summary-output", "optional"),
        ],
    )

def add_divergence_breadth_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("latest-breadth", help="为分歧转向候选叠加当前宽度快照。")
    add_python_arg(parser)
    parser.add_argument("--rank-input", type=Path, default=None)
    parser.add_argument("--theme-source", choices=["concept_ths", "industry_ths"], default="concept_ths")
    parser.add_argument("--top-n", type=int, default=0, help="宽度复核候选数量，0 表示按 rank 输入全部复核。")
    parser.add_argument("--sleep-seconds", type=float, default=0.35)
    parser.add_argument("--skip-summary", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--history-output", type=Path, default=None)
    parser.add_argument("--no-history", action="store_true")
    set_script_runner(
        parser,
        ["research", "divergence_turning_point", "build_latest_breadth_snapshot.py"],
        [
            ForwardArg("rank_input", "--rank-input", "optional"),
            ForwardArg("theme_source", "--theme-source"),
            ForwardArg("top_n", "--top-n"),
            ForwardArg("sleep_seconds", "--sleep-seconds"),
            ForwardArg("skip_summary", "--skip-summary", "flag"),
            ForwardArg("output", "--output", "optional"),
            ForwardArg("history_output", "--history-output", "optional"),
            ForwardArg("no_history", "--no-history", "flag"),
        ],
    )

def add_divergence_dashboard_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("dashboard", help="生成分歧转向点看板。")
    add_python_arg(parser)
    parser.add_argument("--breadth-input", type=Path, default=None)
    parser.add_argument("--summary-input", type=Path, default=None)
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=None)
    set_script_runner(
        parser,
        ["research", "divergence_turning_point", "build_divergence_turning_dashboard.py"],
        [
            ForwardArg("breadth_input", "--breadth-input", "optional"),
            ForwardArg("summary_input", "--summary-input", "optional"),
            ForwardArg("top_n", "--top-n"),
            ForwardArg("output_dir", "--output-dir", "optional"),
        ],
    )

def add_divergence_intraday_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("intraday", help="盘中循环刷新分歧转向点宽度快照。")
    add_python_arg(parser)
    set_script_runner(
        parser,
        ["research", "divergence_turning_point", "run_intraday_divergence_monitor.py"],
        [],
    )
