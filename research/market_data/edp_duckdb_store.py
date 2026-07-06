from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

MARKET_DATA_DIR = Path(__file__).resolve().parent
if str(MARKET_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(MARKET_DATA_DIR))

from market_time import (  # noqa: E402
    CHINA_TZ,
    china_today,
    is_after_daily_reliable_close,
)
from provider_cache import ProviderCacheStore  # noqa: E402
from akshare_cache import (  # noqa: E402
    default_cache_dir,
)


PRICE_COLUMNS = ["open", "high", "low", "close"]
LIVE_TODAY_CACHE_TTL_SECONDS = 60.0
_LIVE_TODAY_RAW_CACHE: dict[str, tuple[pd.Timestamp, pd.DataFrame]] = {}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def path_value(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root() / path


def default_database_path(config: dict[str, Any] | None = None) -> Path:
    data_config = (config or {}).get("data", {})
    value = str(data_config.get("market_data_db") or "data/market_data/edp_market_data.duckdb")
    return path_value(value)


def sina_symbol(code: str) -> str:
    code = str(code).zfill(6)
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("0", "2", "3")):
        return f"sz{code}"
    raise ValueError(f"unsupported A-share code for Sina daily data: {code}")


def import_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "当前环境缺少 duckdb，EDP 自维护行情库无法打开。"
            "请先安装：python -m pip install duckdb"
        ) from exc
    return duckdb


def ensure_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("当前环境缺少 akshare，无法下载 A 股行情。") from exc
    return ak


def yyyymmdd(value: date | pd.Timestamp | str) -> str:
    return pd.to_datetime(value).strftime("%Y%m%d")


def persistable_end_date(end_date: str, today: date | None = None) -> str:
    requested = pd.to_datetime(end_date).date()
    current = today or china_today()
    if requested >= current:
        return yyyymmdd(pd.Timestamp(current) - pd.Timedelta(days=1))
    return yyyymmdd(requested)


def is_daily_period(period: str) -> bool:
    return str(period).strip().lower() in {"1d", "d", "day", "daily"}


def daily_reliable_data_time(value: date | pd.Timestamp | str) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(value).date())


def period_to_timedelta(period: str) -> pd.Timedelta:
    normalized = str(period).strip().lower()
    if normalized in {"1d", "d", "day", "daily"}:
        return pd.Timedelta(days=1)
    if normalized.endswith("min"):
        return pd.Timedelta(minutes=int(normalized[:-3]))
    if normalized.endswith("m"):
        return pd.Timedelta(minutes=int(normalized[:-1]))
    if normalized.endswith("h"):
        return pd.Timedelta(hours=int(normalized[:-1]))
    raise ValueError(f"unsupported market data period: {period}")


def infer_reliable_data_time(
    period: str,
    latest_data_time: date | pd.Timestamp | str,
    now: pd.Timestamp | None = None,
) -> pd.Timestamp:
    latest = pd.to_datetime(latest_data_time)
    if is_daily_period(period):
        return daily_reliable_data_time(latest)
    if is_after_daily_reliable_close(now):
        return latest
    return latest - period_to_timedelta(period)


