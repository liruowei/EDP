from __future__ import annotations

import argparse
import copy
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from run_full_market_oos_backtest import (
    DEFAULT_CONFIG,
    fetch_history_direct,
    load_config,
    load_universe,
    output_dir,
    rank_top_per_day,
    rules_from_config,
)
from strategy_core import select_signal_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor full-market second-day low-buy signals.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--end-date", default="", help="YYYYMMDD；留空使用配置或今天。")
    parser.add_argument("--max-stocks", type=int, default=None, help="调试用；留空使用配置。")
    parser.add_argument("--iterations", type=int, default=None, help="循环次数；留空使用配置。")
    parser.add_argument("--interval-seconds", type=int, default=None, help="循环间隔；留空使用配置。")
    parser.add_argument("--refresh-universe", action="store_true")
    return parser.parse_args()


def today_yyyymmdd() -> str:
    return pd.Timestamp.today().strftime("%Y%m%d")


def load_monitor_history(
    universe: pd.DataFrame,
    config: dict[str, Any],
    end_date: str,
    max_stocks: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if max_stocks and max_stocks > 0:
        universe = universe.head(max_stocks).copy()

    frames: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    request_interval = float(config["data"].get("request_interval_seconds", 0.03))
    total = len(universe)
    loaded = 0

    for index, row in enumerate(universe.itertuples(index=False), start=1):
        code = str(row.stock_code).zfill(6)
        name = str(row.stock_name)
        try:
            df = fetch_history_direct(code, name, config)
            if not df.empty:
                frames.append(df)
                loaded += 1
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            failures.append({"stock_code": code, "stock_name": name, "error": error})
            print(f"skip {index}/{total} {code} {name}: {error}", file=sys.stderr)
        if index % 200 == 0 or index == total:
            print(
                "loaded_history="
                f"{index}/{total} loaded={loaded} failures={len(failures)} source=edp_duckdb"
            )
        if request_interval > 0 and index < total:
            time.sleep(request_interval)

    history = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return history, pd.DataFrame(failures)


def close_position_10d(df: pd.DataFrame) -> pd.Series:
    span = df["recent_high_10d"] - df["recent_low_10d"]
    return ((df["close"] - df["recent_low_10d"]) / span).where(span != 0)


def add_rebound_filter(signals: pd.DataFrame, monitor_config: dict[str, Any]) -> pd.DataFrame:
    if signals.empty:
        return signals

    result = signals.copy()
    result["close_pos_10d"] = close_position_10d(result)
    result["pullback_from_recent_high"] = result["close"] / result["recent_high_10d"] - 1.0
    result["buy_high_discount_to_close"] = result["buy_high"] / result["close"] - 1.0

    min_runup = float(monitor_config.get("min_runup_for_watch", 0.5))
    min_amount = float(monitor_config.get("min_amount_for_priority", 1_000_000_000.0))
    strong_amount = float(monitor_config.get("strong_amount", 2_000_000_000.0))
    strong_amp = float(monitor_config.get("strong_amplitude", 0.14))
    extreme_amp = float(monitor_config.get("extreme_amplitude", 0.20))
    min_position = float(monitor_config.get("min_close_position_10d", 0.65))
    discount_low = float(monitor_config.get("discount_low", -0.08))
    discount_high = float(monitor_config.get("discount_high", -0.025))

    result["monitor_runup_ok"] = result["runup_close_8d"] >= min_runup
    result["monitor_amount_ok"] = result["amount"] >= min_amount
    result["monitor_strong_amount"] = result["amount"] >= strong_amount
    result["monitor_amplitude_ok"] = result["intraday_amplitude"] >= strong_amp
    result["monitor_extreme_amplitude"] = result["intraday_amplitude"] >= extreme_amp
    result["monitor_position_ok"] = result["close_pos_10d"] >= min_position
    result["monitor_rank_ok"] = result["rank_in_day"] <= 4
    result["monitor_discount_ok"] = result["buy_high_discount_to_close"].between(discount_low, discount_high)

    result["rebound_filter_score"] = (
        result["monitor_runup_ok"].astype(int) * 2
        + result["monitor_amount_ok"].astype(int)
        + result["monitor_strong_amount"].astype(int)
        + result["monitor_amplitude_ok"].astype(int)
        + result["monitor_extreme_amplitude"].astype(int)
        + result["monitor_position_ok"].astype(int)
        + result["monitor_rank_ok"].astype(int)
        + result["monitor_discount_ok"].astype(int)
    )

    priority_score = int(monitor_config.get("priority_score", 6))
    watch_score = int(monitor_config.get("watch_score", 4))

    def level(row: pd.Series) -> str:
        if (
            int(row["rebound_filter_score"]) >= priority_score
            and bool(row["monitor_runup_ok"])
            and bool(row["monitor_amount_ok"])
            and bool(row["monitor_position_ok"])
        ):
            return "优先入选"
        if int(row["rebound_filter_score"]) >= watch_score and bool(row["monitor_runup_ok"]):
            return "备选观察"
        return "原始信号/谨慎"

    result["monitor_level"] = result.apply(level, axis=1)
    level_order = {"优先入选": 0, "备选观察": 1, "原始信号/谨慎": 2}
    result["monitor_level_order"] = result["monitor_level"].map(level_order).fillna(9)
    return result.sort_values(["monitor_level_order", "rebound_filter_score", "rank_in_day"], ascending=[True, False, True])


def output_paths(config: dict[str, Any], end_date: str) -> dict[str, Path]:
    monitor_config = config.get("monitor", {})
    root = Path(str(monitor_config.get("output_dir") or output_dir(config, None)))
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    run_dir = root / end_date
    run_dir.mkdir(parents=True, exist_ok=True)
    return {
        "dir": run_dir,
        "signals": run_dir / "signals_all.csv",
        "selected": run_dir / "monitor_signals.csv",
        "priority": run_dir / "priority_signals.csv",
        "failures": run_dir / "download_failures.csv",
        "report": run_dir / "report.md",
    }


def display_columns() -> list[str]:
    return [
        "date",
        "stock_code",
        "stock_name",
        "monitor_level",
        "rank_in_day",
        "rebound_filter_score",
        "signal_score",
        "pct_change",
        "intraday_amplitude",
        "turnover",
        "amount",
        "runup_close_8d",
        "close_pos_10d",
        "buy_low",
        "buy_high",
        "reclaim_price",
        "stop_price",
    ]


def write_report(
    path: Path,
    end_date: str,
    signal_date: str,
    selected: pd.DataFrame,
    priority: pd.DataFrame,
    failures: pd.DataFrame,
    config: dict[str, Any],
) -> None:
    lines = [
        "# 次日低吸实盘监控",
        "",
        f"- monitor_date: `{end_date}`",
        f"- signal_date: `{signal_date or '无'}`",
        f"- top_n: `{config.get('monitor', {}).get('top_n', 20)}`",
        f"- download_failures: `{len(failures)}`",
        "",
        "## 优先入选",
        "",
    ]
    if priority.empty:
        lines.append("无优先入选。")
    else:
        lines.append(priority[display_columns()].to_markdown(index=False))
    lines.extend(["", "## 全部监控信号", ""])
    if selected.empty:
        lines.append("无信号。")
    else:
        lines.append(selected[display_columns()].to_markdown(index=False))
    lines.extend(
        [
            "",
            "说明：`monitor_level` 来自全市场回测后提炼的大反弹共性过滤器；这是研究监控，不是交易指令。",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_once(config: dict[str, Any], args: argparse.Namespace, iteration: int) -> dict[str, Path]:
    monitor_config = config.get("monitor", {})
    end_date = args.end_date or str(monitor_config.get("end_date") or "") or today_yyyymmdd()
    config = copy.deepcopy(config)
    config["data"]["end_date"] = end_date

    max_stocks = args.max_stocks
    if max_stocks is None:
        max_stocks = int(monitor_config.get("max_stocks", 0)) or None
    refresh_universe = bool(args.refresh_universe or monitor_config.get("refresh_universe", False))
    top_n = int(monitor_config.get("top_n", config.get("backtest", {}).get("top_n_per_day", 20)))

    paths = output_paths(config, end_date)
    universe = load_universe(config, refresh_universe)
    history, failures = load_monitor_history(universe, config, end_date, max_stocks)
    if history.empty:
        failures.to_csv(paths["failures"], index=False, encoding="utf-8-sig")
        raise RuntimeError(f"No market history was loaded. failure_file={paths['failures']}")
    history["date"] = pd.to_datetime(history["date"])

    rules = rules_from_config(config)
    signals = select_signal_rows(history, rules)
    target_date = history.loc[history["date"] <= pd.to_datetime(end_date), "date"].max()
    signal_date = target_date.strftime("%Y-%m-%d") if pd.notna(target_date) else ""
    if signals.empty or not signal_date:
        selected = signals
    else:
        signal_dates = pd.to_datetime(signals["date"]).dt.strftime("%Y-%m-%d")
        selected = rank_top_per_day(signals[signal_dates == signal_date].copy(), top_n)
    selected = add_rebound_filter(selected, monitor_config)
    priority = selected[selected["monitor_level"] == "优先入选"].copy() if not selected.empty else selected

    signals.to_csv(paths["signals"], index=False, encoding="utf-8-sig")
    selected.to_csv(paths["selected"], index=False, encoding="utf-8-sig")
    priority.to_csv(paths["priority"], index=False, encoding="utf-8-sig")
    failures.to_csv(paths["failures"], index=False, encoding="utf-8-sig")
    write_report(paths["report"], end_date, signal_date, selected, priority, failures, config)

    print(f"iteration={iteration}")
    print(f"monitor_date={end_date}")
    print(f"signal_date={signal_date or 'none'}")
    print(f"history_rows={len(history)}")
    print(f"signals_all={len(signals)}")
    print(f"selected={len(selected)}")
    print(f"priority={len(priority)}")
    print(f"report={paths['report']}")
    if not selected.empty:
        print(selected[display_columns()].to_string(index=False))
    return paths


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    monitor_config = config.get("monitor", {})
    iterations = args.iterations
    if iterations is None:
        iterations = int(monitor_config.get("iterations", 1))
    interval = args.interval_seconds
    if interval is None:
        interval = int(monitor_config.get("interval_seconds", 300))

    for iteration in range(1, max(iterations, 1) + 1):
        run_once(config, args, iteration)
        if iteration < iterations:
            time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("monitor interrupted", file=sys.stderr)
