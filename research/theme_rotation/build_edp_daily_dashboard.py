from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_RANK_PATHS = {
    1: Path("data") / "theme_rotation" / "theme_rotation_concept_ths_1d_live_rank.csv",
    3: Path("data") / "theme_rotation" / "theme_rotation_concept_ths_3d_live_rank.csv",
    5: Path("data") / "theme_rotation" / "theme_rotation_concept_ths_5d_live_rank.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="根据 1日、3日、5日 live 题材排名生成 EDP 每日题材看板。"
    )
    parser.add_argument("--rank-1d", type=Path, default=DEFAULT_RANK_PATHS[1])
    parser.add_argument("--rank-3d", type=Path, default=DEFAULT_RANK_PATHS[3])
    parser.add_argument("--rank-5d", type=Path, default=DEFAULT_RANK_PATHS[5])
    parser.add_argument(
        "--breadth-input",
        type=Path,
        default=Path("data")
        / "theme_rotation"
        / "theme_rotation_concept_ths_3d_live_latest_breadth.csv",
    )
    parser.add_argument("--skip-breadth", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data") / "theme_rotation" / "edp_daily_dashboard",
    )
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--mainline-rank", type=int, default=20)
    parser.add_argument("--launch-rank-1d", type=int, default=20)
    parser.add_argument("--launch-rank-3d", type=int, default=45)
    parser.add_argument("--crowded-rank-1d", type=int, default=20)
    parser.add_argument("--crowded-rank-mid", type=int, default=70)
    parser.add_argument("--cooling-rank-3d", type=int, default=60)
    parser.add_argument("--prob-floor", type=float, default=0.55)
    parser.add_argument("--flow-up-pp", type=float, default=0.5)
    parser.add_argument("--flow-down-pp", type=float, default=-1.0)
    parser.add_argument("--momentum-down-pp", type=float, default=-0.5)
    parser.add_argument("--weight-1d", type=float, default=0.2)
    parser.add_argument("--weight-3d", type=float, default=0.5)
    parser.add_argument("--weight-5d", type=float, default=0.3)
    return parser.parse_args()


