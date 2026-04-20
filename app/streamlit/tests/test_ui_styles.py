from __future__ import annotations

import unittest

from app.streamlit.ui_styles import APP_CSS


class UiStylesTest(unittest.TestCase):
    def test_app_css_forces_light_color_scheme(self) -> None:
        self.assertIn("color-scheme: light", APP_CSS)
        self.assertIn("[data-baseweb=\"portal\"]", APP_CSS)
        self.assertIn("[role=\"presentation\"]", APP_CSS)
        self.assertIn("#root", APP_CSS)
        self.assertIn("background: var(--tiq-offwhite) !important;", APP_CSS)

    def test_feed_sort_control_does_not_use_charcoal_shell(self) -> None:
        self.assertIn("--tiq-control-shell", APP_CSS)
        self.assertNotIn(
            'div[data-testid="stVerticalBlock"]:has(.tiq-feed-sort-control-anchor) [data-baseweb="segmented-control"] {\n  background: var(--tiq-charcoal);',
            APP_CSS,
        )

    def test_active_segmented_controls_use_mint_palette(self) -> None:
        self.assertNotIn("#ff5f55", APP_CSS)
        self.assertIn("background: var(--tiq-mint-soft) !important;", APP_CSS)
        self.assertIn("color: #0f5a39 !important;", APP_CSS)

    def test_popover_secondary_actions_do_not_depend_on_specific_kind_value(self) -> None:
        self.assertIn(
            'div[data-testid="stVerticalBlock"]:has(.tiq-filter-popover-footer-anchor) .stButton button:not([kind="primary"])',
            APP_CSS,
        )
        self.assertIn(
            'div[role="dialog"] .stButton button:not([kind="primary"])',
            APP_CSS,
        )

    def test_keyed_choice_buttons_override_streamlit_min_width(self) -> None:
        self.assertIn('[class*="st-key-lookback_days_choice_"] [data-testid^="stBaseButton"]', APP_CSS)
        self.assertIn("min-inline-size: 0 !important;", APP_CSS)


if __name__ == "__main__":
    unittest.main()
