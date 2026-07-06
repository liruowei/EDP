from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


DEFAULT_OUTPUT_DIR = Path("data") / "divergence_turning_point" / "edp_divergence_dashboard"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an EDP dashboard for latest divergence-turning candidates."
    )
    parser.add_argument(
        "--breadth-input",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d_concept_ths_latest_breadth.csv",
    )
    parser.add_argument(
        "--summary-input",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d_concept_ths_summary.json",
    )
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def classify_dashboard_group(row: pd.Series) -> str:
    confirmation = str(row.get("breadth_confirmation_state", ""))
    signal = str(row.get("signal_state", ""))
    position = str(row.get("position_state", ""))
    regime = str(row.get("market_regime_state", ""))
    rank = float(row.get("rank_turn_breadth", 9999))

    if rank <= 10 and confirmation in {"breadth_confirmed", "risk_off_breadth_resilient"}:
        if regime == "risk_off":
            return "resilient_watchlist"
        return "confirmed_turning_candidate"
    if rank <= 10 and confirmation == "breadth_neutral":
        return "breadth_unconfirmed_watchlist"
    if rank <= 15 and confirmation == "breadth_improving":
        return "breadth_improving_watchlist"
    if confirmation == "breadth_weak" and rank <= 20:
        return "model_high_breadth_weak"
    if position == "already_extended":
        return "already_extended"
    if "cooling" in signal or position == "cooling_or_failed":
        return "cooling_or_failed"
    return "neutral_or_wait"


def add_dashboard_fields(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["dashboard_group"] = result.apply(classify_dashboard_group, axis=1)
    result["action_priority"] = result["dashboard_group"].map(
        {
            "confirmed_turning_candidate": 1,
            "resilient_watchlist": 2,
            "breadth_unconfirmed_watchlist": 3,
            "breadth_improving_watchlist": 4,
            "model_high_breadth_weak": 5,
            "already_extended": 6,
            "cooling_or_failed": 7,
            "neutral_or_wait": 8,
        }
    ).fillna(9)
    return result.sort_values(["action_priority", "rank_turn_breadth"]).reset_index(drop=True)


def write_group_csvs(scored: pd.DataFrame, output_dir: Path) -> dict[str, int]:
    for old_group_file in output_dir.glob("*.csv"):
        if old_group_file.name != "dashboard.csv":
            old_group_file.unlink()

    group_counts: dict[str, int] = {}
    for group, group_df in scored.groupby("dashboard_group", sort=False):
        group_counts[str(group)] = int(len(group_df))
        group_df.to_csv(output_dir / f"{group}.csv", index=False, encoding="utf-8-sig")
    return group_counts


def build_markdown(scored: pd.DataFrame, summary: dict[str, object], group_counts: dict[str, int]) -> str:
    latest_date = str(scored["date"].max()) if "date" in scored.columns else ""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    regime = scored["market_regime_state"].dropna().astype(str).iloc[0] if "market_regime_state" in scored.columns and not scored.empty else "unknown"
    regime_score = scored["market_regime_score"].dropna().iloc[0] if "market_regime_score" in scored.columns and not scored.empty else None

    lines = [
        "# EDP Divergence Turning Dashboard",
        "",
        f"- Generated at: {generated_at}",
        f"- Latest model date: {latest_date}",
        f"- Market regime: {regime}",
        f"- Market regime score: {regime_score:.4f}" if regime_score is not None else "- Market regime score: unknown",
        f"- Validation AUC: {summary.get('auc')}",
        f"- Base positive rate: {summary.get('base_positive_rate')}",
        f"- Top hit rate: {summary.get('top_n_hit_rate')}",
        "",
        "## Group Counts",
        "",
    ]
    for group, count in group_counts.items():
        lines.append(f"- `{group}`: {count}")

    lines.extend(["", "## Top Candidates", ""])
    display_columns = [
        "rank_turn_breadth",
        "rank_probability",
        "theme_name",
        "dashboard_group",
        "prob_divergence_turn",
        "signal_state",
        "breadth_confirmation_state",
        "board_change_pct",
        "up_ratio",
        "rank_strength",
        "net_inflow_100m",
        "turn_breadth_score",
    ]
    display_columns = [column for column in display_columns if column in scored.columns]
    lines.append(scored[display_columns].head(30).to_markdown(index=False))
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `confirmed_turning_candidate`: model, position, and constituent breadth agree.",
            "- `resilient_watchlist`: weak market regime, but constituent breadth is resilient.",
            "- `breadth_unconfirmed_watchlist`: ranked highly, but constituent breadth is not confirmed.",
            "- `breadth_improving_watchlist`: not fully confirmed, but internal breadth is improving.",
            "- `model_high_breadth_weak`: model probability is high while internal breadth is weak.",
            "- `already_extended`: the move may be late rather than an early turn.",
            "- `cooling_or_failed`: weak follow-through or failed divergence.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.breadth_input)
    if df.empty:
        raise RuntimeError("Breadth input is empty.")
    if args.top_n > 0:
        df = df.head(args.top_n).copy()

    summary = {}
    if args.summary_input.exists():
        summary = json.loads(args.summary_input.read_text(encoding="utf-8"))

    scored = add_dashboard_fields(df)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.output_dir / "dashboard.csv", index=False, encoding="utf-8-sig")
    group_counts = write_group_csvs(scored, args.output_dir)
    (args.output_dir / "summary.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "breadth_input": str(args.breadth_input),
                "summary_input": str(args.summary_input),
                "rows": int(len(scored)),
                "group_counts": group_counts,
                "validation": summary,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (args.output_dir / "dashboard.md").write_text(
        build_markdown(scored, summary, group_counts),
        encoding="utf-8",
    )

    print(f"output_dir={args.output_dir}")
    print("group_counts=")
    for group, count in group_counts.items():
        print(f"{group}={count}")
    print("top_dashboard=")
    print(
        scored[
            [
                "rank_turn_breadth",
                "theme_name",
                "dashboard_group",
                "prob_divergence_turn",
                "breadth_confirmation_state",
                "turn_breadth_score",
            ]
        ]
        .head(15)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
