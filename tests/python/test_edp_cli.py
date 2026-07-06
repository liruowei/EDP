from __future__ import annotations

import json
from pathlib import Path

import edp_cli


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_cli(argv: list[str], monkeypatch) -> list[str]:
    calls: list[list[str]] = []

    class Completed:
        returncode = 0

    def fake_run(command: list[str], cwd: Path) -> Completed:
        assert cwd == REPO_ROOT
        calls.append(command)
        return Completed()

    monkeypatch.setattr(edp_cli.subprocess, "run", fake_run)
    exit_code = edp_cli.parse_args(["--repo-root", str(REPO_ROOT), *argv]).func(
        edp_cli.parse_args(["--repo-root", str(REPO_ROOT), *argv])
    )

    assert exit_code == 0
    assert len(calls) == 1
    return calls[0]


def test_theme_build_forwards_script_and_filters(monkeypatch) -> None:
    command = run_cli(
        [
            "theme",
            "build",
            "--theme-source",
            "concept_ths",
            "--theme-names",
            "AI手机,机器人",
            "--max-themes",
            "2",
            "--keep-unlabeled-tail",
            "--output",
            "tmp/theme.csv",
        ],
        monkeypatch,
    )

    assert command[1].endswith("research\\theme_rotation\\build_theme_dataset.py")
    assert "--theme-source" in command
    assert command[command.index("--theme-source") + 1] == "concept_ths"
    assert "--theme-names" in command
    assert command[command.index("--theme-names") + 1] == "AI手机,机器人"
    assert "--keep-unlabeled-tail" in command
    assert "--output" in command


def test_theme_daily_uses_research_config(monkeypatch) -> None:
    command = run_cli(["theme", "daily"], monkeypatch)

    assert command[1].endswith("research\\theme_rotation\\run_daily_theme_dashboard.py")
    assert "--python" in command
    assert "--theme-source" not in command
    assert "--horizons" not in command
    assert "--top-n" not in command
    assert "--dry-run" not in command


def test_theme_stock_daily_uses_research_config(monkeypatch) -> None:
    command = run_cli(["theme-stock", "daily"], monkeypatch)

    assert command[1].endswith("research\\theme_stock_rotation\\run_daily_theme_stock_dashboard.py")
    assert "--python" in command
    assert "--theme-source" not in command
    assert "--theme-names" not in command
    assert "--horizons" not in command
    assert "--refresh-constituents" not in command
    assert "--dry-run" not in command


def test_divergence_breadth_can_disable_history(monkeypatch) -> None:
    command = run_cli(
        [
            "divergence",
            "latest-breadth",
            "--rank-input",
            "rank.csv",
            "--history-output",
            "history.csv",
            "--no-history",
        ],
        monkeypatch,
    )

    assert command[1].endswith(
        "research\\divergence_turning_point\\build_latest_breadth_snapshot.py"
    )
    assert "--rank-input" in command
    assert command[command.index("--rank-input") + 1] == "rank.csv"
    assert "--history-output" in command
    assert command[command.index("--history-output") + 1] == "history.csv"
    assert "--no-history" in command


def test_theme_breadth_can_write_history(monkeypatch) -> None:
    command = run_cli(
        [
            "theme",
            "latest-breadth",
            "--rank-input",
            "rank.csv",
            "--history-output",
            "history.csv",
            "--no-history",
        ],
        monkeypatch,
    )

    assert command[1].endswith("research\\theme_rotation\\build_latest_breadth_snapshot.py")
    assert "--rank-input" in command
    assert command[command.index("--rank-input") + 1] == "rank.csv"
    assert "--history-output" in command
    assert command[command.index("--history-output") + 1] == "history.csv"
    assert "--no-history" in command


