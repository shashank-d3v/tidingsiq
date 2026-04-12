from __future__ import annotations

import unittest

from pipeline.bruin.gold_scoring_v3 import (
    EXCLUSION_REASON_BELOW_POSITIVITY,
    EXCLUSION_REASON_HARD_DENY,
    EXCLUSION_REASON_LOW_SUITABILITY,
    EXCLUSION_REASON_MALFORMED_URL,
    EXCLUSION_REASON_MISSING_TITLE,
    EXCLUSION_REASON_SOFT_DENY,
    EXCLUSION_REASON_URL_BROKEN,
    EXCLUSION_REASON_URL_REDIRECT_LOOP,
    EXCLUSION_REASON_URL_UNAVAILABLE,
    composite_happy_factor,
    exclusion_reason,
    headline_shape_features,
    positivity_score,
    suitability_score,
)


class GoldScoringV3Test(unittest.TestCase):
    def test_positivity_score_is_monotonic_and_bounded(self) -> None:
        low = positivity_score(-20.0, allow_token_hits=0, allow_phrase_hits=0)
        mid = positivity_score(0.0, allow_token_hits=0, allow_phrase_hits=0)
        high = positivity_score(12.5, allow_token_hits=0, allow_phrase_hits=0)

        self.assertEqual(low, 0.0)
        self.assertLess(low, mid)
        self.assertLess(mid, high)
        self.assertEqual(high, 100.0)

    def test_constructive_bonus_improves_positivity_score(self) -> None:
        base = positivity_score(5.0, allow_token_hits=0, allow_phrase_hits=0)
        boosted = positivity_score(5.0, allow_token_hits=2, allow_phrase_hits=1)

        self.assertGreater(boosted, base)
        self.assertLessEqual(boosted, 100.0)

    def test_headline_shape_penalty_caps_at_twenty(self) -> None:
        features = headline_shape_features(
            "WATCH LIVE UPDATES!!! PHOTO GALLERY FROM BIG EVENT...",
            template_repeat_count=8,
        )

        self.assertTrue(features.punctuation_bait)
        self.assertTrue(features.gallery_bait)
        self.assertTrue(features.repeated_template)
        self.assertEqual(features.penalty, 20.0)

    def test_suitability_score_hard_deny_excludes_completely(self) -> None:
        score = suitability_score(
            has_title=True,
            has_valid_url=True,
            url_quality_status="valid",
            hard_deny_hit_count=1,
            soft_deny_hit_count=0,
            allow_hit_count=0,
            headline_shape_penalty=0.0,
            source_quality_adjustment=0.0,
        )

        self.assertEqual(score, 0.0)

    def test_soft_deny_without_allow_reduces_suitability(self) -> None:
        score = suitability_score(
            has_title=True,
            has_valid_url=True,
            url_quality_status="valid",
            hard_deny_hit_count=0,
            soft_deny_hit_count=1,
            allow_hit_count=0,
            headline_shape_penalty=0.0,
            source_quality_adjustment=0.0,
        )

        self.assertEqual(score, 75.0)

    def test_timeout_and_forbidden_do_not_force_exclusion(self) -> None:
        suitability_timeout = suitability_score(
            has_title=True,
            has_valid_url=True,
            url_quality_status="timeout",
            hard_deny_hit_count=0,
            soft_deny_hit_count=0,
            allow_hit_count=0,
            headline_shape_penalty=0.0,
            source_quality_adjustment=0.0,
        )
        suitability_forbidden = suitability_score(
            has_title=True,
            has_valid_url=True,
            url_quality_status="forbidden",
            hard_deny_hit_count=0,
            soft_deny_hit_count=0,
            allow_hit_count=0,
            headline_shape_penalty=0.0,
            source_quality_adjustment=0.0,
        )

        self.assertGreaterEqual(suitability_timeout, 60.0)
        self.assertGreaterEqual(suitability_forbidden, 60.0)
        self.assertIsNone(
            exclusion_reason(
                has_title=True,
                has_url=True,
                has_valid_url=True,
                hard_deny_hit_count=0,
                soft_deny_hit_count=0,
                allow_hit_count=0,
                positivity=70.0,
                suitability=suitability_timeout,
                url_quality_status="timeout",
            )
        )

    def test_broken_and_redirect_loop_urls_force_exclusion(self) -> None:
        self.assertEqual(
            exclusion_reason(
                has_title=True,
                has_url=True,
                has_valid_url=True,
                hard_deny_hit_count=0,
                soft_deny_hit_count=0,
                allow_hit_count=0,
                positivity=80.0,
                suitability=70.0,
                url_quality_status="broken",
            ),
            EXCLUSION_REASON_URL_BROKEN,
        )
        self.assertEqual(
            exclusion_reason(
                has_title=True,
                has_url=True,
                has_valid_url=True,
                hard_deny_hit_count=0,
                soft_deny_hit_count=0,
                allow_hit_count=0,
                positivity=80.0,
                suitability=70.0,
                url_quality_status="redirect_loop",
            ),
            EXCLUSION_REASON_URL_REDIRECT_LOOP,
        )
        self.assertEqual(
            exclusion_reason(
                has_title=True,
                has_url=True,
                has_valid_url=True,
                hard_deny_hit_count=0,
                soft_deny_hit_count=0,
                allow_hit_count=0,
                positivity=80.0,
                suitability=70.0,
                url_quality_status="unavailable",
            ),
            EXCLUSION_REASON_URL_UNAVAILABLE,
        )

    def test_missing_title_and_bad_url_exclusions_take_priority(self) -> None:
        self.assertEqual(
            exclusion_reason(
                has_title=False,
                has_url=True,
                has_valid_url=True,
                hard_deny_hit_count=0,
                soft_deny_hit_count=0,
                allow_hit_count=0,
                positivity=80.0,
                suitability=70.0,
                url_quality_status="valid",
            ),
            EXCLUSION_REASON_MISSING_TITLE,
        )
        self.assertEqual(
            exclusion_reason(
                has_title=True,
                has_url=True,
                has_valid_url=False,
                hard_deny_hit_count=0,
                soft_deny_hit_count=0,
                allow_hit_count=0,
                positivity=80.0,
                suitability=70.0,
                url_quality_status="valid",
            ),
            EXCLUSION_REASON_MALFORMED_URL,
        )

    def test_threshold_exclusions_follow_status_checks(self) -> None:
        self.assertEqual(
            exclusion_reason(
                has_title=True,
                has_url=True,
                has_valid_url=True,
                hard_deny_hit_count=1,
                soft_deny_hit_count=0,
                allow_hit_count=0,
                positivity=90.0,
                suitability=0.0,
                url_quality_status="valid",
            ),
            EXCLUSION_REASON_HARD_DENY,
        )
        self.assertEqual(
            exclusion_reason(
                has_title=True,
                has_url=True,
                has_valid_url=True,
                hard_deny_hit_count=0,
                soft_deny_hit_count=1,
                allow_hit_count=0,
                positivity=90.0,
                suitability=75.0,
                url_quality_status="valid",
            ),
            EXCLUSION_REASON_SOFT_DENY,
        )
        self.assertEqual(
            exclusion_reason(
                has_title=True,
                has_url=True,
                has_valid_url=True,
                hard_deny_hit_count=0,
                soft_deny_hit_count=0,
                allow_hit_count=0,
                positivity=50.0,
                suitability=90.0,
                url_quality_status="valid",
            ),
            EXCLUSION_REASON_BELOW_POSITIVITY,
        )
        self.assertEqual(
            exclusion_reason(
                has_title=True,
                has_url=True,
                has_valid_url=True,
                hard_deny_hit_count=0,
                soft_deny_hit_count=0,
                allow_hit_count=0,
                positivity=80.0,
                suitability=55.0,
                url_quality_status="timeout",
            ),
            EXCLUSION_REASON_LOW_SUITABILITY,
        )

    def test_source_quality_adjustment_is_bounded(self) -> None:
        boosted = suitability_score(
            has_title=True,
            has_valid_url=True,
            url_quality_status="valid",
            hard_deny_hit_count=0,
            soft_deny_hit_count=0,
            allow_hit_count=0,
            headline_shape_penalty=0.0,
            source_quality_adjustment=99.0,
        )
        penalized = suitability_score(
            has_title=True,
            has_valid_url=True,
            url_quality_status="valid",
            hard_deny_hit_count=0,
            soft_deny_hit_count=0,
            allow_hit_count=0,
            headline_shape_penalty=0.0,
            source_quality_adjustment=-99.0,
        )

        self.assertEqual(boosted, 100.0)
        self.assertEqual(penalized, 92.0)

    def test_composite_happy_factor_stays_in_range(self) -> None:
        self.assertEqual(composite_happy_factor(positivity=100.0, suitability=100.0), 100.0)
        self.assertEqual(composite_happy_factor(positivity=0.0, suitability=0.0), 0.0)
        self.assertEqual(composite_happy_factor(positivity=80.0, suitability=60.0), 74.0)


if __name__ == "__main__":
    unittest.main()
