from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


market_data = load_module(
    "edp_market_data_store",
    "research/market_data/edp_duckdb_store.py",
)


def test_normalize_raw_daily_keeps_unadjusted_prices_and_percent_turnover() -> None:
    raw = pd.DataFrame(
        [
            {
                "date": "2026-07-02",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 10000,
                "amount": 123000000.0,
                "outstanding_share": 1000000.0,
                "turnover": 0.052,
            }
        ]
    )

    result = market_data.normalize_raw_daily(raw, "1", "平安银行")

    assert result.iloc[0]["stock_code"] == "000001"
    assert result.iloc[0]["close"] == 10.2
    assert result.iloc[0]["turnover_rate"] == 5.2


def test_persistable_end_date_never_returns_today() -> None:
    assert market_data.persistable_end_date("20260703", today=date(2026, 7, 3)) == "20260702"
    assert market_data.persistable_end_date("20260702", today=date(2026, 7, 3)) == "20260702"


def test_infer_reliable_data_time_for_intraday_periods() -> None:
    before_close = pd.Timestamp("2026-07-03 14:35:00", tz=market_data.CHINA_TZ)
    after_close = pd.Timestamp("2026-07-03 15:04:00", tz=market_data.CHINA_TZ)

    assert market_data.infer_reliable_data_time(
        "1d",
        "2026-07-02 15:03:00",
        now=after_close,
    ) == pd.Timestamp("2026-07-02")
    assert market_data.infer_reliable_data_time(
        "15m",
        "2026-07-03 14:30:00",
        now=before_close,
    ) == pd.Timestamp("2026-07-03 14:15:00")
    assert market_data.infer_reliable_data_time(
        "15m",
        "2026-07-03 14:45:00",
        now=after_close,
    ) == pd.Timestamp("2026-07-03 14:45:00")


def test_duckdb_sync_status_roundtrip(tmp_path: Path) -> None:
    store = market_data.DuckDBMarketDataStore(tmp_path / "market.duckdb")
    try:
        store.save_sync_status(
            "1",
            "1d",
            pd.Timestamp("2026-07-02 15:03:00"),
            "stock_daily_raw",
            "downloaded_daily",
        )
        status = store.load_sync_status("000001", "1d")
    finally:
        store.close()

    assert status is not None
    assert status.stock_code == "000001"
    assert status.period == "1d"
    assert status.reliable_data_time == pd.Timestamp("2026-07-02")
    assert status.reason == "downloaded_daily"


def test_save_period_sync_from_latest_bar_uses_period_rules(tmp_path: Path) -> None:
    store = market_data.DuckDBMarketDataStore(tmp_path / "market.duckdb")
    try:
        reliable = store.save_period_sync_from_latest_bar(
            "1",
            "15m",
            "2026-07-03 14:30:00",
            "akshare.intraday",
            "newer_bar_observed",
            now=pd.Timestamp("2026-07-03 14:35:00", tz=market_data.CHINA_TZ),
        )
        status = store.load_sync_status("000001", "15m")
    finally:
        store.close()

    assert reliable == pd.Timestamp("2026-07-03 14:15:00")
    assert status is not None
    assert status.reliable_data_time == pd.Timestamp("2026-07-03 14:15:00")
    assert status.period == "15m"


def test_normalize_live_spot_snapshot_maps_realtime_columns() -> None:
    raw = pd.DataFrame(
        [
            {
                "代码": "1",
                "名称": "平安银行",
                "今开": 11.0,
                "最高": 11.5,
                "最低": 10.9,
                "最新价": 11.2,
                "成交量": 10000,
                "成交额": 123000000.0,
                "换手率": 3.5,
            }
        ]
    )

    result = market_data.normalize_live_spot_snapshot(raw, date(2026, 7, 3))

    assert result.iloc[0]["stock_code"] == "000001"
    assert result.iloc[0]["trade_date"] == date(2026, 7, 3)
    assert result.iloc[0]["close"] == 11.2
    assert result.iloc[0]["turnover_rate"] == 3.5
    assert result.iloc[0]["source"] == "akshare.stock_zh_a_spot_em.live"


