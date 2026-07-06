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
    "amount_change_3d",
    "amount_change_5d",
    "amount_change_10d",
    "amount_change_20d",
    "volatility_5d",
    "volatility_20d",
    "amount_ratio_5_20",
    "intraday_position",
    "cross_section_ret_1d_rank_pct",
    "cross_section_amount_rank_pct",
    "cross_section_amount_ratio_rank_pct",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Walk-forward rank themes by probability of next-day strength."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data") / "theme_rotation" / "theme_rotation_1d.csv",
    )
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--top-pct", type=int, default=20)
    parser.add_argument("--initial-train-days", type=int, default=252)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--model", choices=["logistic", "hgb"], default="logistic")
    parser.add_argument("--flow-low-pp", type=float, default=5.0)
    parser.add_argument("--flow-high-pp", type=float, default=10.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data") / "theme_rotation" / "theme_rotation_walk_forward_rank.csv",
    )
    parser.add_argument(
        "--latest-output",
        type=Path,
        default=Path("data") / "theme_rotation" / "theme_rotation_latest_rank.csv",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data") / "theme_rotation" / "theme_rotation_summary.json",
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
    initial_train_days: int,
    model_kind: str,
) -> pd.DataFrame:
    dates = sorted(df["date"].dropna().unique())
    if len(dates) <= initial_train_days + 1:
        raise ValueError(
            f"Need more than initial_train_days + 1 dates; got {len(dates)} dates."
        )

    frames: list[pd.DataFrame] = []
    for current_date in dates[initial_train_days:]:
        train = df[df["date"] < current_date].dropna(subset=[label_column]).copy()
        test = df[df["date"] == current_date].copy()
        if train.empty or test.empty:
            continue
        if train[label_column].nunique() < 2:
            continue

        model = create_model(model_kind)
        model.fit(train[FEATURE_COLUMNS], train[label_column].astype(int))
        probabilities = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]

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
                f"fwd_ret_{label_column_horizon(label_column)}d",
                label_column,
            ]
        ].copy()
        block["prob_strong_theme"] = probabilities
        block["train_rows"] = len(train)
        block["train_start_date"] = train["date"].min()
        block["train_end_date"] = train["date"].max()
        frames.append(block)

    if not frames:
        raise RuntimeError("No walk-forward predictions were produced.")
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


def add_probability_flow(
    predictions: pd.DataFrame,
    flow_low_pp: float,
    flow_high_pp: float,
) -> pd.DataFrame:
    result = predictions.sort_values(["theme_name", "date"]).copy()
    grouped = result.groupby("theme_name", group_keys=False)
    result["prob_flow_pp"] = grouped["prob_strong_theme"].diff() * 100.0
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
        classify_signal(prob, flow, momentum, rank)
        for prob, flow, momentum, rank in zip(
            result["prob_strong_theme"],
            result["prob_flow_pp"].fillna(0.0),
            result["prob_momentum_3d_pp"].fillna(0.0),
            result["rank_probability"],
        )
    ]
    return result.sort_values(["date", "rank_probability"]).reset_index(drop=True)


def classify_signal(probability: float, flow_pp: float, momentum_pp: float, rank: float) -> str:
    if rank <= 10 and probability >= 0.65 and momentum_pp > 0:
        return "strong_rising_theme"
    if rank <= 20 and probability >= 0.55 and flow_pp > 0:
        return "rising_candidate"
    if probability < 0.35 and flow_pp < 0:
        return "cooling_theme"
    return "neutral_or_wait"


def summarize(scored: pd.DataFrame, label_column: str, top_n: int) -> dict[str, object]:
    y_true = scored[label_column].astype(int)
    probabilities = scored["prob_strong_theme"]

    top_n_rows = scored[scored["rank_probability"] <= top_n]
    latest = scored[scored["date"] == scored["date"].max()].sort_values("rank_probability")
    signal_summary = (
        scored.groupby("signal_state", observed=True)
        .agg(
            rows=(label_column, "size"),
            hit_rate=(label_column, "mean"),
            avg_probability=("prob_strong_theme", "mean"),
            avg_forward_return=(f"fwd_ret_{label_column_horizon(label_column)}d", "mean"),
        )
        .reset_index()
        .sort_values("avg_probability", ascending=False)
    )
    daily_top_n = (
        top_n_rows.groupby("date", observed=True)
        .agg(
            rows=(label_column, "size"),
            hit_rate=(label_column, "mean"),
            avg_forward_return=(f"fwd_ret_{label_column_horizon(label_column)}d", "mean"),
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
        "top_n_avg_forward_return": float(
            top_n_rows[f"fwd_ret_{label_column_horizon(label_column)}d"].mean()
        ),
        "daily_top_n_hit_rate_mean": float(daily_top_n["hit_rate"].mean()),
        "signal_summary": signal_summary.to_dict(orient="records"),
        "latest_top": latest.head(top_n).to_dict(orient="records"),
    }


def main() -> None:
    args = parse_args()
    label_column = f"label_top_{args.top_pct}pct_{args.horizon}d"
    df = pd.read_csv(args.input, parse_dates=["date"]).sort_values(["date", "theme_name"])

    required = FEATURE_COLUMNS + [label_column, f"fwd_ret_{args.horizon}d"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    model_df = df.dropna(subset=FEATURE_COLUMNS + [label_column]).copy()
    predictions = walk_forward_by_date(
        model_df,
        label_column=label_column,
        initial_train_days=args.initial_train_days,
        model_kind=args.model,
    )
    scored = add_probability_flow(
        predictions,
        flow_low_pp=args.flow_low_pp,
        flow_high_pp=args.flow_high_pp,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.output, index=False, encoding="utf-8-sig")

    latest = scored[scored["date"] == scored["date"].max()].sort_values("rank_probability")
    latest.head(args.top_n).to_csv(args.latest_output, index=False, encoding="utf-8-sig")

    summary = summarize(scored, label_column, args.top_n)
    args.summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"input={args.input}")
    print(f"output={args.output}")
    print(f"latest_output={args.latest_output}")
    print(f"summary_output={args.summary_output}")
    print(f"rows={summary['rows']} dates={summary['dates']} themes={summary['themes']}")
    print(f"date_range={summary['date_start']}..{summary['date_end']}")
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
                "prob_strong_theme",
                "prob_flow_pp",
                "prob_momentum_3d_pp",
                "signal_state",
                "ret_1d",
                f"fwd_ret_{args.horizon}d",
                label_column,
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
