from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"


class _StreamlitStop(RuntimeError):
    pass


class _QueryConfig:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class _DummyPlaceholder:
    def __init__(self) -> None:
        self.empty = Mock()


def _build_stub_modules(
    *,
    session_state: dict[str, object] | None = None,
    runtime_error_message: str | None = None,
    event_log: list[str] | None = None,
) -> dict[str, object]:
    if session_state is None:
        session_state = {}
    if event_log is None:
        event_log = []

    placeholder = _DummyPlaceholder()
    streamlit_stub = types.SimpleNamespace(
        empty=Mock(return_value=placeholder),
        error=Mock(),
        markdown=Mock(),
        session_state=session_state,
        set_page_config=Mock(),
        stop=Mock(side_effect=_StreamlitStop("streamlit stop")),
    )

    constants_stub = types.SimpleNamespace(
        LOOKBACK_OPTIONS=[1, 3, 7, 30],
        PAGE_BRIEF="The Brief",
        PAGE_METHODOLOGY="Methodology",
        PAGE_PULSE="Pulse",
        RECOMMENDED_PAGE_SIZE=10,
        resolve_runtime_config=Mock(),
    )
    if runtime_error_message is not None:
        constants_stub.resolve_runtime_config.side_effect = RuntimeError(
            runtime_error_message
        )
    else:
        constants_stub.resolve_runtime_config.return_value = (
            "demo-project",
            "demo-project.gold.positive_news_feed",
        )

    def _build_scope_signature(
        lookback_days: int,
        selected_languages: list[str] | tuple[str, ...],
        selected_geographies: list[str] | tuple[str, ...],
    ) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
        return (
            int(lookback_days),
            tuple(sorted(str(value) for value in selected_languages)),
            tuple(sorted(str(value) for value in selected_geographies)),
        )

    def _build_rows_signature(
        scope_signature: tuple[int, tuple[str, ...], tuple[str, ...]],
        sort_order: str,
        page_number: int,
        page_size: int,
    ) -> tuple[tuple[int, tuple[str, ...], tuple[str, ...]], str, int, int]:
        return (scope_signature, str(sort_order), int(page_number), int(page_size))

    brief_state_stub = types.SimpleNamespace(
        build_geography_options_signature=Mock(
            side_effect=lambda lookback_days, selected_languages: (
                int(lookback_days),
                tuple(sorted(str(value) for value in selected_languages)),
            )
        ),
        build_language_options_signature=Mock(
            side_effect=lambda lookback_days, selected_geographies: (
                int(lookback_days),
                tuple(sorted(str(value) for value in selected_geographies)),
            )
        ),
        build_rows_signature=Mock(side_effect=_build_rows_signature),
        build_scope_signature=Mock(side_effect=_build_scope_signature),
        clamp_page_number=Mock(side_effect=lambda page_number, *_args: int(page_number)),
        compute_total_pages=Mock(side_effect=lambda total_rows, page_size: 1),
        reset_page_on_scope_change=Mock(
            side_effect=lambda previous_scope_signature, scope_signature, current_page: (
                1 if previous_scope_signature != scope_signature else int(current_page)
            )
        ),
        resolve_brief_filter_state=Mock(
            side_effect=lambda **kwargs: (
                list(kwargs["selected_languages"]),
                list(kwargs["selected_geographies"]),
                ["EN", "FR"],
                ["India", "United States"],
            )
        ),
    )

    data_access_stub = types.SimpleNamespace(
        load_brief_geography_options=Mock(return_value=["India", "United States"]),
        load_brief_language_options=Mock(return_value=["EN", "FR"]),
        load_brief_rows=Mock(
            side_effect=lambda *args, **kwargs: (
                event_log.append("brief_rows"),
                ([{"article_id": "story-1", "title": "Story"}], "sql"),
            )[1]
        ),
        load_brief_scope_summary=Mock(
            side_effect=lambda *args, **kwargs: (
                event_log.append("brief_summary"),
                {
                    "row_count": 1,
                    "avg_happy_factor": 74.2,
                    "max_happy_factor": 81.0,
                    "source_count": 1,
                },
            )[1]
        ),
        load_pipeline_status=Mock(
            side_effect=lambda *args, **kwargs: (
                event_log.append("pipeline_status"),
                {"audit_run_at": "2026-04-17T09:00:00+00:00"},
            )[1]
        ),
        load_pulse_dashboard=Mock(
            side_effect=lambda *args, **kwargs: (
                event_log.append("pulse_dashboard"),
                {"latest_snapshot": {"audit_run_at": "2026-04-17T09:00:00+00:00"}},
            )[1]
        ),
    )

    ui_helpers_stub = types.SimpleNamespace(
        render_global_header=Mock(),
        render_loading_state=Mock(
            side_effect=lambda message, **kwargs: event_log.append(
                f"loader:{message}:{kwargs.get('variant', 'inline')}"
            )
        ),
        render_pipeline_status=Mock(return_value="<status>"),
    )

    return {
        "streamlit": streamlit_stub,
        "constants": constants_stub,
        "brief_state": brief_state_stub,
        "data_access": data_access_stub,
        "query_builder": types.SimpleNamespace(
            BriefGeographyOptionsQueryConfig=_QueryConfig,
            BriefLanguageOptionsQueryConfig=_QueryConfig,
            BriefRowsQueryConfig=_QueryConfig,
            BriefScopeQueryConfig=_QueryConfig,
        ),
        "ui_helpers": ui_helpers_stub,
        "ui_pages": types.SimpleNamespace(
            render_brief=Mock(),
            render_methodology=Mock(),
            render_pulse=Mock(),
        ),
        "ui_styles": types.SimpleNamespace(APP_CSS=""),
    }


