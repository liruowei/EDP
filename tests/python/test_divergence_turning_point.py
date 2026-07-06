from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


build_dataset = load_module(
    "build_divergence_turning_dataset",
    "research/divergence_turning_point/build_divergence_turning_dataset.py",
)
build_breadth = load_module(
    "build_latest_breadth_snapshot",
    "research/divergence_turning_point/build_latest_breadth_snapshot.py",
)
build_dashboard = load_module(
    "build_divergence_turning_dashboard",
    "research/divergence_turning_point/build_divergence_turning_dashboard.py",
)
divergence_config = load_module(
    "divergence_config",
    "research/divergence_turning_point/divergence_config.py",
)
intraday_monitor = load_module(
    "run_intraday_divergence_monitor",
    "research/divergence_turning_point/run_intraday_divergence_monitor.py",
)


def test_future_rolling_max_uses_future_values_only() -> None:
    series = pd.Series([10.0, 12.0, 11.0, 15.0])

    result = build_dataset.future_rolling_max(series, 2)

    assert result.iloc[:3].tolist() == [12.0, 15.0, 15.0]
    assert pd.isna(result.iloc[3])


def test_market_context_classification() -> None:
    assert build_dataset.classify_market_regime(0.70) == "risk_on"
    assert build_dataset.classify_market_regime(0.50) == "mixed"
    assert build_dataset.classify_market_regime(0.20) == "risk_off"


def test_divergence_config_contains_daily_and_intraday_defaults() -> None:
    config = divergence_config.load_config()

    assert config["theme_source"] == "concept_ths"
    assert config["daily"]["horizon"] == 10
    assert config["daily"]["include_breadth"] is True
    assert config["intraday"]["interval_seconds"] == 600


def test_snapshot_history_replaces_same_date_theme(tmp_path: Path) -> None:
    history = tmp_path / "history.csv"
    first = pd.DataFrame(
        [
            {
                "date": "2026-06-18",
                "theme_name": "啤酒概念",
                "rank_turn_breadth": 3.0,
                "constituent_breadth_score": 0.4,
            }
        ]
    )
    second = pd.DataFrame(
        [
            {
                "date": "2026-06-18",
                "theme_name": "啤酒概念",
                "rank_turn_breadth": 1.0,
                "constituent_breadth_score": 0.8,
            }
        ]
    )

    build_breadth.update_snapshot_history(first, history)
    build_breadth.update_snapshot_history(second, history)

    result = pd.read_csv(history)
    assert len(result) == 1
    assert result.loc[0, "rank_turn_breadth"] == 1.0
    assert result.loc[0, "constituent_breadth_score"] == 0.8
    assert result.duplicated(["date", "theme_name"]).sum() == 0


def test_intraday_history_keeps_multiple_same_day_snapshots(tmp_path: Path) -> None:
    history = tmp_path / "intraday_history.csv"
    first = pd.DataFrame(
        [
            {
                "date": "2026-06-18",
                "snapshot_at": "2026-06-22 09:35:00",
                "theme_name": "啤酒概念",
                "rank_turn_breadth": 3.0,
            }
        ]
    )
    second = pd.DataFrame(
        [
            {
                "date": "2026-06-18",
                "snapshot_at": "2026-06-22 09:45:00",
                "theme_name": "啤酒概念",
                "rank_turn_breadth": 1.0,
            }
        ]
    )

    intraday_monitor.append_intraday_snapshot_history(first, history)
    intraday_monitor.append_intraday_snapshot_history(second, history)

    result = pd.read_csv(history)
    assert len(result) == 2
    assert result["snapshot_at"].tolist() == [
        "2026-06-22 09:35:00",
        "2026-06-22 09:45:00",
    ]
    assert result.duplicated(["snapshot_at", "theme_name"]).sum() == 0


def test_intraday_state_uses_previous_snapshot_delta() -> None:
    current = pd.DataFrame(
        [
            {
                "theme_name": "啤酒概念",
                "snapshot_at": "2026-06-22 09:45:00",
                "rank_turn_breadth": 4.0,
                "board_change_pct": 1.2,
                "up_ratio": 0.62,
                "rank_strength": 0.8,
                "net_inflow_100m": 3.0,
                "amount_100m": 20.0,
                "turn_breadth_score": 0.72,
                "breadth_confirmation_state": "breadth_confirmed",
            }
        ]
    )
    previous = pd.DataFrame(
        [
            {
                "theme_name": "啤酒概念",
                "snapshot_at": "2026-06-22 09:35:00",
                "rank_turn_breadth": 6.0,
                "board_change_pct": 0.8,
                "up_ratio": 0.55,
                "rank_strength": 0.7,
                "net_inflow_100m": 1.0,
                "amount_100m": 15.0,
                "turn_breadth_score": 0.65,
            }
        ]
    )

    result = intraday_monitor.add_intraday_fields(current, previous)

    assert abs(result.loc[0, "board_change_delta_pct"] - 0.4) < 1e-9
    assert abs(result.loc[0, "up_ratio_delta"] - 0.07) < 1e-9
    assert result.loc[0, "intraday_state"] == "intraday_confirming"


def test_dashboard_group_csv_cleanup(tmp_path: Path) -> None:
    output_dir = tmp_path / "dashboard"
    output_dir.mkdir()
    stale = output_dir / "resilient_watchlist.csv"
    stale.write_text("stale", encoding="utf-8")
    dashboard = output_dir / "dashboard.csv"
    dashboard.write_text("keep", encoding="utf-8")
    scored = pd.DataFrame(
        [
            {"dashboard_group": "neutral_or_wait", "theme_name": "A"},
            {"dashboard_group": "model_high_breadth_weak", "theme_name": "B"},
        ]
    )

    counts = build_dashboard.write_group_csvs(scored, output_dir)

    assert counts == {"neutral_or_wait": 1, "model_high_breadth_weak": 1}
    assert not stale.exists()
    assert dashboard.exists()
    assert (output_dir / "neutral_or_wait.csv").exists()
    assert (output_dir / "model_high_breadth_weak.csv").exists()


def test_dashboard_classifies_unconfirmed_watchlist() -> None:
    row = pd.Series(
        {
            "breadth_confirmation_state": "breadth_neutral",
            "signal_state": "early_divergence_watch",
            "position_state": "hidden_divergence_candidate",
            "market_regime_state": "mixed",
            "rank_turn_breadth": 3.0,
        }
    )

    assert build_dashboard.classify_dashboard_group(row) == "breadth_unconfirmed_watchlist"