def test_theme_stock_list_themes_forwards_cache_args(monkeypatch) -> None:
    command = run_cli(
        [
            "theme-stock",
            "list-themes",
            "--theme-source",
            "concept_ths",
            "--keyword",
            "光刻",
            "--cache-dir",
            "tmp/theme-cache",
            "--refresh-list",
        ],
        monkeypatch,
    )

    assert command[1].endswith("research\\theme_stock_rotation\\list_theme_names.py")
    assert "--cache-dir" in command
    assert Path(command[command.index("--cache-dir") + 1]) == Path("tmp/theme-cache")
    assert "--refresh-list" in command


def test_divergence_daily_uses_research_config(monkeypatch) -> None:
    daily = run_cli(["divergence", "daily"], monkeypatch)
    assert daily[1].endswith(
        "research\\divergence_turning_point\\run_daily_divergence_turning.py"
    )
    assert "--python" in daily
    assert "--top-n" not in daily
    assert "--breadth-top-n" not in daily
    assert "--theme-source" not in daily
    assert "--model" not in daily


def test_divergence_step_defaults_use_full_latest_candidates(monkeypatch) -> None:
    rank = run_cli(["divergence", "rank"], monkeypatch)
    assert "--top-n" in rank
    assert rank[rank.index("--top-n") + 1] == "30"
    assert "--latest-output-limit" in rank
    assert rank[rank.index("--latest-output-limit") + 1] == "0"

    breadth = run_cli(["divergence", "latest-breadth"], monkeypatch)
    assert "--top-n" in breadth
    assert breadth[breadth.index("--top-n") + 1] == "0"


def test_divergence_intraday_uses_standard_monitor(monkeypatch) -> None:
    command = run_cli(["divergence", "intraday"], monkeypatch)

    assert command[1].endswith(
        "research\\divergence_turning_point\\run_intraday_divergence_monitor.py"
    )
    assert "--rank-input" not in command
    assert "--top-n" not in command
    assert "--interval-seconds" not in command
    assert "--iterations" not in command
    assert "--dry-run" not in command


def test_strategy_backtest_uses_research_config(monkeypatch) -> None:
    command = run_cli(["strategy", "backtest"], monkeypatch)

    assert command[1].endswith(
        "research\\edp_turning_strategy\\run_edp_turning_strategy_backtest.py"
    )
    assert "--python" in command
    assert "--rank-input" not in command
    assert "--panel-input" not in command
    assert "--holding-days" not in command


def test_low_buy_daily_uses_research_config(monkeypatch) -> None:
    command = run_cli(["low-buy", "daily"], monkeypatch)

    assert command[1].endswith(
        "research\\second_day_low_buy\\run_second_day_low_buy.py"
    )
    assert "--mode" not in command
    assert "--codes" not in command


def test_low_buy_backtest_forwards_mode_and_codes(monkeypatch) -> None:
    command = run_cli(["low-buy", "backtest", "--codes", "300401,300420"], monkeypatch)

    assert command[1].endswith(
        "research\\second_day_low_buy\\run_second_day_low_buy.py"
    )
    assert "--mode" in command
    assert command[command.index("--mode") + 1] == "backtest"
    assert "--codes" in command
    assert command[command.index("--codes") + 1] == "300401,300420"


def test_low_buy_full_backtest_forwards_max_stocks(monkeypatch) -> None:
    command = run_cli(["low-buy", "full-backtest", "--max-stocks", "50"], monkeypatch)

    assert command[1].endswith(
        "research\\second_day_low_buy\\run_full_market_oos_backtest.py"
    )
    assert "--max-stocks" in command
    assert command[command.index("--max-stocks") + 1] == "50"
    assert "--codes" not in command
    assert "--mode" not in command


def test_low_buy_monitor_can_forward_debug_runtime_args(monkeypatch) -> None:
    command = run_cli(
        [
            "low-buy",
            "monitor",
            "--end-date",
            "20260630",
            "--max-stocks",
            "5",
            "--iterations",
            "1",
        ],
        monkeypatch,
    )

    assert command[1].endswith(
        "research\\second_day_low_buy\\run_low_buy_monitor.py"
    )
    assert "--end-date" in command
    assert command[command.index("--end-date") + 1] == "20260630"
    assert "--max-stocks" in command
    assert command[command.index("--max-stocks") + 1] == "5"
    assert "--iterations" in command
    assert command[command.index("--iterations") + 1] == "1"
    assert not any(arg.endswith("refresh-history") for arg in command)
    assert "--interval-seconds" not in command


