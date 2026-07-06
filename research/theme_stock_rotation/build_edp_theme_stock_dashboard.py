from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_DATA_DIR = Path("data") / "theme_stock_rotation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="根据题材内部个股 1日、3日、5日排名生成 EDP 个股看板。"
    )
    parser.add_argument("--rank-1d", type=Path, default=DEFAULT_DATA_DIR / "theme_stock_1d_live_rank.csv")
    parser.add_argument("--rank-3d", type=Path, default=DEFAULT_DATA_DIR / "theme_stock_3d_live_rank.csv")
    parser.add_argument("--rank-5d", type=Path, default=DEFAULT_DATA_DIR / "theme_stock_5d_live_rank.csv")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DATA_DIR / "edp_theme_stock_dashboard")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--leader-rank", type=int, default=5)
    parser.add_argument("--launch-rank-1d", type=int, default=5)
    parser.add_argument("--launch-rank-3d", type=int, default=12)
    parser.add_argument("--crowded-rank-1d", type=int, default=5)
    parser.add_argument("--crowded-rank-mid", type=int, default=15)
    parser.add_argument("--cooling-rank-3d", type=int, default=12)
    parser.add_argument("--prob-floor", type=float, default=0.55)
    parser.add_argument("--flow-up-pp", type=float, default=0.5)
    parser.add_argument("--flow-down-pp", type=float, default=-1.0)
    parser.add_argument("--momentum-down-pp", type=float, default=-0.5)
    parser.add_argument("--catchup-ret-pct-max", type=float, default=0.55)
    parser.add_argument("--weight-1d", type=float, default=0.2)
    parser.add_argument("--weight-3d", type=float, default=0.5)
    parser.add_argument("--weight-5d", type=float, default=0.3)
    return parser.parse_args()


def latest_rows(path: Path, horizon: int) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date", "train_start_date", "train_end_date"])
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date].copy()
    rename = {
        "prob_theme_stock": f"prob_{horizon}d",
        "rank_in_theme_probability": f"rank_{horizon}d",
        "prob_flow_pp": f"flow_{horizon}d",
        "prob_momentum_3d_pp": f"momentum3_{horizon}d",
        "prob_momentum_5d_pp": f"momentum5_{horizon}d",
        "signal_state": f"signal_state_{horizon}d",
        "stock_ret_1d": f"stock_ret_1d_{horizon}d",
        "excess_ret_1d": f"excess_ret_1d_{horizon}d",
        "stock_amount_ratio_5_20": f"stock_amount_ratio_5_20_{horizon}d",
        "rank_in_theme_ret_1d": f"rank_ret_1d_{horizon}d",
        "rank_in_theme_ret_1d_pct": f"rank_ret_1d_pct_{horizon}d",
        "rank_in_theme_excess_1d_pct": f"rank_excess_1d_pct_{horizon}d",
        "rank_in_theme_amount_pct": f"rank_amount_pct_{horizon}d",
        "train_start_date": f"train_start_date_{horizon}d",
        "train_end_date": f"train_end_date_{horizon}d",
    }
    keep = [
        "date",
        "theme_source",
        "theme_name",
        "stock_code",
        "stock_name",
        *rename.keys(),
    ]
    keep = [column for column in keep if column in latest.columns]
    missing = [
        column
        for column in ["date", "theme_name", "stock_code", "stock_name", "prob_theme_stock"]
        if column not in latest.columns
    ]
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

    key = ["theme_name", "stock_code"]
    merged = one.merge(
        three.drop(columns=["date", "theme_source", "stock_name"], errors="ignore"),
        on=key,
        how="inner",
    ).merge(
        five.drop(columns=["date", "theme_source", "stock_name"], errors="ignore"),
        on=key,
        how="inner",
    )

    theme_sizes = merged.groupby("theme_name")["stock_code"].transform("count")
    for horizon in [1, 3, 5]:
        merged[f"score_{horizon}d"] = 1.0 - (
            (merged[f"rank_{horizon}d"] - 1.0) / (theme_sizes - 1.0).replace(0, pd.NA)
        )
        merged[f"score_{horizon}d"] = merged[f"score_{horizon}d"].fillna(1.0)

    total_weight = args.weight_1d + args.weight_3d + args.weight_5d
    if total_weight <= 0:
        raise ValueError("At least one horizon weight must be positive.")
    merged["consensus_score"] = (
        merged["score_1d"] * args.weight_1d
        + merged["score_3d"] * args.weight_3d
        + merged["score_5d"] * args.weight_5d
    ) / total_weight
    merged["rank_consensus_in_theme"] = merged.groupby("theme_name")[
        "consensus_score"
    ].rank(method="first", ascending=False)
    return merged, predict_date


