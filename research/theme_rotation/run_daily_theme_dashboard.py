from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from theme_config import load_config, path_value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "运行完整每日题材 EDP 工作流：构建数据集、预测 1/3/5 日 live 排名、"
            "拉取题材内部热度快照，并生成看板。"
        )
    )
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    return parser.parse_args()


def script_path(script_name: str) -> Path:
    return Path(__file__).resolve().parent / script_name


def run_command(command: list[str]) -> None:
    print(">>> " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def rank_output(data_dir: Path, theme_source: str, horizon: int) -> Path:
    return data_dir / f"theme_rotation_{theme_source}_{horizon}d_live_rank.csv"


def latest_rank_output(data_dir: Path, theme_source: str, horizon: int) -> Path:
    return data_dir / f"theme_rotation_{theme_source}_{horizon}d_live_latest_rank.csv"


def breadth_output(data_dir: Path, theme_source: str) -> Path:
    return data_dir / f"theme_rotation_{theme_source}_3d_live_latest_breadth.csv"


def breadth_history_output(data_dir: Path) -> Path:
    return data_dir / "theme_rotation_breadth_snapshot_history.csv"


def build_dataset_command(args: argparse.Namespace) -> list[str]:
    command = [
        str(args.python),
        str(script_path("build_theme_dataset.py")),
        "--theme-source",
        args.theme_source,
        "--start-date",
        args.start_date,
        "--horizons",
        ",".join(str(horizon) for horizon in args.horizons),
        "--min-history-rows",
        str(args.min_history_rows),
        "--keep-unlabeled-tail",
        "--sleep-seconds",
        str(args.sleep_seconds),
        "--output",
        str(args.dataset_output),
    ]
    if args.refresh_list:
        command.append("--refresh-list")
    if not args.use_cache:
        command.append("--refresh-history")
    return command


def predict_command(args: argparse.Namespace, horizon: int) -> list[str]:
    return [
        str(args.python),
        str(script_path("predict_live_rank.py")),
        "--input",
        str(args.dataset_output),
        "--horizon",
        str(horizon),
        "--top-n",
        str(args.top_n),
        "--model",
        args.model,
            "--output",
            str(rank_output(args.data_dir, args.theme_source, horizon)),
            "--latest-output",
            str(latest_rank_output(args.data_dir, args.theme_source, horizon)),
    ]


def breadth_command(args: argparse.Namespace) -> list[str]:
    return [
        str(args.python),
        str(script_path("build_latest_breadth_snapshot.py")),
        "--rank-input",
        str(latest_rank_output(args.data_dir, args.theme_source, 3)),
        "--theme-source",
        args.theme_source,
        "--top-n",
        str(args.top_n),
        "--sleep-seconds",
        str(args.sleep_seconds),
        "--output",
        str(breadth_output(args.data_dir, args.theme_source)),
        "--history-output",
        str(breadth_history_output(args.data_dir)),
    ]


def dashboard_command(args: argparse.Namespace) -> list[str]:
    command = [
        str(args.python),
        str(script_path("build_edp_daily_dashboard.py")),
        "--rank-1d",
        str(rank_output(args.data_dir, args.theme_source, 1)),
        "--rank-3d",
        str(rank_output(args.data_dir, args.theme_source, 3)),
        "--rank-5d",
        str(rank_output(args.data_dir, args.theme_source, 5)),
        "--output-dir",
        str(args.output_dir),
        "--top-n",
        str(args.top_n),
    ]
    if args.include_breadth:
        command.extend(["--breadth-input", str(breadth_output(args.data_dir, args.theme_source))])
    else:
        command.append("--skip-breadth")
    return command


def main() -> None:
    args = parse_args()
    config = load_config()
    args.theme_source = str(config["theme_source"])
    args.start_date = str(config["start_date"])
    args.horizons = [int(horizon) for horizon in config["horizons"]]
    args.min_history_rows = int(config["min_history_rows"])
    args.top_n = int(config["dashboard_top_n"])
    args.model = str(config["model"])
    args.use_cache = bool(config["use_cache"])
    args.refresh_list = bool(config["refresh_list"])
    args.include_breadth = bool(config["include_breadth"])
    args.sleep_seconds = float(config["sleep_seconds"])
    args.data_dir = path_value(str(config["data_dir"]))
    args.dataset_output = path_value(str(config["dataset_output"]))
    args.output_dir = path_value(str(config["dashboard_output_dir"]))
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    commands = [build_dataset_command(args)]
    commands.extend(predict_command(args, horizon) for horizon in args.horizons)
    if args.include_breadth:
        commands.append(breadth_command(args))
    commands.append(dashboard_command(args))

    for command in commands:
        run_command(command)

    print("daily_theme_dashboard_done=true")
    print(f"dashboard={args.output_dir / 'dashboard.md'}")
    print(f"summary={args.output_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
