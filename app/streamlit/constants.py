from __future__ import annotations

import os
from typing import Final


DEFAULT_PROJECT_ID = os.getenv("TIDINGSIQ_GCP_PROJECT", "tidingsiq-dev")
DEFAULT_TABLE_FQN = os.getenv(
    "TIDINGSIQ_GOLD_TABLE",
    f"{DEFAULT_PROJECT_ID}.gold.positive_news_feed",
)

PAGE_BRIEF: Final[str] = "The Brief"
PAGE_PULSE: Final[str] = "Pulse"
PAGE_METHODOLOGY: Final[str] = "Methodology"

LOOKBACK_OPTIONS: Final[list[int]] = [1, 3, 7, 30]
RESULT_LIMIT_OPTIONS: Final[list[int]] = [25, 50, 100, 200]

RECOMMENDED_PAGE_SIZE: Final[int] = 10
EXPLORE_PAGE_SIZE: Final[int] = 6