def test_append_live_today_uses_memory_snapshot_without_persisting(monkeypatch) -> None:
    raw = pd.DataFrame(
        [
            {
                "stock_code": "000001",
                "trade_date": date(2026, 7, 2),
                "stock_name": "平安银行",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 10000,
                "amount": 123000000.0,
                "turnover_rate": 5.2,
            }
        ]
    )
    live = pd.DataFrame(
        [
            {
                "stock_code": "000001",
                "trade_date": date(2026, 7, 3),
                "stock_name": "平安银行",
                "open": 10.3,
                "high": 10.8,
                "low": 10.1,
                "close": 10.6,
                "volume": 8000,
                "amount": 88000000.0,
                "turnover_rate": 4.0,
                "source": "akshare.stock_zh_a_spot_em.live",
            }
        ]
    )

    monkeypatch.setattr(market_data, "fetch_live_today_raw", lambda today=None: live)

    result = market_data.maybe_append_live_today(
        raw,
        "000001",
        "平安银行",
        "20260701",
        "20260703",
        today=date(2026, 7, 3),
    )

    assert result["trade_date"].tolist() == [date(2026, 7, 2), date(2026, 7, 3)]
    assert result.iloc[-1]["source"] == "akshare.stock_zh_a_spot_em.live"


def test_live_today_snapshot_cache_refreshes_after_ttl() -> None:
    market_data._LIVE_TODAY_RAW_CACHE.clear()

    class FakeAk:
        def __init__(self) -> None:
            self.calls = 0

        def stock_zh_a_spot_em(self) -> pd.DataFrame:
            self.calls += 1
            return pd.DataFrame(
                [
                    {
                        "代码": "1",
                        "名称": "平安银行",
                        "今开": 10.0,
                        "最高": 10.5,
                        "最低": 9.8,
                        "最新价": 10.0 + self.calls,
                        "成交量": 10000,
                        "成交额": 123000000.0,
                        "换手率": 3.5,
                    }
                ]
            )

    ak = FakeAk()

    first = market_data.fetch_live_today_raw(ak=ak, today=date(2026, 7, 3), max_age_seconds=999)
    second = market_data.fetch_live_today_raw(ak=ak, today=date(2026, 7, 3), max_age_seconds=999)
    refreshed = market_data.fetch_live_today_raw(ak=ak, today=date(2026, 7, 3), max_age_seconds=-1)

    assert ak.calls == 2
    assert first.iloc[0]["close"] == second.iloc[0]["close"]
    assert refreshed.iloc[0]["close"] != first.iloc[0]["close"]


def test_apply_qfq_adjustment_uses_factor_as_divisor() -> None:
    raw = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2025-01-01"),
                "stock_code": "000001",
                "stock_name": "平安银行",
                "open": 10.32906764,
                "high": 10.32906764,
                "low": 10.32906764,
                "close": 10.32906764,
                "volume": 10000,
                "amount": 123000000.0,
                "turnover_rate": 5.0,
            },
            {
                "date": pd.Timestamp("2026-06-11"),
                "stock_code": "000001",
                "stock_name": "平安银行",
                "open": 11.0,
                "high": 12.0,
                "low": 10.0,
                "close": 11.3,
                "volume": 10000,
                "amount": 123000000.0,
                "turnover_rate": 5.0,
            },
            {
                "date": pd.Timestamp("2026-06-12"),
                "stock_code": "000001",
                "stock_name": "平安银行",
                "open": 11.24,
                "high": 11.5,
                "low": 11.0,
                "close": 11.24,
                "volume": 10000,
                "amount": 123000000.0,
                "turnover_rate": 5.0,
            },
        ]
    )
    factors = pd.DataFrame(
        [
            {"factor_date": pd.Timestamp("2025-10-15"), "factor_type": "qfq", "factor": 1.032906764},
            {"factor_date": pd.Timestamp("2026-06-12"), "factor_type": "qfq", "factor": 1.0},
        ]
    )

    result = market_data.apply_adjustment(raw, factors, "qfq")

    assert round(result.iloc[0]["close"], 2) == 10.00
    assert round(result.iloc[1]["close"], 2) == 10.94
    assert round(result.iloc[2]["close"], 2) == 11.24
    assert result.iloc[0]["turnover"] == 5.0


def test_apply_adjustment_fails_when_adjust_factors_are_missing() -> None:
    raw = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-06-12"),
                "stock_code": "000001",
                "stock_name": "平安银行",
                "open": 11.24,
                "high": 11.5,
                "low": 11.0,
                "close": 11.24,
                "volume": 10000,
                "amount": 123000000.0,
                "turnover_rate": 5.0,
            }
        ]
    )

    with pytest.raises(RuntimeError, match="missing qfq adjustment factors"):
        market_data.apply_adjustment(raw, pd.DataFrame(), "qfq")


