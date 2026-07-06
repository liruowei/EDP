from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from build_divergence_turning_dashboard import add_dashboard_fields  # noqa: E402
from build_latest_breadth_snapshot import (  # noqa: E402
    add_scores,
    fetch_concept_summary,
    fetch_info,
    info_to_record,
)
from divergence_config import data_path, load_config  # noqa: E402


CONFIG = load_config()
DAILY_CONFIG = CONFIG["daily"]
INTRADAY_CONFIG = CONFIG["intraday"]
THEME_SOURCE = str(CONFIG["theme_source"])
HORIZON = int(DAILY_CONFIG["horizon"])
DEFAULT_RANK_INPUT = data_path(CONFIG, f"divergence_turning_{HORIZON}d_{THEME_SOURCE}_latest_rank.csv")
DEFAULT_SUMMARY_INPUT = data_path(CONFIG, f"divergence_turning_{HORIZON}d_{THEME_SOURCE}_summary.json")
DEFAULT_LATEST_OUTPUT = data_path(CONFIG, "divergence_turning_intraday_latest.csv")
DEFAULT_HISTORY_OUTPUT = data_path(CONFIG, "divergence_turning_intraday_snapshot_history.csv")
DEFAULT_DASHBOARD_DIR = data_path(CONFIG, "edp_intraday_dashboard")
SLEEP_SECONDS = float(INTRADAY_CONFIG["sleep_seconds"])
INTERVAL_SECONDS = float(INTRADAY_CONFIG["interval_seconds"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the standard intraday divergence-turning monitor from config.json."
    )
    return parser.parse_args()


def build_intraday_snapshot() -> pd.DataFrame:
    rank_df = pd.read_csv(DEFAULT_RANK_INPUT)
    required = {"theme_name", "prob_divergence_turn", "rank_probability"}
    missing = sorted(required - set(rank_df.columns))
    if missing:
        raise ValueError(f"rank input missing columns: {missing}")

    theme_names = rank_df["theme_name"].dropna().astype(str).drop_duplicates()
    selected_theme_names = set(theme_names)
    rank_candidates = rank_df[rank_df["theme_name"].astype(str).isin(selected_theme_names)].copy()

    records: list[dict[str, object]] = []
    for index, theme_name in enumerate(theme_names, start=1):
        print(f"[{index}/{len(theme_names)}] fetch intraday breadth: {theme_name}", flush=True)
        try:
            info = fetch_info(THEME_SOURCE, theme_name)
            records.append(info_to_record(THEME_SOURCE, theme_name, info))
        except Exception as exc:
            print(f"skip {theme_name}: {exc}", flush=True)
        time.sleep(SLEEP_SECONDS)

    breadth = pd.DataFrame(records)
    if breadth.empty:
        raise RuntimeError("No intraday breadth snapshot rows were produced.")

    merged = pd.merge(rank_candidates, breadth, on="theme_name", how="left")
    try:
        concept_summary = fetch_concept_summary()
        merged = pd.merge(merged, concept_summary, on="theme_name", how="left")
    except Exception as exc:
        print(f"skip concept summary: {exc}", flush=True)

    scored = add_scores(merged)
    scored["snapshot_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scored = add_intraday_fields(scored, load_previous_snapshot(DEFAULT_HISTORY_OUTPUT))
    return scored


def load_previous_snapshot(history_output: Path) -> pd.DataFrame:
    if not history_output.exists():
        return pd.DataFrame()
    history = pd.read_csv(history_output)
    if history.empty or "snapshot_at" not in history.columns or "theme_name" not in history.columns:
        return pd.DataFrame()
    history["_snapshot_at_dt"] = pd.to_datetime(history["snapshot_at"], errors="coerce")
    history = history.dropna(subset=["_snapshot_at_dt"])
    if history.empty:
        return pd.DataFrame()
    previous = (
        history.sort_values("_snapshot_at_dt")
        .drop_duplicates(subset=["theme_name"], keep="last")
        .copy()
    )
    return previous.drop(columns=["_snapshot_at_dt"])


def add_intraday_fields(current: pd.DataFrame, previous: pd.DataFrame) -> pd.DataFrame:
    result = current.copy()
    if previous.empty:
        result["previous_snapshot_at"] = ""
        for column in intraday_delta_columns():
            result[column] = pd.NA
        result["intraday_state"] = "intraday_first_snapshot"
        return result

    previous = previous.drop_duplicates(subset=["theme_name"], keep="last")
    previous_columns = [
        "theme_name",
        "snapshot_at",
        "board_change_pct",
        "up_ratio",
        "rank_strength",
        "net_inflow_100m",
        "amount_100m",
        "turn_breadth_score",
        "rank_turn_breadth",
    ]
    previous_columns = [column for column in previous_columns if column in previous.columns]
    joined = pd.merge(
        result,
        previous[previous_columns].add_prefix("previous_"),
        left_on="theme_name",
        right_on="previous_theme_name",
        how="left",
    )
    if "previous_theme_name" in joined.columns:
        joined = joined.drop(columns=["previous_theme_name"])

    delta_map = {
        "board_change_delta_pct": ("board_change_pct", "previous_board_change_pct"),
        "up_ratio_delta": ("up_ratio", "previous_up_ratio"),
        "rank_strength_delta": ("rank_strength", "previous_rank_strength"),
        "net_inflow_delta_100m": ("net_inflow_100m", "previous_net_inflow_100m"),
        "amount_delta_100m": ("amount_100m", "previous_amount_100m"),
        "turn_breadth_delta": ("turn_breadth_score", "previous_turn_breadth_score"),
        "rank_turn_breadth_delta": ("rank_turn_breadth", "previous_rank_turn_breadth"),
    }
    for delta_column, (current_column, previous_column) in delta_map.items():
        if current_column in joined.columns and previous_column in joined.columns:
            joined[delta_column] = pd.to_numeric(joined[current_column], errors="coerce") - pd.to_numeric(
                joined[previous_column],
                errors="coerce",
            )
        else:
            joined[delta_column] = pd.NA

    joined["intraday_state"] = joined.apply(classify_intraday_state, axis=1)
    return joined


def intraday_delta_columns() -> list[str]:
    return [
        "board_change_delta_pct",
        "up_ratio_delta",
        "rank_strength_delta",
        "net_inflow_delta_100m",
        "amount_delta_100m",
        "turn_breadth_delta",
        "rank_turn_breadth_delta",
    ]


def classify_intraday_state(row: pd.Series) -> str:
    confirmation = str(row.get("breadth_confirmation_state", ""))
    rank = float(row.get("rank_turn_breadth", 9999))
    board_delta = safe_float(row.get("board_change_delta_pct"))
    up_delta = safe_float(row.get("up_ratio_delta"))
    inflow_delta = safe_float(row.get("net_inflow_delta_100m"))
    score_delta = safe_float(row.get("turn_breadth_delta"))

    if pd.isna(score_delta):
        return "intraday_first_snapshot"
    if rank <= 10 and confirmation in {"breadth_confirmed", "risk_off_breadth_resilient"}:
        if board_delta >= 0 and up_delta >= 0:
            return "intraday_confirming"
    if rank <= 15 and score_delta >= 0.03 and board_delta > 0:
        return "intraday_accelerating"
    if confirmation == "breadth_improving" and score_delta > 0 and (up_delta > 0 or inflow_delta > 0):
        return "intraday_recovering"
    if board_delta <= -0.5 or up_delta <= -0.08 or (score_delta < 0 and inflow_delta < 0):
        return "intraday_fading"
    return "intraday_watch"


def safe_float(value: object) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(parsed) if not pd.isna(parsed) else float("nan")


def append_intraday_snapshot_history(scored: pd.DataFrame, history_output: Path) -> None:
    history_output.parent.mkdir(parents=True, exist_ok=True)
    current = scored.copy()
    if "snapshot_at" not in current.columns:
        raise ValueError("Intraday snapshot must include `snapshot_at`.")
    if history_output.exists():
        history = pd.read_csv(history_output)
        combined = pd.concat([history, current], ignore_index=True, sort=False)
    else:
        combined = current

    combined = combined.drop_duplicates(subset=["snapshot_at", "theme_name"], keep="last")
    if "snapshot_at" in combined.columns:
        combined["_snapshot_at_dt"] = pd.to_datetime(combined["snapshot_at"], errors="coerce")
        combined = combined.sort_values(["_snapshot_at_dt", "rank_turn_breadth", "theme_name"]).drop(
            columns=["_snapshot_at_dt"]
        )
    combined.to_csv(history_output, index=False, encoding="utf-8-sig")


def write_intraday_dashboard(scored: pd.DataFrame) -> None:
    dashboard = add_dashboard_fields(scored)
    DEFAULT_DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    dashboard.to_csv(DEFAULT_DASHBOARD_DIR / "dashboard.csv", index=False, encoding="utf-8-sig")
    (DEFAULT_DASHBOARD_DIR / "dashboard.md").write_text(
        build_intraday_markdown(dashboard),
        encoding="utf-8",
    )
    (DEFAULT_DASHBOARD_DIR / "summary.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "rank_input": str(DEFAULT_RANK_INPUT),
                "latest_output": str(DEFAULT_LATEST_OUTPUT),
                "history_output": str(DEFAULT_HISTORY_OUTPUT),
                "rows": int(len(dashboard)),
                "snapshot_at": str(dashboard["snapshot_at"].dropna().iloc[0])
                if "snapshot_at" in dashboard.columns and not dashboard.empty
                else "",
                "intraday_state_counts": dashboard["intraday_state"].value_counts(dropna=False).to_dict()
                if "intraday_state" in dashboard.columns
                else {},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def build_intraday_markdown(scored: pd.DataFrame) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot_at = ""
    if "snapshot_at" in scored.columns and not scored.empty:
        snapshot_at = str(scored["snapshot_at"].dropna().iloc[0])
    latest_date = str(scored["date"].max()) if "date" in scored.columns else ""
    validation = {}
    if DEFAULT_SUMMARY_INPUT.exists():
        validation = json.loads(DEFAULT_SUMMARY_INPUT.read_text(encoding="utf-8"))

    lines = [
        "# EDP Intraday Divergence Monitor",
        "",
        f"- Generated at: {generated_at}",
        f"- Snapshot at: {snapshot_at}",
        f"- Latest model date: {latest_date}",
        f"- Validation AUC: {validation.get('auc')}",
        "",
        "## Intraday State Counts",
        "",
    ]
    if "intraday_state" in scored.columns:
        for state, count in scored["intraday_state"].value_counts(dropna=False).items():
            lines.append(f"- `{state}`: {int(count)}")

    display_columns = [
        "rank_turn_breadth",
        "theme_name",
        "dashboard_group",
        "intraday_state",
        "prob_divergence_turn",
        "breadth_confirmation_state",
        "board_change_pct",
        "board_change_delta_pct",
        "up_ratio",
        "up_ratio_delta",
        "net_inflow_100m",
        "net_inflow_delta_100m",
        "turn_breadth_score",
        "turn_breadth_delta",
    ]
    display_columns = [column for column in display_columns if column in scored.columns]
    lines.extend(["", "## Top Candidates", "", scored[display_columns].head(30).to_markdown(index=False), ""])
    return "\n".join(lines)


def run_once(iteration: int) -> None:
    print(f"=== intraday snapshot #{iteration} {datetime.now():%Y-%m-%d %H:%M:%S} ===", flush=True)
    scored = build_intraday_snapshot()
    DEFAULT_LATEST_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(DEFAULT_LATEST_OUTPUT, index=False, encoding="utf-8-sig")
    append_intraday_snapshot_history(scored, DEFAULT_HISTORY_OUTPUT)
    write_intraday_dashboard(scored)
    print(f"latest_output={DEFAULT_LATEST_OUTPUT}", flush=True)
    print(f"history_output={DEFAULT_HISTORY_OUTPUT}", flush=True)
    print(f"dashboard_output_dir={DEFAULT_DASHBOARD_DIR}", flush=True)


def main() -> None:
    parse_args()
    iteration = 1
    try:
        while True:
            run_once(iteration)
            iteration += 1
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("intraday monitor stopped by user", flush=True)


if __name__ == "__main__":
    main()
