from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_DATA_DIR = Path("data") / "edp_turning_strategy"


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    candidate_rank: int
    top_n: int
    min_probability: float
    max_ret_5d_rank_pct: float
    min_market_score: float | None
    allow_risk_off_watch: bool
    exclude_cooling: bool
    exclude_already_extended: bool


STRATEGIES = [
    StrategyConfig(
        name="model_top30",
        candidate_rank=30,
        top_n=5,
        min_probability=0.0,
        max_ret_5d_rank_pct=1.0,
        min_market_score=None,
        allow_risk_off_watch=True,
        exclude_cooling=False,
        exclude_already_extended=False,
    ),
    StrategyConfig(
        name="edp_filtered",
        candidate_rank=60,
        top_n=5,
        min_probability=0.50,
        max_ret_5d_rank_pct=0.78,
        min_market_score=None,
        allow_risk_off_watch=True,
        exclude_cooling=True,
        exclude_already_extended=True,
    ),
    StrategyConfig(
        name="edp_risk_adaptive",
        candidate_rank=60,
        top_n=5,
        min_probability=0.50,
        max_ret_5d_rank_pct=0.78,
        min_market_score=0.35,
        allow_risk_off_watch=False,
        exclude_cooling=True,
        exclude_already_extended=True,
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest EDP divergence-turning theme selection strategies."
    )
    parser.add_argument(
        "--rank-input",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d_concept_ths_walk_forward_rank.csv",
    )
    parser.add_argument(
        "--panel-input",
        type=Path,
        default=Path("data")
        / "divergence_turning_point"
        / "divergence_turning_10d_concept_ths_live.csv",
    )
    parser.add_argument("--holding-days", type=int, default=5)
    parser.add_argument("--rebalance-days", type=int, default=None)
    parser.add_argument("--benchmark-top-n", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DATA_DIR)
    return parser.parse_args()


def add_composite_score(rank: pd.DataFrame) -> pd.DataFrame:
    result = rank.copy()
    universe = result.groupby("date", observed=True)["theme_name"].transform("count")
    result["probability_score"] = 1.0 - (
        (result["rank_probability"].astype(float) - 1.0) / (universe.astype(float) - 1.0)
    ).clip(lower=0.0, upper=1.0)
    result["visibility_score"] = result["turn_visibility_score_rank_pct"].fillna(0.5)
    result["divergence_rank_score"] = result["divergence_score_rank_pct"].fillna(0.5)
    result["amount_score"] = (
        result.groupby("date", observed=True)["amount_ratio_5_20"]
        .rank(pct=True)
        .fillna(0.5)
    )
    result["not_extended_score"] = 1.0 - result["ret_5d_rank_pct"].fillna(0.5)
    result["edp_strategy_score"] = (
        result["probability_score"] * 0.42
        + result["divergence_rank_score"] * 0.22
        + result["visibility_score"] * 0.18
        + result["amount_score"] * 0.10
        + result["not_extended_score"] * 0.08
    )
    return result


def strategy_candidates(day: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    candidates = day[day["rank_probability"] <= config.candidate_rank].copy()
    if config.min_probability > 0:
        candidates = candidates[
            candidates["prob_divergence_turn"] >= config.min_probability
        ].copy()
    candidates = candidates[
        candidates["ret_5d_rank_pct"].fillna(1.0) <= config.max_ret_5d_rank_pct
    ].copy()

    if config.min_market_score is not None:
        candidates = candidates[
            candidates["market_regime_score"].fillna(0.0) >= config.min_market_score
        ].copy()
    if not config.allow_risk_off_watch:
        candidates = candidates[
            candidates["signal_state"] != "risk_off_divergence_watch"
        ].copy()
    if config.exclude_cooling:
        candidates = candidates[
            ~candidates["signal_state"].isin(["cooling_or_failed"])
        ].copy()
        candidates = candidates[
            ~candidates["position_state"].isin(["cooling_or_failed"])
        ].copy()
    if config.exclude_already_extended:
        candidates = candidates[
            ~candidates["signal_state"].isin(["already_extended"])
        ].copy()
        candidates = candidates[
            ~candidates["position_state"].isin(["already_extended"])
        ].copy()

    sort_column = "rank_probability" if config.name == "model_top30" else "edp_strategy_score"
    ascending = config.name == "model_top30"
    return candidates.sort_values(sort_column, ascending=ascending).head(config.top_n)


def build_price_tables(panel: pd.DataFrame) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    price = (
        panel.pivot_table(
            index="date",
            columns="theme_name",
            values="close",
            aggfunc="last",
        )
        .sort_index()
        .ffill()
    )
    dates = list(price.index)
    return price, dates


def forward_return(
    price: pd.DataFrame,
    dates: list[pd.Timestamp],
    date: pd.Timestamp,
    theme_names: list[str],
    holding_days: int,
) -> tuple[pd.Timestamp | None, float | None, int]:
    if date not in price.index:
        return None, None, 0
    start_index = dates.index(date)
    exit_index = start_index + holding_days
    if exit_index >= len(dates):
        return None, None, 0
    exit_date = dates[exit_index]
    valid_names = [name for name in theme_names if name in price.columns]
    if not valid_names:
        return exit_date, None, 0
    start_prices = price.loc[date, valid_names]
    exit_prices = price.loc[exit_date, valid_names]
    returns = (exit_prices / start_prices - 1.0).replace([float("inf"), -float("inf")], pd.NA)
    returns = returns.dropna()
    if returns.empty:
        return exit_date, None, 0
    return exit_date, float(returns.mean()), int(len(returns))


def benchmark_return(
    rank_day: pd.DataFrame,
    price: pd.DataFrame,
    dates: list[pd.Timestamp],
    date: pd.Timestamp,
    holding_days: int,
    benchmark_top_n: int,
) -> tuple[float | None, int]:
    if benchmark_top_n > 0:
        names = (
            rank_day.sort_values("rank_probability")
            .head(benchmark_top_n)["theme_name"]
            .astype(str)
            .tolist()
        )
    else:
        names = rank_day["theme_name"].astype(str).tolist()
    _, ret, count = forward_return(price, dates, date, names, holding_days)
    return ret, count


def run_backtest(
    rank: pd.DataFrame,
    panel: pd.DataFrame,
    holding_days: int,
    rebalance_days: int,
    benchmark_top_n: int,
) -> pd.DataFrame:
    price, price_dates = build_price_tables(panel)
    rank_dates = sorted(rank["date"].dropna().unique())
    events: list[dict[str, object]] = []
    selected_dates = rank_dates[::rebalance_days]

    for date in selected_dates:
        rank_day = rank[rank["date"] == date].copy()
        if rank_day.empty or date not in price.index:
            continue
        bench_ret, bench_count = benchmark_return(
            rank_day,
            price,
            price_dates,
            date,
            holding_days,
            benchmark_top_n,
        )
        for config in STRATEGIES:
            picks = strategy_candidates(rank_day, config)
            exit_date, strategy_ret, pick_count = forward_return(
                price,
                price_dates,
                date,
                picks["theme_name"].astype(str).tolist(),
                holding_days,
            )
            if exit_date is None or strategy_ret is None:
                continue
            events.append(
                {
                    "strategy": config.name,
                    "entry_date": date.date().isoformat(),
                    "exit_date": exit_date.date().isoformat(),
                    "holding_days": holding_days,
                    "pick_count": pick_count,
                    "benchmark_count": bench_count,
                    "portfolio_return": strategy_ret,
                    "benchmark_return": bench_ret,
                    "excess_return": strategy_ret - bench_ret if bench_ret is not None else None,
                    "market_regime_state": rank_day["market_regime_state"].mode().iloc[0],
                    "market_regime_score": float(rank_day["market_regime_score"].median()),
                    "selected_themes": ",".join(picks["theme_name"].astype(str).tolist()),
                    "avg_probability": float(picks["prob_divergence_turn"].mean()) if not picks.empty else None,
                    "avg_rank_probability": float(picks["rank_probability"].mean()) if not picks.empty else None,
                    "avg_strategy_score": float(picks["edp_strategy_score"].mean()) if not picks.empty else None,
                }
            )
    return pd.DataFrame(events)


def max_drawdown(returns: pd.Series) -> float:
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min()) if not drawdown.empty else 0.0


def summarize(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for strategy, block in events.groupby("strategy", observed=True):
        returns = block["portfolio_return"].astype(float)
        excess = block["excess_return"].astype(float)
        rows.append(
            {
                "strategy": strategy,
                "events": int(len(block)),
                "avg_return": float(returns.mean()),
                "median_return": float(returns.median()),
                "win_rate": float((returns > 0).mean()),
                "avg_benchmark_return": float(block["benchmark_return"].mean()),
                "avg_excess_return": float(excess.mean()),
                "excess_win_rate": float((excess > 0).mean()),
                "best_return": float(returns.max()),
                "worst_return": float(returns.min()),
                "max_drawdown": max_drawdown(returns),
                "avg_pick_count": float(block["pick_count"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("avg_excess_return", ascending=False)


def write_markdown_report(
    output: Path,
    summary: pd.DataFrame,
    events: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    lines = [
        "# EDP 转向策略回测",
        "",
        "## 参数",
        "",
        f"- rank_input: `{args.rank_input}`",
        f"- panel_input: `{args.panel_input}`",
        f"- holding_days: `{args.holding_days}`",
        f"- rebalance_days: `{args.rebalance_days or args.holding_days}`",
        f"- benchmark_top_n: `{args.benchmark_top_n}`，0 表示全题材等权基准",
        "",
        "## 策略说明",
        "",
        "- `model_top30`：纯模型概率前 30 里取前 5，作为基线。",
        "- `edp_filtered`：模型候选池 + 非过热 + 非冷却 + 分歧/可见性综合分。",
        "- `edp_risk_adaptive`：在 `edp_filtered` 基础上，弱市场阶段空仓或少交易。",
        "",
        "## 汇总",
        "",
        summary.to_markdown(index=False),
        "",
        "## 最近 12 次事件",
        "",
        events.sort_values(["entry_date", "strategy"]).tail(36).to_markdown(index=False),
        "",
        "说明：这是题材指数层回测，不使用当前成分股宽度做历史回测，避免未来函数。",
    ]
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    rebalance_days = args.rebalance_days or args.holding_days
    rank = pd.read_csv(args.rank_input, parse_dates=["date"])
    panel = pd.read_csv(args.panel_input, parse_dates=["date"])
    rank = add_composite_score(rank)

    events = run_backtest(
        rank,
        panel,
        holding_days=args.holding_days,
        rebalance_days=rebalance_days,
        benchmark_top_n=args.benchmark_top_n,
    )
    if events.empty:
        raise RuntimeError("No backtest events were produced.")

    summary = summarize(events)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    events_path = args.output_dir / f"events_{args.holding_days}d.csv"
    summary_path = args.output_dir / f"summary_{args.holding_days}d.csv"
    report_path = args.output_dir / f"report_{args.holding_days}d.md"
    meta_path = args.output_dir / f"meta_{args.holding_days}d.json"
    events.to_csv(events_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    write_markdown_report(report_path, summary, events, args)
    meta_path.write_text(
        json.dumps(
            {
                "rank_input": str(args.rank_input),
                "panel_input": str(args.panel_input),
                "holding_days": args.holding_days,
                "rebalance_days": rebalance_days,
                "benchmark_top_n": args.benchmark_top_n,
                "events": int(len(events)),
                "date_start": str(events["entry_date"].min()),
                "date_end": str(events["entry_date"].max()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"events={events_path}")
    print(f"summary={summary_path}")
    print(f"report={report_path}")
    print("summary_table=")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
