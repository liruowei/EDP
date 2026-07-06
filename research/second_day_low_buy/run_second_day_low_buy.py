from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_core import LowBuyRules, backtest_signals, normalize_daily_frame, select_signal_rows, summarize_backtest


DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.json"
MARKET_DATA_DIR = Path(__file__).resolve().parents[1] / "market_data"
sys.path.insert(0, str(MARKET_DATA_DIR))

from edp_duckdb_store import DuckDBMarketDataStore, default_database_path  # noqa: E402
from provider_cache import ProviderCacheStore  # noqa: E402


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def path_value(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root() / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run second-day low-buy stock strategy.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", choices=["daily", "backtest"], default="daily")
    parser.add_argument("--codes", default="", help="逗号分隔股票代码；设置后覆盖配置候选池。")
    parser.add_argument("--end-date", default="", help="YYYYMMDD；留空使用配置或最新。")
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
        raise RuntimeError("当前环境缺少 akshare，暂不能拉取行情。") from exc
    return ak


def parse_codes(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def spot_cache_path(config: dict[str, Any]) -> Path:
    cache_dir = path_value(str(config["data"].get("cache_dir") or "data/second_day_low_buy/cache"))
    snapshot_date = pd.Timestamp.today().strftime("%Y%m%d")
    return cache_dir / "spot" / f"stock_zh_a_spot_em_{snapshot_date}.csv"


def load_spot_snapshot(config: dict[str, Any]) -> pd.DataFrame:
    cache = spot_cache_path(config)
    ak = ensure_akshare()
    store = ProviderCacheStore(cache.parent, provider="akshare", client=ak)
    result = store.get_dataset(
        cache.stem,
        lambda api: api.stock_zh_a_spot_em(),
        refresh=not bool(config["data"].get("use_cache", True)),
        realtime_today=True,
        source_function="akshare.stock_zh_a_spot_em",
        params={"snapshot_date": pd.Timestamp.today().strftime("%Y%m%d")},
        empty_ok=False,
        dtype={"代码": str},
    )
    if "代码" in result.frame.columns:
        result.frame["代码"] = result.frame["代码"].astype(str).str.zfill(6)
    return result.frame


def spot_prefilter(config: dict[str, Any]) -> list[tuple[str, str]]:
    daily = config["daily"]
    spot = load_spot_snapshot(config)
    df = spot.rename(
        columns={
            "代码": "stock_code",
            "名称": "stock_name",
            "最新价": "close",
            "涨跌幅": "pct_change",
            "成交额": "amount",
            "振幅": "amplitude",
            "换手率": "turnover",
            "60日涨跌幅": "ret_60d",
        }
    ).copy()
    for column in ["close", "pct_change", "amount", "amplitude", "turnover", "ret_60d"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df[
        (df["close"] >= float(daily["min_price"]))
        & (df["close"] <= float(daily["max_price"]))
        & (df["pct_change"] <= float(daily["max_signal_pct_change"]))
        & (df["amplitude"] >= float(daily["min_intraday_amplitude_pct"]))
        & (df["turnover"] >= float(daily["min_turnover"]))
        & (df["amount"] >= float(daily["min_amount"]))
        & (df["ret_60d"] >= float(daily["min_ret_60d_pct"]))
    ].copy()
    df = df.sort_values(["ret_60d", "amount"], ascending=[False, False]).head(
        int(daily["max_prefilter_candidates"])
    )
    return [(str(row.stock_code).zfill(6), str(row.stock_name)) for row in df.itertuples()]


def configured_universe(args: argparse.Namespace, config: dict[str, Any]) -> list[tuple[str, str]]:
    override_codes = parse_codes(args.codes)
    if override_codes:
        fallback_names = {
            str(item["code"]).zfill(6): str(item.get("name", item["code"]))
            for item in config["daily"].get("fallback_codes", [])
        }
        return [(code.zfill(6), fallback_names.get(code.zfill(6), code.zfill(6))) for code in override_codes]

    daily = config["daily"]
    configured = daily.get("stock_codes", [])
    if configured:
        return [(str(item["code"]).zfill(6), str(item.get("name", item["code"]))) for item in configured]

    if daily.get("use_spot_prefilter", True):
        universe = spot_prefilter(config)
        if universe:
            return universe

    fallback = daily.get("fallback_codes", [])
    return [(str(item["code"]).zfill(6), str(item.get("name", item["code"]))) for item in fallback]


def fetch_daily_history(
    code: str,
    name: str,
    config: dict[str, Any],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    adjust = str(config["data"].get("adjust") or "qfq")
    store = DuckDBMarketDataStore(default_database_path(config))
    try:
        df = store.load_history(code, name, start_date=start_date, end_date=end_date, adjust=adjust)
    finally:
        store.close()
    if df.empty:
        raise RuntimeError(f"empty EDP DuckDB market data for {code} {start_date}-{end_date}")
    normalized = normalize_daily_frame(df)
    normalized["stock_code"] = code
    normalized["stock_name"] = name
    return normalized


def load_histories(universe: list[tuple[str, str]], config: dict[str, Any], start_date: str, end_date: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for code, name in universe:
        try:
            frames.append(fetch_daily_history(code, name, config, start_date, end_date))
        except Exception as exc:
            print(f"skip {code} {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def output_paths(config: dict[str, Any], run_tag: str) -> dict[str, Path]:
    output_dir = path_value(str(config["data"]["output_dir"])) / run_tag
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "dir": output_dir,
        "candidates": output_dir / "candidates.csv",
        "signals": output_dir / "signals_history.csv",
        "report": output_dir / "report.md",
        "events": output_dir / "backtest_events.csv",
        "summary": output_dir / "backtest_summary.csv",
    }


def signal_display_columns() -> list[str]:
    return [
        "date",
        "stock_code",
        "stock_name",
        "signal_score",
        "close",
        "pct_change",
        "intraday_amplitude",
        "turnover",
        "buy_low",
        "buy_high",
        "deep_buy_low",
        "deep_buy_high",
        "stop_price",
        "reclaim_price",
    ]


def write_report(
    path: Path,
    candidates: pd.DataFrame,
    signals: pd.DataFrame,
    events: pd.DataFrame,
    summary: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    lines = [
        "# 次日低吸选股策略",
        "",
        "## 运行参数",
        "",
        f"- mode: `{args.mode}`",
        f"- end_date: `{args.end_date or 'config/latest'}`",
        "",
        "## 今日候选",
        "",
    ]
    if candidates.empty:
        lines.append("无候选。")
    else:
        lines.append(candidates[signal_display_columns()].to_markdown(index=False))
    lines.extend(["", "## 历史候选", ""])
    if signals.empty:
        lines.append("无历史候选。")
    else:
        lines.append(signals[signal_display_columns()].tail(50).to_markdown(index=False))
    lines.extend(["", "## 回测汇总", ""])
    lines.append(summary.to_markdown(index=False) if not summary.empty else "无回测交易。")
    lines.extend(["", "## 最近回测事件", ""])
    if not events.empty:
        lines.append(events.tail(20).to_markdown(index=False))
    else:
        lines.append("无事件。")
    lines.append("")
    lines.append("说明：本策略是研究用低吸计划生成器，不构成买卖建议。")
    path.write_text("\n".join(lines), encoding="utf-8")


def latest_candidates(signals: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if signals.empty:
        return signals
    latest_date = signals["date"].max()
    return signals[signals["date"] == latest_date].sort_values("signal_score", ascending=False).head(top_n)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    rules = rules_from_config(config)
    start_date = str(config["data"]["start_date"])
    end_date = args.end_date or str(config["data"].get("end_date", ""))
    if not end_date:
        end_date = pd.Timestamp.today().strftime("%Y%m%d")
    run_tag = end_date
    paths = output_paths(config, run_tag)

    universe = configured_universe(args, config)
    if not universe:
        raise RuntimeError(
            "No stock universe was produced. Check spot prefilter/AkShare data source, "
            "or pass --codes for a clearly scoped validation run."
        )
    history = load_histories(universe, config, start_date, end_date)
    if history.empty:
        raise RuntimeError("No history data was loaded.")

    signals = select_signal_rows(history, rules)
    candidates = latest_candidates(signals, int(config["daily"]["top_n"]))
    events = backtest_signals(history, rules) if args.mode == "backtest" else pd.DataFrame()
    summary = summarize_backtest(events)

    candidates.to_csv(paths["candidates"], index=False, encoding="utf-8-sig")
    signals.to_csv(paths["signals"], index=False, encoding="utf-8-sig")
    if not events.empty:
        events.to_csv(paths["events"], index=False, encoding="utf-8-sig")
    if not summary.empty:
        summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    write_report(paths["report"], candidates, signals, events, summary, args)

    print(f"candidates={paths['candidates']}")
    print(f"signals={paths['signals']}")
    print(f"report={paths['report']}")
    if not events.empty:
        print(f"events={paths['events']}")
    if not summary.empty:
        print(f"summary={paths['summary']}")
    if candidates.empty:
        print("latest_candidates=0")
    else:
        print("latest_candidates=")
        print(
            candidates[
                ["date", "stock_code", "stock_name", "signal_score", "buy_low", "buy_high", "deep_buy_low", "deep_buy_high"]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
