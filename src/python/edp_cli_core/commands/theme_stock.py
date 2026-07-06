from __future__ import annotations

import argparse
from pathlib import Path

from ..common import ChineseArgumentParser, ForwardArg, add_python_arg, set_script_runner
from .shared import common_rank_forward_args


def add_theme_stock_area(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    theme_stock = subparsers.add_parser(
        "theme-stock",
        help="题材内部个股排名命令。",
    )
    commands = theme_stock.add_subparsers(
        dest="command",
        metavar="commands",
        required=True,
        parser_class=ChineseArgumentParser,
    )
    add_theme_stock_daily_parser(commands)
    add_theme_stock_build_parser(commands)
    add_theme_stock_rank_parser(commands)
    add_theme_stock_dashboard_parser(commands)
    add_theme_stock_diagnose_api_parser(commands)
    add_theme_stock_list_themes_parser(commands)

def add_theme_stock_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--theme-source",
        choices=["concept_em", "concept_ths", "industry_em"],
        default="concept_em",
        help="题材/行业成分股数据源。",
    )
    parser.add_argument("--theme-names", default="国家大基金持股", help="逗号分隔的题材或行业名称。")
    parser.add_argument("--theme-code-map", default="", help='题材名称到东方财富板块代码的映射，如 "国家大基金持股=BK1234"。')
    parser.add_argument("--theme-code-map-file", type=Path, default=None, help="题材代码映射 CSV。")
    parser.add_argument("--theme-code-cache", type=Path, default=None, help="题材代码本地缓存 CSV。")
    parser.add_argument("--start-date", default="20240101", help="开始日期，格式 YYYYMMDD。")
    parser.add_argument("--end-date", default="", help="结束日期，格式 YYYYMMDD；留空使用脚本默认值。")
    parser.add_argument("--horizons", default="1,3,5", help="逗号分隔的预测窗口。")
    parser.add_argument("--top-quantile", type=float, default=0.8, help="题材内强势标签分位阈值。")
    parser.add_argument("--min-history-rows", type=int, default=80, help="最少历史行数。")
    parser.add_argument("--min-amount", type=float, default=0.0, help="最低成交额过滤阈值。")
    parser.add_argument("--max-stocks-per-theme", type=int, default=0, help="每个题材最多取多少只股票，0 表示不限制。")
    parser.add_argument("--adjust", default="", choices=["", "qfq", "hfq"], help="个股复权方式。")
    parser.add_argument("--keep-unlabeled-tail", action="store_true", help="保留无未来标签的最新尾部。")
    parser.add_argument("--refresh-constituents", action="store_true", help="刷新成分股列表。")
    parser.add_argument("--refresh-history", action="store_true", help="刷新个股和题材历史。")
    parser.add_argument("--fetch-attempts", type=int, default=3, help="远程拉取失败后的最大尝试次数。")
    parser.add_argument("--retry-base-seconds", type=float, default=2.0, help="重试退避基础秒数。")
    parser.add_argument("--sleep-seconds", type=float, default=0.2, help="AkShare 请求间隔秒数。")
    parser.add_argument("--remote-request-interval", type=float, default=1.2, help="直连远程接口最小间隔秒数。")
    parser.add_argument("--em-hosts", default="79.push2.eastmoney.com,29.push2.eastmoney.com", help="东方财富题材列表 host。")
    parser.add_argument("--em-max-pages", type=int, default=50, help="东方财富题材列表最多扫描页数。")
    parser.add_argument("--allow-akshare-name-fallback", action="store_true", help="东方财富解析失败后允许 AkShare 名称接口兜底。")
    parser.add_argument("--cache-dir", type=Path, default=None, help="AkShare 缓存目录。")
    parser.add_argument("--membership-output", type=Path, default=None, help="成分股快照输出 CSV。")
    parser.add_argument("--output", type=Path, default=None, help="输出 CSV。")

def add_theme_stock_daily_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "daily",
        help="生成每日题材内部个股 EDP 看板。",
    )
    add_python_arg(parser)
    set_script_runner(
        parser,
        ["research", "theme_stock_rotation", "run_daily_theme_stock_dashboard.py"],
        [ForwardArg("python", "--python")],
    )