def test_data_update_forwards_end_date_to_market_data_update(monkeypatch) -> None:
    command = run_cli(
        [
            "data",
            "update",
            "--end-date",
            "20260702",
            "--max-stocks",
            "10",
            "--progress-every",
            "5",
        ],
        monkeypatch,
    )

    assert command[1].endswith("research\\market_data\\update_market_data.py")
    assert "--" + "provider" not in command
    assert "--end-date" in command
    assert command[command.index("--end-date") + 1] == "20260702"
    assert "--max-stocks" in command
    assert command[command.index("--max-stocks") + 1] == "10"
    assert "--progress-every" in command
    assert command[command.index("--progress-every") + 1] == "5"


def test_data_update_can_omit_end_date(monkeypatch) -> None:
    command = run_cli(["data", "update", "--max-stocks", "1"], monkeypatch)

    assert command[1].endswith("research\\market_data\\update_market_data.py")
    assert "--end-date" not in command
    assert "--max-stocks" in command
    assert command[command.index("--max-stocks") + 1] == "1"


def test_data_update_factors_forwards_to_factor_update(monkeypatch) -> None:
    command = run_cli(
        [
            "data",
            "update-factors",
            "--end-date",
            "20260702",
            "--factor-types",
            "qfq",
            "--max-stocks",
            "10",
            "--progress-every",
            "5",
        ],
        monkeypatch,
    )

    assert command[1].endswith("research\\market_data\\update_market_factors.py")
    assert "--end-date" in command
    assert command[command.index("--end-date") + 1] == "20260702"
    assert "--factor-types" in command
    assert command[command.index("--factor-types") + 1] == "qfq"
    assert "--max-stocks" in command
    assert command[command.index("--max-stocks") + 1] == "10"
    assert "--progress-every" in command
    assert command[command.index("--progress-every") + 1] == "5"


def test_data_update_factors_can_omit_end_date(monkeypatch) -> None:
    command = run_cli(["data", "update-factors", "--factor-types", "qfq"], monkeypatch)

    assert command[1].endswith("research\\market_data\\update_market_factors.py")
    assert "--end-date" not in command
    assert "--factor-types" in command
    assert command[command.index("--factor-types") + 1] == "qfq"


def test_active_research_workflows_have_config_files() -> None:
    for relative_path in [
        "research/theme_rotation/config.json",
        "research/theme_stock_rotation/config.json",
        "research/divergence_turning_point/config.json",
        "research/edp_turning_strategy/config.json",
        "research/second_day_low_buy/config.json",
    ]:
        config_path = REPO_ROOT / relative_path
        assert config_path.exists()
        assert json.loads(config_path.read_text(encoding="utf-8"))


def test_status_reports_workflows(capsys) -> None:
    args = edp_cli.parse_args(["--repo-root", str(REPO_ROOT), "status"])

    assert args.func(args) == 0

    output = capsys.readouterr().out
    assert "workflows=theme,theme-stock,divergence,strategy,low-buy,data" in output
    assert f"repo_root={REPO_ROOT}" in output
    assert "menu_hint=edp menu" in output


def test_menu_is_default_entry(capsys) -> None:
    args = edp_cli.parse_args(["--repo-root", str(REPO_ROOT)])

    assert args.func(args) == 0

    output = capsys.readouterr().out
    assert "EDP 工作流菜单" in output
    assert "edp theme daily" in output
    assert "edp theme-stock daily" in output
    assert "edp strategy backtest" in output
    assert "edp low-buy daily" in output
    assert "docs/research_contract.md" in output


def test_menu_command(capsys) -> None:
    args = edp_cli.parse_args(["--repo-root", str(REPO_ROOT), "menu"])

    assert args.func(args) == 0

    output = capsys.readouterr().out
    assert "不知道从哪里开始" in output
