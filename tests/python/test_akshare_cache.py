from __future__ import annotations

import importlib.util
import sys
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


market_time = load_module("market_time", "research/market_data/market_time.py")
provider_cache = load_module("provider_cache", "research/market_data/provider_cache.py")
ak_cache = load_module("edp_akshare_cache", "research/market_data/akshare_cache.py")


class FakeAk:
    def stock_info_a_code_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"code": "1", "name": "平安银行"},
                {"code": "300001", "name": "样本科技"},
                {"code": "600001", "name": "邯郸钢铁"},
                {"code": "603722", "name": "阿科力"},
                {"code": "000010", "name": "ST样本"},
            ]
        )

    def stock_info_sh_delist(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "公司代码": "600001",
                    "公司简称": "邯郸钢铁",
                    "上市日期": "1998-01-22",
                    "暂停上市日期": "2009-12-29",
                }
            ]
        )

    def stock_info_sz_delist(self) -> pd.DataFrame:
        return pd.DataFrame(columns=["证券代码", "证券简称", "上市日期", "终止上市日期"])

    def stock_info_sh_name_code(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "证券代码": "603722",
                    "证券简称": "阿科力",
                    "上市日期": "2017-10-25",
                }
            ]
        )

    def stock_info_sz_name_code(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "A股代码": "000001",
                    "A股简称": "平安银行",
                    "A股上市日期": "1991-04-03",
                }
            ]
        )

    def stock_info_sz_change_name(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "证券代码": "000001",
                    "证券简称": "平安银行",
                    "变更日期": "2020-01-01",
                }
            ]
        )


class FailingAk:
    def __getattr__(self, name: str):
        raise AssertionError(f"should read cached AkShare table instead of calling {name}")


def test_build_current_universe_uses_cached_akshare_stock_info(tmp_path: Path) -> None:
    config = {
        "data": {"akshare_cache_dir": str(tmp_path / "akshare_cache")},
        "universe": {"include_prefixes": ["0", "3", "6"], "exclude_name_contains": ["ST", "退"]},
    }

    first = ak_cache.build_current_a_share_universe(ak=FakeAk(), config=config, refresh=True)
    second = ak_cache.build_current_a_share_universe(ak=FailingAk(), config=config, refresh=False)

    assert first["stock_code"].tolist() == ["000001", "300001", "603722"]
    assert second["stock_code"].tolist() == first["stock_code"].tolist()
    assert (tmp_path / "akshare_cache" / "stock_info" / "a_code_name.csv").exists()
    assert (tmp_path / "akshare_cache" / "stock_info" / "sh_delist.csv").exists()
    assert (tmp_path / "akshare_cache" / "stock_info" / "sz_change_name.csv").exists()
    assert (tmp_path / "akshare_cache" / "universe" / "current_a_share.csv").exists()


def test_cache_data_time_uses_max_date_or_close_boundary() -> None:
    non_realtime = pd.DataFrame(
        [
            {"终止上市日期": "2025-01-01"},
            {"终止上市日期": "2026-06-30"},
        ]
    )

    assert provider_cache.cache_data_time(
        non_realtime,
        date_columns=["终止上市日期"],
        now=pd.Timestamp("2026-07-03 10:00:00", tz=market_time.CHINA_TZ),
    ) == pd.Timestamp("2026-06-30")
    assert provider_cache.cache_data_time(
        pd.DataFrame([{"代码": "000001"}]),
        realtime_today=True,
        now=pd.Timestamp("2026-07-03 14:59:00", tz=market_time.CHINA_TZ),
    ) == pd.Timestamp("2026-07-02")
    assert provider_cache.cache_data_time(
        pd.DataFrame([{"代码": "000001"}]),
        realtime_today=True,
        now=pd.Timestamp("2026-07-03 15:03:00", tz=market_time.CHINA_TZ),
    ) == pd.Timestamp("2026-07-03")


