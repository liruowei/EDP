from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


theme_names = load_module(
    "theme_stock_list_theme_names",
    "research/theme_stock_rotation/list_theme_names.py",
)
theme_breadth = load_module(
    "theme_rotation_latest_breadth",
    "research/theme_rotation/build_latest_breadth_snapshot.py",
)


def test_theme_stock_list_names_uses_cached_csv(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "akshare_cache"
    cache_path = theme_names.theme_name_cache_path(cache_dir, "concept_ths")
    cache_path.parent.mkdir(parents=True)
    pd.DataFrame(
        [{"theme_name": "光刻机", "theme_code": "885800"}]
    ).to_csv(cache_path, index=False, encoding="utf-8-sig")

    def fail_fetch(_theme_source: str) -> pd.DataFrame:
        raise AssertionError("should not fetch remote names when cache exists")

    monkeypatch.setattr(theme_names, "fetch_names", fail_fetch)

    result = theme_names.load_names("concept_ths", cache_dir, refresh_list=False)

    assert result.to_dict("records") == [{"theme_name": "光刻机", "theme_code": "885800"}]


def test_theme_breadth_history_replaces_same_date_theme(tmp_path: Path) -> None:
    history = tmp_path / "theme_breadth_history.csv"
    first = pd.DataFrame(
        [
            {
                "date": "2026-07-03",
                "theme_name": "光刻机",
                "rank_prob_breadth": 4.0,
                "breadth_score": 0.4,
            }
        ]
    )
    second = pd.DataFrame(
        [
            {
                "date": "2026-07-03",
                "theme_name": "光刻机",
                "rank_prob_breadth": 1.0,
                "breadth_score": 0.8,
            }
        ]
    )

    theme_breadth.update_snapshot_history(first, history)
    theme_breadth.update_snapshot_history(second, history)

    result = pd.read_csv(history)
    assert len(result) == 1
    assert result.loc[0, "rank_prob_breadth"] == 1.0
    assert result.loc[0, "breadth_score"] == 0.8
    assert result.duplicated(["date", "theme_name"]).sum() == 0