def latest_rows(path: Path, horizon: int) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date", "train_start_date", "train_end_date"])
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date].copy()
    rename = {
        "prob_strong_theme": f"prob_{horizon}d",
        "rank_probability": f"rank_{horizon}d",
        "prob_flow_pp": f"flow_{horizon}d",
        "prob_momentum_3d_pp": f"momentum3_{horizon}d",
        "prob_momentum_5d_pp": f"momentum5_{horizon}d",
        "signal_state": f"signal_state_{horizon}d",
        "ret_1d": f"ret_1d_{horizon}d",
        "ret_3d": f"ret_3d_{horizon}d",
        "ret_5d": f"ret_5d_{horizon}d",
        "amount_ratio_5_20": f"amount_ratio_5_20_{horizon}d",
        "train_start_date": f"train_start_date_{horizon}d",
        "train_end_date": f"train_end_date_{horizon}d",
    }
    keep = ["date", "theme_name", "theme_code", "theme_type", *rename.keys()]
    missing = [column for column in keep if column not in latest.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    return latest[keep].rename(columns=rename)


def build_universe(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.Timestamp]:
    one = latest_rows(args.rank_1d, 1)
    three = latest_rows(args.rank_3d, 3)
    five = latest_rows(args.rank_5d, 5)

    predict_dates = {one["date"].max(), three["date"].max(), five["date"].max()}
    if len(predict_dates) != 1:
        readable = ", ".join(str(date.date()) for date in sorted(predict_dates))
        raise ValueError(f"1/3/5 rank files have different latest dates: {readable}")
    predict_date = next(iter(predict_dates))

    merged = one.merge(
        three.drop(columns=["date", "theme_code", "theme_type"]),
        on="theme_name",
        how="inner",
    ).merge(
        five.drop(columns=["date", "theme_code", "theme_type"]),
        on="theme_name",
        how="inner",
    )
    universe_size = len(merged)
    if universe_size < 2:
        raise ValueError("Need at least two themes to build cross-sectional scores.")

    for horizon in [1, 3, 5]:
        merged[f"score_{horizon}d"] = 1.0 - (
            (merged[f"rank_{horizon}d"] - 1.0) / (universe_size - 1.0)
        )

    total_weight = args.weight_1d + args.weight_3d + args.weight_5d
    if total_weight <= 0:
        raise ValueError("At least one horizon weight must be positive.")
    merged["consensus_score"] = (
        merged["score_1d"] * args.weight_1d
        + merged["score_3d"] * args.weight_3d
        + merged["score_5d"] * args.weight_5d
    ) / total_weight

    merged["rank_consensus"] = merged["consensus_score"].rank(
        method="first", ascending=False
    )
    return merged, predict_date


def merge_breadth(universe: pd.DataFrame, breadth_input: Path) -> pd.DataFrame:
    if not breadth_input.exists():
        return universe
    breadth = pd.read_csv(breadth_input)
    keep = [
        "theme_name",
        "rank_prob_breadth",
        "rank_change_after_breadth",
        "board_change_pct",
        "rank",
        "rank_total",
        "up_ratio",
        "net_inflow_100m",
        "amount_100m",
        "breadth_score",
        "driver_event",
        "leader_stock",
        "constituent_count",
        "snapshot_at",
    ]
    keep = [column for column in keep if column in breadth.columns]
    return universe.merge(breadth[keep], on="theme_name", how="left")


def add_categories(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    result = df.copy()
    result["is_mainline"] = (
        (result["rank_3d"] <= args.mainline_rank)
        & (result["rank_5d"] <= args.mainline_rank)
        & (result["prob_3d"] >= args.prob_floor)
    )
    result["is_launch"] = (
        (result["rank_1d"] <= args.launch_rank_1d)
        & (result["rank_3d"] <= args.launch_rank_3d)
        & (result["flow_3d"] >= args.flow_up_pp)
        & ~result["is_mainline"]
    )
    result["is_crowded_short_term"] = (
        (result["rank_1d"] <= args.crowded_rank_1d)
        & (
            (result["rank_3d"] > args.crowded_rank_mid)
            | (result["rank_5d"] > args.crowded_rank_mid)
        )
    )
    result["is_cooling"] = (
        (result["rank_3d"] <= args.cooling_rank_3d)
        & (
            (result["flow_3d"] <= args.flow_down_pp)
            | (
                (result["momentum3_3d"] <= args.momentum_down_pp)
                & (result["flow_3d"] <= args.flow_up_pp)
            )
        )
    )

    categories = []
    primary = []
    for row in result.itertuples(index=False):
        row_categories = []
        if row.is_mainline:
            row_categories.append("mainline_candidate")
        if row.is_launch:
            row_categories.append("launch_candidate")
        if row.is_crowded_short_term:
            row_categories.append("crowded_short_term")
        if row.is_cooling:
            row_categories.append("cooling_candidate")
        categories.append(",".join(row_categories) if row_categories else "watchlist")
        primary.append(row_categories[0] if row_categories else "watchlist")
    result["edp_categories"] = categories
    result["primary_category"] = primary
    return result


def dashboard_columns(df: pd.DataFrame) -> list[str]:
    candidates = [
        "date",
        "theme_name",
        "primary_category",
        "edp_categories",
        "rank_consensus",
        "consensus_score",
        "rank_1d",
        "rank_3d",
        "rank_5d",
        "prob_1d",
        "prob_3d",
        "prob_5d",
        "flow_3d",
        "momentum3_3d",
        "rank_prob_breadth",
        "rank_change_after_breadth",
        "board_change_pct",
        "up_ratio",
        "net_inflow_100m",
        "amount_100m",
        "breadth_score",
        "driver_event",
        "leader_stock",
        "constituent_count",
        "train_end_date_1d",
        "train_end_date_3d",
        "train_end_date_5d",
    ]
    return [column for column in candidates if column in df.columns]


def write_category_csvs(
    dashboard: pd.DataFrame,
    output_dir: Path,
    top_n: int,
) -> dict[str, Path]:
    category_specs = {
        "mainline_candidate": ("is_mainline", ["rank_consensus", "rank_prob_breadth"]),
        "launch_candidate": ("is_launch", ["rank_1d", "rank_3d"]),
        "crowded_short_term": ("is_crowded_short_term", ["rank_1d"]),
        "cooling_candidate": ("is_cooling", ["rank_3d"]),
    }
    paths: dict[str, Path] = {}
    columns = dashboard_columns(dashboard)
    for name, (flag, sort_columns) in category_specs.items():
        rows = dashboard[dashboard[flag]].copy()
        sort_columns = [column for column in sort_columns if column in rows.columns]
        if sort_columns:
            rows = rows.sort_values(sort_columns, na_position="last")
        path = output_dir / f"{name}.csv"
        rows[columns].head(top_n).to_csv(path, index=False, encoding="utf-8-sig")
        paths[name] = path
    return paths


def write_markdown(
    dashboard: pd.DataFrame,
    output_path: Path,
    predict_date: pd.Timestamp,
    top_n: int,
) -> None:
    sections = [
        ("主线候选", "is_mainline", ["rank_consensus", "rank_prob_breadth"]),
        ("启动候选", "is_launch", ["rank_1d", "rank_3d"]),
        ("拥挤短线", "is_crowded_short_term", ["rank_1d"]),
        ("退潮候选", "is_cooling", ["rank_3d"]),
    ]
    lines = [
        f"# EDP 每日题材看板 - {predict_date.date()}",
        "",
        "本报告由 1日、3日、5日题材 live 排名生成。",
        "若提供题材内部热度文件，报告会合并同花顺当前快照中的上涨占比、资金流和成交额等解释字段。",
        "",
    ]
    display = [
        "theme_name",
        "rank_consensus",
        "rank_1d",
        "rank_3d",
        "rank_5d",
        "prob_3d",
        "flow_3d",
        "rank_prob_breadth",
        "board_change_pct",
        "up_ratio",
        "net_inflow_100m",
    ]
    display = [column for column in display if column in dashboard.columns]

    for title, flag, sort_columns in sections:
        rows = dashboard[dashboard[flag]].copy()
        sort_columns = [column for column in sort_columns if column in rows.columns]
        if sort_columns:
            rows = rows.sort_values(sort_columns, na_position="last")
        lines.extend([f"## {title}", ""])
        if rows.empty:
            lines.extend(["暂无符合条件的记录。", ""])
            continue
        lines.extend(rows[display].head(top_n).to_markdown(index=False).splitlines())
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    universe, predict_date = build_universe(args)
    dashboard = universe if args.skip_breadth else merge_breadth(universe, args.breadth_input)
    dashboard = add_categories(dashboard, args)
    dashboard = dashboard.sort_values("rank_consensus").reset_index(drop=True)

    columns = dashboard_columns(dashboard)
    dashboard_path = args.output_dir / "dashboard.csv"
    top_path = args.output_dir / "consensus_top.csv"
    summary_path = args.output_dir / "summary.json"
    markdown_path = args.output_dir / "dashboard.md"

    dashboard[columns].to_csv(dashboard_path, index=False, encoding="utf-8-sig")
    dashboard[columns].head(args.top_n).to_csv(top_path, index=False, encoding="utf-8-sig")
    category_paths = write_category_csvs(dashboard, args.output_dir, args.top_n)
    write_markdown(dashboard, markdown_path, predict_date, args.top_n)

    summary = {
        "predict_date": str(predict_date.date()),
        "themes": int(len(dashboard)),
        "top_n": args.top_n,
        "counts": {
            "mainline_candidate": int(dashboard["is_mainline"].sum()),
            "launch_candidate": int(dashboard["is_launch"].sum()),
            "crowded_short_term": int(dashboard["is_crowded_short_term"].sum()),
            "cooling_candidate": int(dashboard["is_cooling"].sum()),
        },
        "outputs": {
            "dashboard": str(dashboard_path),
            "consensus_top": str(top_path),
            "markdown": str(markdown_path),
            **{name: str(path) for name, path in category_paths.items()},
        },
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"predict_date={summary['predict_date']} themes={summary['themes']}")
    print(f"dashboard={dashboard_path}")
    print(f"markdown={markdown_path}")
    print(f"summary={summary_path}")
    print("counts=" + json.dumps(summary["counts"], ensure_ascii=False))
    print("consensus_top=")
    print(
        dashboard[
            [
                "rank_consensus",
                "theme_name",
                "primary_category",
                "rank_1d",
                "rank_3d",
                "rank_5d",
                "prob_3d",
                "flow_3d",
                *[
                    column
                    for column in [
                        "rank_prob_breadth",
                        "board_change_pct",
                        "up_ratio",
                        "net_inflow_100m",
                    ]
                    if column in dashboard.columns
                ],
            ]
        ]
        .head(args.top_n)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
