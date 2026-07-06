from __future__ import annotations

import argparse
import re
import time
from datetime import datetime
from pathlib import Path

import akshare as ak
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build latest theme breadth snapshot from AkShare THS board info."
    )
    parser.add_argument(
        "--rank-input",
        type=Path,
        default=Path("data")
        / "theme_rotation"
        / "theme_rotation_concept_ths_3d_latest_rank.csv",
    )
    parser.add_argument("--theme-source", choices=["concept_ths", "industry_ths"], default="concept_ths")
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Skip THS concept summary metadata such as driver event and leader stock.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data") / "theme_rotation" / "theme_rotation_latest_breadth.csv",
    )
    parser.add_argument(
        "--history-output",
        type=Path,
        default=Path("data") / "theme_rotation" / "theme_rotation_breadth_snapshot_history.csv",
        help="Point-in-time latest breadth history. Rows are replaced by date/theme_name.",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Do not append/update the point-in-time breadth history file.",
    )
    return parser.parse_args()


def fetch_info(source: str, theme_name: str) -> pd.DataFrame:
    if source == "concept_ths":
        return ak.stock_board_concept_info_ths(symbol=theme_name)
    return ak.stock_board_industry_info_ths(symbol=theme_name)


def fetch_concept_summary() -> pd.DataFrame:
    summary = ak.stock_board_concept_summary_ths()
    summary = summary.rename(
        columns={
            "日期": "summary_date",
            "概念名称": "theme_name",
            "驱动事件": "driver_event",
            "龙头股": "leader_stock",
            "成分股数量": "constituent_count",
        }
    )
    keep = [
        "summary_date",
        "theme_name",
        "driver_event",
        "leader_stock",
        "constituent_count",
    ]
    missing = [column for column in keep if column not in summary.columns]
    if missing:
        raise ValueError(f"Unexpected THS concept summary columns, missing: {missing}")
    return summary[keep].drop_duplicates(subset=["theme_name"], keep="first")


def info_to_record(source: str, theme_name: str, info: pd.DataFrame) -> dict[str, object]:
    missing = {"项目", "值"} - set(info.columns)
    if missing:
        raise ValueError(f"Unexpected THS info columns, missing: {sorted(missing)}")

    values = dict(zip(info["项目"].astype(str), info["值"].astype(str)))
    up_count, down_count = parse_pair(values.get("涨跌家数", ""))
    rank, rank_total = parse_pair(values.get("涨幅排名", ""))
    board_change_pct = parse_percent(values.get("板块涨幅", ""))
    net_inflow_100m = parse_number(values.get("资金净流入(亿)", ""))
    amount_100m = parse_number(values.get("成交额(亿)", ""))
    volume_10k_lot = parse_number(values.get("成交量(万手)", ""))
    total = up_count + down_count if up_count is not None and down_count is not None else None
    up_ratio = up_count / total if total else None
    rank_strength = None
    if rank is not None and rank_total and rank_total > 1:
        rank_strength = 1.0 - ((rank - 1) / (rank_total - 1))

    return {
        "snapshot_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "theme_source": source,
        "theme_name": theme_name,
        "board_change_pct": board_change_pct,
        "rank": rank,
        "rank_total": rank_total,
        "rank_strength": rank_strength,
        "up_count": up_count,
        "down_count": down_count,
        "up_down_total": total,
        "up_ratio": up_ratio,
        "net_inflow_100m": net_inflow_100m,
        "amount_100m": amount_100m,
        "volume_10k_lot": volume_10k_lot,
        "open": parse_number(values.get("今开", "")),
        "previous_close": parse_number(values.get("昨收", "")),
        "high": parse_number(values.get("最高", "")),
        "low": parse_number(values.get("最低", "")),
    }


def parse_pair(value: str) -> tuple[int | None, int | None]:
    match = re.search(r"(-?\d+)\s*/\s*(-?\d+)", value)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_percent(value: str) -> float | None:
    if not value or value == "--":
        return None
    return parse_number(value.replace("%", ""))