def add_theme_stock_build_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("build", help="构建题材内部个股特征面板。")
    add_python_arg(parser)
    add_theme_stock_common_args(parser)
    set_script_runner(
        parser,
        ["research", "theme_stock_rotation", "build_theme_stock_dataset.py"],
        theme_stock_build_forward_args(),
    )

def add_theme_stock_rank_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("rank", help="基于题材个股面板生成 live 排名。")
    add_python_arg(parser)
    parser.add_argument("--input", type=Path, default=None, help="输入题材个股面板 CSV。")
    parser.add_argument("--horizon", type=int, choices=[1, 3, 5], default=3)
    parser.add_argument("--target", choices=["top", "outperform"], default="top")
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
        ["research", "theme_stock_rotation", "predict_theme_stock_live_rank.py"],
        common_rank_forward_args(extra=[ForwardArg("target", "--target")]),
    )

def add_theme_stock_dashboard_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser("dashboard", help="根据 1/3/5 日题材个股排名生成看板。")
    add_python_arg(parser)
    add_theme_stock_dashboard_args(parser)
    set_script_runner(
        parser,
        ["research", "theme_stock_rotation", "build_edp_theme_stock_dashboard.py"],
        theme_stock_dashboard_forward_args(),
    )

def add_theme_stock_dashboard_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rank-1d", type=Path, default=None)
    parser.add_argument("--rank-3d", type=Path, default=None)
    parser.add_argument("--rank-5d", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--leader-rank", type=int, default=5)
    parser.add_argument("--launch-rank-1d", type=int, default=5)
    parser.add_argument("--launch-rank-3d", type=int, default=12)
    parser.add_argument("--crowded-rank-1d", type=int, default=5)
    parser.add_argument("--crowded-rank-mid", type=int, default=15)
    parser.add_argument("--cooling-rank-3d", type=int, default=12)
    parser.add_argument("--prob-floor", type=float, default=0.55)
    parser.add_argument("--flow-up-pp", type=float, default=0.5)
    parser.add_argument("--flow-down-pp", type=float, default=-1.0)
    parser.add_argument("--momentum-down-pp", type=float, default=-0.5)
    parser.add_argument("--catchup-ret-pct-max", type=float, default=0.55)
    parser.add_argument("--weight-1d", type=float, default=0.2)
    parser.add_argument("--weight-3d", type=float, default=0.5)
    parser.add_argument("--weight-5d", type=float, default=0.3)

def add_theme_stock_diagnose_api_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "diagnose-api",
        help="诊断东方财富/AkShare 题材接口连通性。",
    )
    add_python_arg(parser, purpose="执行诊断脚本")
    parser.add_argument("--theme-name", default="国家大基金持股", help="要测试的题材名称。")
    parser.add_argument("--theme-code", default="", help="已知东方财富板块代码，如 BK1234。")
    parser.add_argument("--timeout", type=float, default=15.0, help="单次请求超时时间，单位秒。")
    parser.add_argument("--max-pages", type=int, default=50, help="题材列表最多扫描页数。")
    parser.add_argument("--request-interval", type=float, default=1.2, help="诊断请求之间的最小间隔秒数。")
    parser.add_argument("--skip-akshare", action="store_true", help="跳过 AkShare 包装接口测试。")
    set_script_runner(
        parser,
        ["research", "theme_stock_rotation", "diagnose_eastmoney_api.py"],
        [
            ForwardArg("theme_name", "--theme-name"),
            ForwardArg("theme_code", "--theme-code", "non_empty"),
            ForwardArg("timeout", "--timeout"),
            ForwardArg("max_pages", "--max-pages"),
            ForwardArg("request_interval", "--request-interval"),
            ForwardArg("skip_akshare", "--skip-akshare", "flag"),
        ],
    )

