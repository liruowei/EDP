from __future__ import annotations

import argparse
from pathlib import Path

from .commands.data import add_data_area
from .commands.divergence import add_divergence_area
from .commands.low_buy import add_low_buy_area
from .commands.strategy import add_strategy_area
from .commands.theme import add_theme_area
from .commands.theme_stock import add_theme_stock_area
from .common import ChineseArgumentParser
from .runtime import find_repo_root
from .shell import run_menu, run_status
from .version import VERSION


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = ChineseArgumentParser(
        prog="edp",
        description="EDP 研究工作流命令行工具。直接运行 edp 会显示菜单引导。",
    )
    parser.set_defaults(func=run_menu)
    parser.add_argument("--version", action="version", version=f"edp {VERSION}")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=find_repo_root(),
        help="EDP 仓库根目录，默认自动识别当前检出的 EDP 项目。",
    )
    subparsers = parser.add_subparsers(
        dest="area",
        metavar="commands",
        required=False,
        parser_class=ChineseArgumentParser,
    )

    menu = subparsers.add_parser("menu", help="显示 EDP 工作流菜单引导。")
    menu.set_defaults(func=run_menu)

    status = subparsers.add_parser("status", help="显示本地 EDP 工作流状态。")
    status.set_defaults(func=run_status)

    add_theme_area(subparsers)
    add_theme_stock_area(subparsers)
    add_divergence_area(subparsers)
    add_strategy_area(subparsers)
    add_data_area(subparsers)
    add_low_buy_area(subparsers)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
