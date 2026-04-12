from __future__ import annotations

import unittest

from scripts.generate_scoring_eval_sample import (
    BUCKETS,
    build_sampling_sql,
    qualify_table,
)


class GenerateScoringEvalSampleTest(unittest.TestCase):
    def test_build_sampling_sql_covers_expected_buckets(self) -> None:
        sql = build_sampling_sql(
            "tidingsiq-dev.gold.positive_news_feed",
            "tidingsiq-dev.silver.gdelt_news_refined",
            lookback_days=30,
            bucket_size=50,
        )

        for bucket in BUCKETS:
            self.assertIn(bucket, sql)
        self.assertIn("weak_domains", sql)
        self.assertIn("row_number() over", sql)
        self.assertIn("order by rand()", sql.lower())

    def test_qualify_table_adds_project_when_needed(self) -> None:
        self.assertEqual(
            qualify_table("tidingsiq-dev", "gold.positive_news_feed"),
            "tidingsiq-dev.gold.positive_news_feed",
        )
        self.assertEqual(
            qualify_table("tidingsiq-dev", "other.gold.positive_news_feed"),
            "other.gold.positive_news_feed",
        )


if __name__ == "__main__":
    unittest.main()
