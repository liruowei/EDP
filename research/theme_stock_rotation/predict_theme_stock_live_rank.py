from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_COLUMNS = [
    "stock_ret_1d",
    "stock_ret_3d",
    "stock_ret_5d",
    "stock_ret_10d",
    "stock_ret_20d",
    "theme_ret_1d",
    "theme_ret_3d",
    "theme_ret_5d",
    "theme_ret_10d",
    "theme_ret_20d",
    "excess_ret_1d",
    "excess_ret_3d",
    "excess_ret_5d",
    "excess_ret_10d",
    "excess_ret_20d",
    "stock_amount_change_3d",
    "stock_amount_change_5d",
    "stock_amount_change_10d",
    "stock_amount_change_20d",
    "stock_volatility_5d",
    "stock_volatility_20d",
    "stock_amount_ratio_5_20",
    "stock_intraday_position",
    "stock_distance_to_20d_high",
    "stock_recent_limit_up_count_5d",
    "rank_in_theme_ret_1d_pct",
    "rank_in_theme_excess_1d_pct",
    "rank_in_theme_amount_pct",
    "rank_in_theme_amount_ratio_pct",
    "rank_in_theme_distance_high_pct",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict latest stock-in-theme EDP ranking without future labels."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data")
        / "theme_stock_rotation"
        / "theme_stock_1_3_5d_live.csv",
    )
    parser.add_argument("--horizon", type=int, choices=[1, 3, 5], default=3)
    parser.add_argument("--target", choices=["top", "outperform"], default="top")
    parser.add_argument("--top-pct", type=int, default=20)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--model", choices=["logistic", "hgb"], default="logistic")
    parser.add_argument("--predict-date", default="latest")
    parser.add_argument("--flow-lookback-dates", type=int, default=6)
    parser.add_argument("--flow-low-pp", type=float, default=5.0)
    parser.add_argument("--flow-high-pp", type=float, default=10.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data")
        / "theme_stock_rotation"
        / "theme_stock_live_rank.csv",
    )
    parser.add_argument(
        "--latest-output",
        type=Path,
        default=Path("data")
        / "theme_stock_rotation"
        / "theme_stock_live_latest_rank.csv",
    )
    return parser.parse_args()


def label_column(target: str, top_pct: int, horizon: int) -> str:
    if target == "top":
        return f"label_top_{top_pct}pct_in_theme_{horizon}d"
    return f"label_outperform_theme_{horizon}d"


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


def resolve_predict_date(df: pd.DataFrame, value: str) -> pd.Timestamp:
    if value == "latest":
        return df["date"].max()
    return pd.Timestamp(value)


def score_dates(
    df: pd.DataFrame,
    label: str,
    score_date: pd.Timestamp,
    flow_lookback_dates: int,
    model_kind: str,
) -> pd.DataFrame:
    all_dates = sorted(df["date"].dropna().unique())
    if score_date not in all_dates:
        raise ValueError(f"predict date {score_date.date()} is not present in input data.")

    score_index = all_dates.index(score_date)
    first_index = max(0, score_index - flow_lookback_dates + 1)
    dates_to_score = all_dates[first_index : score_index + 1]
    frames: list[pd.DataFrame] = []

    for current_date in dates_to_score:
        train = df[df["date"] < current_date].dropna(subset=[label]).copy()
        test = df[df["date"] == current_date].dropna(subset=FEATURE_COLUMNS).copy()
        if train.empty or test.empty:
            continue
        if train[label].nunique() < 2:
            continue

        model = create_model(model_kind)
        model.fit(train[FEATURE_COLUMNS], train[label].astype(int))
        block = test[
            [
                "date",
                "theme_source",
                "theme_name",
                "stock_code",
                "stock_name",
                "stock_close",
                "stock_amount",
                "theme_close",
                "stock_ret_1d",
                "stock_ret_3d",
                "stock_ret_5d",
                "theme_ret_1d",
                "excess_ret_1d",
                "excess_ret_3d",
                "excess_ret_5d",
                "stock_amount_ratio_5_20",
                "rank_in_theme_ret_1d_pct",
                "rank_in_theme_excess_1d_pct",
                "rank_in_theme_amount_pct",
            ]
        ].copy()
        for column in [
            f"fwd_stock_ret_{label_horizon(label)}d",
            f"fwd_theme_ret_{label_horizon(label)}d",
            f"fwd_excess_ret_{label_horizon(label)}d",
            label,
        ]:
            if column in test.columns:
                block[column] = test[column].values
        block["prob_theme_stock"] = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]
        block["train_rows"] = len(train)
        block["train_start_date"] = train["date"].min()
        block["train_end_date"] = train["date"].max()
        frames.append(block)

    if not frames:
        raise RuntimeError("No live stock-in-theme predictions were produced.")

    predictions = pd.concat(frames, ignore_index=True)
    predictions["rank_in_theme_probability"] = predictions.groupby(
        ["date", "theme_name"]
    )["prob_theme_stock"].rank(method="first", ascending=False)
    predictions["rank_in_theme_ret_1d"] = predictions.groupby(
        ["date", "theme_name"]
    )["stock_ret_1d"].rank(method="first", ascending=False)
    return predictions.sort_values(
        ["date", "theme_name", "rank_in_theme_probability"]
    ).reset_index(drop=True)


