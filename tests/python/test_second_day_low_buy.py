from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


core = load_module(
    "second_day_low_buy_strategy_core",
    "research/second_day_low_buy/strategy_core.py",
)
sys.path.insert(0, str(REPO_ROOT / "research/second_day_low_buy"))
monitor = load_module(
    "second_day_low_buy_monitor",
    "research/second_day_low_buy/run_low_buy_monitor.py",
)
full_market = sys.modules["run_full_market_oos_backtest"]
single_low_buy = load_module(
    "second_day_low_buy_single",
    "research/second_day_low_buy/run_second_day_low_buy.py",
)


def test_edp_duckdb_database_defaults_to_shared_market_data_path() -> None:
    expected = full_market.repo_root() / "data" / "market_data" / "edp_market_data.duckdb"

    assert full_market.default_database_path({"data": {}}) == expected


def sample_history() -> pd.DataFrame:
    closes = [10.0, 10.2, 10.6, 11.0, 11.5, 12.0, 12.8, 14.2, 14.8, 15.5, 14.2, 14.8, 15.1]
    rows = []
    for index, close in enumerate(closes):
        date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=index)
        if index == 10:
            open_price = 15.1
            high = 15.4
            low = 13.5
            pct_change = (close / closes[index - 1] - 1.0) * 100
            turnover = 12.0
        elif index == 11:
            open_price = 13.7
            high = 14.6
            low = 13.45
            pct_change = (close / closes[index - 1] - 1.0) * 100
            turnover = 9.0
        else:
            open_price = close * 0.98
            high = close * 1.02
            low = close * 0.97
            pct_change = 0.0 if index == 0 else (close / closes[index - 1] - 1.0) * 100
            turnover = 8.0
        rows.append(
            {
                "date": date,
                "stock_code": "300001",
                "stock_name": "样本科技",
                "open": open_price,
                "close": close,
                "high": high,
                "low": low,
                "volume": 100000,
                "amount": 500000000.0,
                "pct_change": pct_change,
                "ret_1d": pct_change / 100.0,
                "turnover": turnover,
            }
        )
    return pd.DataFrame(rows)


def test_select_signal_rows_builds_buy_plan() -> None:
    signals = core.select_signal_rows(sample_history())

    assert len(signals) == 1
    signal = signals.iloc[0]
    assert signal["stock_code"] == "300001"
    assert signal["signal_state"] == "next_day_low_buy_watch"
    assert signal["buy_low"] < signal["buy_high"]
    assert signal["deep_buy_low"] < signal["deep_buy_high"]
    assert signal["stop_price"] < signal["buy_low"]


def test_backtest_triggers_when_next_day_touches_buy_zone() -> None:
    events = core.backtest_signals(sample_history())
    summary = core.summarize_backtest(events)

    assert len(events) == 1
    assert bool(events.iloc[0]["touched"]) is True
    assert events.iloc[0]["return"] > 0
    assert summary.iloc[0]["triggered"] == 1


def test_monitor_rebound_filter_marks_priority_signal() -> None:
    signals = core.select_signal_rows(sample_history())
    signals["rank_in_day"] = 1.0
    signals["amount"] = 2_500_000_000.0
    signals["runup_close_8d"] = 0.55
    signals["intraday_amplitude"] = 0.16
    signals["recent_high_10d"] = signals["close"] / 0.9
    signals["recent_low_10d"] = signals["close"] * 0.7
    signals["buy_high"] = signals["close"] * 0.95

    filtered = monitor.add_rebound_filter(signals, {"priority_score": 6})

    assert filtered.iloc[0]["monitor_level"] == "优先入选"
    assert filtered.iloc[0]["rebound_filter_score"] >= 6


def test_monitor_reads_duckdb_history_without_csv_cache(monkeypatch) -> None:
    universe = pd.DataFrame(
        [{"stock_code": "300001", "stock_name": "样本科技"}]
    )
    calls: list[tuple[str, str, str]] = []

    def fake_fetch(code, name, config):
        calls.append((code, name, config["data"]["end_date"]))
        return pd.DataFrame(
            [
                {
                    "date": "2026-06-29",
                    "stock_code": code,
                    "stock_name": name,
                    "close": 13.0,
                }
            ]
        )

    monkeypatch.setattr(monitor, "fetch_history_direct", fake_fetch)

    history, failures = monitor.load_monitor_history(
        universe,
        {"data": {"request_interval_seconds": 0, "end_date": "20260629"}},
        "20260629",
        None,
    )

    assert calls == [("300001", "样本科技", "20260629")]
    assert len(history) == 1
    assert failures.empty


