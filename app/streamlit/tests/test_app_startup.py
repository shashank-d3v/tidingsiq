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


def _build_stub_modules(*, runtime_error_message: str) -> dict[str, object]:
    streamlit_stub = types.SimpleNamespace(
        error=Mock(),
        markdown=Mock(),
        session_state={},
        set_page_config=Mock(),
        stop=Mock(side_effect=_StreamlitStop("streamlit stop")),
    )

    return {
        "streamlit": streamlit_stub,
        "constants": types.SimpleNamespace(
            LOOKBACK_OPTIONS=[1, 3, 7, 30],
            PAGE_BRIEF="The Brief",
            PAGE_METHODOLOGY="Methodology",
            PAGE_PULSE="Pulse",
            RECOMMENDED_PAGE_SIZE=10,
            resolve_runtime_config=Mock(
                side_effect=RuntimeError(runtime_error_message)
            ),
        ),
        "brief_state": types.SimpleNamespace(
            build_geography_options_signature=Mock(),
            build_language_options_signature=Mock(),
            build_rows_signature=Mock(),
            build_scope_signature=Mock(),
            clamp_page_number=Mock(),
            compute_total_pages=Mock(),
            reset_page_on_scope_change=Mock(),
            resolve_brief_filter_state=Mock(),
        ),
        "data_access": types.SimpleNamespace(
            load_brief_geography_options=Mock(),
            load_brief_language_options=Mock(),
            load_brief_rows=Mock(),
            load_brief_scope_summary=Mock(),
            load_pipeline_status=Mock(),
            load_pulse_dashboard=Mock(),
        ),
        "query_builder": types.SimpleNamespace(
            BriefGeographyOptionsQueryConfig=object,
            BriefLanguageOptionsQueryConfig=object,
            BriefRowsQueryConfig=object,
            BriefScopeQueryConfig=object,
        ),
        "ui_helpers": types.SimpleNamespace(
            render_global_header=Mock(),
            render_loading_state=Mock(),
            render_pipeline_status=Mock(),
        ),
        "ui_pages": types.SimpleNamespace(
            render_brief=Mock(),
            render_methodology=Mock(),
            render_pulse=Mock(),
        ),
        "ui_styles": types.SimpleNamespace(APP_CSS=""),
    }


def _load_app_module(*, runtime_error_message: str):
    module_name = "test_streamlit_app_startup"
    stub_modules = _build_stub_modules(runtime_error_message=runtime_error_message)
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


class StreamlitStartupTest(unittest.TestCase):
    def test_main_surfaces_missing_project_env_before_any_ui_query_work(self) -> None:
        message = "TIDINGSIQ_GCP_PROJECT must be set before starting the Streamlit app."
        app_module, stub_modules = _load_app_module(runtime_error_message=message)

        with self.assertRaisesRegex(_StreamlitStop, "streamlit stop"):
            app_module.main()

        streamlit_stub = stub_modules["streamlit"]
        constants_stub = stub_modules["constants"]
        ui_helpers_stub = stub_modules["ui_helpers"]

        constants_stub.resolve_runtime_config.assert_called_once_with()
        streamlit_stub.error.assert_called_once_with(message)
        streamlit_stub.stop.assert_called_once_with()
        streamlit_stub.markdown.assert_not_called()
        ui_helpers_stub.render_global_header.assert_not_called()


if __name__ == "__main__":
    unittest.main()