def add_theme_stock_list_themes_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "list-themes",
        help="列出题材/行业名称，方便确认真实名称。",
    )
    add_python_arg(parser)
    parser.add_argument("--theme-source", choices=["concept_em", "concept_ths", "industry_em"], default="concept_ths", help="题材/行业名称来源。")
    parser.add_argument("--keyword", default="", help="按关键词过滤名称。")
    parser.add_argument("--top-n", type=int, default=80, help="最多输出多少行。")
    parser.add_argument("--cache-dir", type=Path, default=None, help="AkShare 名称列表缓存目录。")
    parser.add_argument("--refresh-list", action="store_true", help="刷新名称列表缓存。")
    set_script_runner(
        parser,
        ["research", "theme_stock_rotation", "list_theme_names.py"],
        [
            ForwardArg("theme_source", "--theme-source"),
            ForwardArg("keyword", "--keyword", "non_empty"),
            ForwardArg("top_n", "--top-n"),
            ForwardArg("cache_dir", "--cache-dir", "optional"),
            ForwardArg("refresh_list", "--refresh-list", "flag"),
        ],
    )

def theme_stock_dashboard_forward_args() -> list[ForwardArg]:
    return [
        ForwardArg("rank_1d", "--rank-1d", "optional"),
        ForwardArg("rank_3d", "--rank-3d", "optional"),
        ForwardArg("rank_5d", "--rank-5d", "optional"),
        ForwardArg("output_dir", "--output-dir", "optional"),
        ForwardArg("top_n", "--top-n"),
        ForwardArg("leader_rank", "--leader-rank"),
        ForwardArg("launch_rank_1d", "--launch-rank-1d"),
        ForwardArg("launch_rank_3d", "--launch-rank-3d"),
        ForwardArg("crowded_rank_1d", "--crowded-rank-1d"),
        ForwardArg("crowded_rank_mid", "--crowded-rank-mid"),
        ForwardArg("cooling_rank_3d", "--cooling-rank-3d"),
        ForwardArg("prob_floor", "--prob-floor"),
        ForwardArg("flow_up_pp", "--flow-up-pp"),
        ForwardArg("flow_down_pp", "--flow-down-pp"),
        ForwardArg("momentum_down_pp", "--momentum-down-pp"),
        ForwardArg("catchup_ret_pct_max", "--catchup-ret-pct-max"),
        ForwardArg("weight_1d", "--weight-1d"),
        ForwardArg("weight_3d", "--weight-3d"),
        ForwardArg("weight_5d", "--weight-5d"),
    ]

def theme_stock_build_forward_args() -> list[ForwardArg]:
    return [
        ForwardArg("theme_source", "--theme-source"),
        ForwardArg("theme_names", "--theme-names"),
        ForwardArg("theme_code_map", "--theme-code-map", "non_empty"),
        ForwardArg("theme_code_map_file", "--theme-code-map-file", "optional"),
        ForwardArg("theme_code_cache", "--theme-code-cache", "optional"),
        ForwardArg("start_date", "--start-date"),
        ForwardArg("end_date", "--end-date", "non_empty"),
        ForwardArg("horizons", "--horizons"),
        ForwardArg("top_quantile", "--top-quantile"),
        ForwardArg("min_history_rows", "--min-history-rows"),
        ForwardArg("min_amount", "--min-amount"),
        ForwardArg("max_stocks_per_theme", "--max-stocks-per-theme"),
        ForwardArg("adjust", "--adjust", "non_empty"),
        ForwardArg("keep_unlabeled_tail", "--keep-unlabeled-tail", "flag"),
        ForwardArg("refresh_constituents", "--refresh-constituents", "flag"),
        ForwardArg("refresh_history", "--refresh-history", "flag"),
        ForwardArg("fetch_attempts", "--fetch-attempts"),
        ForwardArg("retry_base_seconds", "--retry-base-seconds"),
        ForwardArg("sleep_seconds", "--sleep-seconds"),
        ForwardArg("remote_request_interval", "--remote-request-interval"),
        ForwardArg("em_hosts", "--em-hosts"),
        ForwardArg("em_max_pages", "--em-max-pages"),
        ForwardArg("allow_akshare_name_fallback", "--allow-akshare-name-fallback", "flag"),
        ForwardArg("cache_dir", "--cache-dir", "optional"),
        ForwardArg("membership_output", "--membership-output", "optional"),
        ForwardArg("output", "--output", "optional"),
    ]
