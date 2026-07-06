from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_COLUMNS = [
    "ret_1d",
    "ret_3d",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "amount_ratio_3_20",
    "amount_ratio_5_20",
    "amount_ratio_10_20",
    "amount_acceleration_3_10",
    "volatility_ratio_5_20",
    "volatility_compression",
    "ma_gap_5_20",
    "price_reclaim_5d",
    "price_reclaim_20d",
    "drawdown_20d",
    "rebound_from_20d_low",
    "intraday_position",
    "upper_shadow_pct",
    "lower_shadow_pct",
    "ret_1d_rank_pct",
    "ret_3d_rank_pct",
    "ret_5d_rank_pct",
    "ret_10d_rank_pct",
    "amount_ratio_rank_pct",
    "amount_acceleration_rank_pct",
    "intraday_position_rank_pct",
    "volatility_compression_rank_pct",
    "ma_gap_5_20_rank_pct",
    "price_reclaim_5d_rank_pct",
    "price_reclaim_20d_rank_pct",
    "ret_rank_flow_3d",
    "amount_rank_flow_3d",
    "divergence_score",
    "turn_visibility_score",
    "divergence_score_rank_pct",
    "turn_visibility_score_rank_pct",
    "theme_universe_ret_1d_median",
    "theme_universe_ret_3d_median",
    "theme_universe_ret_5d_median",
    "theme_universe_ret_10d_median",
    "universe_amount_ratio_5_20_median",
    "universe_volatility_ratio_5_20_median",
    "universe_ret_5d_dispersion",
    "universe_intraday_position_median",
    "breadth_ret_1d_positive_pct",
    "breadth_ret_5d_positive_pct",
    "breadth_above_ma20_pct",
    "breadth_amount_expand_pct",
    "market_regime_score",
    "market_regime_score_ma5",
    "market_regime_score_5d_delta",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Walk-forward rank divergence turning points before theme main waves."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d.csv",
    )
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--initial-train-days", type=int, default=252)
    parser.add_argument(
        "--refit-every-days",
        type=int,
        default=1,
        help="Refit the expanding-window model every N prediction dates. 1 means daily refit.",
    )
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument(
        "--latest-output-limit",
        type=int,
        default=0,
        help="Limit rows written to latest-output. 0 writes the full latest universe.",
    )
    parser.add_argument("--model", choices=["logistic", "hgb"], default="logistic")
    parser.add_argument("--flow-low-pp", type=float, default=5.0)
    parser.add_argument("--flow-high-pp", type=float, default=10.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d_walk_forward_rank.csv",
    )
    parser.add_argument(
        "--latest-output",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d_latest_rank.csv",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d_summary.json",
    )
    return parser.parse_args()


def create_model(kind: str) -> Pipeline:
    if kind == "logistic":
        return Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
            ]
        )

    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                HistGradientBoostingClassifier(
                    max_iter=200,
                    learning_rate=0.05,
                    l2_regularization=0.05,
                    random_state=42,
                ),
            ),
        ]
    )


