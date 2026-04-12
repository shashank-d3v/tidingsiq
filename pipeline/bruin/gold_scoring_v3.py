from __future__ import annotations

from dataclasses import dataclass
import math
import re

URL_QUALITY_PENALTIES = {
    "valid": 0.0,
    "broken": 40.0,
    "timeout": 15.0,
    "forbidden": 10.0,
    "redirect_loop": 30.0,
    "unavailable": 20.0,
    "unchecked": 5.0,
}

EXCLUSION_REASON_MISSING_TITLE = "missing_title"
EXCLUSION_REASON_MISSING_URL = "missing_url"
EXCLUSION_REASON_MALFORMED_URL = "malformed_url"
EXCLUSION_REASON_HARD_DENY = "hard_deny_term"
EXCLUSION_REASON_SOFT_DENY = "soft_deny_without_exception"
EXCLUSION_REASON_BELOW_POSITIVITY = "below_positivity_threshold"
EXCLUSION_REASON_LOW_SUITABILITY = "low_suitability"
EXCLUSION_REASON_URL_BROKEN = "url_broken"
EXCLUSION_REASON_URL_REDIRECT_LOOP = "url_redirect_loop"
EXCLUSION_REASON_URL_UNAVAILABLE = "url_unavailable"

PUNCTUATION_BAIT_PATTERN = re.compile(r"([!?]{2,}|\.{3,})")
GALLERY_BAIT_PATTERN = re.compile(
    r"\b(photo gallery|gallery|slideshow|photos|watch|live updates?|live blog)\b",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
UPPERCASE_TOKEN_PATTERN = re.compile(r"[A-Z]{2,}")


@dataclass(frozen=True)
class HeadlineShapeFeatures:
    punctuation_bait: bool
    gallery_bait: bool
    uppercase_ratio: float
    repeated_template: bool
    penalty: float


def clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def base_positivity_score(tone_score: float | None) -> float:
    tone_value = 0.0 if tone_score is None or math.isnan(float(tone_score)) else float(tone_score)
    return clamp_score(100.0 * max(0.0, min(1.0, (tone_value + 10.0) / 20.0)))


def constructive_bonus(*, allow_token_hits: int, allow_phrase_hits: int) -> float:
    return min(10.0, 2.0 * float(max(0, allow_token_hits)) + 5.0 * float(max(0, allow_phrase_hits)))


def positivity_score(
    tone_score: float | None,
    *,
    allow_token_hits: int,
    allow_phrase_hits: int,
    upstream_adjustment: float = 0.0,
) -> float:
    return clamp_score(
        base_positivity_score(tone_score)
        + constructive_bonus(
            allow_token_hits=allow_token_hits,
            allow_phrase_hits=allow_phrase_hits,
        )
        + float(upstream_adjustment)
    )


def headline_shape_features(
    title: str | None,
    *,
    template_repeat_count: int = 0,
) -> HeadlineShapeFeatures:
    normalized_title = str(title or "")
    tokens = TOKEN_PATTERN.findall(normalized_title)
    alpha_tokens = [token for token in tokens if any(char.isalpha() for char in token)]
    uppercase_tokens = [
        token
        for token in alpha_tokens
        if token.isupper() and UPPERCASE_TOKEN_PATTERN.fullmatch(token)
    ]
    uppercase_ratio = (
        len(uppercase_tokens) / len(alpha_tokens)
        if len(alpha_tokens) >= 5
        else 0.0
    )
    punctuation_bait = bool(PUNCTUATION_BAIT_PATTERN.search(normalized_title))
    gallery_bait = bool(GALLERY_BAIT_PATTERN.search(normalized_title))
    repeated_template = template_repeat_count >= 5

    penalty = 0.0
    if punctuation_bait:
        penalty += 6.0
    if uppercase_ratio >= 0.4:
        penalty += 6.0
    if gallery_bait:
        penalty += 8.0
    if repeated_template:
        penalty += 6.0

    return HeadlineShapeFeatures(
        punctuation_bait=punctuation_bait,
        gallery_bait=gallery_bait,
        uppercase_ratio=round(uppercase_ratio, 4),
        repeated_template=repeated_template,
        penalty=min(20.0, penalty),
    )


def url_quality_penalty(status: str | None) -> float:
    return float(URL_QUALITY_PENALTIES.get(str(status or "unchecked").lower(), 5.0))


def suitability_score(
    *,
    has_title: bool,
    has_valid_url: bool,
    url_quality_status: str | None,
    hard_deny_hit_count: int,
    soft_deny_hit_count: int,
    allow_hit_count: int,
    headline_shape_penalty: float,
    source_quality_adjustment: float,
) -> float:
    total_penalty = min(20.0, max(0.0, float(headline_shape_penalty))) + url_quality_penalty(
        url_quality_status
    )
    if not has_title:
        total_penalty += 100.0
    if not has_valid_url:
        total_penalty += 100.0
    if int(hard_deny_hit_count) > 0:
        total_penalty += 100.0
    if int(soft_deny_hit_count) > 0 and int(allow_hit_count) == 0:
        total_penalty += 25.0
    bounded_source_adjustment = max(-8.0, min(8.0, float(source_quality_adjustment)))
    return clamp_score(100.0 - total_penalty + bounded_source_adjustment)


def composite_happy_factor(*, positivity: float, suitability: float) -> float:
    return clamp_score(0.7 * float(positivity) + 0.3 * float(suitability))


def exclusion_reason(
    *,
    has_title: bool,
    has_url: bool,
    has_valid_url: bool,
    hard_deny_hit_count: int,
    soft_deny_hit_count: int,
    allow_hit_count: int,
    positivity: float,
    suitability: float,
    url_quality_status: str | None,
) -> str | None:
    status = str(url_quality_status or "unchecked").lower()
    if not has_title:
        return EXCLUSION_REASON_MISSING_TITLE
    if not has_url:
        return EXCLUSION_REASON_MISSING_URL
    if not has_valid_url:
        return EXCLUSION_REASON_MALFORMED_URL
    if int(hard_deny_hit_count) > 0:
        return EXCLUSION_REASON_HARD_DENY
    if int(soft_deny_hit_count) > 0 and int(allow_hit_count) == 0:
        return EXCLUSION_REASON_SOFT_DENY
    if status == "broken":
        return EXCLUSION_REASON_URL_BROKEN
    if status == "redirect_loop":
        return EXCLUSION_REASON_URL_REDIRECT_LOOP
    if status == "unavailable":
        return EXCLUSION_REASON_URL_UNAVAILABLE
    if float(positivity) < 65.0:
        return EXCLUSION_REASON_BELOW_POSITIVITY
    if float(suitability) < 60.0:
        return EXCLUSION_REASON_LOW_SUITABILITY
    return None