def test_edp_duckdb_reader_maps_amount_and_turnover(monkeypatch) -> None:
    calls: list[tuple[str, str, str, str]] = []

    class FakeStore:
        def __init__(self, database_path) -> None:
            self.database_path = database_path

        def load_history(self, code, name, start_date=None, end_date=None, adjust=""):
            calls.append((code, start_date, end_date, adjust))
            return pd.DataFrame(
                [
                    {
                        "date": "2026-07-01",
                        "stock_code": code,
                        "stock_name": name,
                        "open": 10.0,
                        "close": 9.5,
                        "high": 10.5,
                        "low": 9.4,
                        "volume": 10000,
                        "amount": 450000000.0,
                        "turnover": 8.5,
                        "amplitude": 11.7,
                        "pct_change": -5.0,
                        "change": -0.5,
                    }
                ]
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(full_market, "DuckDBMarketDataStore", FakeStore)

    df = full_market.fetch_history_direct(
        "300001",
        "样本科技",
        {
            "data": {
                "start_date": "20260701",
                "end_date": "20260701",
                "adjust": "qfq",
                "market_data_db": "data/market_data/edp_market_data.duckdb",
            }
        },
    )

    assert calls == [("300001", "20260701", "20260701", "qfq")]
    assert df.iloc[0]["amount"] == 450000000.0
    assert df.iloc[0]["turnover"] == 8.5
    assert df.iloc[0]["stock_code"] == "300001"


def test_single_low_buy_fetch_daily_history_reads_duckdb(monkeypatch) -> None:
    calls: list[tuple[str, str, str, str]] = []

    class FakeStore:
        def __init__(self, database_path) -> None:
            self.database_path = database_path

        def load_history(self, code, name, start_date=None, end_date=None, adjust=""):
            calls.append((code, start_date, end_date, adjust))
            return pd.DataFrame(
                [
                    {
                        "date": "2026-07-01",
                        "stock_code": code,
                        "stock_name": name,
                        "open": 10.0,
                        "close": 9.6,
                        "high": 10.5,
                        "low": 9.4,
                        "volume": 10000,
                        "amount": 450000000.0,
                        "pct_change": -4.0,
                        "turnover": 8.5,
                    }
                ]
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(single_low_buy, "DuckDBMarketDataStore", FakeStore)

    df = single_low_buy.fetch_daily_history(
        "300001",
        "样本科技",
        {"data": {"adjust": "qfq", "market_data_db": "data/market_data/edp_market_data.duckdb"}},
        "20260701",
        "20260701",
    )

    assert calls == [("300001", "20260701", "20260701", "qfq")]
    assert df.iloc[0]["stock_code"] == "300001"
    assert df.iloc[0]["stock_name"] == "样本科技"
    assert df.iloc[0]["ret_1d"] == -0.04


def test_edp_duckdb_reader_does_not_apply_end_date_validation(monkeypatch) -> None:
    class FakeStore:
        def __init__(self, database_path) -> None:
            pass

        def load_history(self, code, name, start_date=None, end_date=None, adjust=""):
            return pd.DataFrame(
                [
                    {
                        "date": "2026-06-30",
                        "stock_code": code,
                        "stock_name": name,
                        "open": 10.0,
                        "close": 10.0,
                        "high": 10.0,
                        "low": 10.0,
                        "volume": 10000,
                        "amount": 100000000.0,
                        "turnover": 5.0,
                    }
                ]
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(full_market, "DuckDBMarketDataStore", FakeStore)

    df = full_market.fetch_history_direct(
        "300001",
        "样本科技",
        {
            "data": {
                "start_date": "20260630",
                "end_date": "20260701",
            }
        },
    )

    assert df.iloc[0]["date"].strftime("%Y%m%d") == "20260630"
    assert df.iloc[0]["stock_code"] == "300001"


def test_monitor_records_duckdb_read_failures_without_stale_cache_reuse(monkeypatch) -> None:
    universe = pd.DataFrame(
        [
            {"stock_code": f"30000{i}", "stock_name": f"样本{i}"}
            for i in range(1, 8)
        ]
    )

    def fake_fetch(code, name, config):
        if code == "300001":
            return pd.DataFrame(
                [
                    {
                        "date": "2026-07-01",
                        "stock_code": code,
                        "stock_name": name,
                        "close": 10.0,
                    }
                ]
            )
        raise RuntimeError("missing EDP DuckDB market data")

    monkeypatch.setattr(monitor, "fetch_history_direct", fake_fetch)
    monkeypatch.setattr(monitor.time, "sleep", lambda *_args, **_kwargs: None)

    history, failures = monitor.load_monitor_history(
        universe,
        {
            "data": {"request_interval_seconds": 0, "end_date": "20260701"},
        },
        "20260701",
        None,
    )

    assert len(history) == 1
    assert len(failures) == 6
    assert set(failures["stock_code"]) == {f"30000{i}" for i in range(2, 8)}