def test_cache_store_writes_successful_query_and_reuses_cache(tmp_path: Path) -> None:
    calls = 0
    store = provider_cache.ProviderCacheStore(tmp_path / "provider_cache", provider="test_provider")

    def fetch(_api) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return pd.DataFrame([{"date": "2026-07-02", "value": 1}])

    first = store.get_dataset(
        "sample/daily",
        fetch,
        date_columns=["date"],
        source_function="test.sample_daily",
        empty_ok=False,
    )
    second = store.get_dataset(
        "sample/daily",
        lambda _api: (_ for _ in ()).throw(AssertionError("should not fetch")),
        date_columns=["date"],
        empty_ok=False,
    )

    assert calls == 1
    assert first.refreshed is True
    assert second.cache_hit is True
    assert second.frame.to_dict("records") == [{"date": "2026-07-02", "value": 1}]
    assert (tmp_path / "provider_cache" / "sample" / "daily.csv").exists()
    meta = pd.read_json(tmp_path / "provider_cache" / "sample" / "daily.meta.json", typ="series")
    assert meta["provider"] == "test_provider"
    assert meta["rows"] == 1
    assert meta["source_function"] == "test.sample_daily"


def test_cache_store_incremental_fetches_only_missing_tail(tmp_path: Path) -> None:
    store = provider_cache.ProviderCacheStore(tmp_path / "provider_cache", provider="test_provider")
    store.write(
        "stock_daily_raw/000001",
        pd.DataFrame(
            [
                {"stock_code": "000001", "trade_date": "2026-07-01", "close": 10.0},
                {"stock_code": "000001", "trade_date": "2026-07-02", "close": 10.2},
            ]
        ),
        date_columns=["trade_date"],
    )
    fetch_ranges: list[tuple[str, str]] = []

    def fetch(_api, start_date: str, end_date: str) -> pd.DataFrame:
        fetch_ranges.append((start_date, end_date))
        return pd.DataFrame(
            [
                {"stock_code": "000001", "trade_date": "2026-07-03", "close": 10.5},
            ]
        )

    result = store.get_incremental_dataset(
        "stock_daily_raw/000001",
        fetch,
        start_date="20260701",
        end_date="20260703",
        date_column="trade_date",
        key_columns=["stock_code"],
        source_function="akshare.stock_zh_a_daily",
    )

    assert fetch_ranges == [("20260703", "20260703")]
    assert result.frame["trade_date"].astype(str).tolist() == [
        "2026-07-01",
        "2026-07-02",
        "2026-07-03",
    ]
    cached = pd.read_csv(tmp_path / "provider_cache" / "stock_daily_raw" / "000001.csv")
    assert cached["trade_date"].astype(str).tolist() == [
        "2026-07-01",
        "2026-07-02",
        "2026-07-03",
    ]


def test_cache_store_failure_does_not_overwrite_existing_cache(tmp_path: Path) -> None:
    store = provider_cache.ProviderCacheStore(tmp_path / "provider_cache", provider="test_provider")
    store.write(
        "sample/daily",
        pd.DataFrame([{"date": "2026-07-02", "value": 1}]),
        date_columns=["date"],
    )

    def fail(_api) -> pd.DataFrame:
        raise RuntimeError("remote disconnected")

    with pytest.raises(RuntimeError, match="remote disconnected"):
        store.get_dataset("sample/daily", fail, refresh=True, date_columns=["date"])

    cached = pd.read_csv(tmp_path / "provider_cache" / "sample" / "daily.csv")
    assert cached.to_dict("records") == [{"date": "2026-07-02", "value": 1}]


def test_cache_store_incremental_empty_remote_keeps_existing_partial_cache(tmp_path: Path) -> None:
    store = provider_cache.ProviderCacheStore(tmp_path / "provider_cache", provider="test_provider")
    store.write(
        "stock_daily_raw/000001",
        pd.DataFrame(
            [
                {"stock_code": "000001", "trade_date": "2026-07-02", "close": 10.2},
            ]
        ),
        date_columns=["trade_date"],
    )

    result = store.get_incremental_dataset(
        "stock_daily_raw/000001",
        lambda _api, _start, _end: pd.DataFrame(columns=["stock_code", "trade_date", "close"]),
        start_date="20260702",
        end_date="20260703",
        date_column="trade_date",
        key_columns=["stock_code"],
    )

    assert result.frame.to_dict("records") == [
        {"stock_code": "000001", "trade_date": "2026-07-02", "close": 10.2}
    ]
    cached = pd.read_csv(tmp_path / "provider_cache" / "stock_daily_raw" / "000001.csv")
    assert cached.to_dict("records") == [
        {"stock_code": 1, "trade_date": "2026-07-02", "close": 10.2}
    ]
