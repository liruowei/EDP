from __future__ import annotations

import json
import sys
import time as time_module
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd


MARKET_DATA_DIR = Path(__file__).resolve().parent
if str(MARKET_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(MARKET_DATA_DIR))

from market_time import CHINA_TZ, is_after_daily_reliable_close  # noqa: E402


def cache_data_time(
    frame: pd.DataFrame,
    date_columns: Iterable[str] = (),
    realtime_today: bool = False,
    now: pd.Timestamp | None = None,
) -> pd.Timestamp:
    current = now or pd.Timestamp.now(tz=CHINA_TZ)
    if current.tzinfo is not None:
        current = current.tz_convert(CHINA_TZ).tz_localize(None)
    if realtime_today:
        today = current.normalize()
        if is_after_daily_reliable_close(pd.Timestamp(current, tz=CHINA_TZ)):
            return today
        return today - pd.Timedelta(days=1)

    candidates: list[pd.Timestamp] = []
    for column in date_columns:
        if column in frame.columns:
            values = pd.to_datetime(frame[column], errors="coerce").dropna()
            if not values.empty:
                candidates.append(pd.Timestamp(values.max()).normalize())
    if candidates:
        return max(candidates)
    return pd.Timestamp(current.date())


@dataclass(frozen=True)
class CacheResult:
    frame: pd.DataFrame
    cache_path: Path
    meta_path: Path
    reliable_data_time: pd.Timestamp
    cache_hit: bool = False
    refreshed: bool = False
    metadata: dict[str, Any] | None = None


def cache_path(cache_dir: Path, dataset: str) -> Path:
    return cache_dir / f"{dataset}.csv"


def cache_meta_path(cache_dir: Path, dataset: str) -> Path:
    return cache_dir / f"{dataset}.meta.json"


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def read_cache_meta(meta_path: Path) -> dict[str, Any]:
    if not meta_path.exists():
        return {}
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_cached_csv(path: Path, dtype: Any | None = None) -> pd.DataFrame:
    return pd.read_csv(path, dtype=dtype)


def write_cached_frame(
    frame: pd.DataFrame,
    cache_dir: Path,
    dataset: str,
    *,
    date_columns: Iterable[str] = (),
    realtime_today: bool = False,
    now: pd.Timestamp | None = None,
    source_function: str = "",
    params: dict[str, Any] | None = None,
    provider: str = "",
) -> CacheResult:
    path = cache_path(cache_dir, dataset)
    meta = cache_meta_path(cache_dir, dataset)
    path.parent.mkdir(parents=True, exist_ok=True)
    reliable_data_time = cache_data_time(
        frame,
        date_columns=date_columns,
        realtime_today=realtime_today,
        now=now,
    )
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    payload = {
        "provider": provider,
        "dataset": dataset,
        "rows": int(len(frame)),
        "reliable_data_time": reliable_data_time.strftime("%Y-%m-%d"),
        "fetched_at": pd.Timestamp.now(tz=CHINA_TZ).isoformat(),
        "realtime_today": bool(realtime_today),
        "date_columns": list(date_columns),
        "source_function": source_function,
        "params": json_safe(params or {}),
    }
    meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return CacheResult(
        frame=frame.copy(),
        cache_path=path,
        meta_path=meta,
        reliable_data_time=reliable_data_time,
        refreshed=True,
        metadata=payload,
    )