def normalize_raw_daily(raw: pd.DataFrame, code: str, name: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    result = raw.copy()
    result["stock_code"] = str(code).zfill(6)
    result["stock_name"] = str(name)
    result["trade_date"] = pd.to_datetime(result["date"]).dt.date

    for column in ["open", "high", "low", "close", "volume", "amount", "outstanding_share", "turnover"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")

    turnover = pd.to_numeric(result.get("turnover"), errors="coerce")
    result["turnover_rate"] = turnover * 100.0
    result["source"] = "akshare.stock_zh_a_daily"
    result["updated_at"] = pd.Timestamp.now()

    columns = [
        "stock_code",
        "trade_date",
        "stock_name",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "outstanding_share",
        "turnover_rate",
        "source",
        "updated_at",
    ]
    return result[columns].dropna(subset=["trade_date", "open", "high", "low", "close"])


def coerce_raw_daily_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "stock_code",
        "trade_date",
        "stock_name",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "outstanding_share",
        "turnover_rate",
        "source",
        "updated_at",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    result = frame.copy()
    result["stock_code"] = result["stock_code"].astype(str).str.extract(r"(\d{1,6})")[0].str.zfill(6)
    result["trade_date"] = pd.to_datetime(result["trade_date"]).dt.date
    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "outstanding_share",
        "turnover_rate",
    ]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
        else:
            result[column] = pd.NA
    if "stock_name" not in result.columns:
        result["stock_name"] = ""
    if "source" not in result.columns:
        result["source"] = "akshare.stock_zh_a_daily"
    if "updated_at" not in result.columns:
        result["updated_at"] = pd.Timestamp.now()
    else:
        result["updated_at"] = pd.to_datetime(result["updated_at"], errors="coerce").fillna(pd.Timestamp.now())
    return result[columns].dropna(subset=["trade_date", "open", "high", "low", "close"])


def normalize_live_spot_snapshot(raw: pd.DataFrame, snapshot_date: date | str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    result = raw.rename(
        columns={
            "代码": "stock_code",
            "名称": "stock_name",
            "今开": "open",
            "最高": "high",
            "最低": "low",
            "最新价": "close",
            "成交量": "volume",
            "成交额": "amount",
            "换手率": "turnover_rate",
        }
    ).copy()
    missing = {"stock_code", "stock_name", "open", "high", "low", "close"} - set(result.columns)
    if missing:
        raise ValueError(f"Unexpected AkShare spot columns, missing: {sorted(missing)}")

    result["stock_code"] = result["stock_code"].astype(str).str.extract(r"(\d{1,6})")[0]
    result["stock_code"] = result["stock_code"].str.zfill(6)
    result["stock_name"] = result["stock_name"].astype(str)
    result["trade_date"] = pd.to_datetime(snapshot_date).date()
    for column in ["open", "high", "low", "close", "volume", "amount", "turnover_rate"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
        else:
            result[column] = pd.NA
    result["outstanding_share"] = pd.NA
    result["source"] = "akshare.stock_zh_a_spot_em.live"
    result["updated_at"] = pd.Timestamp.now()

    columns = [
        "stock_code",
        "trade_date",
        "stock_name",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "outstanding_share",
        "turnover_rate",
        "source",
        "updated_at",
    ]
    result = result[columns].dropna(subset=["stock_code", "trade_date", "open", "high", "low", "close"])
    return result[result["close"].astype(float) > 0].drop_duplicates("stock_code", keep="last")


def fetch_live_today_raw(
    ak: Any | None = None,
    today: date | None = None,
    max_age_seconds: float = LIVE_TODAY_CACHE_TTL_SECONDS,
    cache_store: ProviderCacheStore | None = None,
) -> pd.DataFrame:
    snapshot_date = today or china_today()
    cache_key = yyyymmdd(snapshot_date)
    now = pd.Timestamp.now()
    cached = _LIVE_TODAY_RAW_CACHE.get(cache_key)
    if cached is None or (now - cached[0]).total_seconds() > max_age_seconds:
        api = ak or ensure_akshare()
        if cache_store is None and ak is None:
            cache_store = ProviderCacheStore(default_cache_dir(), provider="akshare", client=api)
        if cache_store is not None:
            cache_store.client = api
            result = cache_store.get_dataset(
                "live/stock_zh_a_spot_em",
                lambda api_client: normalize_live_spot_snapshot(
                    api_client.stock_zh_a_spot_em(),
                    snapshot_date,
                ),
                refresh=True,
                date_columns=["trade_date"],
                realtime_today=True,
                source_function="akshare.stock_zh_a_spot_em",
                params={"snapshot_date": cache_key},
            )
            frame = coerce_raw_daily_frame(result.frame)
        else:
            frame = normalize_live_spot_snapshot(
                api.stock_zh_a_spot_em(),
                snapshot_date,
            )
        _LIVE_TODAY_RAW_CACHE[cache_key] = (now, frame)
    return _LIVE_TODAY_RAW_CACHE[cache_key][1].copy()


def maybe_append_live_today(
    raw: pd.DataFrame,
    code: str,
    name: str,
    start_date: str,
    end_date: str,
    today: date | None = None,
    cache_store: ProviderCacheStore | None = None,
) -> pd.DataFrame:
    current = today or china_today()
    start = pd.to_datetime(start_date).date()
    end = pd.to_datetime(end_date).date()
    if not (start <= current <= end):
        return raw

    if cache_store is None:
        live = fetch_live_today_raw(today=current)
    else:
        live = fetch_live_today_raw(today=current, cache_store=cache_store)
    live = live[live["stock_code"].astype(str).str.zfill(6).eq(str(code).zfill(6))].copy()
    if live.empty:
        return raw
    live["stock_code"] = str(code).zfill(6)
    live["stock_name"] = live["stock_name"].fillna(name).replace("", name)
    if raw.empty:
        return live
    combined = pd.concat([raw, live], ignore_index=True, sort=False)
    return combined.drop_duplicates(["stock_code", "trade_date"], keep="last")


def normalize_adjustment_factor(raw: pd.DataFrame, code: str, factor_type: str) -> pd.DataFrame:
    factor_column = f"{factor_type}_factor"
    if raw.empty or factor_column not in raw.columns:
        return pd.DataFrame(
            columns=["stock_code", "factor_date", "factor_type", "factor", "source", "updated_at"]
        )

    result = raw[["date", factor_column]].copy()
    result["stock_code"] = str(code).zfill(6)
    result["factor_date"] = pd.to_datetime(result["date"]).dt.date
    result["factor_type"] = factor_type
    result["factor"] = pd.to_numeric(result[factor_column], errors="coerce")
    result["source"] = f"akshare.stock_zh_a_daily.{factor_type}-factor"
    result["updated_at"] = pd.Timestamp.now()
    return result[
        ["stock_code", "factor_date", "factor_type", "factor", "source", "updated_at"]
    ].dropna(subset=["factor_date", "factor"])


def coerce_adjustment_factor_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["stock_code", "factor_date", "factor_type", "factor", "source", "updated_at"]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    result = frame.copy()
    result["stock_code"] = result["stock_code"].astype(str).str.extract(r"(\d{1,6})")[0].str.zfill(6)
    result["factor_date"] = pd.to_datetime(result["factor_date"]).dt.date
    result["factor_type"] = result["factor_type"].astype(str)
    result["factor"] = pd.to_numeric(result["factor"], errors="coerce")
    if "source" not in result.columns:
        result["source"] = "akshare.stock_zh_a_daily.factor"
    if "updated_at" not in result.columns:
        result["updated_at"] = pd.Timestamp.now()
    else:
        result["updated_at"] = pd.to_datetime(result["updated_at"], errors="coerce").fillna(pd.Timestamp.now())
    return result[columns].dropna(subset=["factor_date", "factor"])


def apply_adjustment(raw: pd.DataFrame, factors: pd.DataFrame, adjust: str) -> pd.DataFrame:
    if raw.empty:
        return raw
    if adjust not in {"", "qfq", "hfq"}:
        raise ValueError(f"unsupported adjust mode: {adjust}")

    result = raw.sort_values("date").copy()
    if adjust == "":
        result["adjust_factor"] = 1.0
    else:
        factor_type = adjust
        if factors.empty or "factor_type" not in factors.columns:
            raise RuntimeError(f"missing {adjust} adjustment factors; cannot derive adjusted prices")
        factors = factors[factors["factor_type"].eq(factor_type)].copy()
        if factors.empty:
            raise RuntimeError(f"missing {adjust} adjustment factors; cannot derive adjusted prices")
        else:
            factors["factor_date"] = pd.to_datetime(factors["factor_date"])
            factors = factors.sort_values("factor_date")
            first_factor = float(factors["factor"].iloc[0])
            result = pd.merge_asof(
                result.sort_values("date"),
                factors[["factor_date", "factor"]].rename(columns={"factor_date": "date"}),
                on="date",
                direction="backward",
            )
            result["adjust_factor"] = pd.to_numeric(result["factor"], errors="coerce").fillna(
                first_factor
            )
            result = result.drop(columns=["factor"])

        if adjust == "qfq":
            multiplier = 1.0 / result["adjust_factor"].replace(0, pd.NA).astype(float)
        else:
            multiplier = result["adjust_factor"].astype(float)
        for column in PRICE_COLUMNS:
            result[column] = (result[column].astype(float) * multiplier).round(2)

    result["prev_close"] = result["close"].shift(1)
    result["change"] = result["close"] - result["prev_close"]
    result["pct_change"] = (result["close"] / result["prev_close"] - 1.0) * 100.0
    result["amplitude"] = (result["high"] / result["prev_close"] - result["low"] / result["prev_close"]) * 100.0
    result["turnover"] = result["turnover_rate"]
    return result.drop(columns=["prev_close"])


@dataclass(frozen=True)
class UpdateResult:
    stock_code: str
    raw_rows: int
    fetch_start_date: str
    skipped: bool = False


@dataclass(frozen=True)
class FactorUpdateResult:
    stock_code: str
    factor_rows: int
    factor_types: tuple[str, ...]


@dataclass(frozen=True)
class SyncStatus:
    stock_code: str
    period: str
    reliable_data_time: pd.Timestamp
    source: str
    reason: str


class DuckDBMarketDataStore:
    def __init__(self, database_path: str | Path):
        self.database_path = path_value(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        duckdb = import_duckdb()
        self.connection = duckdb.connect(str(self.database_path))
        self.ensure_schema()

    def close(self) -> None:
        self.connection.close()

    def ensure_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_daily_raw (
                stock_code VARCHAR NOT NULL,
                trade_date DATE NOT NULL,
                stock_name VARCHAR,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                amount DOUBLE,
                outstanding_share DOUBLE,
                turnover_rate DOUBLE,
                source VARCHAR,
                updated_at TIMESTAMP,
                PRIMARY KEY (stock_code, trade_date)
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_adj_factor (
                stock_code VARCHAR NOT NULL,
                factor_date DATE NOT NULL,
                factor_type VARCHAR NOT NULL,
                factor DOUBLE,
                source VARCHAR,
                updated_at TIMESTAMP,
                PRIMARY KEY (stock_code, factor_type, factor_date)
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_data_sync_status (
                stock_code VARCHAR NOT NULL,
                period VARCHAR NOT NULL,
                reliable_data_time TIMESTAMP,
                source VARCHAR,
                reason VARCHAR,
                updated_at TIMESTAMP,
                PRIMARY KEY (stock_code, period)
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_stock_daily_raw_code_date "
            "ON stock_daily_raw(stock_code, trade_date)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_stock_adj_factor_code_type_date "
            "ON stock_adj_factor(stock_code, factor_type, factor_date)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_market_data_sync_status_period "
            "ON market_data_sync_status(period, reliable_data_time)"
        )
        self.connection.execute(
            """
            UPDATE market_data_sync_status
            SET reliable_data_time = CAST(CAST(reliable_data_time AS DATE) AS TIMESTAMP)
            WHERE lower(period) IN ('1d', 'd', 'day', 'daily')
              AND reliable_data_time IS NOT NULL
              AND reliable_data_time <> CAST(CAST(reliable_data_time AS DATE) AS TIMESTAMP)
            """
        )

    def latest_raw_date(self, code: str) -> str | None:
        row = self.connection.execute(
            "SELECT max(trade_date) FROM stock_daily_raw WHERE stock_code = ?",
            [str(code).zfill(6)],
        ).fetchone()
        if not row or row[0] is None:
            return None
        return pd.to_datetime(row[0]).strftime("%Y%m%d")

    def dynamic_start_date(self, code: str, floor_start_date: str, overlap_days: int) -> str:
        latest = self.latest_raw_date(code)
        if not latest:
            return floor_start_date
        if overlap_days > 0:
            start = pd.to_datetime(latest) - pd.Timedelta(days=overlap_days)
        else:
            start = pd.to_datetime(latest) + pd.Timedelta(days=1)
        floor = pd.to_datetime(floor_start_date)
        return max(start, floor).strftime("%Y%m%d")

    def delete_raw_from_date(self, start_date: str) -> int:
        boundary = pd.to_datetime(start_date).date()
        count = self.connection.execute(
            "SELECT count(*) FROM stock_daily_raw WHERE trade_date >= ?",
            [boundary],
        ).fetchone()[0]
        self.connection.execute("DELETE FROM stock_daily_raw WHERE trade_date >= ?", [boundary])
        return int(count or 0)

    def save_raw_daily(self, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0
        code = str(frame["stock_code"].iloc[0]).zfill(6)
        min_date = frame["trade_date"].min()
        max_date = frame["trade_date"].max()
        self.connection.execute(
            "DELETE FROM stock_daily_raw WHERE stock_code = ? AND trade_date BETWEEN ? AND ?",
            [code, min_date, max_date],
        )
        self.connection.register("_edp_raw_daily", frame)
        try:
            self.connection.execute(
                """
                INSERT INTO stock_daily_raw
                SELECT stock_code, trade_date, stock_name, open, high, low, close, volume, amount,
                       outstanding_share, turnover_rate, source, updated_at
                FROM _edp_raw_daily
                """
            )
        finally:
            self.connection.unregister("_edp_raw_daily")
        return int(len(frame))

    def save_adjustment_factors(self, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0
        code = str(frame["stock_code"].iloc[0]).zfill(6)
        factor_types = sorted(str(value) for value in frame["factor_type"].dropna().unique())
        for factor_type in factor_types:
            self.connection.execute(
                "DELETE FROM stock_adj_factor WHERE stock_code = ? AND factor_type = ?",
                [code, factor_type],
            )
        self.connection.register("_edp_adj_factor", frame)
        try:
            self.connection.execute(
                """
                INSERT INTO stock_adj_factor
                SELECT stock_code, factor_date, factor_type, factor, source, updated_at
                FROM _edp_adj_factor
                """
            )
        finally:
            self.connection.unregister("_edp_adj_factor")
        return int(len(frame))

    def save_sync_status(
        self,
        stock_code: str,
        period: str,
        reliable_data_time: date | pd.Timestamp | str,
        source: str,
        reason: str,
    ) -> None:
        frame = pd.DataFrame(
            [
                {
                    "stock_code": str(stock_code).zfill(6),
                    "period": str(period),
                    "reliable_data_time": pd.to_datetime(reliable_data_time),
                    "source": source,
                    "reason": reason,
                    "updated_at": pd.Timestamp.now(),
                }
            ]
        )
        self.save_sync_status_bulk(frame)

    def save_sync_status_bulk(self, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0
        rows = frame.copy()
        rows["stock_code"] = rows["stock_code"].astype(str).str.zfill(6)
        rows["period"] = rows["period"].astype(str)
        rows["reliable_data_time"] = pd.to_datetime(rows["reliable_data_time"])
        daily_mask = rows["period"].map(is_daily_period)
        rows.loc[daily_mask, "reliable_data_time"] = rows.loc[
            daily_mask, "reliable_data_time"
        ].map(daily_reliable_data_time)
        if "updated_at" not in rows.columns:
            rows["updated_at"] = pd.Timestamp.now()
        for column in ["source", "reason"]:
            if column not in rows.columns:
                rows[column] = ""
        self.connection.register("_edp_sync_status", rows)
        try:
            self.connection.execute(
                """
                DELETE FROM market_data_sync_status
                USING _edp_sync_status
                WHERE market_data_sync_status.stock_code = _edp_sync_status.stock_code
                  AND market_data_sync_status.period = _edp_sync_status.period
                """
            )
            self.connection.execute(
                """
                INSERT INTO market_data_sync_status
                SELECT stock_code, period, reliable_data_time, source, reason, updated_at
                FROM _edp_sync_status
                """
            )
        finally:
            self.connection.unregister("_edp_sync_status")
        return int(len(rows))

    def load_sync_status(self, stock_code: str, period: str) -> SyncStatus | None:
        row = self.connection.execute(
            """
            SELECT stock_code, period, reliable_data_time, source, reason
            FROM market_data_sync_status
            WHERE stock_code = ? AND period = ?
            """,
            [str(stock_code).zfill(6), str(period)],
        ).fetchone()
        if not row:
            return None
        return SyncStatus(
            stock_code=str(row[0]).zfill(6),
            period=str(row[1]),
            reliable_data_time=pd.to_datetime(row[2]),
            source=str(row[3] or ""),
            reason=str(row[4] or ""),
        )

    def save_period_sync_from_latest_bar(
        self,
        stock_code: str,
        period: str,
        latest_data_time: date | pd.Timestamp | str,
        source: str,
        reason: str,
        now: pd.Timestamp | None = None,
    ) -> pd.Timestamp:
        reliable_time = infer_reliable_data_time(period, latest_data_time, now=now)
        self.save_sync_status(stock_code, period, reliable_time, source, reason)
        return reliable_time

    def load_history(
        self,
        code: str,
        name: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        code = str(code).zfill(6)
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        current = china_today()
        historical_end = min(end, (pd.Timestamp(current) - pd.Timedelta(days=1)).date())
        if historical_end >= start:
            raw = self.connection.execute(
                """
                SELECT stock_code, trade_date, stock_name, open, high, low, close, volume,
                       amount, turnover_rate
                FROM stock_daily_raw
                WHERE stock_code = ? AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date
                """,
                [code, start, historical_end],
            ).fetchdf()
        else:
            raw = pd.DataFrame()
        raw = maybe_append_live_today(raw, code, name, start_date, end_date, today=current)
        if raw.empty:
            return raw
        raw["date"] = pd.to_datetime(raw["trade_date"])
        raw["stock_code"] = code
        raw["stock_name"] = raw["stock_name"].fillna(name).replace("", name)

        factors = self.connection.execute(
            """
            SELECT factor_date, factor_type, factor
            FROM stock_adj_factor
            WHERE stock_code = ? AND factor_date <= ?
            ORDER BY factor_date
            """,
            [code, pd.to_datetime(end_date).date()],
        ).fetchdf()
        adjusted = apply_adjustment(raw, factors, adjust)
        return adjusted.drop(columns=["trade_date"], errors="ignore")


def fetch_raw_daily(
    ak: Any,
    code: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_store: ProviderCacheStore | None = None,
) -> pd.DataFrame:
    symbol = sina_symbol(code)
    normalized_code = str(code).zfill(6)
    if cache_store is not None:
        cache_store.client = ak

        def fetch(api: Any, fetch_start: str, fetch_end: str) -> pd.DataFrame:
            raw = api.stock_zh_a_daily(
                symbol=symbol,
                start_date=fetch_start,
                end_date=fetch_end,
                adjust="",
            )
            return normalize_raw_daily(raw, normalized_code, name)

        result = cache_store.get_incremental_dataset(
            f"stock_daily_raw/{normalized_code}",
            fetch,
            start_date=start_date,
            end_date=end_date,
            date_column="trade_date",
            key_columns=["stock_code"],
            source_function="akshare.stock_zh_a_daily",
            params={"symbol": symbol, "adjust": ""},
        )
        return coerce_raw_daily_frame(result.frame)

    raw = ak.stock_zh_a_daily(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        adjust="",
    )
    return normalize_raw_daily(raw, normalized_code, name)


def fetch_adjustment_factors(
    ak: Any,
    code: str,
    factor_types: Iterable[str],
    cache_store: ProviderCacheStore | None = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    normalized_code = str(code).zfill(6)
    symbol = sina_symbol(normalized_code)
    if cache_store is not None:
        cache_store.client = ak
    for factor_type in factor_types:
        factor_type = str(factor_type)
        if factor_type not in {"qfq", "hfq"}:
            raise ValueError(f"unsupported adjustment factor mode: {factor_type}")
        if cache_store is not None:
            result = cache_store.get_dataset(
                f"stock_adj_factor/{normalized_code}_{factor_type}",
                lambda api, mode=factor_type: normalize_adjustment_factor(
                    api.stock_zh_a_daily(symbol=symbol, adjust=f"{mode}-factor"),
                    normalized_code,
                    mode,
                ),
                refresh=True,
                date_columns=["factor_date"],
                source_function="akshare.stock_zh_a_daily",
                params={"symbol": symbol, "adjust": f"{factor_type}-factor"},
                empty_ok=False,
            )
            frame = coerce_adjustment_factor_frame(result.frame)
        else:
            raw = ak.stock_zh_a_daily(symbol=symbol, adjust=f"{factor_type}-factor")
            frame = normalize_adjustment_factor(raw, normalized_code, factor_type)
        if frame.empty:
            raise RuntimeError(f"empty {factor_type} adjustment factors from AkShare for {code}")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def update_symbol(
    store: DuckDBMarketDataStore,
    ak: Any,
    code: str,
    name: str,
    start_date: str,
    end_date: str,
    overlap_days: int,
    cache_store: ProviderCacheStore | None = None,
) -> UpdateResult:
    persist_end = persistable_end_date(end_date)
    if pd.to_datetime(persist_end) < pd.to_datetime(start_date):
        store.save_sync_status(
            code,
            "1d",
            daily_reliable_data_time(persist_end),
            "stock_daily_raw",
            "before_start_date",
        )
        return UpdateResult(
            stock_code=str(code).zfill(6),
            raw_rows=0,
            fetch_start_date=persist_end,
            skipped=True,
        )
    latest = store.latest_raw_date(code)
    if latest and pd.to_datetime(latest) >= pd.to_datetime(persist_end):
        store.save_sync_status(
            code,
            "1d",
            daily_reliable_data_time(persist_end),
            "stock_daily_raw",
            "already_current",
        )
        return UpdateResult(
            stock_code=str(code).zfill(6),
            raw_rows=0,
            fetch_start_date=latest,
            skipped=True,
        )
    fetch_start = store.dynamic_start_date(code, start_date, overlap_days)
    raw = fetch_raw_daily(ak, code, name, fetch_start, persist_end, cache_store=cache_store)
    if raw.empty:
        if latest:
            store.save_sync_status(
                code,
                "1d",
                daily_reliable_data_time(latest),
                "stock_daily_raw",
                "no_new_daily_rows",
            )
            return UpdateResult(
                stock_code=str(code).zfill(6),
                raw_rows=0,
                fetch_start_date=fetch_start,
                skipped=True,
            )
        raise RuntimeError(f"empty raw daily data from AkShare for {code} {fetch_start}-{persist_end}")
    raw_rows = store.save_raw_daily(raw)
    if raw_rows > 0:
        reliable_date = raw["trade_date"].max()
        store.save_sync_status(
            code,
            "1d",
            daily_reliable_data_time(reliable_date),
            "stock_daily_raw",
            "downloaded_daily",
        )
    return UpdateResult(
        stock_code=str(code).zfill(6),
        raw_rows=raw_rows,
        fetch_start_date=fetch_start,
    )


def update_symbol_factors(
    store: DuckDBMarketDataStore,
    ak: Any,
    code: str,
    factor_types: Iterable[str],
    cache_store: ProviderCacheStore | None = None,
) -> FactorUpdateResult:
    normalized_types = tuple(str(value) for value in factor_types)
    factors = fetch_adjustment_factors(ak, code, normalized_types, cache_store=cache_store)
    factor_rows = store.save_adjustment_factors(factors)
    return FactorUpdateResult(
        stock_code=str(code).zfill(6),
        factor_rows=factor_rows,
        factor_types=normalized_types,
    )
