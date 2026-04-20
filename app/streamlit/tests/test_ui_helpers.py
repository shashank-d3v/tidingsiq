from __future__ import annotations

import inspect
import sys
import types
import unittest
from unittest.mock import patch


class _DummyContainer:
    def __enter__(self) -> "_DummyContainer":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = types.SimpleNamespace(
        button=lambda *args, **kwargs: False,
        columns=lambda *args, **kwargs: [],
        container=lambda *args, **kwargs: _DummyContainer(),
        form=lambda *args, **kwargs: _DummyContainer(),
        form_submit_button=lambda *args, **kwargs: False,
        markdown=lambda *args, **kwargs: None,
        multiselect=lambda *args, **kwargs: [],
        popover=lambda *args, **kwargs: _DummyContainer(),
        rerun=lambda: None,
        session_state={},
        vega_lite_chart=lambda *args, **kwargs: None,
    )

from app.streamlit import ui_helpers

if not hasattr(ui_helpers.st, "rerun"):
    ui_helpers.st.rerun = lambda: None


class UiHelpersTest(unittest.TestCase):
    def test_ui_helpers_no_longer_use_segmented_control(self) -> None:
        source = inspect.getsource(ui_helpers)
        self.assertNotIn("segmented_control(", source)

    def test_render_choice_button_group_updates_state_and_reruns(self) -> None:
        session_state = {"lookback_days": 7}

        with patch.object(ui_helpers.st, "session_state", session_state), patch.object(
            ui_helpers.st,
            "markdown",
        ), patch.object(
            ui_helpers.st,
            "columns",
            return_value=[_DummyContainer(), _DummyContainer()],
        ), patch.object(
            ui_helpers.st,
            "button",
            side_effect=[False, True],
        ), patch.object(ui_helpers.st, "rerun") as rerun:
            ui_helpers.render_choice_button_group(
                anchor_class="tiq-lookback-control-anchor",
                state_key="lookback_days",
                options=[3, 7],
                current_value=3,
                format_func=str,
            )

        self.assertEqual(session_state["lookback_days"], 7)
        rerun.assert_called_once()


if __name__ == "__main__":
    unittest.main()