def label_horizon(label: str) -> int:
    return int(label.rsplit("_", 1)[-1].removesuffix("d"))


def add_probability_flow(
    predictions: pd.DataFrame,
    flow_low_pp: float,
    flow_high_pp: float,
) -> pd.DataFrame:
    result = predictions.sort_values(["theme_name", "stock_code", "date"]).copy()
    grouped = result.groupby(["theme_name", "stock_code"], group_keys=False)
    result["prob_flow_pp"] = grouped["prob_theme_stock"].diff() * 100.0
    result["prob_momentum_3d_pp"] = (
        grouped["prob_flow_pp"].rolling(3).mean().reset_index(level=[0, 1], drop=True)
    )
    result["prob_momentum_5d_pp"] = (
        grouped["prob_flow_pp"].rolling(5).mean().reset_index(level=[0, 1], drop=True)
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
        classify_signal(prob, flow, momentum, rank)
        for prob, flow, momentum, rank in zip(
            result["prob_theme_stock"],
            result["prob_flow_pp"].fillna(0.0),
            result["prob_momentum_3d_pp"].fillna(0.0),
            result["rank_in_theme_probability"],
        )
    ]
    return result.sort_values(
        ["date", "theme_name", "rank_in_theme_probability"]
    ).reset_index(drop=True)


def classify_signal(probability: float, flow_pp: float, momentum_pp: float, rank: float) -> str:
    if rank <= 3 and probability >= 0.65 and momentum_pp > 0:
        return "leader_candidate"
    if rank <= 10 and probability >= 0.55 and flow_pp > 0:
        return "rising_candidate"
    if probability < 0.40 and flow_pp < 0:
        return "weak_or_cooling"
    return "neutral_or_wait"


def main() -> None:
    args = parse_args()
    label = label_column(args.target, args.top_pct, args.horizon)
    df = pd.read_csv(args.input, parse_dates=["date"]).sort_values(
        ["date", "theme_name", "stock_code"]
    )

    required = FEATURE_COLUMNS + [label]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    predict_date = resolve_predict_date(df, args.predict_date)
    predictions = score_dates(
        df,
        label=label,
        score_date=predict_date,
        flow_lookback_dates=args.flow_lookback_dates,
        model_kind=args.model,
    )
    scored = add_probability_flow(
        predictions,
        flow_low_pp=args.flow_low_pp,
        flow_high_pp=args.flow_high_pp,
    )
    latest = scored[scored["date"] == predict_date].sort_values(
        ["theme_name", "rank_in_theme_probability"]
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.output, index=False, encoding="utf-8-sig")
    latest.groupby("theme_name", group_keys=False).head(args.top_n).to_csv(
        args.latest_output,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"input={args.input}")
    print(f"output={args.output}")
    print(f"latest_output={args.latest_output}")
    print(f"predict_date={predict_date.date()}")
    print(f"target={args.target} horizon={args.horizon}")
    print(f"train_end_date={latest['train_end_date'].max().date()}")
    print("live_top=")
    display_columns = [
        "date",
        "theme_name",
        "rank_in_theme_probability",
        "stock_code",
        "stock_name",
        "prob_theme_stock",
        "prob_flow_pp",
        "prob_momentum_3d_pp",
        "signal_state",
        "stock_ret_1d",
        "excess_ret_1d",
        "stock_amount_ratio_5_20",
    ]
    print(
        latest.groupby("theme_name", group_keys=False)
        .head(args.top_n)[display_columns]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
