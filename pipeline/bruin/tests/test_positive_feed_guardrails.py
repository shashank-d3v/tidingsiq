from __future__ import annotations

import re
import unittest


DENY_HARD = {
    "obit",
    "obituary",
    "death",
    "dead",
    "dies",
    "killed",
    "kill",
    "murder",
    "murdered",
    "suicide",
    "rape",
    "terrorist",
    "terrorism",
    "bombing",
    "crash",
    "crashed",
    "stabbing",
    "stabbed",
}

DENY_SOFT = {
    "attack",
    "attacked",
    "blast",
    "blasts",
    "bomb",
    "bombs",
    "explosion",
    "explosions",
    "war",
    "warfare",
    "conflict",
    "clashes",
    "riot",
    "riots",
    "unrest",
    "injured",
    "injury",
    "injuries",
    "wounded",
    "hostage",
    "arrest",
    "arrested",
    "probe",
    "scandal",
    "fraud",
    "scam",
    "corruption",
    "fire",
    "wildfire",
    "flood",
    "earthquake",
    "hurricane",
    "cyclone",
    "tornado",
    "disaster",
    "outbreak",
    "epidemic",
    "pandemic",
    "robbery",
    "theft",
    "shooting",
    "shootings",
    "gunfire",
    "shelling",
    "missile",
    "missiles",
    "evacuation",
    "evacuate",
    "toxic",
    "poisoning",
    "panic",
}

ALLOW_TOKENS = {
    "rescue",
    "rescued",
    "recovery",
    "recovered",
    "relief",
    "aid",
    "charity",
    "donation",
    "donate",
    "fundraiser",
    "scholarship",
    "award",
    "awarded",
    "breakthrough",
    "heal",
    "healing",
    "cure",
    "cured",
    "save",
    "saved",
    "peace",
    "ceasefire",
    "community",
    "volunteer",
    "support",
    "celebration",
    "win",
    "wins",
    "victory",
    "reunion",
    "free",
}

ALLOW_PHRASES = {
    "brings community together",
    "free family fun",
    "wins award",
    "peace talks",
    "relief effort",
    "recovery effort",
    "charity event",
    "fundraiser for",
    "rescued from",
    "saved by",
}


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _tokenize(title: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", title.lower()))


def score_title(title: str, tone_score: float, *, has_url: bool = True) -> dict[str, object]:
    normalized_title = _normalize_title(title)
    tokens = _tokenize(title)

    allow_token_hits = sum(token in ALLOW_TOKENS for token in tokens)
    allow_phrase_hits = sum(phrase in normalized_title for phrase in ALLOW_PHRASES)
    allow_hit_count = allow_token_hits + allow_phrase_hits
    soft_deny_hit_count = sum(token in DENY_SOFT for token in tokens)
    hard_deny_hit_count = sum(token in DENY_HARD for token in tokens)

    base_happy_factor = round(max(0.0, min(1.0, (tone_score + 10.0) / 20.0)) * 100, 2)
    positive_bonus = min(10.0, 2.0 * allow_token_hits + 5.0 * allow_phrase_hits)
    soft_penalty = 12.0 if soft_deny_hit_count > 0 and allow_hit_count == 0 else 0.0
    happy_factor = round(max(0.0, min(100.0, base_happy_factor + positive_bonus - soft_penalty)), 2)

    if not normalized_title:
        exclusion_reason = "missing_title"
    elif not has_url:
        exclusion_reason = "missing_url"
    elif hard_deny_hit_count > 0:
        exclusion_reason = "hard_deny_term"
    elif soft_deny_hit_count > 0 and allow_hit_count == 0:
        exclusion_reason = "soft_deny_without_exception"
    elif happy_factor < 65:
        exclusion_reason = "below_threshold"
    else:
        exclusion_reason = None

    return {
        "base_happy_factor": base_happy_factor,
        "happy_factor": happy_factor,
        "allow_token_hits": allow_token_hits,
        "allow_phrase_hits": allow_phrase_hits,
        "allow_hit_count": allow_hit_count,
        "soft_deny_hit_count": soft_deny_hit_count,
        "hard_deny_hit_count": hard_deny_hit_count,
        "is_positive_feed_eligible": exclusion_reason is None,
        "exclusion_reason": exclusion_reason,
    }


class PositiveFeedGuardrailsTest(unittest.TestCase):
    def test_base_score_normalization_from_tone(self) -> None:
        scored = score_title("Neutral headline", 5.88)

        self.assertEqual(scored["base_happy_factor"], 79.4)

    def test_allowlist_bonus_application(self) -> None:
        scored = score_title(
            "Cookie Foundation's FREE Easter Family Fun day brings community together",
            5.0,
        )

        self.assertGreater(scored["happy_factor"], scored["base_happy_factor"])
        self.assertTrue(scored["is_positive_feed_eligible"])

    def test_soft_deny_penalty_application(self) -> None:
        scored = score_title(
            "International Business Senior Kenya executives quit over fuel supply probe",
            5.88,
        )

        self.assertEqual(scored["soft_deny_hit_count"], 1)
        self.assertEqual(scored["exclusion_reason"], "soft_deny_without_exception")
        self.assertFalse(scored["is_positive_feed_eligible"])

    def test_hard_deny_always_excludes(self) -> None:
        scored = score_title('Robert "Bob" Emerson Lee Obit', 5.86)

        self.assertGreater(scored["hard_deny_hit_count"], 0)
        self.assertEqual(scored["exclusion_reason"], "hard_deny_term")
        self.assertFalse(scored["is_positive_feed_eligible"])

    def test_allowlist_overrides_soft_deny(self) -> None:
        scored = score_title("Four Israelis rescued from hostage situation", 5.5)

        self.assertGreater(scored["allow_hit_count"], 0)
        self.assertGreater(scored["soft_deny_hit_count"], 0)
        self.assertTrue(scored["is_positive_feed_eligible"])

    def test_allowlist_does_not_override_hard_deny(self) -> None:
        scored = score_title("Obituary fundraiser announced", 8.0)

        self.assertGreater(scored["allow_hit_count"], 0)
        self.assertGreater(scored["hard_deny_hit_count"], 0)
        self.assertFalse(scored["is_positive_feed_eligible"])
        self.assertEqual(scored["exclusion_reason"], "hard_deny_term")

    def test_soft_deny_without_exception_stays_ineligible(self) -> None:
        scored = score_title("AVOID AREA Explosions Reported near highway", 5.55)

        self.assertEqual(scored["soft_deny_hit_count"], 1)
        self.assertEqual(scored["allow_hit_count"], 0)
        self.assertFalse(scored["is_positive_feed_eligible"])


if __name__ == "__main__":
    unittest.main()