def add_categories(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    result = df.copy()
    result["is_leader_candidate"] = (
        (result["rank_3d"] <= args.leader_rank)
        & (result["rank_5d"] <= args.leader_rank)
        & (result["prob_3d"] >= args.prob_floor)
    )
    result["is_launch_candidate"] = (
        (result["rank_1d"] <= args.launch_rank_1d)
        & (result["rank_3d"] <= args.launch_rank_3d)
        & (result["flow_3d"] >= args.flow_up_pp)
        & ~result["is_leader_candidate"]
    )
    result["is_catchup_candidate"] = (
        (result["rank_3d"] <= args.launch_rank_3d)
        & (result["flow_3d"] >= args.flow_up_pp)
        & (result.get("rank_ret_1d_pct_3d", pd.Series(1.0, index=result.index)) <= args.catchup_ret_pct_max)
        & ~result["is_leader_candidate"]
    )
    result["is_crowded_leader"] = (
        (result["rank_1d"] <= args.crowded_rank_1d)
        & (
            (result["rank_3d"] > args.crowded_rank_mid)
            | (result["rank_5d"] > args.crowded_rank_mid)
        )
    )
    result["is_cooling_stock"] = (
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
        if row.is_leader_candidate:
            row_categories.append("leader_candidate")
        if row.is_launch_candidate:
            row_categories.append("launch_candidate")
        if row.is_catchup_candidate:
            row_categories.append("catchup_candidate")
        if row.is_crowded_leader:
            row_categories.append("crowded_leader")
        if row.is_cooling_stock:
            row_categories.append("cooling_stock")
        categories.append(",".join(row_categories) if row_categories else "watchlist")
        primary.append(row_categories[0] if row_categories else "watchlist")
    result["edp_categories"] = categories
    result["primary_category"] = primary
    return result


def dashboard_columns(df: pd.DataFrame) -> list[str]:
    candidates = [
        "date",
        "theme_name",
        "stock_code",
        "stock_name",
        "primary_category",
        "edp_categories",
        "rank_consensus_in_theme",
        "consensus_score",
        "rank_1d",
        "rank_3d",
        "rank_5d",
        "prob_1d",
        "prob_3d",
        "prob_5d",
        "flow_3d",
        "momentum3_3d",
        "stock_ret_1d_3d",
        "excess_ret_1d_3d",
        "rank_ret_1d_pct_3d",
        "rank_excess_1d_pct_3d",
        "rank_amount_pct_3d",
        "stock_amount_ratio_5_20_3d",
        "train_end_date_1d",
        "train_end_date_3d",
        "train_end_date_5d",
    ]
    return [column for column in candidates if column in df.columns]


def write_category_csvs(dashboard: pd.DataFrame, output_dir: Path, top_n: int) -> dict[str, Path]:
    specs = {
        "leader_candidate": ("is_leader_candidate", ["theme_name", "rank_consensus_in_theme"]),
        "launch_candidate": ("is_launch_candidate", ["theme_name", "rank_1d", "rank_3d"]),
        "catchup_candidate": ("is_catchup_candidate", ["theme_name", "rank_3d"]),
        "crowded_leader": ("is_crowded_leader", ["theme_name", "rank_1d"]),
        "cooling_stock": ("is_cooling_stock", ["theme_name", "rank_3d"]),
    }
    columns = dashboard_columns(dashboard)
    paths: dict[str, Path] = {}
    for name, (flag, sort_columns) in specs.items():
        rows = dashboard[dashboard[flag]].copy()
        rows = rows.sort_values([column for column in sort_columns if column in rows.columns])
        path = output_dir / f"{name}.csv"
        rows.groupby("theme_name", group_keys=False).head(top_n)[columns].to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )
        paths[name] = path
    return paths


def write_markdown(
    dashboard: pd.DataFrame,
    output_path: Path,
    predict_date: pd.Timestamp,
    top_n: int,
) -> None:
    display = [
        "theme_name",
        "stock_code",
        "stock_name",
        "rank_consensus_in_theme",
        "rank_1d",
        "rank_3d",
        "rank_5d",
        "prob_3d",
        "flow_3d",
        "stock_ret_1d_3d",
        "excess_ret_1d_3d",
    ]
    display = [column for column in display if column in dashboard.columns]
    sections = [
        ("龙头候选", "is_leader_candidate", ["theme_name", "rank_consensus_in_theme"]),
        ("启动候选", "is_launch_candidate", ["theme_name", "rank_1d"]),
        ("补涨候选", "is_catchup_candidate", ["theme_name", "rank_3d"]),
        ("拥挤龙头", "is_crowded_leader", ["theme_name", "rank_1d"]),
        ("退潮个股", "is_cooling_stock", ["theme_name", "rank_3d"]),
    ]
    lines = [
        f"# EDP 题材内部个股看板 - {predict_date.date()}",
        "",
        "本报告对选定题材内部的成分股进行 1日、3日、5日 EDP 概率排名，并按龙头、启动、补涨、拥挤、退潮状态分类。",
        "",
    ]
    for title, flag, sort_columns in sections:
        rows = dashboard[dashboard[flag]].copy()
        rows = rows.sort_values([column for column in sort_columns if column in rows.columns])
        lines.extend([f"## {title}", ""])
        if rows.empty:
            lines.extend(["暂无符合条件的记录。", ""])
            continue
        rows = rows.groupby("theme_name", group_keys=False).head(top_n)
        lines.extend(rows[display].to_markdown(index=False).splitlines())
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    universe, predict_date = build_universe(args)
    dashboard = add_categories(universe, args).sort_values(
        ["theme_name", "rank_consensus_in_theme"]
    )

    columns = dashboard_columns(dashboard)
    dashboard_path = args.output_dir / "dashboard.csv"
    top_path = args.output_dir / "consensus_top.csv"
    markdown_path = args.output_dir / "dashboard.md"
    summary_path = args.output_dir / "summary.json"

    dashboard[columns].to_csv(dashboard_path, index=False, encoding="utf-8-sig")
    dashboard.groupby("theme_name", group_keys=False).head(args.top_n)[columns].to_csv(
        top_path,
        index=False,
        encoding="utf-8-sig",
    )
    category_paths = write_category_csvs(dashboard, args.output_dir, args.top_n)
    write_markdown(dashboard, markdown_path, predict_date, args.top_n)

    summary = {
        "predict_date": str(predict_date.date()),
        "themes": int(dashboard["theme_name"].nunique()),
        "theme_stock_rows": int(len(dashboard)),
        "top_n": args.top_n,
        "counts": {
            "leader_candidate": int(dashboard["is_leader_candidate"].sum()),
            "launch_candidate": int(dashboard["is_launch_candidate"].sum()),
            "catchup_candidate": int(dashboard["is_catchup_candidate"].sum()),
            "crowded_leader": int(dashboard["is_crowded_leader"].sum()),
            "cooling_stock": int(dashboard["is_cooling_stock"].sum()),
        },
        "outputs": {
            "dashboard": str(dashboard_path),
            "consensus_top": str(top_path),
            "markdown": str(markdown_path),
            **{name: str(path) for name, path in category_paths.items()},
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"predict_date={summary['predict_date']} themes={summary['themes']} "
        f"theme_stock_rows={summary['theme_stock_rows']}"
    )
    print(f"dashboard={dashboard_path}")
    print(f"markdown={markdown_path}")
    print(f"summary={summary_path}")
    print("counts=" + json.dumps(summary["counts"], ensure_ascii=False))
    print("consensus_top=")
    print(
        dashboard[
            [
                "theme_name",
                "rank_consensus_in_theme",
                "stock_code",
                "stock_name",
                "primary_category",
                "rank_1d",
                "rank_3d",
                "rank_5d",
                "prob_3d",
                "flow_3d",
            ]
        ]
        .groupby("theme_name", group_keys=False)
        .head(args.top_n)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
