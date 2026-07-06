from __future__ import annotations

from ..common import ForwardArg


def common_rank_forward_args(extra: list[ForwardArg] | None = None) -> list[ForwardArg]:
    args = [
        ForwardArg("input", "--input", "optional"),
        ForwardArg("horizon", "--horizon"),
        ForwardArg("top_pct", "--top-pct"),
        ForwardArg("top_n", "--top-n"),
        ForwardArg("model", "--model"),
        ForwardArg("predict_date", "--predict-date"),
        ForwardArg("flow_lookback_dates", "--flow-lookback-dates"),
        ForwardArg("flow_low_pp", "--flow-low-pp"),
        ForwardArg("flow_high_pp", "--flow-high-pp"),
        ForwardArg("output", "--output", "optional"),
        ForwardArg("latest_output", "--latest-output", "optional"),
    ]
    if extra:
        args[2:2] = extra
    return args