class ProviderCacheStore:
    """File-backed cache boundary for external provider query results."""

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        provider: str = "",
        client: Any | None = None,
        now: pd.Timestamp | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.provider = provider
        self.client = client
        self.now = now

    def path(self, dataset: str) -> Path:
        return cache_path(self.cache_dir, dataset)

    def meta_path(self, dataset: str) -> Path:
        return cache_meta_path(self.cache_dir, dataset)

    def load(
        self,
        dataset: str,
        *,
        date_columns: Iterable[str] = (),
        realtime_today: bool = False,
        dtype: Any | None = None,
    ) -> CacheResult | None:
        path = self.path(dataset)
        meta = self.meta_path(dataset)
        if not path.exists():
            return None
        frame = read_cached_csv(path, dtype=dtype)
        reliable_data_time = cache_data_time(
            frame,
            date_columns=date_columns,
            realtime_today=realtime_today,
            now=self.now,
        )
        return CacheResult(
            frame=frame,
            cache_path=path,
            meta_path=meta,
            reliable_data_time=reliable_data_time,
            cache_hit=True,
            metadata=read_cache_meta(meta),
        )

    def write(
        self,
        dataset: str,
        frame: pd.DataFrame,
        *,
        date_columns: Iterable[str] = (),
        realtime_today: bool = False,
        source_function: str = "",
        params: dict[str, Any] | None = None,
        provider: str | None = None,
    ) -> CacheResult:
        return write_cached_frame(
            frame,
            self.cache_dir,
            dataset,
            date_columns=date_columns,
            realtime_today=realtime_today,
            now=self.now,
            source_function=source_function,
            params=params,
            provider=self.provider if provider is None else provider,
        )

    def get_dataset(
        self,
        dataset: str,
        fetcher: Callable[[Any], pd.DataFrame],
        *,
        refresh: bool = False,
        date_columns: Iterable[str] = (),
        realtime_today: bool = False,
        source_function: str = "",
        params: dict[str, Any] | None = None,
        attempts: int = 1,
        retry_base_seconds: float = 1.0,
        empty_ok: bool = True,
        dtype: Any | None = None,
    ) -> CacheResult:
        if not refresh:
            cached = self.load(
                dataset,
                date_columns=date_columns,
                realtime_today=realtime_today,
                dtype=dtype,
            )
            if cached is not None:
                return cached

        frame = self._fetch_with_retries(
            dataset,
            lambda: fetcher(self.client),
            attempts=attempts,
            retry_base_seconds=retry_base_seconds,
        )
        if frame.empty and not empty_ok:
            raise RuntimeError(f"No rows returned for provider dataset {dataset}")
        return self.write(
            dataset,
            frame,
            date_columns=date_columns,
            realtime_today=realtime_today,
            source_function=source_function,
            params=params,
        )

    def get_incremental_dataset(
        self,
        dataset: str,
        fetcher: Callable[[Any, str, str], pd.DataFrame],
        *,
        start_date: str,
        end_date: str,
        date_column: str,
        key_columns: Iterable[str] = (),
        refresh: bool = False,
        overlap_days: int = 0,
        date_format: str = "%Y%m%d",
        source_function: str = "",
        params: dict[str, Any] | None = None,
        attempts: int = 1,
        retry_base_seconds: float = 1.0,
    ) -> CacheResult:
        start = pd.to_datetime(start_date).normalize()
        end = pd.to_datetime(end_date).normalize()
        if end < start:
            return CacheResult(
                frame=pd.DataFrame(),
                cache_path=self.path(dataset),
                meta_path=self.meta_path(dataset),
                reliable_data_time=start,
            )

        key_columns = tuple(key_columns)
        dtype = {column: str for column in key_columns}
        cached = None if refresh else self.load(dataset, date_columns=[date_column], dtype=dtype or None)
        if cached is not None and date_column in cached.frame.columns:
            cached_max = max_cache_date(cached.frame, date_column)
            if cached_max is not None and cached_max >= end:
                return CacheResult(
                    frame=filter_by_date(cached.frame, date_column, start, end),
                    cache_path=cached.cache_path,
                    meta_path=cached.meta_path,
                    reliable_data_time=cached.reliable_data_time,
                    cache_hit=True,
                    metadata=cached.metadata,
                )
            if cached_max is not None:
                fetch_start = cached_max + pd.Timedelta(days=1)
                if overlap_days > 0:
                    fetch_start = cached_max - pd.Timedelta(days=overlap_days)
                fetch_start = max(fetch_start, start)
            else:
                fetch_start = start
        else:
            fetch_start = start

        fetch_start_text = fetch_start.strftime(date_format)
        fetch_end_text = end.strftime(date_format)
        fetch_params = {
            **(params or {}),
            "start_date": fetch_start_text,
            "end_date": fetch_end_text,
        }
        remote = self._fetch_with_retries(
            dataset,
            lambda: fetcher(self.client, fetch_start_text, fetch_end_text),
            attempts=attempts,
            retry_base_seconds=retry_base_seconds,
        )
        if remote.empty:
            cached_frame = (
                filter_by_date(cached.frame, date_column, start, end)
                if cached is not None
                else remote.copy()
            )
            return CacheResult(
                frame=cached_frame,
                cache_path=self.path(dataset),
                meta_path=self.meta_path(dataset),
                reliable_data_time=(
                    cached.reliable_data_time
                    if cached is not None
                    else cache_data_time(remote, date_columns=[date_column], now=self.now)
                ),
                refreshed=True,
                metadata=read_cache_meta(self.meta_path(dataset)),
            )

        merged = merge_incremental_frames(
            cached.frame if cached is not None else None,
            remote,
            date_column=date_column,
            key_columns=key_columns,
        )
        written = self.write(
            dataset,
            merged,
            date_columns=[date_column],
            source_function=source_function,
            params=fetch_params,
        )
        return CacheResult(
            frame=filter_by_date(written.frame, date_column, start, end),
            cache_path=written.cache_path,
            meta_path=written.meta_path,
            reliable_data_time=written.reliable_data_time,
            refreshed=True,
            metadata=written.metadata,
        )

    def _fetch_with_retries(
        self,
        dataset: str,
        fetch: Callable[[], pd.DataFrame],
        *,
        attempts: int,
        retry_base_seconds: float,
    ) -> pd.DataFrame:
        last_exception: Exception | None = None
        for attempt in range(1, max(int(attempts), 1) + 1):
            try:
                frame = fetch()
                if not isinstance(frame, pd.DataFrame):
                    raise RuntimeError(f"Provider dataset {dataset} did not return a DataFrame")
                return frame
            except Exception as exc:
                last_exception = exc
                if attempt >= max(int(attempts), 1):
                    raise
                delay_seconds = float(retry_base_seconds) * (2 ** (attempt - 1))
                time_module.sleep(max(delay_seconds, 0.0))
        raise RuntimeError(f"Fetch failed for provider dataset {dataset}: {last_exception}")