def _load_app_module(
    *,
    session_state: dict[str, object] | None = None,
    runtime_error_message: str | None = None,
    event_log: list[str] | None = None,
):
    module_name = "test_streamlit_app_loading"
    stub_modules = _build_stub_modules(
        session_state=session_state,
        runtime_error_message=runtime_error_message,
        event_log=event_log,
    )
    previous_modules = {
        name: sys.modules.get(name) for name in (*stub_modules.keys(), module_name)
    }
    try:
        sys.modules.update(stub_modules)
        spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module, stub_modules
    finally:
        for name, original_module in previous_modules.items():
            if original_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original_module


class StreamlitLoadingTest(unittest.TestCase):
    def test_section_switch_to_pulse_shows_page_loader_before_dashboard_fetch(self) -> None:
        events: list[str] = []
        session_state = {
            "current_page": "Pulse",
            "last_loaded_page": "The Brief",
        }

        app_module, stub_modules = _load_app_module(
            session_state=session_state,
            event_log=events,
        )
        app_module.main()

        self.assertEqual(
            events[:2],
            [
                "loader:Loading the latest pipeline pulse from the warehouse.:page",
                "pulse_dashboard",
            ],
        )
        stub_modules["ui_pages"].render_pulse.assert_called_once()

    def test_brief_scope_change_shows_loader_before_scope_queries_and_updates_markers(self) -> None:
        events: list[str] = []
        session_state = {
            "current_page": "The Brief",
            "last_loaded_page": "The Brief",
            "lookback_days": 7,
            "feed_sort_order": "Most optimistic first",
            "recommended_page": 1,
            "selected_languages": ["EN"],
            "selected_geographies": ["India"],
            "last_loaded_brief_scope_signature": (7, ("FR",), ("India",)),
            "last_loaded_brief_rows_signature": (
                (7, ("FR",), ("India",)),
                "Most optimistic first",
                1,
                10,
            ),
        }

        app_module, _stub_modules = _load_app_module(
            session_state=session_state,
            event_log=events,
        )
        app_module.main()

        self.assertEqual(
            events[:3],
            [
                "loader:Refreshing the brief and calibrating the latest trend line.:page",
                "brief_summary",
                "brief_rows",
            ],
        )
        self.assertEqual(
            session_state["last_loaded_brief_scope_signature"],
            (7, ("EN",), ("India",)),
        )
        self.assertEqual(
            session_state["last_loaded_brief_rows_signature"],
            ((7, ("EN",), ("India",)), "Most optimistic first", 1, 10),
        )
        self.assertEqual(session_state["last_loaded_page"], "The Brief")

    def test_brief_pagination_change_uses_same_loader_path(self) -> None:
        events: list[str] = []
        scope_signature = (7, ("EN",), ("India",))
        session_state = {
            "current_page": "The Brief",
            "last_loaded_page": "The Brief",
            "lookback_days": 7,
            "feed_sort_order": "Most optimistic first",
            "recommended_page": 2,
            "selected_languages": ["EN"],
            "selected_geographies": ["India"],
            "last_loaded_brief_scope_signature": scope_signature,
            "last_loaded_brief_rows_signature": (
                scope_signature,
                "Most optimistic first",
                1,
                10,
            ),
        }

        app_module, _stub_modules = _load_app_module(
            session_state=session_state,
            event_log=events,
        )
        app_module.main()

        self.assertEqual(
            events[:3],
            [
                "loader:Refreshing the brief and calibrating the latest trend line.:page",
                "brief_summary",
                "brief_rows",
            ],
        )


if __name__ == "__main__":
    unittest.main()
