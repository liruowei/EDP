from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd


MARKET_DATA_DIR = Path(__file__).resolve().parent
if str(MARKET_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(MARKET_DATA_DIR))

from market_time import CHINA_TZ  # noqa: E402
from provider_cache import (  # noqa: E402
    CacheResult,
    ProviderCacheStore,
    cache_data_time,
    read_or_fetch_csv as provider_read_or_fetch_csv,
    write_cached_frame,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def path_value(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root() / path


def default_cache_dir(config: dict[str, Any] | None = None) -> Path:
    data_config = (config or {}).get("data", {})
    value = str(data_config.get("akshare_cache_dir") or "data/market_data/akshare_cache")
    return path_value(value)


def load_cached_frame(
    *,
    ak: Any,
    cache_dir: Path,
    dataset: str,
    fetcher: Callable[[Any], pd.DataFrame],
    refresh: bool = False,
    date_columns: Iterable[str] = (),
    realtime_today: bool = False,
    now: pd.Timestamp | None = None,
) -> CacheResult:
    store = ProviderCacheStore(cache_dir, provider="akshare", client=ak, now=now)
    return store.get_dataset(
        dataset,
        fetcher,
        refresh=refresh,
        date_columns=date_columns,
        realtime_today=realtime_today,
        source_function=f"akshare.{dataset}",
        dtype=str,
    )


def read_or_fetch_csv(
    path: Path,
    fetch: Callable[[], pd.DataFrame],
    refresh: bool,
    *,
    attempts: int = 1,
    retry_base_seconds: float = 1.0,
    date_columns: Iterable[str] = (),
    realtime_today: bool = False,
    empty_ok: bool = False,
    source_function: str = "",
) -> pd.DataFrame:
    return provider_read_or_fetch_csv(
        path,
        fetch,
        refresh,
        provider="akshare",
        attempts=attempts,
        retry_base_seconds=retry_base_seconds,
        date_columns=date_columns,
        realtime_today=realtime_today,
        empty_ok=empty_ok,
        source_function=source_function,
    )


def normalize_code(value: Any) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits.zfill(6)[-6:]


def normalize_current_codes(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.rename(columns={"code": "stock_code", "name": "stock_name", "代码": "stock_code", "名称": "stock_name"})
    missing = {"stock_code", "stock_name"} - set(renamed.columns)
    if missing:
        raise RuntimeError(f"stock_info_a_code_name missing columns: {sorted(missing)}")
    result = renamed[["stock_code", "stock_name"]].dropna().copy()
    result["stock_code"] = result["stock_code"].map(normalize_code)
    result["stock_name"] = result["stock_name"].astype(str)
    return result.drop_duplicates("stock_code").sort_values("stock_code").reset_index(drop=True)


def normalize_delist_codes(frame: pd.DataFrame) -> set[str]:
    code_columns = ["公司代码", "证券代码", "code", "代码", "A股代码"]
    for column in code_columns:
        if column in frame.columns:
            return set(frame[column].dropna().map(normalize_code))
    return set()


def load_stock_info_tables(
    *,
    ak: Any,
    cache_dir: Path,
    refresh: bool = False,
) -> dict[str, CacheResult]:
    stock_info_dir = cache_dir / "stock_info"
    return {
        "a_code_name": load_cached_frame(
            ak=ak,
            cache_dir=stock_info_dir,
            dataset="a_code_name",
            fetcher=lambda api: api.stock_info_a_code_name(),
            refresh=refresh,
        ),
        "sh_delist": load_cached_frame(
            ak=ak,
            cache_dir=stock_info_dir,
            dataset="sh_delist",
            fetcher=lambda api: api.stock_info_sh_delist(),
            refresh=refresh,
            date_columns=["暂停上市日期", "终止上市日期", "上市日期"],
        ),
        "sz_delist": load_cached_frame(
            ak=ak,
            cache_dir=stock_info_dir,
            dataset="sz_delist",
            fetcher=lambda api: api.stock_info_sz_delist(),
            refresh=refresh,
            date_columns=["终止上市日期", "暂停上市日期", "上市日期"],
        ),
        "sh_name_code": load_cached_frame(
            ak=ak,
            cache_dir=stock_info_dir,
            dataset="sh_name_code",
            fetcher=lambda api: api.stock_info_sh_name_code(),
            refresh=refresh,
            date_columns=["上市日期"],
        ),
        "sz_name_code": load_cached_frame(
            ak=ak,
            cache_dir=stock_info_dir,
            dataset="sz_name_code",
            fetcher=lambda api: api.stock_info_sz_name_code(),
            refresh=refresh,
            date_columns=["A股上市日期", "上市日期"],
        ),
        "sz_change_name": load_cached_frame(
            ak=ak,
            cache_dir=stock_info_dir,
            dataset="sz_change_name",
            fetcher=lambda api: api.stock_info_sz_change_name(),
            refresh=refresh,
            date_columns=["变更日期", "公告日期"],
        ),
    }


def build_current_a_share_universe(
    *,
    ak: Any,
    config: dict[str, Any],
    refresh: bool = False,
) -> pd.DataFrame:
    cache_dir = default_cache_dir(config)
    tables = load_stock_info_tables(ak=ak, cache_dir=cache_dir, refresh=refresh)
    universe = normalize_current_codes(tables["a_code_name"].frame)
    delisted = normalize_delist_codes(tables["sh_delist"].frame) | normalize_delist_codes(tables["sz_delist"].frame)
    if delisted:
        universe = universe[~universe["stock_code"].isin(delisted)].copy()

    universe_config = config.get("universe", {})
    include_prefixes = tuple(universe_config.get("include_prefixes", ["0", "3", "6"]))
    exclude_name_contains = tuple(universe_config.get("exclude_name_contains", ["ST", "退"]))
    if include_prefixes:
        universe = universe[universe["stock_code"].str.startswith(include_prefixes)].copy()
    for pattern in exclude_name_contains:
        universe = universe[~universe["stock_name"].str.contains(str(pattern), na=False)].copy()
    universe = universe[["stock_code", "stock_name"]].drop_duplicates("stock_code")
    universe = universe.sort_values("stock_code").reset_index(drop=True)

    write_cached_frame(
        universe,
        cache_dir / "universe",
        "current_a_share",
        now=pd.Timestamp.now(tz=CHINA_TZ),
        provider="akshare",
        source_function="akshare.current_a_share_universe",
    )
    return universe
