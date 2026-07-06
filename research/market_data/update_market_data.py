from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


LOW_BUY_DIR = Path(__file__).resolve().parents[1] / "second_day_low_buy"
sys.path.insert(0, str(LOW_BUY_DIR))

from run_full_market_oos_backtest import DEFAULT_CONFIG, load_config, load_universe, path_value  # noqa: E402

from edp_duckdb_store import (  # noqa: E402
    DuckDBMarketDataStore,
    china_today,
    daily_reliable_data_time,
    default_database_path,
    ensure_akshare,
    fetch_live_today_raw,
    is_after_daily_reliable_close,
    persistable_end_date,
    update_symbol,
    yyyymmdd,
)
from akshare_cache import default_cache_dir  # noqa: E402
from provider_cache import ProviderCacheStore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update EDP DuckDB market data warehouse.")
    parser.add_argument("--end-date", default="", help="YYYYMMDD; empty uses today.")
    parser.add_argument("--start-date", default="", help="YYYYMMDD; empty uses config data.start_date.")
    parser.add_argument("--max-stocks", type=int, default=None, help="Debug limit; empty means full universe.")
    parser.add_argument("--refresh-universe", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--progress-every", type=int, default=100)
    return parser.parse_args()


def validate_yyyymmdd(value: str, name: str) -> str:
    try:
        pd.to_datetime(value, format="%Y%m%d")
    except Exception as exc:
        raise ValueError(f"{name} must be YYYYMMDD: {value}") from exc
    return value


def default_end_date() -> str:
    return yyyymmdd(china_today())


def failure_path(config: dict[str, Any], end_date: str) -> Path:
    log_dir = path_value(str(config["data"].get("market_data_log_dir") or "data/market_data/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return log_dir / f"market_data_update_failures_{end_date}_{stamp}.csv"


def write_failures(path: Path, failures: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stock_code", "stock_name", "error"])
        writer.writeheader()
        writer.writerows(failures)


def suppress_noisy_logs() -> None:
    for name in ["urllib3", "requests", "akshare"]:
        logging.getLogger(name).setLevel(logging.WARNING)


def main() -> None:
    args = parse_args()
    suppress_noisy_logs()

    requested_end_date = validate_yyyymmdd(str(args.end_date or default_end_date()), "end_date")
    end_date = persistable_end_date(requested_end_date)
    config = load_config(args.config)
    config["data"]["end_date"] = end_date
    if args.start_date:
        config["data"]["start_date"] = validate_yyyymmdd(str(args.start_date), "start_date")

    start_date = str(config["data"]["start_date"])
    request_interval = float(config["data"].get("request_interval_seconds", 0.05))
    overlap_days = int(config["data"].get("incremental_overlap_days", 0))
    max_stocks = args.max_stocks if args.max_stocks and args.max_stocks > 0 else None
    progress_every = max(int(args.progress_every or 100), 1)

    universe = load_universe(config, args.refresh_universe)
    if max_stocks:
        universe = universe.head(max_stocks).copy()

    database = default_database_path(config)
    ak = ensure_akshare()
    cache_store = ProviderCacheStore(default_cache_dir(config), provider="akshare", client=ak)
    store = DuckDBMarketDataStore(database)
    live_boundary = yyyymmdd(china_today())
    deleted_live_rows = 0
    if pd.to_datetime(requested_end_date) >= pd.to_datetime(live_boundary):
        deleted_live_rows = store.delete_raw_from_date(live_boundary)
    post_close_reliable_data_time = None
    post_close_live_codes: set[str] = set()
    post_close_live_error = ""
    if (
        pd.to_datetime(requested_end_date) >= pd.to_datetime(live_boundary)
        and is_after_daily_reliable_close()
    ):
        try:
            live_snapshot = fetch_live_today_raw(ak=ak, max_age_seconds=-1, cache_store=cache_store)
            post_close_live_codes = set(live_snapshot["stock_code"].astype(str).str.zfill(6))
            post_close_reliable_data_time = daily_reliable_data_time(live_boundary)
        except Exception as exc:
            post_close_live_error = f"{type(exc).__name__}: {exc}"
    total = len(universe)
    failures: list[dict[str, str]] = []
    successful_codes: list[str] = []
    updated = 0
    skipped = 0
    live_status_rows = 0
    raw_rows = 0
    started = time.time()

    print("engine=edp_duckdb")
    print("provider=akshare")
    print("dataset=stock_daily_raw")
    print(f"database={database}")
    print(f"akshare_cache={path_value(str(config['data'].get('akshare_cache_dir') or 'data/market_data/akshare_cache'))}")
    print(f"start_date={start_date}")
    print(f"requested_end_date={requested_end_date}")
    print(f"end_date={end_date}")
    print(f"today_live_boundary={live_boundary}")
    print(f"deleted_today_or_future_rows={deleted_live_rows}")
    print(f"post_close_live_status={'enabled' if post_close_reliable_data_time is not None else 'disabled'}")
    if post_close_live_error:
        print(f"post_close_live_error={post_close_live_error}")
    print(f"universe={total}")

    failures_file = failure_path(config, end_date)
    try:
        for index, row in enumerate(universe.itertuples(index=False), start=1):
            code = str(row.stock_code).zfill(6)
            name = str(row.stock_name)
            if index == 1 or index % progress_every == 0 or index == total:
                print(f"data_update_current={index}/{total} code={code} name={name}", flush=True)
            try:
                result = update_symbol(
                    store,
                    ak,
                    code,
                    name,
                    start_date,
                    end_date,
                    overlap_days,
                    cache_store=cache_store,
                )
                if result.skipped:
                    skipped += 1
                else:
                    updated += 1
                raw_rows += result.raw_rows
                successful_codes.append(code)
            except Exception as exc:
                failures.append(
                    {
                        "stock_code": code,
                        "stock_name": name,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if index % progress_every == 0 or index == total:
                print(
                    "data_update_progress="
                    f"{index}/{total} updated={updated} skipped={skipped} failures={len(failures)} "
                    f"raw_rows={raw_rows} "
                    f"elapsed_seconds={time.time() - started:.1f}",
                    flush=True,
                )
            if request_interval > 0 and index < total:
                time.sleep(request_interval)
        if post_close_reliable_data_time is not None and successful_codes:
            live_status_codes = [
                code for code in successful_codes if code in post_close_live_codes
            ]
            if live_status_codes:
                live_status_rows = store.save_sync_status_bulk(
                    pd.DataFrame(
                        [
                            {
                                "stock_code": code,
                                "period": "1d",
                                "reliable_data_time": post_close_reliable_data_time,
                                "source": "akshare.stock_zh_a_spot_em.live",
                                "reason": "post_close_live_daily",
                            }
                            for code in live_status_codes
                        ]
                    )
                )
                print(f"post_close_live_sync_rows={live_status_rows}", flush=True)
    except KeyboardInterrupt:
        write_failures(failures_file, failures)
        print(f"data_update_interrupted={updated}/{total}", flush=True)
        print(f"skipped={skipped}", flush=True)
        print(f"post_close_live_sync_rows={live_status_rows}", flush=True)
        print(f"failures={len(failures)}", flush=True)
        print(f"failure_file={failures_file}", flush=True)
        raise SystemExit(130) from None
    finally:
        store.close()

    write_failures(failures_file, failures)
    print(f"data_update_done={updated}/{total}")
    print(f"skipped={skipped}")
    print(f"post_close_live_sync_rows={live_status_rows}")
    print(f"failures={len(failures)}")
    print(f"failure_file={failures_file}")


if __name__ == "__main__":
    main()