def max_cache_date(frame: pd.DataFrame, date_column: str) -> pd.Timestamp | None:
    if frame.empty or date_column not in frame.columns:
        return None
    values = pd.to_datetime(frame[date_column], errors="coerce").dropna()
    if values.empty:
        return None
    return pd.Timestamp(values.max()).normalize()


def filter_by_date(
    frame: pd.DataFrame,
    date_column: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    if frame.empty or date_column not in frame.columns:
        return frame.copy()
    dates = pd.to_datetime(frame[date_column], errors="coerce").dt.normalize()
    return frame.loc[(dates >= start) & (dates <= end)].copy()


def merge_incremental_frames(
    cached: pd.DataFrame | None,
    remote: pd.DataFrame,
    *,
    date_column: str,
    key_columns: Iterable[str] = (),
) -> pd.DataFrame:
    if cached is None or cached.empty:
        combined = remote.copy()
    else:
        combined = pd.concat([cached, remote], ignore_index=True, sort=False)

    dedupe_columns = [column for column in [*key_columns, date_column] if column in combined.columns]
    if dedupe_columns:
        combined = combined.drop_duplicates(dedupe_columns, keep="last")
    sort_columns = [column for column in [*key_columns, date_column] if column in combined.columns]
    if sort_columns:
        combined = combined.sort_values(sort_columns)
    return combined.reset_index(drop=True)


def read_or_fetch_csv(
    path: Path,
    fetch: Callable[[], pd.DataFrame],
    refresh: bool,
    *,
    provider: str = "",
    attempts: int = 1,
    retry_base_seconds: float = 1.0,
    date_columns: Iterable[str] = (),
    realtime_today: bool = False,
    empty_ok: bool = False,
    source_function: str = "",
) -> pd.DataFrame:
    store = ProviderCacheStore(path.parent, provider=provider)
    result = store.get_dataset(
        path.stem,
        lambda _client: fetch(),
        refresh=refresh,
        date_columns=date_columns,
        realtime_today=realtime_today,
        attempts=attempts,
        retry_base_seconds=retry_base_seconds,
        empty_ok=empty_ok,
        source_function=source_function,
    )
    return result.frame
