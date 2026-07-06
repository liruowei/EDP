from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
THEME_ROTATION_DIR = REPO_ROOT / "research" / "theme_rotation"
if str(THEME_ROTATION_DIR) not in sys.path:
    sys.path.insert(0, str(THEME_ROTATION_DIR))

from build_theme_dataset import (  # noqa: E402
    build_theme_panel,
    fetch_theme_list,
    parse_horizons,
    read_or_fetch_csv,
    theme_list_from_names,
)


DEFAULT_START_DATE = "20240101"
DEFAULT_HORIZON = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a divergence-turning-point dataset for theme main-wave research."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Optional existing theme panel/dataset CSV. When set, remote fetching is skipped.",
    )
    parser.add_argument("--theme-source", default="concept_ths")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON)
    parser.add_argument(
        "--horizons",
        default="",
        help="Optional comma-separated horizons. Overrides --horizon when provided.",
    )
    parser.add_argument("--top-quantile", type=float, default=0.8)
    parser.add_argument("--min-forward-runup", type=float, default=0.04)
    parser.add_argument("--max-entry-ret-5d-rank-pct", type=float, default=0.70)
    parser.add_argument("--min-history-rows", type=int, default=160)
    parser.add_argument("--min-amount", type=float, default=0.0)
    parser.add_argument("--max-themes", type=int, default=0)
    parser.add_argument("--theme-names", default="")
    parser.add_argument("--theme-filter", default="")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data") / "theme_rotation" / "akshare_cache",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d.csv",
    )
    parser.add_argument("--refresh-list", action="store_true")
    parser.add_argument("--refresh-history", action="store_true")
    parser.add_argument("--keep-unlabeled-tail", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    return parser.parse_args()


def load_or_build_panel(args: argparse.Namespace) -> pd.DataFrame:
    if args.input is not None:
        return pd.read_csv(args.input, parse_dates=["date"])

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    if args.theme_names:
        theme_list = theme_list_from_names(args.theme_source, args.theme_names)
    else:
        list_cache = args.cache_dir / f"theme_list_{args.theme_source}.csv"
        theme_list = read_or_fetch_csv(
            list_cache,
            lambda: fetch_theme_list(args.theme_source),
            args.refresh_list,
        )
    if args.theme_filter:
        theme_list = theme_list[
            theme_list["theme_name"].astype(str).str.contains(args.theme_filter, regex=True)
        ].copy()
    if args.max_themes > 0:
        theme_list = theme_list.head(args.max_themes).copy()
    if theme_list.empty:
        raise RuntimeError("Theme list is empty after filters.")

    return build_theme_panel(
        theme_list=theme_list,
        source=args.theme_source,
        start_date=args.start_date,
        end_date=args.end_date,
        cache_dir=args.cache_dir,
        refresh_history=args.refresh_history,
        min_history_rows=args.min_history_rows,
        sleep_seconds=args.sleep_seconds,
    )


def add_divergence_features_and_labels(
    panel: pd.DataFrame,
    horizons: list[int],
    top_quantile: float,
    min_forward_runup: float,
    max_entry_ret_5d_rank_pct: float,
    min_amount: float,
    keep_unlabeled_tail: bool,
) -> pd.DataFrame:
    result = normalize_panel(panel)
    grouped = result.groupby("theme_name", group_keys=False)

    for window in [1, 3, 5, 10, 20]:
        result[f"ret_{window}d"] = grouped["close"].pct_change(window)

    for window in [3, 5, 10, 20]:
        result[f"amount_ma_{window}d"] = (
            grouped["amount"].rolling(window).mean().reset_index(level=0, drop=True)
        )
        result[f"amount_change_{window}d"] = grouped["amount"].pct_change(window)

    result["amount_ratio_3_20"] = result["amount_ma_3d"] / result["amount_ma_20d"]
    result["amount_ratio_5_20"] = result["amount_ma_5d"] / result["amount_ma_20d"]
    result["amount_ratio_10_20"] = result["amount_ma_10d"] / result["amount_ma_20d"]
    result["amount_acceleration_3_10"] = result["amount_ratio_3_20"] / result[
        "amount_ratio_10_20"
    ] - 1.0

    result["ma_5d"] = grouped["close"].rolling(5).mean().reset_index(level=0, drop=True)
    result["ma_10d"] = grouped["close"].rolling(10).mean().reset_index(level=0, drop=True)
    result["ma_20d"] = grouped["close"].rolling(20).mean().reset_index(level=0, drop=True)
    result["ma_gap_5_20"] = result["ma_5d"] / result["ma_20d"] - 1.0
    result["price_reclaim_5d"] = result["close"] / result["ma_5d"] - 1.0
    result["price_reclaim_20d"] = result["close"] / result["ma_20d"] - 1.0

    result["ret_1d_std_5d"] = (
        grouped["ret_1d"].rolling(5).std().reset_index(level=0, drop=True)
    )
    result["ret_1d_std_20d"] = (
        grouped["ret_1d"].rolling(20).std().reset_index(level=0, drop=True)
    )
    result["volatility_ratio_5_20"] = result["ret_1d_std_5d"] / result["ret_1d_std_20d"]
    result["volatility_compression"] = 1.0 - result["volatility_ratio_5_20"]

    high_20d = grouped["high"].rolling(20).max().reset_index(level=0, drop=True)
    low_20d = grouped["low"].rolling(20).min().reset_index(level=0, drop=True)
    result["drawdown_20d"] = result["close"] / high_20d - 1.0
    result["rebound_from_20d_low"] = result["close"] / low_20d - 1.0

    daily_range = (result["high"] - result["low"]).replace(0, pd.NA)
    result["intraday_position"] = (result["close"] - result["low"]) / daily_range
    result["upper_shadow_pct"] = (result["high"] - result["close"]) / daily_range
    result["lower_shadow_pct"] = (result["close"] - result["low"]) / daily_range

    for horizon in horizons:
        result[f"fwd_ret_{horizon}d"] = grouped["close"].shift(-horizon) / result["close"] - 1.0
        result[f"fwd_mfe_{horizon}d"] = grouped["close"].transform(
            lambda series, window=horizon: future_rolling_max(series, window)
        ) / result["close"] - 1.0

    add_cross_section_ranks(result)
    add_market_context(result)
    add_scores(result)
    add_labels(
        result,
        horizons=horizons,
        top_quantile=top_quantile,
        min_forward_runup=min_forward_runup,
        max_entry_ret_5d_rank_pct=max_entry_ret_5d_rank_pct,
    )
    result["position_state"] = [
        classify_position_state(ret_rank, divergence_rank, visibility_rank, flow, amount_rank)
        for ret_rank, divergence_rank, visibility_rank, flow, amount_rank in zip(
            result["ret_5d_rank_pct"],
            result["divergence_score_rank_pct"],
            result["turn_visibility_score_rank_pct"],
            result["ret_rank_flow_3d"],
            result["amount_ratio_rank_pct"],
        )
    ]

    result["theme_quality_ok"] = (result["amount"] >= min_amount).astype("Int64")
    result = result[result["theme_quality_ok"] == 1].copy()
    if keep_unlabeled_tail:
        return result.reset_index(drop=True)

    label_columns = [f"label_divergence_turn_{horizon}d" for horizon in horizons]
    return result.dropna(subset=label_columns).reset_index(drop=True)


def normalize_panel(panel: pd.DataFrame) -> pd.DataFrame:
    result = panel.copy()
    required = ["date", "theme_name", "theme_code", "theme_type", "open", "close", "high", "low", "amount"]
    missing = [column for column in required if column not in result.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    result["date"] = pd.to_datetime(result["date"])
    for column in ["open", "close", "high", "low", "amount", "volume"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.sort_values(["theme_name", "date"]).drop_duplicates(
        ["theme_name", "date"]
    ).reset_index(drop=True)


def future_rolling_max(series: pd.Series, window: int) -> pd.Series:
    return series.shift(-1).iloc[::-1].rolling(window, min_periods=1).max().iloc[::-1]


def add_cross_section_ranks(result: pd.DataFrame) -> None:
    rank_columns = {
        "ret_1d": "ret_1d_rank_pct",
        "ret_3d": "ret_3d_rank_pct",
        "ret_5d": "ret_5d_rank_pct",
        "ret_10d": "ret_10d_rank_pct",
        "amount_ratio_5_20": "amount_ratio_rank_pct",
        "amount_acceleration_3_10": "amount_acceleration_rank_pct",
        "intraday_position": "intraday_position_rank_pct",
        "volatility_compression": "volatility_compression_rank_pct",
        "ma_gap_5_20": "ma_gap_5_20_rank_pct",
        "price_reclaim_5d": "price_reclaim_5d_rank_pct",
        "price_reclaim_20d": "price_reclaim_20d_rank_pct",
    }
    for source, target in rank_columns.items():
        result[target] = result.groupby("date")[source].rank(pct=True)

    result["ret_rank_flow_3d"] = result.groupby("theme_name")["ret_5d_rank_pct"].diff(3)
    result["amount_rank_flow_3d"] = result.groupby("theme_name")[
        "amount_ratio_rank_pct"
    ].diff(3)


def add_market_context(result: pd.DataFrame) -> None:
    daily = (
        result.groupby("date", observed=True)
        .agg(
            theme_universe_count=("theme_name", "size"),
            theme_universe_ret_1d_median=("ret_1d", "median"),
            theme_universe_ret_3d_median=("ret_3d", "median"),
            theme_universe_ret_5d_median=("ret_5d", "median"),
            theme_universe_ret_10d_median=("ret_10d", "median"),
            universe_amount_ratio_5_20_median=("amount_ratio_5_20", "median"),
            universe_volatility_ratio_5_20_median=("volatility_ratio_5_20", "median"),
            universe_ret_5d_dispersion=("ret_5d", "std"),
            universe_intraday_position_median=("intraday_position", "median"),
            breadth_ret_1d_positive_pct=("ret_1d", lambda value: (value > 0).mean()),
            breadth_ret_5d_positive_pct=("ret_5d", lambda value: (value > 0).mean()),
            breadth_above_ma20_pct=("price_reclaim_20d", lambda value: (value > 0).mean()),
            breadth_amount_expand_pct=("amount_ratio_5_20", lambda value: (value > 1).mean()),
        )
        .reset_index()
        .sort_values("date")
    )
    daily["market_regime_score"] = (
        daily["breadth_ret_5d_positive_pct"].fillna(0.0) * 0.30
        + daily["breadth_above_ma20_pct"].fillna(0.0) * 0.30
        + daily["breadth_amount_expand_pct"].fillna(0.0) * 0.20
        + daily["universe_intraday_position_median"].clip(0.0, 1.0).fillna(0.0) * 0.20
    )
    daily["market_regime_score_ma5"] = daily["market_regime_score"].rolling(
        5,
        min_periods=1,
    ).mean()
    daily["market_regime_score_5d_delta"] = daily["market_regime_score"] - daily[
        "market_regime_score"
    ].shift(5)
    daily["market_regime_state"] = daily["market_regime_score"].map(classify_market_regime)

    context_columns = [column for column in daily.columns if column != "date"]
    result.drop(columns=[column for column in context_columns if column in result.columns], inplace=True)
    enriched = result.merge(daily, on="date", how="left")
    for column in context_columns:
        result[column] = enriched[column].to_numpy()


def classify_market_regime(score: float) -> str:
    if pd.isna(score):
        return "unknown"
    if score >= 0.62:
        return "risk_on"
    if score >= 0.45:
        return "mixed"
    return "risk_off"


def add_scores(result: pd.DataFrame) -> None:
    quiet_price = 1.0 - result["ret_5d_rank_pct"]
    volume_support = result["amount_ratio_rank_pct"]
    close_support = result["intraday_position_rank_pct"]
    compression = result["volatility_compression_rank_pct"]
    hidden_relative_improvement = result["ret_rank_flow_3d"].clip(lower=0.0).fillna(0.0)
    amount_improvement = result["amount_rank_flow_3d"].clip(lower=0.0).fillna(0.0)

    result["divergence_score"] = (
        quiet_price * 0.28
        + volume_support * 0.24
        + close_support * 0.18
        + compression * 0.15
        + hidden_relative_improvement * 0.10
        + amount_improvement * 0.05
    )

    result["turn_visibility_score"] = (
        result["ret_3d_rank_pct"] * 0.20
        + result["amount_acceleration_rank_pct"] * 0.22
        + result["price_reclaim_5d_rank_pct"] * 0.18
        + result["intraday_position_rank_pct"] * 0.16
        + result["ret_rank_flow_3d"].clip(lower=0.0).fillna(0.0) * 0.16
        + result["amount_rank_flow_3d"].clip(lower=0.0).fillna(0.0) * 0.08
    )

    result["divergence_score_rank_pct"] = result.groupby("date")["divergence_score"].rank(
        pct=True
    )
    result["turn_visibility_score_rank_pct"] = result.groupby("date")[
        "turn_visibility_score"
    ].rank(pct=True)


def add_labels(
    result: pd.DataFrame,
    horizons: list[int],
    top_quantile: float,
    min_forward_runup: float,
    max_entry_ret_5d_rank_pct: float,
) -> None:
    for horizon in horizons:
        fwd_ret = f"fwd_ret_{horizon}d"
        fwd_mfe = f"fwd_mfe_{horizon}d"
        main_wave_rank = result.groupby("date")[fwd_ret].rank(pct=True)
        main_wave = (main_wave_rank >= top_quantile) & (
            result[fwd_mfe] >= min_forward_runup
        )
        not_already_hot = result["ret_5d_rank_pct"] <= max_entry_ret_5d_rank_pct
        label = (main_wave & not_already_hot).astype("Int64")
        label[result[fwd_ret].isna()] = pd.NA
        result[f"label_main_wave_{horizon}d"] = main_wave.astype("Int64")
        result[f"label_divergence_turn_{horizon}d"] = label


def classify_position_state(
    ret_5d_rank_pct: float,
    divergence_score_rank_pct: float,
    turn_visibility_score_rank_pct: float,
    ret_rank_flow_3d: float,
    amount_ratio_rank_pct: float,
) -> str:
    if pd.isna(ret_5d_rank_pct) or pd.isna(divergence_score_rank_pct):
        return "insufficient_history"
    if ret_5d_rank_pct >= 0.82 and turn_visibility_score_rank_pct >= 0.65:
        return "already_extended"
    if divergence_score_rank_pct >= 0.72 and turn_visibility_score_rank_pct >= 0.65:
        return "visible_turn_candidate"
    if divergence_score_rank_pct >= 0.70 and ret_5d_rank_pct <= 0.55:
        return "hidden_divergence_candidate"
    if ret_5d_rank_pct <= 0.35 and amount_ratio_rank_pct <= 0.45 and ret_rank_flow_3d < 0:
        return "cooling_or_failed"
    return "neutral"


def parse_requested_horizons(args: argparse.Namespace) -> list[int]:
    if args.horizons:
        return parse_horizons(None, args.horizons)
    return [args.horizon]


def main() -> None:
    args = parse_args()
    horizons = parse_requested_horizons(args)
    panel = load_or_build_panel(args)
    dataset = add_divergence_features_and_labels(
        panel,
        horizons=horizons,
        top_quantile=args.top_quantile,
        min_forward_runup=args.min_forward_runup,
        max_entry_ret_5d_rank_pct=args.max_entry_ret_5d_rank_pct,
        min_amount=args.min_amount,
        keep_unlabeled_tail=args.keep_unlabeled_tail,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"output={args.output}")
    print(f"rows={len(dataset)}")
    print(f"themes={dataset['theme_name'].nunique()}")
    print(f"date_range={dataset['date'].min().date()}..{dataset['date'].max().date()}")
    for horizon in horizons:
        label = f"label_divergence_turn_{horizon}d"
        print(f"positive_rate_{horizon}d={dataset[label].dropna().mean():.4f}")
    latest = dataset[dataset["date"] == dataset["date"].max()].sort_values(
        "turn_visibility_score_rank_pct",
        ascending=False,
    )
    print("latest_turn_visibility_top=")
    preview_columns = [
        "date",
        "theme_name",
        "position_state",
        "market_regime_state",
        "market_regime_score",
        "ret_5d_rank_pct",
        "divergence_score_rank_pct",
        "turn_visibility_score_rank_pct",
        "amount_ratio_5_20",
        "ret_rank_flow_3d",
    ]
    print(latest[preview_columns].head(12).to_string(index=False))


if __name__ == "__main__":
    main()
