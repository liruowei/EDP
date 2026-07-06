from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class LowBuyRules:
    min_close_runup_8d: float = 0.22
    min_max_gain_8d: float = 0.09
    min_signal_drop: float = -0.035
    min_signal_amplitude: float = 0.075
    min_turnover: float = 5.0
    min_amount: float = 300_000_000.0
    max_ma10_break_pct: float = 0.08
    buy_band_pct: float = 0.008
    deep_band_pct: float = 0.012
    stop_buffer_pct: float = 0.015
    max_entry_gap_pct: float = 0.03
    exit_holding_days: int = 1


REQUIRED_COLUMNS = {
    "date",
    "stock_code",
    "stock_name",
    "open",
    "close",
    "high",
    "low",
    "volume",
    "amount",
    "pct_change",
    "turnover",
}


def coalesce_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not df.columns.has_duplicates:
        return df
    columns = []
    for column in dict.fromkeys(df.columns):
        block = df.loc[:, df.columns == column]
        if block.shape[1] == 1:
            series = block.iloc[:, 0]
        else:
            series = block.bfill(axis=1).iloc[:, 0]
        columns.append(series.rename(column))
    return pd.concat(columns, axis=1)


def normalize_daily_frame(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "日期": "date",
        "股票代码": "stock_code",
        "代码": "stock_code",
        "名称": "stock_name",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "涨跌幅": "pct_change",
        "换手率": "turnover",
    }
    result = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}).copy()
    result = coalesce_duplicate_columns(result)
    if "date" in result.columns:
        result["date"] = pd.to_datetime(result["date"])
    if "stock_code" in result.columns:
        result["stock_code"] = result["stock_code"].astype(str).str.extract(r"(\d+)")[0].str.zfill(6)
    for column in ["open", "close", "high", "low", "volume", "amount", "pct_change", "turnover"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    if "pct_change" in result.columns:
        result["ret_1d"] = result["pct_change"] / 100.0
    return result


def add_low_buy_features(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    result = df.sort_values(["stock_code", "date"]).copy()
    grouped = result.groupby("stock_code", group_keys=False, observed=True)

    result["ma5"] = grouped["close"].transform(lambda s: s.rolling(5, min_periods=5).mean())
    result["ma10"] = grouped["close"].transform(lambda s: s.rolling(10, min_periods=10).mean())
    result["ma20"] = grouped["close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    result["prev_close"] = grouped["close"].shift(1)
    result["intraday_amplitude"] = (result["high"] / result["low"] - 1.0).replace([float("inf")], pd.NA)
    result["close_vs_open"] = result["close"] / result["open"] - 1.0

    result["runup_close_8d"] = grouped["close"].transform(
        lambda s: s.shift(1) / s.shift(8).rolling(1).mean() - 1.0
    )
    result["max_gain_8d"] = grouped["ret_1d"].transform(
        lambda s: s.shift(1).rolling(8, min_periods=3).max()
    )
    result["recent_high_10d"] = grouped["high"].transform(
        lambda s: s.shift(1).rolling(10, min_periods=5).max()
    )
    result["recent_low_10d"] = grouped["low"].transform(
        lambda s: s.shift(1).rolling(10, min_periods=5).min()
    )
    result["recent_low_8d"] = grouped["low"].transform(
        lambda s: s.shift(1).rolling(8, min_periods=5).min()
    )
    result["close_to_ma10"] = result["close"] / result["ma10"] - 1.0
    result["distance_to_ma5"] = result["close"] / result["ma5"] - 1.0
    return result


def buy_plan_for_row(row: pd.Series, rules: LowBuyRules = LowBuyRules()) -> dict[str, float]:
    swing_low_source = row["recent_low_8d"] if "recent_low_8d" in row else row.get("recent_low_10d")
    swing_low = float(swing_low_source) if pd.notna(swing_low_source) else float(row["low"])
    swing_high = max(float(row["recent_high_10d"]), float(row["high"]))
    current_low = float(row["low"])
    close = float(row["close"])
    ma5 = float(row["ma5"]) if pd.notna(row["ma5"]) else close
    ma10 = float(row["ma10"]) if pd.notna(row["ma10"]) else close

    if swing_high <= swing_low:
        fib382 = current_low
        fib50 = current_low * 0.97
        fib618 = current_low * 0.94
    else:
        fib382 = swing_high - (swing_high - swing_low) * 0.382
        fib50 = swing_high - (swing_high - swing_low) * 0.500
        fib618 = swing_high - (swing_high - swing_low) * 0.618

    primary_anchor = min(current_low, fib382)
    primary_low = primary_anchor * (1.0 - rules.buy_band_pct)
    primary_high = primary_anchor * (1.0 + rules.buy_band_pct)

    deep_anchor = max(fib50, ma10 if pd.notna(ma10) else fib50, current_low * 0.97)
    deep_low = deep_anchor * (1.0 - rules.deep_band_pct)
    deep_high = deep_anchor * (1.0 + rules.deep_band_pct)
    stop_price = min(fib618, deep_low) * (1.0 - rules.stop_buffer_pct)
    reclaim_price = max(close, ma5)

    return {
        "swing_low": round(swing_low, 4),
        "swing_high": round(swing_high, 4),
        "fib382": round(fib382, 4),
        "fib50": round(fib50, 4),
        "fib618": round(fib618, 4),
        "buy_low": round(primary_low, 4),
        "buy_high": round(primary_high, 4),
        "deep_buy_low": round(deep_low, 4),
        "deep_buy_high": round(deep_high, 4),
        "stop_price": round(stop_price, 4),
        "reclaim_price": round(reclaim_price, 4),
    }


def signal_score(row: pd.Series, rules: LowBuyRules = LowBuyRules()) -> float:
    runup_score = min(max((float(row["runup_close_8d"]) - rules.min_close_runup_8d) / 0.25, 0.0), 1.0)
    gain_score = min(max((float(row["max_gain_8d"]) - rules.min_max_gain_8d) / 0.12, 0.0), 1.0)
    divergence_score = min(
        max((float(row["intraday_amplitude"]) - rules.min_signal_amplitude) / 0.12, 0.0),
        1.0,
    )
    drop_score = min(max((abs(float(row["ret_1d"])) - abs(rules.min_signal_drop)) / 0.10, 0.0), 1.0)
    turnover_score = min(max((float(row["turnover"]) - rules.min_turnover) / 15.0, 0.0), 1.0)
    support_score = 1.0 - min(max(abs(float(row["close_to_ma10"])) / 0.12, 0.0), 1.0)
    return round(
        runup_score * 0.25
        + gain_score * 0.20
        + divergence_score * 0.20
        + drop_score * 0.15
        + turnover_score * 0.10
        + support_score * 0.10,
        6,
    )


def select_signal_rows(df: pd.DataFrame, rules: LowBuyRules = LowBuyRules()) -> pd.DataFrame:
    featured = add_low_buy_features(df)
    mask = (
        (featured["runup_close_8d"] >= rules.min_close_runup_8d)
        & (featured["max_gain_8d"] >= rules.min_max_gain_8d)
        & (featured["ret_1d"] <= rules.min_signal_drop)
        & (featured["intraday_amplitude"] >= rules.min_signal_amplitude)
        & (featured["turnover"] >= rules.min_turnover)
        & (featured["amount"] >= rules.min_amount)
        & (featured["close_to_ma10"] >= -rules.max_ma10_break_pct)
    )
    result = featured[mask].copy()
    if result.empty:
        return result
    plans = result.apply(lambda row: pd.Series(buy_plan_for_row(row, rules)), axis=1)
    result = pd.concat([result.reset_index(drop=True), plans.reset_index(drop=True)], axis=1)
    result["signal_score"] = result.apply(lambda row: signal_score(row, rules), axis=1)
    result["signal_state"] = "next_day_low_buy_watch"
    return result.sort_values(["date", "signal_score"], ascending=[True, False])


def backtest_signal_rows(
    featured: pd.DataFrame,
    signals: pd.DataFrame,
    rules: LowBuyRules = LowBuyRules(),
) -> pd.DataFrame:
    if signals.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    by_code = {
        str(code).zfill(6): block.sort_values("date").reset_index(drop=True)
        for code, block in featured.groupby("stock_code")
    }
    for _, signal in signals.iterrows():
        code = str(signal["stock_code"]).zfill(6)
        if code not in by_code:
            continue
        block = by_code[code]
        signal_positions = block.index[block["date"] == signal["date"]].tolist()
        if not signal_positions:
            continue
        signal_pos = signal_positions[0]
        entry_pos = signal_pos + 1
        exit_pos = entry_pos + rules.exit_holding_days
        if exit_pos >= len(block):
            continue
        entry_row = block.iloc[entry_pos]
        exit_row = block.iloc[exit_pos]
        gap = float(entry_row["open"]) / float(signal["close"]) - 1.0
        touched = (
            gap <= rules.max_entry_gap_pct
            and float(entry_row["low"]) <= float(signal["buy_high"])
            and float(entry_row["high"]) >= float(signal["buy_low"])
        )
        entry_price = float(signal["buy_high"]) if touched else None
        exit_price = float(exit_row["close"]) if touched else None
        rows.append(
            {
                "stock_code": code,
                "stock_name": signal["stock_name"],
                "signal_date": signal["date"].date().isoformat(),
                "entry_date": entry_row["date"].date().isoformat(),
                "exit_date": exit_row["date"].date().isoformat(),
                "signal_score": signal["signal_score"],
                "rank_in_day": signal.get("rank_in_day", None),
                "buy_low": signal["buy_low"],
                "buy_high": signal["buy_high"],
                "entry_low": entry_row["low"],
                "entry_high": entry_row["high"],
                "entry_open": entry_row["open"],
                "entry_close": entry_row["close"],
                "touched": bool(touched),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return": (exit_price / entry_price - 1.0) if touched and entry_price else None,
                "planned_return_cash_zero": (exit_price / entry_price - 1.0) if touched and entry_price else 0.0,
                "stop_price": signal["stop_price"],
                "reclaim_price": signal["reclaim_price"],
            }
        )
    return pd.DataFrame(rows)


def backtest_signals(df: pd.DataFrame, rules: LowBuyRules = LowBuyRules()) -> pd.DataFrame:
    featured = add_low_buy_features(df)
    signals = select_signal_rows(df, rules)
    return backtest_signal_rows(featured, signals, rules)


def summarize_backtest(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    traded = events[events["touched"]].copy()
    if traded.empty:
        return pd.DataFrame(
            [
                {
                    "signals": int(len(events)),
                    "triggered": 0,
                    "trigger_rate": 0.0,
                    "avg_return": None,
                    "win_rate": None,
                    "best_return": None,
                    "worst_return": None,
                }
            ]
        )
    returns = traded["return"].astype(float)
    planned_returns = events["planned_return_cash_zero"].astype(float) if "planned_return_cash_zero" in events.columns else returns
    return pd.DataFrame(
        [
            {
                "signals": int(len(events)),
                "triggered": int(len(traded)),
                "trigger_rate": float(len(traded) / len(events)),
                "avg_return": float(returns.mean()),
                "avg_planned_return_cash_zero": float(planned_returns.mean()),
                "median_return": float(returns.median()),
                "win_rate": float((returns > 0).mean()),
                "best_return": float(returns.max()),
                "worst_return": float(returns.min()),
            }
        ]
    )