def test_update_symbol_only_updates_unadjusted_daily_data() -> None:
    calls: list[dict[str, str]] = []

    class FakeAk:
        def stock_zh_a_daily(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["adjust"] == ""
            return pd.DataFrame(
                [
                    {
                        "date": "2026-07-02",
                        "open": 10.0,
                        "high": 10.5,
                        "low": 9.8,
                        "close": 10.2,
                        "volume": 10000,
                        "amount": 123000000.0,
                        "outstanding_share": 1000000.0,
                        "turnover": 0.052,
                    }
                ]
            )

    class FakeStore:
        def __init__(self) -> None:
            self.sync_calls = []

        def latest_raw_date(self, code):
            return None

        def dynamic_start_date(self, code, floor_start_date, overlap_days):
            return "20260701"

        def save_raw_daily(self, frame):
            assert list(frame["stock_code"].unique()) == ["000001"]
            return len(frame)

        def save_sync_status(self, *args):
            self.sync_calls.append(args)

    store = FakeStore()
    result = market_data.update_symbol(
        store,
        FakeAk(),
        "000001",
        "平安银行",
        "20250101",
        "20260702",
        10,
    )

    assert result.raw_rows == 1
    assert result.fetch_start_date == "20260701"
    assert store.sync_calls == [
        (
            "000001",
            "1d",
            pd.Timestamp("2026-07-02"),
            "stock_daily_raw",
            "downloaded_daily",
        )
    ]
    assert calls == [
        {
            "symbol": "sz000001",
            "start_date": "20260701",
            "end_date": "20260702",
            "adjust": "",
        }
    ]


def test_update_symbol_skips_when_local_data_already_covers_end_date() -> None:
    class FakeAk:
        def stock_zh_a_daily(self, **kwargs):
            raise AssertionError("should not fetch remote data when local data is current")

    class FakeStore:
        def __init__(self) -> None:
            self.sync_calls = []

        def latest_raw_date(self, code):
            return "20260703"

        def dynamic_start_date(self, code, floor_start_date, overlap_days):
            raise AssertionError("should not compute fetch range when local data is current")

        def save_raw_daily(self, frame):
            raise AssertionError("should not write rows when local data is current")

        def save_sync_status(self, *args):
            self.sync_calls.append(args)

    store = FakeStore()
    result = market_data.update_symbol(
        store,
        FakeAk(),
        "000001",
        "平安银行",
        "20250101",
        "20260702",
        10,
    )

    assert result.skipped is True
    assert result.raw_rows == 0
    assert result.fetch_start_date == "20260703"
    assert store.sync_calls == [
        (
            "000001",
            "1d",
            pd.Timestamp("2026-07-02"),
            "stock_daily_raw",
            "already_current",
        )
    ]


def test_update_symbol_marks_local_latest_when_increment_is_empty() -> None:
    class FakeAk:
        def stock_zh_a_daily(self, **kwargs):
            return pd.DataFrame(
                columns=[
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "amount",
                    "outstanding_share",
                    "turnover",
                ]
            )

    class FakeStore:
        def __init__(self) -> None:
            self.sync_calls = []

        def latest_raw_date(self, code):
            return "20260626"

        def dynamic_start_date(self, code, floor_start_date, overlap_days):
            return "20260627"

        def save_raw_daily(self, frame):
            raise AssertionError("should not write rows when increment is empty")

        def save_sync_status(self, *args):
            self.sync_calls.append(args)

    store = FakeStore()
    result = market_data.update_symbol(
        store,
        FakeAk(),
        "603722",
        "阿科力",
        "20250101",
        "20260702",
        0,
    )

    assert result.skipped is True
    assert result.raw_rows == 0
    assert result.fetch_start_date == "20260627"
    assert store.sync_calls == [
        (
            "603722",
            "1d",
            pd.Timestamp("2026-06-26"),
            "stock_daily_raw",
            "no_new_daily_rows",
        )
    ]


def test_update_symbol_factors_only_updates_requested_factor_types() -> None:
    calls: list[dict[str, str]] = []

    class FakeAk:
        def stock_zh_a_daily(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["adjust"] == "qfq-factor"
            return pd.DataFrame(
                [
                    {"date": "2026-06-12", "qfq_factor": 1.0},
                    {"date": "2025-10-15", "qfq_factor": 1.0329},
                ]
            )

    class FakeStore:
        def save_adjustment_factors(self, frame):
            assert set(frame["factor_type"]) == {"qfq"}
            return len(frame)

    result = market_data.update_symbol_factors(FakeStore(), FakeAk(), "000001", ["qfq"])

    assert result.factor_rows == 2
    assert result.factor_types == ("qfq",)
    assert calls == [{"symbol": "sz000001", "adjust": "qfq-factor"}]