def parse_number(value: str) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text == "--":
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def update_snapshot_history(scored: pd.DataFrame, history_output: Path) -> None:
    history_output.parent.mkdir(parents=True, exist_ok=True)
    current = scored.copy()
    if "date" not in current.columns:
        raise ValueError("Breadth snapshot must include model date column `date`.")
    current["date"] = pd.to_datetime(current["date"]).dt.strftime("%Y-%m-%d")
    current["history_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if history_output.exists():
        history = pd.read_csv(history_output)
        if "date" in history.columns:
            history["date"] = pd.to_datetime(history["date"]).dt.strftime("%Y-%m-%d")
        combined = pd.concat([history, current], ignore_index=True, sort=False)
    else:
        combined = current

    combined = combined.drop_duplicates(subset=["date", "theme_name"], keep="last")
    combined = combined.sort_values(["date", "rank_prob_breadth", "theme_name"]).reset_index(
        drop=True
    )
    combined.to_csv(history_output, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    rank_df = pd.read_csv(args.rank_input)
    if "theme_name" not in rank_df.columns:
        raise ValueError("rank input must include a theme_name column.")
    if "prob_strong_theme" not in rank_df.columns:
        raise ValueError("rank input must include a prob_strong_theme column.")

    theme_names = rank_df["theme_name"].dropna().astype(str).drop_duplicates().head(args.top_n)
    records: list[dict[str, object]] = []

    for index, theme_name in enumerate(theme_names, start=1):
        print(f"[{index}/{len(theme_names)}] fetch breadth: {theme_name}")
        try:
            info = fetch_info(args.theme_source, theme_name)
            records.append(info_to_record(args.theme_source, theme_name, info))
        except Exception as exc:
            print(f"skip {theme_name}: {exc}")
        time.sleep(args.sleep_seconds)

    breadth = pd.DataFrame(records)
    if breadth.empty:
        raise RuntimeError("No breadth snapshot rows were produced.")

    merged = pd.merge(rank_df, breadth, on="theme_name", how="left")
    if args.theme_source == "concept_ths" and not args.skip_summary:
        try:
            concept_summary = fetch_concept_summary()
            merged = pd.merge(merged, concept_summary, on="theme_name", how="left")
        except Exception as exc:
            print(f"skip concept summary: {exc}")

    merged["breadth_score"] = (
        merged["up_ratio"].fillna(0.5) * 0.35
        + merged["rank_strength"].fillna(0.5) * 0.25
        + merged["board_change_pct"].fillna(0.0).rank(pct=True) * 0.10
        + merged["net_inflow_100m"].fillna(0.0).rank(pct=True) * 0.20
        + merged["amount_100m"].fillna(0.0).rank(pct=True) * 0.10
    )
    merged["prob_breadth_score"] = (
        merged["prob_strong_theme"].rank(pct=True) * 0.65
        + merged["breadth_score"].rank(pct=True) * 0.35
    )
    merged["rank_prob_breadth"] = merged["prob_breadth_score"].rank(
        method="first", ascending=False
    )
    merged["rank_change_after_breadth"] = (
        merged["rank_probability"] - merged["rank_prob_breadth"]
    )
    merged = merged.sort_values("rank_prob_breadth")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False, encoding="utf-8-sig")
    if not args.no_history:
        update_snapshot_history(merged, args.history_output)

    print(f"output={args.output}")
    if not args.no_history:
        print(f"history_output={args.history_output}")
    print("latest_breadth_top=")
    display_columns = [
        "rank_prob_breadth",
        "rank_probability",
        "rank_change_after_breadth",
        "theme_name",
        "prob_strong_theme",
        "board_change_pct",
        "rank",
        "rank_total",
        "up_ratio",
        "net_inflow_100m",
        "amount_100m",
        "leader_stock",
        "breadth_score",
        "prob_breadth_score",
    ]
    display_columns = [column for column in display_columns if column in merged.columns]
    print(
        merged[display_columns]
        .head(args.top_n)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
