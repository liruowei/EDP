from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


RUN_TAG_PATTERN = re.compile(r"_([0-9]{8})\.csv$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def path_value(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root() / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the EDP turning strategy backtest from config.json."
    )
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parent / "config.json",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_validation_pair(source: dict[str, Any]) -> tuple[Path, Path, str] | None:
    validation_dir = path_value(str(source["validation_dir"]))
    if not validation_dir.exists():
        return None

    horizon = int(source["horizon"])
    theme_source = str(source["theme_source"])
    rank_pattern = f"divergence_turning_{horizon}d_{theme_source}_walk_forward_rank_*.csv"
    for rank_path in sorted(validation_dir.glob(rank_pattern), reverse=True):
        match = RUN_TAG_PATTERN.search(rank_path.name)
        if match is None:
            continue
        run_tag = match.group(1)
        panel_path = validation_dir / f"divergence_turning_{horizon}d_{theme_source}_live_{run_tag}.csv"
        if panel_path.exists():
            return rank_path, panel_path, run_tag
    return None


def resolve_inputs(config: dict[str, Any]) -> tuple[Path, Path, str]:
    source = config["source"]
    if bool(source.get("prefer_latest_validation", False)):
        latest_pair = latest_validation_pair(source)
        if latest_pair is not None:
            return latest_pair

    rank_input = path_value(str(source["rank_input"]))
    panel_input = path_value(str(source["panel_input"]))
    return rank_input, panel_input, "latest"


def holding_days_list(value: Any) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    return [int(value)]


def output_dir_from_template(template: str, run_tag: str) -> Path:
    return path_value(template.format(run_tag=run_tag))


def run_command(command: list[str]) -> None:
    print(">>> " + " ".join(command), flush=True)
    subprocess.run(command, cwd=repo_root(), check=True)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    backtest = config["backtest"]
    rank_input, panel_input, run_tag = resolve_inputs(config)
    output_dir = output_dir_from_template(str(backtest["output_dir_template"]), run_tag)
    output_dir.mkdir(parents=True, exist_ok=True)

    for holding_days in holding_days_list(backtest["holding_days"]):
        command = [
            str(args.python),
            str(Path(__file__).resolve().parent / "backtest_edp_turning_strategy.py"),
            "--rank-input",
            str(rank_input),
            "--panel-input",
            str(panel_input),
            "--holding-days",
            str(holding_days),
            "--benchmark-top-n",
            str(backtest["benchmark_top_n"]),
            "--output-dir",
            str(output_dir),
        ]
        if backtest.get("rebalance_days") is not None:
            command.extend(["--rebalance-days", str(backtest["rebalance_days"])])
        run_command(command)

    print("edp_turning_strategy_backtest_done=true")
    print(f"run_tag={run_tag}")
    print(f"rank_input={rank_input}")
    print(f"panel_input={panel_input}")
    print(f"output_dir={output_dir}")


if __name__ == "__main__":
    main()
