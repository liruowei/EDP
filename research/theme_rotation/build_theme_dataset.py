from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import akshare as ak
import pandas as pd

MARKET_DATA_DIR = Path(__file__).resolve().parents[1] / "market_data"
if str(MARKET_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(MARKET_DATA_DIR))

from provider_cache import read_or_fetch_csv as cache_read_or_fetch_csv  # noqa: E402


DEFAULT_START_DATE = "20220101"
DEFAULT_THEME_SOURCE = "concept_em"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a theme rotation dataset from AkShare board history."
    )
    parser.add_argument(
        "--theme-source",
        choices=["concept_em", "concept_ths", "industry_em", "industry_ths"],
        default=DEFAULT_THEME_SOURCE,
        help="AkShare board source. concept_em is the default for topic rotation.",
    )
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument(
        "--horizon",
        type=int,
        default=None,
        help="Single forward horizon kept for compatibility. Overrides --horizons when set.",
    )
    parser.add_argument(
        "--horizons",
        default="1,3,5",
        help="Comma-separated forward horizons, e.g. 1,3,5.",
    )
    parser.add_argument("--top-quantile", type=float, default=0.8)
    parser.add_argument("--min-history-rows", type=int, default=120)
    parser.add_argument("--min-amount", type=float, default=0.0)
    parser.add_argument("--max-themes", type=int, default=0)
    parser.add_argument(
        "--theme-names",
        default="",
        help="Optional comma-separated theme names. When set, skips automatic theme list fetching.",
    )
    parser.add_argument(
        "--theme-filter",
        default="",
        help="Optional regex applied to theme names before fetching histories.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data") / "theme_rotation" / "akshare_cache",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data") / "theme_rotation" / "theme_rotation_1d.csv",
    )
    parser.add_argument("--refresh-list", action="store_true")
    parser.add_argument("--refresh-history", action="store_true")
    parser.add_argument(
        "--keep-unlabeled-tail",
        action="store_true",
        help="Keep latest rows without forward labels for live prediction.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    return parser.parse_args()


def read_or_fetch_csv(
    path: Path,
    fetch: Callable[[], pd.DataFrame],
    refresh: bool,
    attempts: int = 4,
) -> pd.DataFrame:
    return cache_read_or_fetch_csv(
        path,
        fetch,
        refresh,
        provider="akshare",
        attempts=attempts,
        retry_base_seconds=1.0,
        empty_ok=False,
        source_function=f"akshare.{path.stem}",
    )


def safe_file_name(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value).strip("_")


def fetch_theme_list(source: str) -> pd.DataFrame:
    if source == "concept_em":
        raw = ak.stock_board_concept_name_em()
        df = raw.rename(columns={"板块名称": "theme_name", "板块代码": "theme_code"})
        df["theme_type"] = "concept"
        return df[["theme_name", "theme_code", "theme_type"]].dropna()

    if source == "concept_ths":
        raw = ak.stock_board_concept_name_ths()
        df = raw.rename(columns={"name": "theme_name", "code": "theme_code"})
        df["theme_type"] = "concept_ths"
        return df[["theme_name", "theme_code", "theme_type"]].dropna()

    if source == "industry_em":
        raw = ak.stock_board_industry_name_em()
        df = raw.rename(columns={"板块名称": "theme_name", "板块代码": "theme_code"})
        df["theme_type"] = "industry_em"
        return df[["theme_name", "theme_code", "theme_type"]].dropna()

    # THS industry list does not have a separate lightweight name endpoint in this workflow.
    # Use the names that are normally stable and useful for a first industry rotation run.
    names = [
        "半导体",
        "元件",
        "软件开发",
        "互联网服务",
        "通信设备",
        "化学制品",
        "化学纤维",
        "电池",
        "光伏设备",
        "汽车零部件",
        "证券",
        "银行",
        "房地产开发",
        "医疗器械",
        "中药",
        "消费电子",
        "军工电子",
    ]
    return pd.DataFrame(
        {
            "theme_name": names,
            "theme_code": names,
            "theme_type": "industry_ths",
        }
    )


def theme_list_from_names(source: str, theme_names: str) -> pd.DataFrame:
    names = [name.strip() for name in theme_names.split(",") if name.strip()]
    if not names:
        raise ValueError("--theme-names was provided but no valid names were found.")
    if source in ("concept_em", "concept_ths"):
        theme_type = "concept"
    else:
        theme_type = source
    return pd.DataFrame(
        {
            "theme_name": names,
            "theme_code": names,
            "theme_type": theme_type,
        }
    )


def fetch_theme_history(
    source: str,
    theme_name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    if source == "concept_em":
        raw = ak.stock_board_concept_hist_em(
            symbol=theme_name,
            start_date=start_date,
            end_date=end_date,
            period="日k",
            adjust="",
        )
        return normalize_em_history(raw)

    if source == "concept_ths":
        raw = ak.stock_board_concept_index_ths(
            symbol=theme_name,
            start_date=start_date,
            end_date=end_date,
        )
        df = raw.rename(
            columns={
                "日期": "date",
                "开盘价": "open",
                "收盘价": "close",
                "最高价": "high",
                "最低价": "low",
                "成交量": "volume",
                "成交额": "amount",
            }
        )
        return normalize_history(
            df[["date", "open", "close", "high", "low", "volume", "amount"]]
        )

    if source == "industry_em":
        raw = ak.stock_board_industry_hist_em(
            symbol=theme_name,
            start_date=start_date,
            end_date=end_date,
            period="日k",
            adjust="",
        )
        return normalize_em_history(raw)

    raw = ak.stock_board_industry_index_ths(
        symbol=theme_name,
        start_date=start_date,
        end_date=end_date,
    )
    df = raw.rename(
        columns={
            "日期": "date",
            "开盘价": "open",
            "收盘价": "close",
            "最高价": "high",
            "最低价": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
    )
    return normalize_history(df[["date", "open", "close", "high", "low", "volume", "amount"]])


def normalize_em_history(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude_pct",
            "涨跌幅": "change_pct",
            "换手率": "turnover_pct",
        }
    )
    keep = [
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "amplitude_pct",
        "change_pct",
        "turnover_pct",
    ]
    return normalize_history(df[[column for column in keep if column in df.columns]])


def normalize_history(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["date"] = pd.to_datetime(result["date"])
    for column in result.columns:
        if column != "date":
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if "change_pct" not in result.columns:
        result["change_pct"] = result["close"].pct_change() * 100.0
    if "amplitude_pct" not in result.columns:
        result["amplitude_pct"] = (
            (result["high"] - result["low"]) / result["close"].shift(1) * 100.0
        )
    if "turnover_pct" not in result.columns:
        result["turnover_pct"] = pd.NA
    return result


def build_theme_panel(
    theme_list: pd.DataFrame,
    source: str,
    start_date: str,
    end_date: str,
    cache_dir: Path,
    refresh_history: bool,
    min_history_rows: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for index, row in theme_list.reset_index(drop=True).iterrows():
        theme_name = str(row["theme_name"])
        theme_code = str(row.get("theme_code", theme_name))
        cache_path = (
            cache_dir
            / "history"
            / source
            / f"{safe_file_name(theme_name)}_{start_date}_{end_date}.csv"
        )
        print(f"[{index + 1}/{len(theme_list)}] fetch theme: {theme_name}")
        try:
            history = read_or_fetch_csv(
                cache_path,
                lambda name=theme_name: fetch_theme_history(source, name, start_date, end_date),
                refresh_history,
            )
        except Exception as exc:
            print(f"skip theme {theme_name}: {exc}")
            continue

        history = normalize_history(history)
        if len(history) < min_history_rows:
            print(f"skip theme {theme_name}: only {len(history)} rows")
            continue

        history["theme_name"] = theme_name
        history["theme_code"] = theme_code
        history["theme_type"] = row.get("theme_type", source)
        frames.append(history)
        time.sleep(sleep_seconds)

    if not frames:
        raise RuntimeError("No theme history could be fetched.")
    return pd.concat(frames, ignore_index=True)


def add_features_and_labels(
    panel: pd.DataFrame,
    horizons: list[int],
    top_quantile: float,
    min_amount: float,
    keep_unlabeled_tail: bool = False,
) -> pd.DataFrame:
    result = panel.sort_values(["theme_name", "date"]).copy()
    grouped = result.groupby("theme_name", group_keys=False)

    result["ret_1d"] = grouped["close"].pct_change()
    for window in [3, 5, 10, 20]:
        result[f"ret_{window}d"] = grouped["close"].pct_change(window)
        result[f"amount_change_{window}d"] = grouped["amount"].pct_change(window)

    for window in [5, 20]:
        result[f"volatility_{window}d"] = grouped["ret_1d"].rolling(window).std().reset_index(
            level=0, drop=True
        )
        result[f"amount_ma_{window}d"] = grouped["amount"].rolling(window).mean().reset_index(
            level=0, drop=True
        )

    result["amount_ratio_5_20"] = result["amount_ma_5d"] / result["amount_ma_20d"]
    result["intraday_position"] = (
        (result["close"] - result["low"]) / (result["high"] - result["low"]).replace(0, pd.NA)
    )
    for horizon in horizons:
        result[f"fwd_ret_{horizon}d"] = grouped["close"].shift(-horizon) / result["close"] - 1.0

    result["cross_section_ret_1d_rank_pct"] = result.groupby("date")["ret_1d"].rank(pct=True)
    result["cross_section_amount_rank_pct"] = result.groupby("date")["amount"].rank(pct=True)
    result["cross_section_amount_ratio_rank_pct"] = result.groupby("date")[
        "amount_ratio_5_20"
    ].rank(pct=True)

    for horizon in horizons:
        next_return_rank = result.groupby("date")[f"fwd_ret_{horizon}d"].rank(pct=True)
        label = (next_return_rank >= top_quantile).astype("Int64")
        label[result[f"fwd_ret_{horizon}d"].isna()] = pd.NA
        result[f"label_top_{top_pct_from_quantile(top_quantile)}pct_{horizon}d"] = label

    result["theme_quality_ok"] = (result["amount"] >= min_amount).astype("Int64")
    result = result[result["theme_quality_ok"] == 1].copy()
    if keep_unlabeled_tail:
        return result.reset_index(drop=True)
    return result.dropna(subset=[f"fwd_ret_{horizon}d" for horizon in horizons]).reset_index(
        drop=True
    )


def top_pct_from_quantile(top_quantile: float) -> int:
    return int(round((1.0 - top_quantile) * 100))


def parse_horizons(horizon: int | None, horizons: str) -> list[int]:
    if horizon is not None:
        return [horizon]
    parsed = sorted({int(item.strip()) for item in horizons.split(",") if item.strip()})
    if not parsed:
        raise ValueError("At least one horizon must be provided.")
    if any(item <= 0 for item in parsed):
        raise ValueError(f"Horizons must be positive integers: {parsed}")
    return parsed


def main() -> None:
    args = parse_args()
    horizons = parse_horizons(args.horizon, args.horizons)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    if args.theme_names:
        theme_list = theme_list_from_names(args.theme_source, args.theme_names)
    else:
        list_cache = args.cache_dir / f"theme_list_{args.theme_source}.csv"
        theme_list = read_or_fetch_csv(
            list_cache,
            lambda: fetch_theme_list(args.theme_source),
            args.refresh_list,
        )
    if args.theme_filter:
        theme_list = theme_list[
            theme_list["theme_name"].astype(str).str.contains(args.theme_filter, regex=True)
        ].copy()
    if args.max_themes > 0:
        theme_list = theme_list.head(args.max_themes).copy()

    if theme_list.empty:
        raise RuntimeError("Theme list is empty after filters.")

    panel = build_theme_panel(
        theme_list=theme_list,
        source=args.theme_source,
        start_date=args.start_date,
        end_date=args.end_date,
        cache_dir=args.cache_dir,
        refresh_history=args.refresh_history,
        min_history_rows=args.min_history_rows,
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
    print(f"output={args.output}")
    print(f"rows={len(dataset)}")
    print(f"themes={dataset['theme_name'].nunique()}")
    print(f"date_range={dataset['date'].min().date()}..{dataset['date'].max().date()}")
    for horizon in horizons:
        label_column = f"label_top_{top_pct}pct_{horizon}d"
        label_rate = dataset[label_column].dropna().mean()
        print(f"positive_rate_{horizon}d={label_rate:.4f}")
    print("latest_date_top_rows=")
    latest = dataset[dataset["date"] == dataset["date"].max()].sort_values(
        "ret_1d", ascending=False
    )
    preview_columns = ["date", "theme_name", "ret_1d", "amount_ratio_5_20"]
    preview_columns.extend([f"label_top_{top_pct}pct_{horizon}d" for horizon in horizons])
    print(latest[preview_columns].head(10))


if __name__ == "__main__":
    main()
