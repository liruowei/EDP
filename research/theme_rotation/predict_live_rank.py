from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from walk_forward_rank import (
    FEATURE_COLUMNS,
    add_probability_flow,
    create_model,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict latest available theme ranking without requiring future labels."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data")
        / "theme_rotation"
        / "theme_rotation_1_3_5d_concept_ths_live.csv",
    )
    parser.add_argument("--horizon", type=int, choices=[1, 3, 5], default=3)
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
        default=Path("data") / "theme_rotation" / "theme_rotation_live_rank.csv",
    )
    parser.add_argument(
        "--latest-output",
        type=Path,
        default=Path("data") / "theme_rotation" / "theme_rotation_live_latest_rank.csv",
    )
    return parser.parse_args()


def resolve_predict_date(df: pd.DataFrame, value: str) -> pd.Timestamp:
    if value == "latest":
        return df["date"].max()
    return pd.Timestamp(value)


def score_dates(
    df: pd.DataFrame,
    label_column: str,
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
        train = df[df["date"] < current_date].dropna(subset=[label_column]).copy()
        test = df[df["date"] == current_date].dropna(subset=FEATURE_COLUMNS).copy()
        if train.empty or test.empty:
            continue
        if train[label_column].nunique() < 2:
            continue

        model = create_model(model_kind)
        model.fit(train[FEATURE_COLUMNS], train[label_column].astype(int))
        block = test[
            [
                "date",
                "theme_name",
                "theme_code",
                "theme_type",
                "close",
                "amount",
                "ret_1d",
                "ret_3d",
                "ret_5d",
                "amount_ratio_5_20",
            ]
        ].copy()
        optional_columns = [f"fwd_ret_{label_column_horizon(label_column)}d", label_column]
        for column in optional_columns:
            if column in test.columns:
                block[column] = test[column].values
        block["prob_strong_theme"] = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]
        block["train_rows"] = len(train)
        block["train_start_date"] = train["date"].min()
        block["train_end_date"] = train["date"].max()
        frames.append(block)

    if not frames:
        raise RuntimeError("No live predictions were produced.")

    predictions = pd.concat(frames, ignore_index=True)
    predictions["rank_probability"] = predictions.groupby("date")["prob_strong_theme"].rank(
        method="first",
        ascending=False,
    )
    predictions["rank_ret_1d"] = predictions.groupby("date")["ret_1d"].rank(
        method="first",
        ascending=False,
    )
    return predictions.sort_values(["date", "rank_probability"]).reset_index(drop=True)


def label_column_horizon(label_column: str) -> int:
    return int(label_column.rsplit("_", 1)[-1].removesuffix("d"))


def main() -> None:
    args = parse_args()
    label_column = f"label_top_{args.top_pct}pct_{args.horizon}d"
    df = pd.read_csv(args.input, parse_dates=["date"]).sort_values(["date", "theme_name"])

    required = FEATURE_COLUMNS + [label_column]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    predict_date = resolve_predict_date(df, args.predict_date)
    predictions = score_dates(
        df,
        label_column=label_column,
        score_date=predict_date,
        flow_lookback_dates=args.flow_lookback_dates,
        model_kind=args.model,
    )
    scored = add_probability_flow(
        predictions,
        flow_low_pp=args.flow_low_pp,
        flow_high_pp=args.flow_high_pp,
    )
    latest = scored[scored["date"] == predict_date].sort_values("rank_probability")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.output, index=False, encoding="utf-8-sig")
    latest.head(args.top_n).to_csv(args.latest_output, index=False, encoding="utf-8-sig")

    print(f"input={args.input}")
    print(f"output={args.output}")
    print(f"latest_output={args.latest_output}")
    print(f"predict_date={predict_date.date()}")
    print(f"train_end_date={latest['train_end_date'].iloc[0].date()}")
    print("live_top=")
    display_columns = [
        "date",
        "rank_probability",
        "theme_name",
        "prob_strong_theme",
        "prob_flow_pp",
        "prob_momentum_3d_pp",
        "signal_state",
        "ret_1d",
        "ret_3d",
        "ret_5d",
        "amount_ratio_5_20",
    ]
    print(latest[display_columns].head(args.top_n).to_string(index=False))


if __name__ == "__main__":
    main()
