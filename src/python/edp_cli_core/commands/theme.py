from __future__ import annotations

import argparse
from pathlib import Path

from ..common import ChineseArgumentParser, ForwardArg, add_python_arg, set_script_runner
from .shared import common_rank_forward_args


def add_theme_area(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    theme = subparsers.add_parser("theme", help="题材轮动分析命令。")
    commands = theme.add_subparsers(
        dest="command",
        metavar="commands",
        required=True,
        parser_class=ChineseArgumentParser,
    )
    add_theme_daily_parser(commands)
    add_theme_build_parser(commands)
    add_theme_rank_parser(commands)
    add_theme_breadth_parser(commands)
    add_theme_dashboard_parser(commands)

def add_theme_dataset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--theme-source",
        choices=["concept_em", "concept_ths", "industry_em", "industry_ths"],
        default="concept_ths",
        help="题材数据源。",
    )
    parser.add_argument("--start-date", default="20240101", help="开始日期，格式 YYYYMMDD。")
    parser.add_argument("--end-date", default="", help="结束日期，格式 YYYYMMDD；留空使用脚本默认值。")
    parser.add_argument("--horizon", type=int, default=None, help="单个预测窗口，会覆盖 --horizons。")
    parser.add_argument("--horizons", default="1,3,5", help="逗号分隔的预测窗口。")
    parser.add_argument("--top-quantile", type=float, default=0.8, help="强势题材标签分位阈值。")
    parser.add_argument("--min-history-rows", type=int, default=120, help="每个题材最少历史行数。")
    parser.add_argument("--min-amount", type=float, default=0.0, help="最低成交额过滤阈值。")
    parser.add_argument("--max-themes", type=int, default=0, help="最多拉取多少个题材，0 表示不限制。")
    parser.add_argument("--theme-names", default="", help="逗号分隔题材名；设置后跳过自动列表拉取。")
    parser.add_argument("--theme-filter", default="", help="按正则过滤题材名称。")
    parser.add_argument("--cache-dir", type=Path, default=None, help="AkShare 缓存目录。")
    parser.add_argument("--output", type=Path, default=None, help="输出 CSV。")
    parser.add_argument("--refresh-list", action="store_true", help="刷新题材列表缓存。")
    parser.add_argument("--refresh-history", action="store_true", help="刷新题材历史缓存。")
    parser.add_argument("--keep-unlabeled-tail", action="store_true", help="保留无未来标签的最新尾部。")
    parser.add_argument("--sleep-seconds", type=float, default=0.25, help="AkShare 请求间隔秒数。")

def add_theme_daily_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("daily", help="生成每日题材 EDP 看板。")
    add_python_arg(parser)
    set_script_runner(
        parser,
        ["research", "theme_rotation", "run_daily_theme_dashboard.py"],
        [ForwardArg("python", "--python")],
    )

