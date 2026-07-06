from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from theme_stock_config import load_config, path_value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "运行完整题材内部个股 EDP 工作流：构建数据集、预测 1/3/5 日内部排名，"
            "并生成看板。"
        )
    )
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    return parser.parse_args()


def script_path(script_name: str) -> Path:
    return Path(__file__).resolve().parent / script_name


def run_command(command: list[str]) -> None:
    print(">>> " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def rank_output(data_dir: Path, horizon: int) -> Path:
    return data_dir / f"theme_stock_{horizon}d_live_rank.csv"


def latest_rank_output(data_dir: Path, horizon: int) -> Path:
    return data_dir / f"theme_stock_{horizon}d_live_latest_rank.csv"


def build_dataset_command(args: argparse.Namespace) -> list[str]:
    command = [
        str(args.python),
        str(script_path("build_theme_stock_dataset.py")),
        "--theme-source",
        args.theme_source,
        "--theme-names",
        ",".join(args.theme_names),
        "--theme-code-map",
        args.theme_code_map,
        "--start-date",
        args.start_date,
        "--horizons",
        ",".join(str(horizon) for horizon in args.horizons),
        "--min-history-rows",
        str(args.min_history_rows),
        "--max-stocks-per-theme",
        str(args.max_stocks_per_theme),
        "--keep-unlabeled-tail",
        "--sleep-seconds",
        str(args.sleep_seconds),
        "--fetch-attempts",
        str(args.fetch_attempts),
        "--retry-base-seconds",
        str(args.retry_base_seconds),
        "--remote-request-interval",
        str(args.remote_request_interval),
        "--em-hosts",
        args.em_hosts,
        "--em-max-pages",
        str(args.em_max_pages),
        "--output",
        str(args.dataset_output),
        "--membership-output",
        str(args.data_dir / "theme_stock_membership_snapshot.csv"),
    ]
    if args.allow_akshare_name_fallback:
        command.append("--allow-akshare-name-fallback")
    if args.theme_code_map_file is not None:
        command.extend(["--theme-code-map-file", str(args.theme_code_map_file)])
    if args.adjust:
        command.extend(["--adjust", args.adjust])
    if not args.use_cache or args.refresh_constituents:
        command.append("--refresh-constituents")
    if not args.use_cache:
        command.append("--refresh-history")
    return command


def predict_command(args: argparse.Namespace, horizon: int) -> list[str]:
    return [
        str(args.python),
        str(script_path("predict_theme_stock_live_rank.py")),
        "--input",
        str(args.dataset_output),
        "--horizon",
        str(horizon),
        "--target",
        args.target,
        "--top-pct",
        str(args.top_pct),
        "--top-n",
        str(args.top_n),
        "--model",
        args.model,
        "--output",
        str(rank_output(args.data_dir, horizon)),
        "--latest-output",
        str(latest_rank_output(args.data_dir, horizon)),
    ]


def dashboard_command(args: argparse.Namespace) -> list[str]:
    return [
        str(args.python),
        str(script_path("build_edp_theme_stock_dashboard.py")),
        "--rank-1d",
        str(rank_output(args.data_dir, 1)),
        "--rank-3d",
        str(rank_output(args.data_dir, 3)),
        "--rank-5d",
        str(rank_output(args.data_dir, 5)),
        "--output-dir",
        str(args.output_dir),
        "--top-n",
        str(args.top_n),
    ]


def main() -> None:
    args = parse_args()
    config = load_config()
    args.theme_source = str(config["theme_source"])
    args.theme_names = [str(name) for name in config["theme_names"]]
    args.theme_code_map = str(config["theme_code_map"])
    args.theme_code_map_file = (
        path_value(str(config["theme_code_map_file"]))
        if str(config["theme_code_map_file"])
        else None
    )
    args.start_date = str(config["start_date"])
    args.horizons = [int(horizon) for horizon in config["horizons"]]
    args.target = str(config["target"])
    args.top_pct = int(config["top_pct"])
    args.top_n = int(config["dashboard_top_n"])
    args.min_history_rows = int(config["min_history_rows"])
    args.max_stocks_per_theme = int(config["max_stocks_per_theme"])
    args.model = str(config["model"])
    args.adjust = str(config["adjust"])
    args.use_cache = bool(config["use_cache"])
    args.refresh_constituents = bool(config["refresh_constituents"])
    args.fetch_attempts = int(config["fetch_attempts"])
    args.retry_base_seconds = float(config["retry_base_seconds"])
    args.sleep_seconds = float(config["sleep_seconds"])
    args.remote_request_interval = float(config["remote_request_interval"])
    args.em_hosts = str(config["em_hosts"])
    args.em_max_pages = int(config["em_max_pages"])
    args.allow_akshare_name_fallback = bool(config["allow_akshare_name_fallback"])
    args.data_dir = path_value(str(config["data_dir"]))
    args.dataset_output = path_value(str(config["dataset_output"]))
    args.output_dir = path_value(str(config["dashboard_output_dir"]))
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    commands = [build_dataset_command(args)]
    commands.extend(predict_command(args, horizon) for horizon in args.horizons)
    commands.append(dashboard_command(args))

    for command in commands:
        run_command(command)

    print("daily_theme_stock_dashboard_done=true")
    print(f"dashboard={args.output_dir / 'dashboard.md'}")
    print(f"summary={args.output_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
