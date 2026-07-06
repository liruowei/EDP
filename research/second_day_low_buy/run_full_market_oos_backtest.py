from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_core import (
    LowBuyRules,
    add_low_buy_features,
    backtest_signal_rows,
    normalize_daily_frame,
    select_signal_rows,
)


DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.full_market_oos.json"
MARKET_DATA_DIR = Path(__file__).resolve().parents[1] / "market_data"
sys.path.insert(0, str(MARKET_DATA_DIR))

from edp_duckdb_store import DuckDBMarketDataStore, default_database_path  # noqa: E402
from akshare_cache import build_current_a_share_universe  # noqa: E402


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def path_value(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root() / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full-market out-of-sample low-buy backtest.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-stocks", type=int, default=None, help="调试用；0/空表示全市场。")
    parser.add_argument("--refresh-universe", action="store_true")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rules_from_config(config: dict[str, Any]) -> LowBuyRules:
    values = config.get("rules", {})
    allowed = set(LowBuyRules.__dataclass_fields__.keys())
    return LowBuyRules(**{key: value for key, value in values.items() if key in allowed})


def ensure_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("当前环境缺少 akshare，无法获取股票列表。") from exc
    return ak


def load_universe(config: dict[str, Any], refresh: bool) -> pd.DataFrame:
    universe_path = path_value(str(config["data"]["universe_cache"]))
    ak = ensure_akshare()
    df = build_current_a_share_universe(ak=ak, config=config, refresh=refresh)
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(universe_path, index=False, encoding="utf-8-sig")
    return df


def normalize_edp_duckdb_frame(df: pd.DataFrame, code: str, name: str) -> pd.DataFrame:
    if df.empty:
        return df
    result = df.copy()
    result["stock_code"] = code
    result["stock_name"] = name
    return normalize_daily_frame(result)


def fetch_history_edp_duckdb(
    code: str,
    name: str,
    config: dict[str, Any],
) -> pd.DataFrame:
    data_config = config["data"]
    start_date = str(data_config["start_date"])
    end_date = str(data_config["end_date"])
    adjust = str(data_config.get("adjust") or "qfq")
    store = DuckDBMarketDataStore(default_database_path(config))
    try:
        df = store.load_history(code, name, start_date=start_date, end_date=end_date, adjust=adjust)
    finally:
        store.close()
    if df.empty:
        raise RuntimeError(f"empty EDP DuckDB market data for {code} {start_date}-{end_date}")
    return normalize_edp_duckdb_frame(df, code, name)


def fetch_history_direct(
    code: str,
    name: str,
    config: dict[str, Any],
) -> pd.DataFrame:
    return fetch_history_edp_duckdb(code, name, config)


def load_one_history(
    row: pd.Series,
    config: dict[str, Any],
) -> pd.DataFrame | None:
    code = str(row["stock_code"]).zfill(6)
    name = str(row["stock_name"])
    return fetch_history_direct(code, name, config)


def load_market_history(
    universe: pd.DataFrame,
    config: dict[str, Any],
    max_stocks: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if max_stocks and max_stocks > 0:
        universe = universe.head(max_stocks).copy()

    request_interval = float(config["data"].get("request_interval_seconds", 0.03))
    frames: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    total = len(universe)
    for index, row in enumerate(universe.itertuples(index=False), start=1):
        series = pd.Series(row._asdict())
        code = str(series["stock_code"]).zfill(6)
        name = str(series["stock_name"])
        try:
            df = load_one_history(series, config)
            if df is not None and not df.empty:
                frames.append(df)
        except Exception as exc:
            failures.append({"stock_code": code, "stock_name": name, "error": f"{type(exc).__name__}: {exc}"})
            print(f"skip {index}/{total} {code} {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
        if index % 100 == 0:
            print(f"history_progress={index}/{total} loaded={len(frames)} failures={len(failures)}", flush=True)
        if request_interval > 0 and index < total:
            time.sleep(request_interval)
    history = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return history, pd.DataFrame(failures)


def rank_top_per_day(signals: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if signals.empty:
        return signals
    result = signals.copy()
    result["rank_in_day"] = result.groupby("date", observed=True)["signal_score"].rank(
        method="first", ascending=False
    )
    return result[result["rank_in_day"] <= top_n].sort_values(["date", "rank_in_day"])


def split_events(events: pd.DataFrame, split: str, train_end: str, test_start: str) -> pd.DataFrame:
    if events.empty:
        return events
    dates = pd.to_datetime(events["signal_date"])
    if split == "in_sample":
        return events[dates <= pd.Timestamp(train_end)].copy()
    if split == "out_of_sample":
        return events[dates >= pd.Timestamp(test_start)].copy()
    return events.copy()


def max_drawdown(returns: pd.Series) -> float:
    equity = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min()) if not drawdown.empty else 0.0


def daily_portfolio(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows = []
    for signal_date, block in events.groupby("signal_date", observed=True):
        returns = block["planned_return_cash_zero"].astype(float)
        rows.append(
            {
                "signal_date": signal_date,
                "selected": int(len(block)),
                "triggered": int(block["touched"].sum()),
                "portfolio_return_cash_zero": float(returns.mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("signal_date")


def summarize_split(events: pd.DataFrame, split_name: str) -> dict[str, Any]:
    if events.empty:
        return {
            "split": split_name,
            "signals": 0,
            "triggered": 0,
            "trigger_rate": 0.0,
            "avg_trade_return": None,
            "avg_planned_return_cash_zero": None,
            "win_rate": None,
            "daily_events": 0,
            "daily_avg_return": None,
            "daily_max_drawdown": None,
        }
    traded = events[events["touched"]].copy()
    planned = events["planned_return_cash_zero"].astype(float)
    daily = daily_portfolio(events)
    trade_returns = traded["return"].astype(float) if not traded.empty else pd.Series(dtype=float)
    return {
        "split": split_name,
        "signals": int(len(events)),
        "triggered": int(len(traded)),
        "trigger_rate": float(len(traded) / len(events)),
        "avg_trade_return": float(trade_returns.mean()) if not trade_returns.empty else None,
        "median_trade_return": float(trade_returns.median()) if not trade_returns.empty else None,
        "avg_planned_return_cash_zero": float(planned.mean()),
        "win_rate": float((trade_returns > 0).mean()) if not trade_returns.empty else None,
        "daily_events": int(len(daily)),
        "daily_avg_return": float(daily["portfolio_return_cash_zero"].mean()) if not daily.empty else None,
        "daily_max_drawdown": max_drawdown(daily["portfolio_return_cash_zero"]) if not daily.empty else None,
    }


def output_dir(config: dict[str, Any], max_stocks: int | None) -> Path:
    suffix = f"max{max_stocks}" if max_stocks and max_stocks > 0 else "full"
    path = path_value(str(config["data"]["output_dir"])) / (
        f"{config['data']['start_date']}_{config['data']['end_date']}_{suffix}"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_report(
    path: Path,
    config: dict[str, Any],
    universe: pd.DataFrame,
    signals: pd.DataFrame,
    selected: pd.DataFrame,
    summary: pd.DataFrame,
    failures: pd.DataFrame,
) -> None:
    lines = [
        "# 全市场样本外次日低吸回测",
        "",
        "## 参数",
        "",
        f"- start_date: `{config['data']['start_date']}`",
        f"- end_date: `{config['data']['end_date']}`",
        f"- train_end_date: `{config['split']['train_end_date']}`",
        f"- test_start_date: `{config['split']['test_start_date']}`",
        f"- top_n_per_day: `{config['backtest']['top_n_per_day']}`",
        f"- universe_size: `{len(universe)}`",
        f"- download_failures: `{len(failures)}`",
        "",
        "## 汇总",
        "",
        summary.to_markdown(index=False) if not summary.empty else "无结果。",
        "",
        "## 最近样本外信号",
        "",
    ]
    if selected.empty:
        lines.append("无信号。")
    else:
        test_start = pd.Timestamp(config["split"]["test_start_date"])
        recent_oos = selected[pd.to_datetime(selected["date"]) >= test_start].tail(30)
        columns = ["date", "stock_code", "stock_name", "rank_in_day", "signal_score", "buy_low", "buy_high"]
        lines.append(recent_oos[columns].to_markdown(index=False) if not recent_oos.empty else "无样本外信号。")
    lines.append("")
    lines.append("说明：这是当前上市股票宇宙的历史回放，仍有幸存者偏差；结果仅供研究。")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    rules = rules_from_config(config)
    max_stocks = args.max_stocks
    if max_stocks is None:
        max_stocks = int(config["data"].get("max_stocks", 0)) or None

    out_dir = output_dir(config, max_stocks)
    universe = load_universe(config, args.refresh_universe)
    history, failures = load_market_history(universe, config, max_stocks)
    if history.empty:
        failures.to_csv(out_dir / "download_failures.csv", index=False, encoding="utf-8-sig")
        raise RuntimeError(f"No market history was loaded. failure_file={out_dir / 'download_failures.csv'}")

    featured = add_low_buy_features(history)
    signals = select_signal_rows(history, rules)
    selected = rank_top_per_day(signals, int(config["backtest"]["top_n_per_day"]))
    events = backtest_signal_rows(featured, selected, rules)
    in_sample = split_events(events, "in_sample", config["split"]["train_end_date"], config["split"]["test_start_date"])
    out_of_sample = split_events(events, "out_of_sample", config["split"]["train_end_date"], config["split"]["test_start_date"])
    summary = pd.DataFrame(
        [
            summarize_split(events, "all"),
            summarize_split(in_sample, "in_sample"),
            summarize_split(out_of_sample, "out_of_sample"),
        ]
    )
    daily = daily_portfolio(events)

    universe.to_csv(out_dir / "universe.csv", index=False, encoding="utf-8-sig")
    failures.to_csv(out_dir / "download_failures.csv", index=False, encoding="utf-8-sig")
    signals.to_csv(out_dir / "signals_all.csv", index=False, encoding="utf-8-sig")
    selected.to_csv(out_dir / "signals_selected_topn.csv", index=False, encoding="utf-8-sig")
    events.to_csv(out_dir / "events_selected_topn.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(out_dir / "daily_portfolio.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out_dir / "summary_by_split.csv", index=False, encoding="utf-8-sig")
    write_report(out_dir / "report.md", config, universe, signals, selected, summary, failures)

    print(f"output_dir={out_dir}")
    print(f"universe={len(universe)}")
    print(f"history_rows={len(history)}")
    print(f"signals_all={len(signals)}")
    print(f"signals_selected={len(selected)}")
    print(f"events={len(events)}")
    print("summary=")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
