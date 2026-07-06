from __future__ import annotations

from datetime import date, time

import pandas as pd


CHINA_TZ = "Asia/Shanghai"
DAILY_RELIABLE_CLOSE_TIME = time(15, 3)


def china_today() -> date:
    return pd.Timestamp.now(tz=CHINA_TZ).date()


def is_after_daily_reliable_close(now: pd.Timestamp | None = None) -> bool:
    current = now or pd.Timestamp.now(tz=CHINA_TZ)
    if current.tzinfo is not None:
        current = current.tz_convert(CHINA_TZ)
    return current.time() >= DAILY_RELIABLE_CLOSE_TIME
