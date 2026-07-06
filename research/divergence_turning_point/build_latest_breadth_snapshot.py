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
        description="Overlay latest THS constituent breadth on divergence-turning candidates."
    )
    parser.add_argument(
        "--rank-input",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d_concept_ths_latest_rank.csv",
    )
    parser.add_argument("--theme-source", choices=["concept_ths", "industry_ths"], default="concept_ths")
    parser.add_argument(
        "--top-n",
        type=int,
        default=0,
        help="Limit candidates fetched from rank input. 0 fetches all rows.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.35)
    parser.add_argument("--skip-summary", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d_concept_ths_latest_breadth.csv",
    )
    parser.add_argument(
        "--history-output",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_breadth_snapshot_history.csv",
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
    total = up_count + down_count if up_count is not None and down_count is not None else None
    up_ratio = up_count / total if total else None
    rank_strength = None
    if rank is not None and rank_total and rank_total > 1:
        rank_strength = 1.0 - ((rank - 1) / (rank_total - 1))

    return {
        "snapshot_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "theme_source": source,
        "theme_name": theme_name,
        "board_change_pct": parse_percent(values.get("板块涨幅", "")),
        "rank": rank,
        "rank_total": rank_total,
        "rank_strength": rank_strength,
        "up_count": up_count,
        "down_count": down_count,
        "up_down_total": total,
        "up_ratio": up_ratio,
        "net_inflow_100m": parse_number(values.get("资金净流入(亿)", "")),
        "amount_100m": parse_number(values.get("成交额(亿)", "")),
        "volume_10k_lot": parse_number(values.get("成交量(万手)", "")),
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


def add_scores(merged: pd.DataFrame) -> pd.DataFrame:
    result = merged.copy()
    result["constituent_breadth_score"] = (
        result["up_ratio"].fillna(0.5) * 0.32
        + result["rank_strength"].fillna(0.5) * 0.22
        + result["board_change_pct"].fillna(0.0).rank(pct=True) * 0.14
        + result["net_inflow_100m"].fillna(0.0).rank(pct=True) * 0.20
        + result["amount_100m"].fillna(0.0).rank(pct=True) * 0.12
    )
    result["model_rank_score"] = result["prob_divergence_turn"].rank(pct=True)
    result["position_rank_score"] = (
        result["divergence_score_rank_pct"].fillna(0.5).rank(pct=True) * 0.55
        + result["turn_visibility_score_rank_pct"].fillna(0.5).rank(pct=True) * 0.45
    )
    risk_penalty = result["market_regime_state"].map({"risk_off": 0.86, "mixed": 0.95}).fillna(1.0)
    result["turn_breadth_score"] = (
        result["model_rank_score"] * 0.52
        + result["constituent_breadth_score"].rank(pct=True) * 0.30
        + result["position_rank_score"].rank(pct=True) * 0.18
    ) * risk_penalty
    result["rank_turn_breadth"] = result["turn_breadth_score"].rank(
        method="first",
        ascending=False,
    )
    result["rank_change_after_breadth"] = (
        result["rank_probability"] - result["rank_turn_breadth"]
    )
    result["breadth_confirmation_state"] = [
        classify_confirmation(score, up_ratio, rank_strength, inflow, regime)
        for score, up_ratio, rank_strength, inflow, regime in zip(
            result["constituent_breadth_score"],
            result["up_ratio"],
            result["rank_strength"],
            result["net_inflow_100m"],
            result["market_regime_state"],
        )
    ]
    return result.sort_values("rank_turn_breadth").reset_index(drop=True)


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
    combined = combined.sort_values(["date", "rank_turn_breadth", "theme_name"]).reset_index(
        drop=True
    )
    combined.to_csv(history_output, index=False, encoding="utf-8-sig")


def classify_confirmation(
    score: float,
    up_ratio: float | None,
    rank_strength: float | None,
    net_inflow_100m: float | None,
    market_regime_state: str,
) -> str:
    if pd.isna(score):
        return "breadth_unknown"
    if market_regime_state == "risk_off" and score >= 0.62:
        return "risk_off_breadth_resilient"
    if score >= 0.68 and (up_ratio or 0.0) >= 0.58:
        return "breadth_confirmed"
    if score >= 0.55 and ((rank_strength or 0.0) >= 0.55 or (net_inflow_100m or 0.0) > 0):
        return "breadth_improving"
    if score <= 0.42:
        return "breadth_weak"
    return "breadth_neutral"


def main() -> None:
    args = parse_args()
    rank_df = pd.read_csv(args.rank_input)
    required = {"theme_name", "prob_divergence_turn", "rank_probability"}
    missing = sorted(required - set(rank_df.columns))
    if missing:
        raise ValueError(f"rank input missing columns: {missing}")

    theme_names = rank_df["theme_name"].dropna().astype(str).drop_duplicates()
    if args.top_n > 0:
        theme_names = theme_names.head(args.top_n)
    selected_theme_names = set(theme_names)
    rank_candidates = rank_df[rank_df["theme_name"].astype(str).isin(selected_theme_names)].copy()
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

    merged = pd.merge(rank_candidates, breadth, on="theme_name", how="left")
    if args.theme_source == "concept_ths" and not args.skip_summary:
        try:
            concept_summary = fetch_concept_summary()
            merged = pd.merge(merged, concept_summary, on="theme_name", how="left")
        except Exception as exc:
            print(f"skip concept summary: {exc}")

    scored = add_scores(merged)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.output, index=False, encoding="utf-8-sig")
    if not args.no_history:
        update_snapshot_history(scored, args.history_output)

    print(f"output={args.output}")
    if not args.no_history:
        print(f"history_output={args.history_output}")
    print(f"rows={len(scored)}")
    print("latest_breadth_top=")
    display_columns = [
        "rank_turn_breadth",
        "rank_probability",
        "rank_change_after_breadth",
        "theme_name",
        "prob_divergence_turn",
        "signal_state",
        "breadth_confirmation_state",
        "board_change_pct",
        "up_ratio",
        "rank_strength",
        "net_inflow_100m",
        "amount_100m",
        "leader_stock",
        "constituent_breadth_score",
        "turn_breadth_score",
    ]
    display_columns = [column for column in display_columns if column in scored.columns]
    display_limit = args.top_n if args.top_n > 0 else min(len(scored), 30)
    print(scored[display_columns].head(display_limit).to_string(index=False))


if __name__ == "__main__":
    main()
