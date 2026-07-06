from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Callable

import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup


DEFAULT_DATA_DIR = Path("data") / "theme_stock_rotation"
MARKET_DATA_DIR = Path(__file__).resolve().parents[1] / "market_data"
sys.path.insert(0, str(MARKET_DATA_DIR))

from edp_duckdb_store import DuckDBMarketDataStore, default_database_path  # noqa: E402
from provider_cache import read_or_fetch_csv as cache_read_or_fetch_csv  # noqa: E402

DEFAULT_EM_HOSTS = [
    "https://79.push2.eastmoney.com",
    "https://29.push2.eastmoney.com",
]
EM_HOSTS = DEFAULT_EM_HOSTS.copy()
EM_MAX_PAGES = 50
REMOTE_REQUEST_INTERVAL_SECONDS = 1.2
ALLOW_AKSHARE_NAME_FALLBACK = False
_LAST_REMOTE_REQUEST_AT = 0.0
THEME_NAME_CACHE_DIR = DEFAULT_DATA_DIR / "akshare_cache" / "theme_names"

EM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json,text/plain,*/*",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build stock-in-theme EDP dataset from AkShare current constituents."
    )
    parser.add_argument(
        "--theme-source",
        choices=["concept_em", "concept_ths", "industry_em"],
        default="concept_em",
    )
    parser.add_argument(
        "--theme-names",
        default="国家大基金持股",
        help="Comma-separated concept/industry board names.",
    )
    parser.add_argument(
        "--theme-code-map",
        default="",
        help='Optional comma-separated mapping, e.g. "国家大基金持股=BK1234,PCB概念=BK5678".',
    )
    parser.add_argument(
        "--theme-code-map-file",
        type=Path,
        default=None,
        help="Optional CSV with theme_name/theme_code or 板块名称/板块代码 columns.",
    )
    parser.add_argument(
        "--theme-code-cache",
        type=Path,
        default=DEFAULT_DATA_DIR / "theme_code_cache.csv",
        help="Local CSV cache for resolved Eastmoney concept board codes.",
    )
    parser.add_argument("--start-date", default="20240101")
    parser.add_argument("--end-date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--horizons", default="1,3,5")
    parser.add_argument("--top-quantile", type=float, default=0.8)
    parser.add_argument("--min-history-rows", type=int, default=80)
    parser.add_argument("--min-amount", type=float, default=0.0)
    parser.add_argument("--max-stocks-per-theme", type=int, default=0)
    parser.add_argument("--adjust", default="", choices=["", "qfq", "hfq"])
    parser.add_argument("--keep-unlabeled-tail", action="store_true")
    parser.add_argument("--refresh-constituents", action="store_true")
    parser.add_argument("--refresh-history", action="store_true")
    parser.add_argument("--fetch-attempts", type=int, default=3)
    parser.add_argument("--retry-base-seconds", type=float, default=2.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument(
        "--remote-request-interval",
        type=float,
        default=1.2,
        help="Minimum seconds between direct remote requests.",
    )
    parser.add_argument(
        "--em-hosts",
        default=",".join(host.removeprefix("https://") for host in DEFAULT_EM_HOSTS),
        help="Comma-separated Eastmoney hosts for concept code lookup.",
    )
    parser.add_argument(
        "--em-max-pages",
        type=int,
        default=50,
        help="Maximum Eastmoney concept-list pages to scan, 100 rows per page.",
    )
    parser.add_argument(
        "--allow-akshare-name-fallback",
        action="store_true",
        help="Allow falling back to AkShare name-based concept API after direct code lookup fails.",
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_DATA_DIR / "akshare_cache")
    parser.add_argument(
        "--membership-output",
        type=Path,
        default=DEFAULT_DATA_DIR / "theme_stock_membership_snapshot.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DATA_DIR / "theme_stock_1_3_5d_live.csv",
    )
    return parser.parse_args()


def configure_remote_fetching(
    remote_request_interval: float,
    em_hosts: str,
    em_max_pages: int,
    allow_akshare_name_fallback: bool,
) -> None:
    global ALLOW_AKSHARE_NAME_FALLBACK
    global EM_HOSTS
    global EM_MAX_PAGES
    global REMOTE_REQUEST_INTERVAL_SECONDS

    REMOTE_REQUEST_INTERVAL_SECONDS = max(0.0, remote_request_interval)
    EM_HOSTS = normalize_em_hosts(em_hosts)
    EM_MAX_PAGES = max(1, em_max_pages)
    ALLOW_AKSHARE_NAME_FALLBACK = allow_akshare_name_fallback


def configure_theme_name_cache(cache_dir: Path) -> None:
    global THEME_NAME_CACHE_DIR

    THEME_NAME_CACHE_DIR = cache_dir / "theme_names"


def normalize_em_hosts(em_hosts: str) -> list[str]:
    hosts = []
    for item in [part.strip() for part in em_hosts.split(",") if part.strip()]:
        hosts.append(item if item.startswith("http") else f"https://{item}")
    return hosts or DEFAULT_EM_HOSTS.copy()


def paced_get(url: str, **kwargs) -> requests.Response:
    global _LAST_REMOTE_REQUEST_AT

    elapsed = time.monotonic() - _LAST_REMOTE_REQUEST_AT
    if elapsed < REMOTE_REQUEST_INTERVAL_SECONDS:
        time.sleep(REMOTE_REQUEST_INTERVAL_SECONDS - elapsed)
    try:
        return requests.get(url, **kwargs)
    finally:
        _LAST_REMOTE_REQUEST_AT = time.monotonic()


def read_or_fetch_csv(
    path: Path,
    fetch: Callable[[], pd.DataFrame],
    refresh: bool,
    attempts: int = 6,
    retry_base_seconds: float = 2.0,
    provider: str = "akshare",
) -> pd.DataFrame:
    return cache_read_or_fetch_csv(
        path,
        fetch,
        refresh,
        provider=provider,
        attempts=attempts,
        retry_base_seconds=retry_base_seconds,
        empty_ok=False,
        source_function=f"akshare.{path.stem}",
    )


def safe_file_name(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value).strip("_")


def parse_horizons(horizons: str) -> list[int]:
    parsed = sorted({int(item.strip()) for item in horizons.split(",") if item.strip()})
    if not parsed:
        raise ValueError("At least one horizon must be provided.")
    if any(item <= 0 for item in parsed):
        raise ValueError(f"Horizons must be positive integers: {parsed}")
    return parsed


def top_pct_from_quantile(top_quantile: float) -> int:
    return int(round((1.0 - top_quantile) * 100))


def theme_names_from_arg(theme_names: str) -> list[str]:
    names = [name.strip() for name in theme_names.split(",") if name.strip()]
    if not names:
        raise ValueError("--theme-names must include at least one theme name.")
    return names


def load_theme_code_map(
    mapping_text: str,
    mapping_file: Path | None,
    cache_file: Path | None = None,
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for file_path in [cache_file, mapping_file]:
        if file_path is None or not file_path.exists():
            continue
        mapping.update(load_theme_code_map_file(file_path))
    for item in [part.strip() for part in mapping_text.split(",") if part.strip()]:
        if "=" not in item:
            raise ValueError(f"Invalid --theme-code-map item: {item}")
        name, code = item.split("=", 1)
        mapping[name.strip()] = code.strip()
    return mapping


def load_theme_code_map_file(file_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    df = pd.read_csv(file_path)
    renamed = df.rename(columns={"板块名称": "theme_name", "板块代码": "theme_code"})
    if {"theme_name", "theme_code"} <= set(renamed.columns):
        for row in renamed[["theme_name", "theme_code"]].dropna().itertuples(index=False):
            mapping[str(row.theme_name).strip()] = str(row.theme_code).strip()
    return mapping


def save_theme_code_cache(cache_file: Path, mapping: dict[str, str]) -> None:
    if not mapping:
        return
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"theme_name": theme_name, "theme_code": theme_code}
        for theme_name, theme_code in sorted(mapping.items())
        if theme_code
    ]
    pd.DataFrame(rows).to_csv(cache_file, index=False, encoding="utf-8-sig")


def valid_em_concept_code(theme_code: str | None) -> bool:
    return bool(theme_code and re.fullmatch(r"BK\d+", str(theme_code).strip().upper()))


def normalize_theme_code(theme_code: str | None) -> str | None:
    if not theme_code:
        return None
    code = str(theme_code).strip().upper()
    return code if valid_em_concept_code(code) else None


def constituent_provider(source: str) -> str:
    if source == "concept_em":
        return "eastmoney"
    if source == "concept_ths":
        return "ths"
    return "akshare"


def theme_history_provider(source: str, theme_code: str | None = None) -> str:
    if source == "concept_em" and normalize_theme_code(theme_code):
        return "eastmoney"
    if source == "concept_ths":
        return "akshare"
    return "akshare"


def fetch_constituents(source: str, theme_name: str) -> pd.DataFrame:
    if source == "concept_em":
        raw = ak.stock_board_concept_cons_em(symbol=theme_name)
    elif source == "concept_ths":
        raw = fetch_ths_concept_constituents(theme_name)
    else:
        raw = ak.stock_board_industry_cons_em(symbol=theme_name)
    return normalize_constituents(raw, source, theme_name)


def fetch_constituents_with_fallback(
    source: str,
    theme_name: str,
    theme_code: str | None,
) -> pd.DataFrame:
    if source == "concept_em":
        normalized_code = normalize_theme_code(theme_code)
        if normalized_code:
            print(f"按板块代码拉取成分股：{theme_name}={normalized_code}")
            return fetch_constituents_by_code(source, theme_name, normalized_code)
        try:
            resolved_code = fetch_em_concept_code_by_name(theme_name)
            print(f"按解析出的板块代码拉取成分股：{theme_name}={resolved_code}")
            return fetch_constituents_by_code(source, theme_name, resolved_code)
        except Exception as direct_exc:
            if not ALLOW_AKSHARE_NAME_FALLBACK:
                raise
            print(f"东方财富直连解析/拉取失败，尝试 AkShare 名称接口：{direct_exc}")

    try:
        return fetch_constituents(source, theme_name)
    except Exception as exc:
        normalized_code = normalize_theme_code(theme_code)
        if not normalized_code and source == "concept_em":
            normalized_code = fetch_em_concept_code_by_name(theme_name)
        if not normalized_code:
            raise
        print(f"按名称拉取成分股失败，改用板块代码 {normalized_code}：{exc}")
        return fetch_constituents_by_code(source, theme_name, normalized_code)


def fetch_em_concept_code_by_name(theme_name: str) -> str:
    base_params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:90 t:3 f:!50",
        "fields": "f12,f14",
        "_": str(int(time.time() * 1000)),
    }
    last_exception: Exception | None = None
    for host in EM_HOSTS:
        try:
            total_rows = 0
            for page_number in range(1, EM_MAX_PAGES + 1):
                params = dict(base_params)
                params["pn"] = str(page_number)
                params["_"] = str(int(time.time() * 1000))
                response = paced_get(
                    f"{host}/api/qt/clist/get",
                    params=params,
                    headers=EM_HEADERS,
                    timeout=15,
                )
                response.raise_for_status()
                payload = response.json()
                rows = eastmoney_rows(payload)
                if not rows:
                    break
                total_rows += len(rows)
                for row in rows:
                    if str(row.get("f14", "")).strip() == theme_name:
                        code = str(row.get("f12", "")).strip().upper()
                        if code:
                            print(f"已通过东方财富直连接口解析板块代码：{theme_name}={code}")
                            return code
                total = payload_total(payload)
                if total and total_rows >= total:
                    break
            print(f"东方财富直连已扫描 {host} 的 {total_rows} 条题材，未命中：{theme_name}")
        except Exception as exc:
            last_exception = exc
            print(f"解析板块代码失败，尝试下一个 host：{host}，原因：{exc}")
    raise RuntimeError(f"无法解析东方财富板块代码：{theme_name}: {last_exception}")


def fetch_constituents_by_code(source: str, theme_name: str, theme_code: str) -> pd.DataFrame:
    if source == "concept_em":
        raw = fetch_em_constituents_by_code(theme_code)
    else:
        raw = ak.stock_board_industry_cons_em(symbol=theme_code)
    return normalize_constituents(raw, source, theme_name)


def fetch_em_constituents_by_code(theme_code: str) -> pd.DataFrame:
    code = str(theme_code).strip().upper()
    if not valid_em_concept_code(code):
        raise ValueError(f"Eastmoney board code must look like BKxxxx: {theme_code}")

    url = "https://29.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": f"b:{code} f:!50",
        "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f15,f16,f17,f18,f23",
        "_": str(int(time.time() * 1000)),
    }
    response = paced_get(url, params=params, headers=EM_HEADERS, timeout=15)
    response.raise_for_status()
    payload = response.json()
    rows = eastmoney_rows(payload)
    if not rows:
        raise RuntimeError(f"No constituent rows returned for {code}")

    return pd.DataFrame(rows).rename(
        columns={
            "f12": "代码",
            "f14": "名称",
            "f2": "最新价",
            "f3": "涨跌幅",
            "f4": "涨跌额",
            "f5": "成交量",
            "f6": "成交额",
            "f7": "振幅",
            "f8": "换手率",
            "f9": "市盈率-动态",
            "f10": "量比",
            "f15": "最高",
            "f16": "最低",
            "f17": "今开",
            "f18": "昨收",
            "f23": "市净率",
        }
    )


def fetch_ths_concept_constituents(theme_name: str) -> pd.DataFrame:
    code_map = load_ths_concept_code_map()
    theme_code = code_map.get(theme_name)
    if not theme_code:
        candidates = ", ".join(list(code_map.keys())[:20])
        raise RuntimeError(f"同花顺题材不存在：{theme_name}；前 20 个题材：{candidates}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        ),
        "Referer": f"https://q.10jqka.com.cn/gn/detail/code/{theme_code}/",
    }
    frames: list[pd.DataFrame] = []
    page_count = 1
    for page in range(1, 101):
        url = (
            "https://q.10jqka.com.cn/gn/detail/field/264648/order/desc/"
            f"page/{page}/ajax/1/code/{theme_code}/"
        )
        response = paced_get(url, headers=headers, timeout=15)
        response.raise_for_status()
        if page == 1:
            soup = BeautifulSoup(response.text, features="lxml")
            page_info = soup.find(name="span", attrs={"class": "page_info"})
            if page_info and "/" in page_info.text:
                page_count = int(page_info.text.strip().split("/")[-1])
        try:
            tables = pd.read_html(StringIO(response.text))
        except ValueError:
            break
        if not tables:
            break
        frames.append(tables[0])
        if page >= page_count:
            break
        time.sleep(REMOTE_REQUEST_INTERVAL_SECONDS)

    if not frames:
        raise RuntimeError(f"同花顺题材成分股为空：{theme_name} {theme_code}")
    return pd.concat(frames, ignore_index=True)


def fetch_ths_concept_code_map_frame() -> pd.DataFrame:
    df = ak.stock_board_concept_name_ths()
    if not {"name", "code"} <= set(df.columns):
        raise ValueError(f"Unexpected THS concept columns: {df.columns.tolist()}")
    return df.rename(columns={"name": "theme_name", "code": "theme_code"})[
        ["theme_name", "theme_code"]
    ].dropna()


def load_ths_concept_code_map() -> dict[str, str]:
    cache_path = THEME_NAME_CACHE_DIR / "concept_ths.csv"
    df = read_or_fetch_csv(
        cache_path,
        fetch_ths_concept_code_map_frame,
        refresh=False,
        attempts=3,
        provider="akshare",
    )
    renamed = df.rename(columns={"name": "theme_name", "code": "theme_code"})
    if not {"theme_name", "theme_code"} <= set(renamed.columns):
        raise ValueError(f"Unexpected THS concept cache columns: {df.columns.tolist()}")
    return {
        str(row.theme_name).strip(): str(row.theme_code).strip()
        for row in renamed[["theme_name", "theme_code"]].dropna().itertuples(index=False)
    }


def eastmoney_rows(payload: dict) -> list[dict]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    rows = data.get("diff", [])
    if isinstance(rows, dict):
        return list(rows.values())
    if isinstance(rows, list):
        return rows
    return []


def payload_total(payload: dict) -> int:
    data = payload.get("data")
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get("total") or 0)
    except (TypeError, ValueError):
        return 0


def normalize_constituents(raw: pd.DataFrame, source: str, theme_name: str) -> pd.DataFrame:
    rename_candidates = {
        "代码": "stock_code",
        "股票代码": "stock_code",
        "股票代码↓": "stock_code",
        "code": "stock_code",
        "名称": "stock_name",
        "股票名称": "stock_name",
        "股票简称": "stock_name",
        "name": "stock_name",
    }
    df = raw.rename(columns=rename_candidates).copy()
    missing = [column for column in ["stock_code", "stock_name"] if column not in df.columns]
    if missing:
        raise ValueError(f"Unexpected constituent columns, missing {missing}: {raw.columns.tolist()}")

    result = df[["stock_code", "stock_name"]].dropna().copy()
    result["stock_code"] = result["stock_code"].astype(str).str.extract(r"(\d{1,6})")[0]
    result["stock_code"] = result["stock_code"].str.zfill(6)
    result = result.dropna(subset=["stock_code"]).drop_duplicates("stock_code")
    result["theme_source"] = source
    result["theme_name"] = theme_name
    result["snapshot_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return result[["snapshot_at", "theme_source", "theme_name", "stock_code", "stock_name"]]


def fetch_theme_history(
    source: str,
    theme_name: str,
    start_date: str,
    end_date: str,
    theme_code: str | None = None,
) -> pd.DataFrame:
    normalized_code = normalize_theme_code(theme_code)
    if source == "concept_em" and normalized_code:
        raw = fetch_em_concept_history_by_code(normalized_code, start_date, end_date)
    elif source == "concept_em":
        raw = ak.stock_board_concept_hist_em(
            symbol=theme_name,
            start_date=start_date,
            end_date=end_date,
            period="日k",
            adjust="",
        )
    elif source == "concept_ths":
        raw = ak.stock_board_concept_index_ths(
            symbol=theme_name,
            start_date=start_date,
            end_date=end_date,
        )
        return normalize_ths_history(raw, prefix="theme")
    else:
        raw = ak.stock_board_industry_hist_em(
            symbol=theme_name,
            start_date=start_date,
            end_date=end_date,
            period="日k",
            adjust="",
        )
    return normalize_em_history(raw, prefix="theme")


def normalize_ths_history(raw: pd.DataFrame, prefix: str) -> pd.DataFrame:
    df = raw.rename(
        columns={
            "日期": "date",
            "开盘价": f"{prefix}_open",
            "收盘价": f"{prefix}_close",
            "最高价": f"{prefix}_high",
            "最低价": f"{prefix}_low",
            "成交量": f"{prefix}_volume",
            "成交额": f"{prefix}_amount",
        }
    )
    keep = [
        "date",
        f"{prefix}_open",
        f"{prefix}_close",
        f"{prefix}_high",
        f"{prefix}_low",
        f"{prefix}_volume",
        f"{prefix}_amount",
    ]
    result = df[[column for column in keep if column in df.columns]].copy()
    result["date"] = pd.to_datetime(result["date"])
    for column in result.columns:
        if column != "date":
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    result[f"{prefix}_change_pct"] = result[f"{prefix}_close"].pct_change() * 100.0
    result[f"{prefix}_turnover_pct"] = pd.NA
    return result


def fetch_em_concept_history_by_code(
    theme_code: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    code = normalize_theme_code(theme_code)
    if not code:
        raise ValueError(f"Eastmoney concept code must look like BK1234: {theme_code}")

    url = "https://91.push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": f"90.{code}",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "0",
        "beg": start_date,
        "end": end_date,
        "smplmt": "10000",
        "lmt": "1000000",
        "_": str(int(time.time() * 1000)),
    }
    response = paced_get(url, params=params, headers=EM_HEADERS, timeout=15)
    response.raise_for_status()
    payload = response.json()
    klines = payload.get("data", {}).get("klines", []) if isinstance(payload.get("data"), dict) else []
    if not klines:
        raise RuntimeError(f"No concept history rows returned for {code}")

    df = pd.DataFrame([item.split(",") for item in klines])
    df.columns = [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "涨跌幅",
        "涨跌额",
        "换手率",
    ]
    return df


def fetch_stock_history(
    stock_code: str,
    stock_name: str,
    start_date: str,
    end_date: str,
    adjust: str,
) -> pd.DataFrame:
    store = DuckDBMarketDataStore(default_database_path())
    try:
        raw = store.load_history(
            stock_code,
            stock_name,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    finally:
        store.close()
    if raw.empty:
        raise RuntimeError(f"empty EDP DuckDB market data for {stock_code} {start_date}-{end_date}")

    result = raw.rename(
        columns={
            "open": "stock_open",
            "close": "stock_close",
            "high": "stock_high",
            "low": "stock_low",
            "volume": "stock_volume",
            "amount": "stock_amount",
            "amplitude": "stock_amplitude_pct",
            "pct_change": "stock_change_pct",
            "turnover": "stock_turnover_pct",
        }
    )
    keep = [
        "date",
        "stock_open",
        "stock_close",
        "stock_high",
        "stock_low",
        "stock_volume",
        "stock_amount",
        "stock_amplitude_pct",
        "stock_change_pct",
        "stock_turnover_pct",
    ]
    return normalize_prefixed_history(result[keep], "stock")


def normalize_em_history(raw: pd.DataFrame, prefix: str) -> pd.DataFrame:
    df = raw.rename(
        columns={
            "日期": "date",
            "开盘": f"{prefix}_open",
            "收盘": f"{prefix}_close",
            "最高": f"{prefix}_high",
            "最低": f"{prefix}_low",
            "成交量": f"{prefix}_volume",
            "成交额": f"{prefix}_amount",
            "振幅": f"{prefix}_amplitude_pct",
            "涨跌幅": f"{prefix}_change_pct",
            "换手率": f"{prefix}_turnover_pct",
        }
    )
    keep = [
        "date",
        f"{prefix}_open",
        f"{prefix}_close",
        f"{prefix}_high",
        f"{prefix}_low",
        f"{prefix}_volume",
        f"{prefix}_amount",
        f"{prefix}_amplitude_pct",
        f"{prefix}_change_pct",
        f"{prefix}_turnover_pct",
    ]
    result = df[[column for column in keep if column in df.columns]].copy()
    result["date"] = pd.to_datetime(result["date"])
    for column in result.columns:
        if column != "date":
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if f"{prefix}_change_pct" not in result.columns:
        result[f"{prefix}_change_pct"] = result[f"{prefix}_close"].pct_change() * 100.0
    if f"{prefix}_turnover_pct" not in result.columns:
        result[f"{prefix}_turnover_pct"] = pd.NA
    return result


def build_membership(
    source: str,
    theme_names: list[str],
    theme_code_map: dict[str, str],
    cache_dir: Path,
    refresh_constituents: bool,
    max_stocks_per_theme: int,
    fetch_attempts: int,
    retry_base_seconds: float,
    theme_code_cache: Path,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for theme_name in theme_names:
        cache_path = cache_dir / "constituents" / source / f"{safe_file_name(theme_name)}.csv"
        print(f"fetch constituents: {theme_name}")

        def fetch_for_theme(name: str = theme_name) -> pd.DataFrame:
            if source == "concept_em" and not normalize_theme_code(theme_code_map.get(name)):
                try:
                    resolved_code = fetch_em_concept_code_by_name(name)
                    theme_code_map[name] = resolved_code
                    save_theme_code_cache(theme_code_cache, theme_code_map)
                except Exception as exc:
                    if not ALLOW_AKSHARE_NAME_FALLBACK:
                        raise
                    print(f"东方财富板块代码解析失败，尝试 AkShare 名称接口：{exc}")
                    return fetch_constituents(source, name)
            return fetch_constituents_with_fallback(
                source,
                name,
                theme_code_map.get(name),
            )

        constituents = read_or_fetch_csv(
            cache_path,
            fetch_for_theme,
            refresh_constituents,
            attempts=fetch_attempts,
            retry_base_seconds=retry_base_seconds,
            provider=constituent_provider(source),
        )
        if max_stocks_per_theme > 0:
            constituents = constituents.head(max_stocks_per_theme).copy()
        theme_code = normalize_theme_code(theme_code_map.get(theme_name))
        if source == "concept_em" and theme_code:
            constituents["theme_code"] = theme_code
        frames.append(constituents)
    if not frames:
        raise RuntimeError("No constituents were fetched.")
    return pd.concat(frames, ignore_index=True)


def build_panel(
    membership: pd.DataFrame,
    source: str,
    start_date: str,
    end_date: str,
    adjust: str,
    cache_dir: Path,
    refresh_history: bool,
    min_history_rows: int,
    fetch_attempts: int,
    retry_base_seconds: float,
    sleep_seconds: float,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for theme_name, group in membership.groupby("theme_name", sort=False):
        theme_cache = (
            cache_dir / "theme_history" / source / f"{safe_file_name(theme_name)}_{start_date}_{end_date}.csv"
        )
        theme_code = None
        if "theme_code" in group.columns:
            codes = group["theme_code"].dropna().astype(str).unique()
            theme_code = codes[0] if len(codes) else None
        print(f"fetch theme history: {theme_name}" + (f" {theme_code}" if theme_code else ""))
        theme_history = read_or_fetch_csv(
            theme_cache,
            lambda name=theme_name, code=theme_code: fetch_theme_history(
                source,
                name,
                start_date,
                end_date,
                code,
            ),
            refresh_history,
            attempts=fetch_attempts,
            retry_base_seconds=retry_base_seconds,
            provider=theme_history_provider(source, theme_code),
        )
        theme_history = normalize_prefixed_history(theme_history, "theme")

        for index, row in group.reset_index(drop=True).iterrows():
            stock_code = str(row["stock_code"]).zfill(6)
            stock_name = str(row["stock_name"])
            print(f"[{index + 1}/{len(group)}] fetch stock: {theme_name} {stock_code} {stock_name}")
            try:
                stock_history = fetch_stock_history(
                    stock_code,
                    stock_name,
                    start_date,
                    end_date,
                    adjust,
                )
            except Exception as exc:
                print(f"skip stock {stock_code} {stock_name}: {exc}")
                continue

            merged = pd.merge(stock_history, theme_history, on="date", how="inner")
            if len(merged) < min_history_rows:
                print(f"skip stock {stock_code} {stock_name}: only {len(merged)} rows")
                continue

            merged["theme_source"] = source
            merged["theme_name"] = theme_name
            merged["stock_code"] = stock_code
            merged["stock_name"] = stock_name
            frames.append(merged)

    if not frames:
        raise RuntimeError("No stock-theme history could be built.")
    return pd.concat(frames, ignore_index=True)


def normalize_prefixed_history(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    result = df.copy()
    if "date" not in result.columns:
        raise ValueError(f"history missing date column: {result.columns.tolist()}")
    result["date"] = pd.to_datetime(result["date"])
    for column in result.columns:
        if column != "date":
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.sort_values("date").drop_duplicates("date").reset_index(drop=True)


def add_features_and_labels(
    panel: pd.DataFrame,
    horizons: list[int],
    top_quantile: float,
    min_amount: float,
    keep_unlabeled_tail: bool,
) -> pd.DataFrame:
    result = panel.sort_values(["theme_name", "stock_code", "date"]).copy()
    grouped_stock = result.groupby(["theme_name", "stock_code"], group_keys=False)
    grouped_theme_date = result.groupby(["theme_name", "date"], group_keys=False)

    result["stock_ret_1d"] = grouped_stock["stock_close"].pct_change()
    result["theme_ret_1d"] = grouped_stock["theme_close"].pct_change()
    result["excess_ret_1d"] = result["stock_ret_1d"] - result["theme_ret_1d"]

    for window in [3, 5, 10, 20]:
        result[f"stock_ret_{window}d"] = grouped_stock["stock_close"].pct_change(window)
        result[f"theme_ret_{window}d"] = grouped_stock["theme_close"].pct_change(window)
        result[f"excess_ret_{window}d"] = result[f"stock_ret_{window}d"] - result[f"theme_ret_{window}d"]
        result[f"stock_amount_change_{window}d"] = grouped_stock["stock_amount"].pct_change(window)

    for window in [5, 20]:
        result[f"stock_volatility_{window}d"] = (
            grouped_stock["stock_ret_1d"].rolling(window).std().reset_index(level=[0, 1], drop=True)
        )
        result[f"stock_amount_ma_{window}d"] = (
            grouped_stock["stock_amount"].rolling(window).mean().reset_index(level=[0, 1], drop=True)
        )

    result["stock_amount_ratio_5_20"] = result["stock_amount_ma_5d"] / result["stock_amount_ma_20d"]
    result["stock_intraday_position"] = (
        (result["stock_close"] - result["stock_low"])
        / (result["stock_high"] - result["stock_low"]).replace(0, pd.NA)
    )
    result["stock_distance_to_20d_high"] = (
        result["stock_close"]
        / grouped_stock["stock_high"].rolling(20).max().reset_index(level=[0, 1], drop=True)
        - 1.0
    )
    result["stock_limit_up_flag"] = (result["stock_change_pct"] >= 9.8).astype("Int64")
    result["stock_recent_limit_up_count_5d"] = (
        grouped_stock["stock_limit_up_flag"].rolling(5).sum().reset_index(level=[0, 1], drop=True)
    )

    rank_specs = {
        "rank_in_theme_ret_1d_pct": "stock_ret_1d",
        "rank_in_theme_excess_1d_pct": "excess_ret_1d",
        "rank_in_theme_amount_pct": "stock_amount",
        "rank_in_theme_amount_ratio_pct": "stock_amount_ratio_5_20",
        "rank_in_theme_distance_high_pct": "stock_distance_to_20d_high",
    }
    for output_column, source_column in rank_specs.items():
        result[output_column] = grouped_theme_date[source_column].rank(pct=True)

    for horizon in horizons:
        result[f"fwd_stock_ret_{horizon}d"] = (
            grouped_stock["stock_close"].shift(-horizon) / result["stock_close"] - 1.0
        )
        result[f"fwd_theme_ret_{horizon}d"] = (
            grouped_stock["theme_close"].shift(-horizon) / result["theme_close"] - 1.0
        )
        result[f"fwd_excess_ret_{horizon}d"] = (
            result[f"fwd_stock_ret_{horizon}d"] - result[f"fwd_theme_ret_{horizon}d"]
        )
        result[f"label_outperform_theme_{horizon}d"] = (
            result[f"fwd_excess_ret_{horizon}d"] > 0
        ).astype("Int64")
        missing_forward = result[f"fwd_excess_ret_{horizon}d"].isna()
        result.loc[missing_forward, f"label_outperform_theme_{horizon}d"] = pd.NA

        next_return_rank = grouped_theme_date[f"fwd_stock_ret_{horizon}d"].rank(pct=True)
        top_label = (next_return_rank >= top_quantile).astype("Int64")
        top_label[result[f"fwd_stock_ret_{horizon}d"].isna()] = pd.NA
        result[f"label_top_{top_pct_from_quantile(top_quantile)}pct_in_theme_{horizon}d"] = top_label

    result["stock_quality_ok"] = (result["stock_amount"] >= min_amount).astype("Int64")
    result = result[result["stock_quality_ok"] == 1].copy()
    if keep_unlabeled_tail:
        return result.reset_index(drop=True)
    return result.dropna(subset=[f"fwd_stock_ret_{horizon}d" for horizon in horizons]).reset_index(
        drop=True
    )


def main() -> None:
    args = parse_args()
    configure_remote_fetching(
        remote_request_interval=args.remote_request_interval,
        em_hosts=args.em_hosts,
        em_max_pages=args.em_max_pages,
        allow_akshare_name_fallback=args.allow_akshare_name_fallback,
    )
    horizons = parse_horizons(args.horizons)
    theme_names = theme_names_from_arg(args.theme_names)
    configure_theme_name_cache(args.cache_dir)
    theme_code_map = load_theme_code_map(
        args.theme_code_map,
        args.theme_code_map_file,
        args.theme_code_cache,
    )
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    membership = build_membership(
        source=args.theme_source,
        theme_names=theme_names,
        theme_code_map=theme_code_map,
        cache_dir=args.cache_dir,
        refresh_constituents=args.refresh_constituents,
        max_stocks_per_theme=args.max_stocks_per_theme,
        fetch_attempts=args.fetch_attempts,
        retry_base_seconds=args.retry_base_seconds,
        theme_code_cache=args.theme_code_cache,
    )
    args.membership_output.parent.mkdir(parents=True, exist_ok=True)
    membership.to_csv(args.membership_output, index=False, encoding="utf-8-sig")

    panel = build_panel(
        membership=membership,
        source=args.theme_source,
        start_date=args.start_date,
        end_date=args.end_date,
        adjust=args.adjust,
        cache_dir=args.cache_dir,
        refresh_history=args.refresh_history,
        min_history_rows=args.min_history_rows,
        fetch_attempts=args.fetch_attempts,
        retry_base_seconds=args.retry_base_seconds,
        sleep_seconds=args.sleep_seconds,
    )
    dataset = add_features_and_labels(
        panel,
        horizons=horizons,
        top_quantile=args.top_quantile,
        min_amount=args.min_amount,
        keep_unlabeled_tail=args.keep_unlabeled_tail,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(args.output, index=False, encoding="utf-8-sig")

    top_pct = top_pct_from_quantile(args.top_quantile)
    print(f"membership_output={args.membership_output}")
    print(f"output={args.output}")
    print(f"rows={len(dataset)}")
    print(f"themes={dataset['theme_name'].nunique()}")
    print(f"stocks={dataset[['theme_name', 'stock_code']].drop_duplicates().shape[0]}")
    print(f"date_range={dataset['date'].min().date()}..{dataset['date'].max().date()}")
    for horizon in horizons:
        label_column = f"label_top_{top_pct}pct_in_theme_{horizon}d"
        print(f"positive_rate_top_{top_pct}pct_{horizon}d={dataset[label_column].dropna().mean():.4f}")
    latest = dataset[dataset["date"] == dataset["date"].max()].sort_values(
        "rank_in_theme_excess_1d_pct",
        ascending=False,
    )
    preview_columns = [
        "date",
        "theme_name",
        "stock_code",
        "stock_name",
        "stock_ret_1d",
        "excess_ret_1d",
        "rank_in_theme_excess_1d_pct",
    ]
    print("latest_top_rows=")
    print(latest[preview_columns].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
