from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


strategy = load_module(
    "backtest_edp_turning_strategy",
    "research/edp_turning_strategy/backtest_edp_turning_strategy.py",
)


def test_edp_filter_can_replace_overextended_probability_pick() -> None:
    entry = pd.Timestamp("2026-01-01")
    exit_date = pd.Timestamp("2026-01-02")
    names = ["A", "B", "C", "D", "E", "F"]
    rank = pd.DataFrame(
        [
            {
                "date": entry,
                "theme_name": name,
                "rank_probability": index + 1,
                "prob_divergence_turn": 0.8 - index * 0.01,
                "ret_5d_rank_pct": 0.95 if name == "A" else 0.30,
                "market_regime_score": 0.60,
                "market_regime_state": "mixed",
                "signal_state": "early_divergence_watch",
                "position_state": "hidden_divergence_candidate",
                "turn_visibility_score_rank_pct": 0.60,
                "divergence_score_rank_pct": 0.90,
                "amount_ratio_5_20": 1.0 + index,
            }
            for index, name in enumerate(names)
        ]
    )
    panel = pd.DataFrame(
        [
            {"date": entry, "theme_name": name, "close": 100.0}
            for name in names
        ]
        + [
            {
                "date": exit_date,
                "theme_name": name,
                "close": 90.0 if name == "A" else 102.0,
            }
            for name in names
        ]
    )

    events = strategy.run_backtest(
        strategy.add_composite_score(rank),
        panel,
        holding_days=1,
        rebalance_days=1,
        benchmark_top_n=0,
    )
    summary = strategy.summarize(events)

    returns = summary.set_index("strategy")["avg_return"]
    assert returns["edp_filtered"] > returns["model_top30"]
    edp_event = events[events["strategy"] == "edp_filtered"].iloc[0]
    assert "A" not in edp_event["selected_themes"].split(",")