def add_theme_build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("build", help="构建题材轮动特征面板。")
    add_python_arg(parser)
    add_theme_dataset_args(parser)
    set_script_runner(
        parser,
        ["research", "theme_rotation", "build_theme_dataset.py"],
        [
            ForwardArg("theme_source", "--theme-source"),
            ForwardArg("start_date", "--start-date"),
            ForwardArg("end_date", "--end-date", "non_empty"),
            ForwardArg("horizon", "--horizon", "optional"),
            ForwardArg("horizons", "--horizons"),
            ForwardArg("top_quantile", "--top-quantile"),
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

def add_theme_rank_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("rank", help="基于题材面板生成 live 排名。")
    add_python_arg(parser)
    parser.add_argument("--input", type=Path, default=None, help="输入题材面板 CSV。")
    parser.add_argument("--horizon", type=int, choices=[1, 3, 5], default=3)
    parser.add_argument("--top-pct", type=int, default=20)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--model", choices=["logistic", "hgb"], default="logistic")
    parser.add_argument("--predict-date", default="latest")
    parser.add_argument("--flow-lookback-dates", type=int, default=6)
    parser.add_argument("--flow-low-pp", type=float, default=5.0)
    parser.add_argument("--flow-high-pp", type=float, default=10.0)
    parser.add_argument("--output", type=Path, default=None, help="完整排名输出 CSV。")
    parser.add_argument("--latest-output", type=Path, default=None, help="latest 排名输出 CSV。")
    set_script_runner(
        parser,
        ["research", "theme_rotation", "predict_live_rank.py"],
        common_rank_forward_args(),
    )

def add_theme_breadth_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("latest-breadth", help="为最新题材排名叠加同花顺热度快照。")
    add_python_arg(parser)
    parser.add_argument("--rank-input", type=Path, default=None, help="latest rank CSV。")
    parser.add_argument("--theme-source", choices=["concept_ths", "industry_ths"], default="concept_ths")
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    parser.add_argument("--skip-summary", action="store_true", help="跳过同花顺概念摘要。")
    parser.add_argument("--output", type=Path, default=None, help="输出 CSV。")
    parser.add_argument("--history-output", type=Path, default=None, help="宽度快照历史 CSV。")
    parser.add_argument("--no-history", action="store_true", help="不更新宽度快照历史。")
    set_script_runner(
        parser,
        ["research", "theme_rotation", "build_latest_breadth_snapshot.py"],
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

def add_theme_dashboard_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("dashboard", help="根据 1/3/5 日排名生成题材看板。")
    add_python_arg(parser)
    add_theme_dashboard_args(parser)
    set_script_runner(
        parser,
        ["research", "theme_rotation", "build_edp_daily_dashboard.py"],
        theme_dashboard_forward_args(),
    )

def add_theme_dashboard_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rank-1d", type=Path, default=None)
    parser.add_argument("--rank-3d", type=Path, default=None)
    parser.add_argument("--rank-5d", type=Path, default=None)
    parser.add_argument("--breadth-input", type=Path, default=None)
    parser.add_argument("--skip-breadth", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--mainline-rank", type=int, default=20)
    parser.add_argument("--launch-rank-1d", type=int, default=20)
    parser.add_argument("--launch-rank-3d", type=int, default=45)
    parser.add_argument("--crowded-rank-1d", type=int, default=20)
    parser.add_argument("--crowded-rank-mid", type=int, default=70)
    parser.add_argument("--cooling-rank-3d", type=int, default=60)
    parser.add_argument("--prob-floor", type=float, default=0.55)
    parser.add_argument("--flow-up-pp", type=float, default=0.5)
    parser.add_argument("--flow-down-pp", type=float, default=-1.0)
    parser.add_argument("--momentum-down-pp", type=float, default=-0.5)
    parser.add_argument("--weight-1d", type=float, default=0.2)
    parser.add_argument("--weight-3d", type=float, default=0.5)
    parser.add_argument("--weight-5d", type=float, default=0.3)

def theme_dashboard_forward_args() -> list[ForwardArg]:
    return [
        ForwardArg("rank_1d", "--rank-1d", "optional"),
        ForwardArg("rank_3d", "--rank-3d", "optional"),
        ForwardArg("rank_5d", "--rank-5d", "optional"),
        ForwardArg("breadth_input", "--breadth-input", "optional"),
        ForwardArg("skip_breadth", "--skip-breadth", "flag"),
        ForwardArg("output_dir", "--output-dir", "optional"),
        ForwardArg("top_n", "--top-n"),
        ForwardArg("mainline_rank", "--mainline-rank"),
        ForwardArg("launch_rank_1d", "--launch-rank-1d"),
        ForwardArg("launch_rank_3d", "--launch-rank-3d"),
        ForwardArg("crowded_rank_1d", "--crowded-rank-1d"),
        ForwardArg("crowded_rank_mid", "--crowded-rank-mid"),
        ForwardArg("cooling_rank_3d", "--cooling-rank-3d"),
        ForwardArg("prob_floor", "--prob-floor"),
        ForwardArg("flow_up_pp", "--flow-up-pp"),
        ForwardArg("flow_down_pp", "--flow-down-pp"),
        ForwardArg("momentum_down_pp", "--momentum-down-pp"),
        ForwardArg("weight_1d", "--weight-1d"),
        ForwardArg("weight_3d", "--weight-3d"),
        ForwardArg("weight_5d", "--weight-5d"),
    ]