def walk_forward_by_date(
    df: pd.DataFrame,
    label_column: str,
    horizon: int,
    initial_train_days: int,
    model_kind: str,
    refit_every_days: int,
) -> pd.DataFrame:
    dates = sorted(df["date"].dropna().unique())
    if len(dates) <= initial_train_days + 1:
        raise ValueError(
            f"Need more than initial_train_days + 1 dates; got {len(dates)} dates."
        )

    frames: list[pd.DataFrame] = []
    model: Pipeline | None = None
    train: pd.DataFrame | None = None
    refit_every_days = max(1, refit_every_days)
    for prediction_index, current_date in enumerate(dates[initial_train_days:]):
        test = df[df["date"] == current_date].copy()
        if test.empty:
            continue

        should_refit = model is None or prediction_index % refit_every_days == 0
        if should_refit:
            train = df[df["date"] < current_date].dropna(subset=[label_column]).copy()
            if train.empty or train[label_column].nunique() < 2:
                continue
            model = create_model(model_kind)
            model.fit(train[FEATURE_COLUMNS], train[label_column].astype(int))
        if model is None or train is None:
            continue

        probabilities = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]

        keep = [
            "date",
            "theme_name",
            "theme_code",
            "theme_type",
            "close",
            "amount",
            "position_state",
            "ret_1d",
            "ret_3d",
            "ret_5d",
            "ret_5d_rank_pct",
            "amount_ratio_5_20",
            "divergence_score_rank_pct",
            "turn_visibility_score_rank_pct",
            "market_regime_state",
            "market_regime_score",
            "breadth_ret_5d_positive_pct",
            "breadth_above_ma20_pct",
            "breadth_amount_expand_pct",
            f"fwd_ret_{horizon}d",
            f"fwd_mfe_{horizon}d",
            label_column,
        ]
        block = test[keep].copy()
        block["prob_divergence_turn"] = probabilities
        block["train_rows"] = len(train)
        block["train_start_date"] = train["date"].min()
        block["train_end_date"] = train["date"].max()
        block["model_refit_date"] = train["date"].max()
        block["refit_every_days"] = refit_every_days
        frames.append(block)

    if not frames:
        raise RuntimeError("No walk-forward predictions were produced.")
    predictions = pd.concat(frames, ignore_index=True)
    predictions["rank_probability"] = predictions.groupby("date")[
        "prob_divergence_turn"
    ].rank(method="first", ascending=False)
    predictions["rank_visibility"] = predictions.groupby("date")[
        "turn_visibility_score_rank_pct"
    ].rank(method="first", ascending=False)
    return predictions.sort_values(["date", "rank_probability"]).reset_index(drop=True)


def score_latest_date(
    df: pd.DataFrame,
    historical_predictions: pd.DataFrame,
    label_column: str,
    horizon: int,
    model_kind: str,
) -> pd.DataFrame:
    latest_date = df["date"].max()
    if latest_date <= historical_predictions["date"].max():
        return pd.DataFrame()

    train = df[df["date"] < latest_date].dropna(subset=[label_column]).copy()
    test = df[df["date"] == latest_date].copy()
    if train.empty or test.empty or train[label_column].nunique() < 2:
        return pd.DataFrame()

    model = create_model(model_kind)
    model.fit(train[FEATURE_COLUMNS], train[label_column].astype(int))
    probabilities = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]

    keep = [
        "date",
        "theme_name",
        "theme_code",
        "theme_type",
        "close",
        "amount",
        "position_state",
        "ret_1d",
        "ret_3d",
        "ret_5d",
        "ret_5d_rank_pct",
        "amount_ratio_5_20",
        "divergence_score_rank_pct",
        "turn_visibility_score_rank_pct",
        "market_regime_state",
        "market_regime_score",
        "breadth_ret_5d_positive_pct",
        "breadth_above_ma20_pct",
        "breadth_amount_expand_pct",
        f"fwd_ret_{horizon}d",
        f"fwd_mfe_{horizon}d",
        label_column,
    ]
    block = test[keep].copy()
    block["prob_divergence_turn"] = probabilities
    block["train_rows"] = len(train)
    block["train_start_date"] = train["date"].min()
    block["train_end_date"] = train["date"].max()
    block["rank_probability"] = block["prob_divergence_turn"].rank(
        method="first",
        ascending=False,
    )
    block["rank_visibility"] = block["turn_visibility_score_rank_pct"].rank(
        method="first",
        ascending=False,
    )
    return block


