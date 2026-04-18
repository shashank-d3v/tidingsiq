from __future__ import annotations

import unittest
from unittest.mock import patch

from app.streamlit.constants import (
    LOOKBACK_OPTIONS,
    QUERY_ROW_LIMIT,
    RECOMMENDED_PAGE_SIZE,
    resolve_runtime_config,
)


class ConstantsTest(unittest.TestCase):
    def test_serving_controls_remain_fixed_and_bounded(self) -> None:
        self.assertEqual(LOOKBACK_OPTIONS, [1, 3, 7, 30])
        self.assertEqual(RECOMMENDED_PAGE_SIZE, 10)
        self.assertEqual(QUERY_ROW_LIMIT, 200)

    def test_resolve_runtime_config_requires_project_env(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(
                RuntimeError,
                "TIDINGSIQ_GCP_PROJECT must be set",
            ):
                resolve_runtime_config()

    def test_resolve_runtime_config_derives_default_table_from_project(self) -> None:
        with patch.dict(
            "os.environ",
            {"TIDINGSIQ_GCP_PROJECT": "example-project"},
            clear=True,
        ):
            self.assertEqual(
                resolve_runtime_config(),
                ("example-project", "example-project.gold.positive_news_feed"),
            )

    def test_resolve_runtime_config_uses_explicit_table_override(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "TIDINGSIQ_GCP_PROJECT": "example-project",
                "TIDINGSIQ_GOLD_TABLE": "other-project.gold.custom_feed",
            },
            clear=True,
        ):
            self.assertEqual(
                resolve_runtime_config(),
                ("example-project", "other-project.gold.custom_feed"),
            )


if __name__ == "__main__":
    unittest.main()
