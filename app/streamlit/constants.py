from __future__ import annotations

import os
from typing import Final


REQUIRED_PROJECT_ENV_VAR: Final[str] = "TIDINGSIQ_GCP_PROJECT"
OPTIONAL_TABLE_ENV_VAR: Final[str] = "TIDINGSIQ_GOLD_TABLE"
DEFAULT_GOLD_TABLE_SUFFIX: Final[str] = "gold.positive_news_feed"


def resolve_runtime_config() -> tuple[str, str]:
    project_id = os.getenv(REQUIRED_PROJECT_ENV_VAR, "").strip()
    if not project_id:
        raise RuntimeError(
            f"{REQUIRED_PROJECT_ENV_VAR} must be set before starting the Streamlit app."
        )

    table_fqn = os.getenv(OPTIONAL_TABLE_ENV_VAR, "").strip()
    if not table_fqn:
        table_fqn = f"{project_id}.{DEFAULT_GOLD_TABLE_SUFFIX}"

    return project_id, table_fqn


PAGE_BRIEF: Final[str] = "The Brief"
PAGE_PULSE: Final[str] = "Pulse"
PAGE_METHODOLOGY: Final[str] = "Methodology"

LOOKBACK_OPTIONS: Final[list[int]] = [1, 3, 7, 30]

# App-side safety cap for BigQuery queries. This is not a user-facing control.
QUERY_ROW_LIMIT: Final[int] = 200

RECOMMENDED_PAGE_SIZE: Final[int] = 10
EXPLORE_PAGE_SIZE: Final[int] = 6