def add_probability_flow(
    predictions: pd.DataFrame,
    flow_low_pp: float,
    flow_high_pp: float,
    top_n: int,
) -> pd.DataFrame:
    result = predictions.sort_values(["theme_name", "date"]).copy()
    grouped = result.groupby("theme_name", group_keys=False)
    result["prob_flow_pp"] = grouped["prob_divergence_turn"].diff() * 100.0
    result["prob_momentum_3d_pp"] = (
        grouped["prob_flow_pp"].rolling(3).mean().reset_index(level=0, drop=True)
    )
    result["prob_momentum_5d_pp"] = (
        grouped["prob_flow_pp"].rolling(5).mean().reset_index(level=0, drop=True)
    )

    def flow_direction(flow_pp: float) -> str:
        if pd.isna(flow_pp) or abs(flow_pp) < flow_low_pp:
            return "stable"
        return "upward" if flow_pp > 0 else "downward"

    def flow_significance(flow_pp: float) -> str:
        if pd.isna(flow_pp) or abs(flow_pp) < flow_low_pp:
            return "low"
        if abs(flow_pp) < flow_high_pp:
            return "medium"
        return "high"

    result["flow_direction"] = result["prob_flow_pp"].map(flow_direction)
    result["flow_significance"] = result["prob_flow_pp"].map(flow_significance)
    result["signal_state"] = [
        classify_signal(
            prob,
            flow,
            momentum,
            rank,
            ret_rank,
            divergence_rank,
            visibility_rank,
            market_score,
            top_n,
        )
        for (
            prob,
            flow,
            momentum,
            rank,
            ret_rank,
            divergence_rank,
            visibility_rank,
            market_score,
        ) in zip(
            result["prob_divergence_turn"],
            result["prob_flow_pp"].fillna(0.0),
            result["prob_momentum_3d_pp"].fillna(0.0),
            result["rank_probability"],
            result["ret_5d_rank_pct"],
            result["divergence_score_rank_pct"],
            result["turn_visibility_score_rank_pct"],
            result["market_regime_score"],
        )
    ]
    return result.sort_values(["date", "rank_probability"]).reset_index(drop=True)


def classify_signal(
    probability: float,
    flow_pp: float,
    momentum_pp: float,
    rank: float,
    ret_5d_rank_pct: float,
    divergence_score_rank_pct: float,
    turn_visibility_score_rank_pct: float,
    market_regime_score: float,
    top_n: int,
) -> str:
    weak_market = pd.notna(market_regime_score) and market_regime_score < 0.45
    if (
        rank <= top_n
        and probability >= 0.65
        and momentum_pp > 0
        and turn_visibility_score_rank_pct >= 0.55
        and ret_5d_rank_pct <= 0.75
    ):
        if weak_market:
            return "risk_off_divergence_watch"
        return "turning_visible"
    if (
        probability >= 0.55
        and divergence_score_rank_pct >= 0.65
        and ret_5d_rank_pct <= 0.75
    ):
        if weak_market:
            return "risk_off_divergence_watch"
        return "early_divergence_watch"
    if ret_5d_rank_pct >= 0.82 and probability < 0.60:
        return "already_extended"
    if probability < 0.35 and flow_pp < 0:
        return "cooling_or_failed"
    return "neutral_or_wait"


def summarize(scored: pd.DataFrame, label_column: str, horizon: int, top_n: int) -> dict[str, object]:
    y_true = scored[label_column].astype(int)
    probabilities = scored["prob_divergence_turn"]
    top_n_rows = scored[scored["rank_probability"] <= top_n]
    latest = scored[scored["date"] == scored["date"].max()].sort_values("rank_probability")
    signal_summary = (
        scored.groupby("signal_state", observed=True)
        .agg(
            rows=(label_column, "size"),
            hit_rate=(label_column, "mean"),
            avg_probability=("prob_divergence_turn", "mean"),
            avg_forward_return=(f"fwd_ret_{horizon}d", "mean"),
            avg_forward_mfe=(f"fwd_mfe_{horizon}d", "mean"),
        )
        .reset_index()
        .sort_values("avg_probability", ascending=False)
    )
    daily_top_n = (
        top_n_rows.groupby("date", observed=True)
        .agg(
            rows=(label_column, "size"),
            hit_rate=(label_column, "mean"),
            avg_forward_return=(f"fwd_ret_{horizon}d", "mean"),
        )
        .reset_index()
    )

    return {
        "rows": int(len(scored)),
        "dates": int(scored["date"].nunique()),
        "themes": int(scored["theme_name"].nunique()),
        "date_start": str(scored["date"].min().date()),
        "date_end": str(scored["date"].max().date()),
        "auc": float(roc_auc_score(y_true, probabilities)) if y_true.nunique() == 2 else None,
        "brier": float(brier_score_loss(y_true, probabilities)),
        "base_positive_rate": float(y_true.mean()),
        "top_n": top_n,
        "top_n_hit_rate": float(top_n_rows[label_column].mean()),
        "top_n_avg_forward_return": float(top_n_rows[f"fwd_ret_{horizon}d"].mean()),
        "daily_top_n_hit_rate_mean": float(daily_top_n["hit_rate"].mean()),
        "signal_summary": signal_summary.to_dict(orient="records"),
        "latest_top": latest.head(top_n).to_dict(orient="records"),
    }


