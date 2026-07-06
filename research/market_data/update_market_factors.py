from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd


LOW_BUY_DIR = Path(__file__).resolve().parents[1] / "second_day_low_buy"
sys.path.insert(0, str(LOW_BUY_DIR))

from run_full_market_oos_backtest import DEFAULT_CONFIG, load_config, load_universe, path_value  # noqa: E402

from edp_duckdb_store import (  # noqa: E402
    DuckDBMarketDataStore,
    default_database_path,
    ensure_akshare,
    update_symbol_factors,
)
from akshare_cache import default_cache_dir  # noqa: E402
from provider_cache import ProviderCacheStore  # noqa: E402
from update_market_data import (
    default_end_date,
    failure_path,
    suppress_noisy_logs,
    validate_yyyymmdd,
    write_failures,
)  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update EDP DuckDB adjustment factors.")
    parser.add_argument("--end-date", default="", help="YYYYMMDD; empty uses today.")
    parser.add_argument("--factor-types", default="", help="Comma-separated qfq/hfq; empty uses config or qfq.")
    parser.add_argument("--max-stocks", type=int, default=None, help="Debug limit; empty means full universe.")
    parser.add_argument("--refresh-universe", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--progress-every", type=int, default=100)
    return parser.parse_args()


def factor_types(config: dict[str, Any], override: str = "") -> list[str]:
    if override:
        values: Any = override
    else:
        values = config["data"].get("factor_types")
    if not values:
        adjust = str(config["data"].get("adjust") or "qfq")
        return [adjust] if adjust in {"qfq", "hfq"} else ["qfq"]
    if isinstance(values, str):
        result = [item.strip() for item in values.split(",") if item.strip()]
    else:
        result = [str(item) for item in values]
    invalid = [item for item in result if item not in {"qfq", "hfq"}]
    if invalid:
        raise ValueError(f"unsupported factor types: {','.join(invalid)}")
    return result


def main() -> None:
    args = parse_args()
    suppress_noisy_logs()

    end_date = validate_yyyymmdd(str(args.end_date or default_end_date()), "end_date")
    config = load_config(args.config)
    config["data"]["end_date"] = end_date

    request_interval = float(config["data"].get("request_interval_seconds", 0.05))
    max_stocks = args.max_stocks if args.max_stocks and args.max_stocks > 0 else None
    progress_every = max(int(args.progress_every or 100), 1)
    types = factor_types(config, args.factor_types)

    universe = load_universe(config, args.refresh_universe)
    if max_stocks:
        universe = universe.head(max_stocks).copy()

    database = default_database_path(config)
    ak = ensure_akshare()
    cache_store = ProviderCacheStore(default_cache_dir(config), provider="akshare", client=ak)
    store = DuckDBMarketDataStore(database)
    total = len(universe)
    failures: list[dict[str, str]] = []
    updated = 0
    factor_rows = 0
    started = time.time()

    print("engine=edp_duckdb")
    print("provider=akshare")
    print("dataset=stock_adj_factor")
    print(f"database={database}")
    print(f"akshare_cache={path_value(str(config['data'].get('akshare_cache_dir') or 'data/market_data/akshare_cache'))}")
    print(f"end_date={end_date}")
    print(f"universe={total}")
    print(f"factor_types={','.join(types)}")

    failures_file = failure_path(config, end_date)
    try:
        for index, row in enumerate(universe.itertuples(index=False), start=1):
            code = str(row.stock_code).zfill(6)
            name = str(row.stock_name)
            if index == 1 or index % progress_every == 0 or index == total:
                print(f"factor_update_current={index}/{total} code={code} name={name}", flush=True)
            try:
                result = update_symbol_factors(store, ak, code, types, cache_store=cache_store)
                updated += 1
                factor_rows += result.factor_rows
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
                    "factor_update_progress="
                    f"{index}/{total} updated={updated} failures={len(failures)} "
                    f"factor_rows={factor_rows} "
                    f"elapsed_seconds={time.time() - started:.1f}",
                    flush=True,
                )
            if request_interval > 0 and index < total:
                time.sleep(request_interval)
    except KeyboardInterrupt:
        write_failures(failures_file, failures)
        print(f"factor_update_interrupted={updated}/{total}", flush=True)
        print(f"failures={len(failures)}", flush=True)
        print(f"failure_file={failures_file}", flush=True)
        raise SystemExit(130) from None
    finally:
        store.close()

    write_failures(failures_file, failures)
    print(f"factor_update_done={updated}/{total}")
    print(f"failures={len(failures)}")
    print(f"failure_file={failures_file}")


if __name__ == "__main__":
    main()
