from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from divergence_config import data_path, load_config, path_value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the daily divergence-turning research workflow from config.json."
    )
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    return parser.parse_args()


def run(command: list[str]) -> None:
    print(" ".join(command))
    subprocess.run(command, check=True)


def main() -> None:
    args = parse_args()
    config = load_config()
    daily = config["daily"]
    theme_source = str(config["theme_source"])
    theme_input = path_value(str(config["theme_input"]))
    horizon = int(daily["horizon"])
    dataset = data_path(config, f"divergence_turning_{horizon}d_{theme_source}_live.csv")
    rank = data_path(config, f"divergence_turning_{horizon}d_{theme_source}_walk_forward_rank.csv")
    latest_rank = data_path(config, f"divergence_turning_{horizon}d_{theme_source}_latest_rank.csv")
    summary = data_path(config, f"divergence_turning_{horizon}d_{theme_source}_summary.json")
    latest_breadth = data_path(config, f"divergence_turning_{horizon}d_{theme_source}_latest_breadth.csv")
    breadth_history = data_path(config, "divergence_turning_breadth_snapshot_history.csv")
    dashboard_dir = data_path(config, "edp_divergence_dashboard")

    run(
        [
            str(args.python),
            "research/divergence_turning_point/build_divergence_turning_dataset.py",
            "--input",
            str(theme_input),
            "--horizon",
            str(horizon),
            "--keep-unlabeled-tail",
            "--output",
            str(dataset),
        ],
    )
    run(
        [
            str(args.python),
            "research/divergence_turning_point/walk_forward_turning_rank.py",
            "--input",
            str(dataset),
            "--horizon",
            str(horizon),
            "--initial-train-days",
            str(daily["initial_train_days"]),
            "--refit-every-days",
            str(daily["refit_every_days"]),
            "--top-n",
            str(daily["dashboard_top_n"]),
            "--model",
            str(daily["model"]),
            "--output",
            str(rank),
            "--latest-output",
            str(latest_rank),
            "--latest-output-limit",
            "0",
            "--summary-output",
            str(summary),
        ],
    )
    if bool(daily["include_breadth"]):
        run(
            [
                str(args.python),
                "research/divergence_turning_point/build_latest_breadth_snapshot.py",
                "--rank-input",
                str(latest_rank),
                "--theme-source",
                theme_source,
                "--top-n",
                str(daily["breadth_top_n"]),
                "--output",
                str(latest_breadth),
                "--history-output",
                str(breadth_history),
            ],
        )
        run(
            [
                str(args.python),
                "research/divergence_turning_point/build_divergence_turning_dashboard.py",
                "--breadth-input",
                str(latest_breadth),
                "--summary-input",
                str(summary),
                "--top-n",
                str(daily["dashboard_top_n"]),
                "--output-dir",
                str(dashboard_dir),
            ],
        )


if __name__ == "__main__":
    main()