def main() -> None:
    args = parse_args()
    label_column = f"label_divergence_turn_{args.horizon}d"
    df = pd.read_csv(args.input, parse_dates=["date"]).sort_values(["date", "theme_name"])
    required = FEATURE_COLUMNS + [label_column, f"fwd_ret_{args.horizon}d", f"fwd_mfe_{args.horizon}d"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    model_df = df.dropna(subset=FEATURE_COLUMNS + [label_column]).copy()
    historical_predictions = walk_forward_by_date(
        model_df,
        label_column=label_column,
        horizon=args.horizon,
        initial_train_days=args.initial_train_days,
        model_kind=args.model,
        refit_every_days=args.refit_every_days,
    )
    latest_predictions = score_latest_date(
        df,
        historical_predictions=historical_predictions,
        label_column=label_column,
        horizon=args.horizon,
        model_kind=args.model,
    )
    all_predictions = (
        pd.concat([historical_predictions, latest_predictions], ignore_index=True)
        if not latest_predictions.empty
        else historical_predictions
    )
    scored = add_probability_flow(
        all_predictions,
        flow_low_pp=args.flow_low_pp,
        flow_high_pp=args.flow_high_pp,
        top_n=args.top_n,
    )
    validation_scored = scored.dropna(subset=[label_column]).copy()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.output, index=False, encoding="utf-8-sig")

    latest = scored[scored["date"] == scored["date"].max()].sort_values("rank_probability")
    latest_output = latest if args.latest_output_limit <= 0 else latest.head(args.latest_output_limit)
    latest_output.to_csv(args.latest_output, index=False, encoding="utf-8-sig")

    summary = summarize(validation_scored, label_column, args.horizon, args.top_n)
    summary["latest_prediction_date"] = str(scored["date"].max().date())
    summary["latest_prediction_rows"] = int(len(latest))
    summary["latest_prediction_is_labeled"] = bool(latest[label_column].notna().all())
    args.summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"input={args.input}")
    print(f"output={args.output}")
    print(f"latest_output={args.latest_output}")
    print(f"latest_output_rows={len(latest_output)}")
    print(f"summary_output={args.summary_output}")
    print(f"rows={summary['rows']} dates={summary['dates']} themes={summary['themes']}")
    print(f"date_range={summary['date_start']}..{summary['date_end']}")
    print(
        "latest_prediction="
        f"{summary['latest_prediction_date']} "
        f"rows={summary['latest_prediction_rows']} "
        f"labeled={summary['latest_prediction_is_labeled']}"
    )
    if summary["auc"] is None:
        print("auc=None")
    else:
        print(f"auc={summary['auc']:.4f}")
    print(f"brier={summary['brier']:.4f}")
    print(f"base_positive_rate={summary['base_positive_rate']:.4f}")
    print(f"top_{args.top_n}_hit_rate={summary['top_n_hit_rate']:.4f}")
    print(f"top_{args.top_n}_avg_forward_return={summary['top_n_avg_forward_return']:.4f}")
    print("latest_top=")
    print(
        latest[
            [
                "date",
                "rank_probability",
                "theme_name",
                "prob_divergence_turn",
                "prob_flow_pp",
                "prob_momentum_3d_pp",
                "signal_state",
                "position_state",
                "market_regime_state",
                "market_regime_score",
                "breadth_ret_5d_positive_pct",
                "breadth_above_ma20_pct",
                "ret_5d_rank_pct",
                "divergence_score_rank_pct",
                "turn_visibility_score_rank_pct",
                f"fwd_ret_{args.horizon}d",
                label_column,
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
