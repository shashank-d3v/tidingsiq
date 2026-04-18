from __future__ import annotations

from collections.abc import Callable


def normalize_brief_selection(values: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def prune_selection_to_options(
    selected_values: list[str] | tuple[str, ...],
    valid_options: list[str] | tuple[str, ...],
) -> list[str]:
    valid_option_set = set(normalize_brief_selection(valid_options))
    return [
        value
        for value in normalize_brief_selection(selected_values)
        if value in valid_option_set
    ]


def merge_options_with_selected(
    options: list[str] | tuple[str, ...],
    selected_values: list[str] | tuple[str, ...],
) -> list[str]:
    return sorted(
        set(normalize_brief_selection(options)) | set(normalize_brief_selection(selected_values))
    )


def build_scope_signature(
    lookback_days: int,
    selected_languages: list[str] | tuple[str, ...],
    selected_geographies: list[str] | tuple[str, ...],
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    return (
        int(lookback_days),
        tuple(sorted(normalize_brief_selection(selected_languages))),
        tuple(sorted(normalize_brief_selection(selected_geographies))),
    )


def build_rows_signature(
    scope_signature: tuple[int, tuple[str, ...], tuple[str, ...]],
    sort_order: str,
    page_number: int,
    page_size: int,
) -> tuple[tuple[int, tuple[str, ...], tuple[str, ...]], str, int, int]:
    return (
        scope_signature,
        str(sort_order),
        max(1, int(page_number)),
        max(1, int(page_size)),
    )


def build_language_options_signature(
    lookback_days: int,
    selected_geographies: list[str] | tuple[str, ...],
) -> tuple[int, tuple[str, ...]]:
    return (
        int(lookback_days),
        tuple(sorted(normalize_brief_selection(selected_geographies))),
    )


def build_geography_options_signature(
    lookback_days: int,
    selected_languages: list[str] | tuple[str, ...],
) -> tuple[int, tuple[str, ...]]:
    return (
        int(lookback_days),
        tuple(sorted(normalize_brief_selection(selected_languages))),
    )


def compute_total_pages(total_rows: int, page_size: int) -> int:
    safe_page_size = max(1, int(page_size))
    safe_total_rows = max(0, int(total_rows))
    return max(1, (safe_total_rows + safe_page_size - 1) // safe_page_size)


def clamp_page_number(page_number: int, total_rows: int, page_size: int) -> int:
    return max(1, min(int(page_number), compute_total_pages(total_rows, page_size)))


def reset_page_on_scope_change(
    previous_scope_signature: object,
    scope_signature: tuple[int, tuple[str, ...], tuple[str, ...]],
    current_page: int,
) -> int:
    if previous_scope_signature != scope_signature:
        return 1
    return max(1, int(current_page))


def resolve_brief_filter_state(
    *,
    lookback_days: int,
    selected_languages: list[str] | tuple[str, ...],
    selected_geographies: list[str] | tuple[str, ...],
    load_language_options: Callable[[int, tuple[str, ...]], list[str]],
    load_geography_options: Callable[[int, tuple[str, ...]], list[str]],
    preserve_selected_in_options: bool = False,
) -> tuple[list[str], list[str], list[str], list[str]]:
    current_languages = normalize_brief_selection(selected_languages)
    current_geographies = normalize_brief_selection(selected_geographies)
    if preserve_selected_in_options:
        language_options = merge_options_with_selected(
            load_language_options(
                *build_language_options_signature(lookback_days, current_geographies)
            ),
            current_languages,
        )
        geography_options = merge_options_with_selected(
            load_geography_options(
                *build_geography_options_signature(lookback_days, current_languages)
            ),
            current_geographies,
        )
        return (
            current_languages,
            current_geographies,
            language_options,
            geography_options,
        )

    language_options: list[str] = []
    geography_options: list[str] = []

    for _ in range(4):
        language_signature = build_language_options_signature(
            lookback_days,
            current_geographies,
        )
        language_options = normalize_brief_selection(
            load_language_options(*language_signature)
        )
        current_languages = prune_selection_to_options(current_languages, language_options)

        geography_signature = build_geography_options_signature(
            lookback_days,
            current_languages,
        )
        geography_options = normalize_brief_selection(
            load_geography_options(*geography_signature)
        )
        next_geographies = prune_selection_to_options(current_geographies, geography_options)

        if next_geographies == current_geographies:
            return (
                current_languages,
                current_geographies,
                language_options,
                geography_options,
            )

        current_geographies = next_geographies

    return (
        current_languages,
        current_geographies,
        language_options,
        geography_options,
    )
