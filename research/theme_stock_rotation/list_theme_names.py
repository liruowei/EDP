from __future__ import annotations

import argparse
import sys
from pathlib import Path

import akshare as ak
import pandas as pd

MARKET_DATA_DIR = Path(__file__).resolve().parents[1] / "market_data"
if str(MARKET_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(MARKET_DATA_DIR))

from provider_cache import read_or_fetch_csv as cache_read_or_fetch_csv  # noqa: E402


DEFAULT_CACHE_DIR = Path("data") / "theme_stock_rotation" / "akshare_cache"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="列出题材/行业名称，方便确认数据源里的真实名称。")
    parser.add_argument(
        "--theme-source",
        choices=["concept_em", "concept_ths", "industry_em"],
        default="concept_ths",
        help="题材/行业名称来源。",
    )
    parser.add_argument("--keyword", default="", help="按关键词过滤名称。")
    parser.add_argument("--top-n", type=int, default=80, help="最多输出多少行。")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="AkShare 名称列表缓存目录。",
    )
    parser.add_argument("--refresh-list", action="store_true", help="刷新名称列表缓存。")
    return parser.parse_args()


def fetch_names(theme_source: str) -> pd.DataFrame:
    if theme_source == "concept_ths":
        df = ak.stock_board_concept_name_ths()
        return df.rename(columns={"name": "theme_name", "code": "theme_code"})
    if theme_source == "concept_em":
        df = ak.stock_board_concept_name_em()
        return df.rename(columns={"板块名称": "theme_name", "板块代码": "theme_code"})
    df = ak.stock_board_industry_name_em()
    return df.rename(columns={"板块名称": "theme_name", "板块代码": "theme_code"})


def theme_name_cache_path(cache_dir: Path, theme_source: str) -> Path:
    return cache_dir / "theme_names" / f"{theme_source}.csv"


def load_names(theme_source: str, cache_dir: Path, refresh_list: bool) -> pd.DataFrame:
    cache_path = theme_name_cache_path(cache_dir, theme_source)
    df = cache_read_or_fetch_csv(
        cache_path,
        lambda: fetch_names(theme_source),
        refresh_list,
        provider="akshare",
        attempts=3,
        retry_base_seconds=1.0,
        empty_ok=False,
        source_function=f"akshare.stock_board_{theme_source}_name",
    )
    if "theme_code" in df.columns:
        df["theme_code"] = df["theme_code"].astype(str)
    return df


def main() -> None:
    args = parse_args()
    df = load_names(args.theme_source, args.cache_dir, args.refresh_list)
    if "theme_code" not in df.columns:
        df["theme_code"] = ""
    result = df[["theme_name", "theme_code"]].copy()
    result["theme_name"] = result["theme_name"].astype(str)
    if args.keyword:
        result = result[result["theme_name"].str.contains(args.keyword, case=False, na=False)]
    result = result.drop_duplicates("theme_name").head(args.top_n)
    print(f"theme_source={args.theme_source}")
    print(f"keyword={args.keyword or '(无)'}")
    print(f"cache={theme_name_cache_path(args.cache_dir, args.theme_source)}")
    print(f"rows={len(result)}")
    if result.empty:
        print("未找到匹配名称。")
        return
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
