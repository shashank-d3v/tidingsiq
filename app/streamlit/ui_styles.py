from __future__ import annotations


APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@700&family=Outfit:wght@600;700&display=swap');

:root {
  --tiq-mint: #00c975;
  --tiq-mint-soft: #e7fbf0;
  --tiq-amber: #d79600;
  --tiq-charcoal: #151515;
  --tiq-offwhite: #f7f6f2;
  --tiq-border: #e6e4dd;
  --tiq-slate: #4d514a;
  --tiq-card-shadow: 0 10px 32px rgba(21, 21, 21, 0.06);
  --tiq-global-header-height: 4.2rem;
}

html, body, [class*="css"]  {
  color: var(--tiq-charcoal);
}

.stApp {
  background: var(--tiq-offwhite);
  color: var(--tiq-charcoal);
}

.stButton button {
  white-space: nowrap;
}

[data-testid="stHorizontalBlock"] {
  align-items: flex-start;
}

button[kind] {
  transition: background-color 140ms ease, border-color 140ms ease, color 140ms ease, box-shadow 140ms ease;
}

[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu,
footer {
  display: none !important;
}

[data-testid="stHeader"] {
  background: transparent !important;
  border: 0 !important;
  min-height: 0 !important;
}

[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"] {
  display: none !important;
  visibility: hidden !important;
}

[data-testid="stAppViewContainer"] > .main {
  background: var(--tiq-offwhite);
}

[data-testid="stAppViewContainer"] > .main > div {
  max-width: 100%;
}

[data-testid="stSidebar"] {
  display: none !important;
}

.stRadio > div {
  gap: 0.5rem;
}

.stRadio label {
  background: #ffffff;
  border: 1px solid transparent;
  border-radius: 14px;
  color: var(--tiq-slate);
  font-weight: 600;
  padding: 0.6rem 0.8rem;
}

.stRadio label:has(input:checked) {
  background: var(--tiq-mint-soft);
  border-color: #ccefdc;
  color: #114f33;
}

.stSelectbox label,
.stSlider label,
.stRadio label p,
.stMarkdown p,
.stMarkdown span {
  color: var(--tiq-charcoal) !important;
  font-family: "Inter", sans-serif;
}

[data-baseweb="select"] > div,
[data-baseweb="select"] input,
.stSlider [data-baseweb="slider"] * {
  color: var(--tiq-charcoal) !important;
}

[data-baseweb="select"] * {
  cursor: pointer !important;
}

[data-baseweb="select"] input {
  caret-color: transparent !important;
}

[data-baseweb="popover"] {
  z-index: 1000 !important;
}

[data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has([data-baseweb="select"]) {
  margin-top: 0.2rem;
}

[data-baseweb="select"] > div {
  background: #ffffff !important;
  border: 1px solid var(--tiq-border) !important;
  border-radius: 14px !important;
  box-shadow: none !important;
  min-height: 2.65rem !important;
}

[data-testid="stSelectbox"] {
  margin-bottom: 0.45rem;
}

[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"] {
  cursor: pointer !important;
}

[data-baseweb="select"] span,
[data-baseweb="select"] div {
  font-family: "Inter", sans-serif !important;
}

[data-baseweb="select"] input::placeholder {
  color: #8b9088 !important;
}

.tiq-global-header-anchor {
  display: block;
  min-height: 0.1rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-global-header-anchor),
div[data-testid="stElementContainer"]:has(.tiq-global-header-anchor) {
  backdrop-filter: none;
  background: rgba(247, 246, 242, 0.96) !important;
  border-bottom: 1px solid rgba(230, 228, 221, 0.9);
  overflow: visible !important;
  padding: 0 0 0.3rem;
  position: relative !important;
  top: auto !important;
  z-index: 1;
}

.tiq-logo {
  align-items: center;
  display: flex;
  gap: 0.75rem;
  padding: 0;
}

.tiq-logo-mark-wrap {
  position: relative;
}

.tiq-logo-mark {
  align-items: center;
  background: linear-gradient(135deg, #1edf72 0%, #c9e915 100%);
  border-radius: 16px;
  box-shadow: 0 10px 18px rgba(0, 201, 117, 0.14);
  display: flex;
  height: 3rem;
  justify-content: center;
  width: 3rem;
}

.tiq-logo-mark-letter {
  color: #ffffff;
  font-family: "Outfit", sans-serif;
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1;
}

.tiq-logo-sparkle {
  align-items: center;
  background: #ffffff;
  border-radius: 999px;
  color: #f1b400;
  display: inline-flex;
  font-size: 0.88rem;
  height: 1.18rem;
  justify-content: center;
  position: absolute;
  right: -0.2rem;
  top: -0.2rem;
  width: 1.18rem;
}

.tiq-logo-copy {
  display: flex;
  flex-direction: column;
  gap: 0.14rem;
}

.tiq-logo-wordmark {
  color: var(--tiq-charcoal);
  font-family: "Outfit", sans-serif;
  font-size: 1.6rem;
  font-weight: 700;
  letter-spacing: -0.045em;
  line-height: 0.98;
}

.tiq-logo-wordmark span {
  color: var(--tiq-mint) !important;
}

.tiq-logo-tagline {
  color: #9aa094;
  font-family: "Inter", sans-serif;
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.tiq-global-nav-anchor {
  display: block;
  min-height: 0.1rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-global-nav-anchor) {
  align-self: center;
  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  padding: 0;
  justify-self: start;
}

div[data-testid="stVerticalBlock"]:has(.tiq-global-nav-anchor) [data-testid="stSegmentedControl"] {
  margin: 0;
}

div[data-testid="stVerticalBlock"]:has(.tiq-global-nav-anchor) [data-baseweb="segmented-control"] {
  background: #f5f6fa;
  border: 1px solid #eaedf3;
  border-radius: 999px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9), 0 1px 2px rgba(21, 21, 21, 0.04);
  display: flex;
  gap: 0.46rem;
  padding: 0.51rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-global-nav-anchor) [data-baseweb="segmented-control"] button {
  background: transparent !important;
  border: 0 !important;
  border-radius: 999px !important;
  box-shadow: none !important;
  color: #a0a8b8 !important;
  font-family: "Inter", sans-serif !important;
  font-size: 1.38rem !important;
  font-weight: 700 !important;
  height: 4rem !important;
  padding: 0 1.62rem !important;
  transition: background-color 140ms ease, color 140ms ease, box-shadow 140ms ease !important;
}

div[data-testid="stVerticalBlock"]:has(.tiq-global-nav-anchor) [data-baseweb="segmented-control"] button[aria-pressed="true"] {
  background: #ffffff !important;
  border: 1px solid #e8ebf2 !important;
  box-shadow: 0 3px 12px rgba(21, 21, 21, 0.08) !important;
  color: var(--tiq-charcoal) !important;
}

div[data-testid="stVerticalBlock"]:has(.tiq-global-nav-anchor) [data-baseweb="segmented-control"] button[aria-pressed="false"] {
  background: transparent !important;
  color: #9ca5b5 !important;
}

div[data-testid="stVerticalBlock"]:has(.tiq-global-nav-anchor) [data-baseweb="segmented-control"] button[aria-pressed="false"]:hover {
  background: rgba(255, 255, 255, 0.42) !important;
  color: #7f899a !important;
}

.tiq-global-status-anchor {
  display: block;
  min-height: 0.1rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-global-status-anchor) {
  align-items: flex-end;
  justify-content: flex-end;
  padding-top: 0.08rem;
}

.tiq-page-title {
  color: var(--tiq-charcoal);
  font-family: "Playfair Display", serif;
  font-size: 2.72rem;
  font-weight: 700;
  letter-spacing: -0.045em;
  line-height: 1.02;
  margin: 0;
  max-width: none;
  white-space: nowrap;
}

div[data-testid="stVerticalBlock"]:has(.tiq-masthead-anchor),
div[data-testid="stElementContainer"]:has(.tiq-masthead-anchor) {
  background: rgba(247, 246, 242, 0.97) !important;
  overflow: visible !important;
  padding-top: 0.7rem;
  padding-bottom: 1.45rem;
  position: relative !important;
  top: auto !important;
  z-index: 1;
}

.tiq-masthead-anchor {
  display: block;
  min-height: 0.15rem;
}

.tiq-masthead-title {
  margin: 0;
  text-align: left;
}

.tiq-status-chip {
  align-items: center;
  background: rgba(231, 251, 240, 0.82);
  border: 1px solid rgba(0, 201, 117, 0.18);
  border-radius: 999px;
  display: inline-flex;
  gap: 0.45rem;
  margin-top: 0.1rem;
  padding: 0.56rem 0.88rem;
  white-space: nowrap;
}

.tiq-status-chip {
  color: #0f6b45;
  font-family: "Inter", sans-serif;
  font-size: 0.74rem;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.08em;
}

.tiq-section-header {
  align-items: baseline;
  border-bottom: 1px solid var(--tiq-border);
  display: flex;
  justify-content: space-between;
  margin: 0 0 1rem;
  padding-bottom: 0.9rem;
}

.tiq-section-title {
  color: var(--tiq-charcoal);
  font-family: "Playfair Display", serif;
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.035em;
  margin: 0;
}

.tiq-section-subtitle {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 0.96rem;
  line-height: 1.5;
  margin-top: 0.28rem;
}

.tiq-pill {
  background: var(--tiq-mint-soft);
  border-radius: 999px;
  color: #0f5a39;
  display: inline-block;
  font-family: "Inter", sans-serif;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-left: 0.7rem;
  padding: 0.22rem 0.55rem;
  text-transform: uppercase;
  vertical-align: middle;
}

.tiq-brief-header-copy {
  margin-bottom: 0.25rem;
}

.tiq-sort-control-anchor {
  display: block;
  min-height: 0.35rem;
}

.tiq-sort-inline-label {
  color: #676b63;
  font-family: "Inter", sans-serif;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  line-height: 2.65rem;
  text-transform: uppercase;
  white-space: nowrap;
}

div[data-testid="stVerticalBlock"]:has(.tiq-sort-control-anchor) {
  padding-top: 0.15rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-sort-control-anchor) [data-testid="stSelectbox"] {
  margin-bottom: 0;
}

div[data-testid="stVerticalBlock"]:has(.tiq-sort-control-anchor) [data-baseweb="select"] > div {
  background: rgba(255, 255, 255, 0.92) !important;
  border-color: #ddd8ca !important;
  border-radius: 999px !important;
  min-height: 2.7rem !important;
}

.tiq-section-divider {
  border-bottom: 1px solid var(--tiq-border);
  margin: 0 0 1rem;
}

.tiq-card {
  background: #ffffff;
  border: 1px solid var(--tiq-border);
  border-radius: 22px;
  box-shadow: 0 8px 22px rgba(21, 21, 21, 0.04);
  margin-bottom: 1rem;
  padding: 1.3rem 1.45rem;
}

.tiq-card-compact {
  min-height: 195px;
}

.tiq-card-headline {
  color: var(--tiq-charcoal);
  display: block;
  font-family: "Playfair Display", serif;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.24;
  margin: 0.75rem 0 0.9rem;
  text-decoration: none;
}

.tiq-card-headline:hover {
  color: #0f5a39;
}

.tiq-card-meta-row,
.tiq-card-footer {
  color: var(--tiq-slate);
  display: flex;
  flex-wrap: wrap;
  font-family: "Inter", sans-serif;
  font-size: 0.86rem;
  gap: 0.75rem;
}

.tiq-card-footer {
  border-top: 1px solid #ece9e1;
  justify-content: space-between;
  margin-top: 1.1rem;
  padding-top: 1rem;
}

.tiq-source-line {
  align-items: center;
  color: #61665f;
  display: flex;
  flex-wrap: wrap;
  font-family: "Inter", sans-serif;
  font-size: 0.78rem;
  font-weight: 700;
  gap: 0.5rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.tiq-score-badge {
  border-radius: 999px;
  display: inline-block;
  font-family: "Inter", sans-serif;
  font-size: 0.76rem;
  font-weight: 700;
  padding: 0.35rem 0.7rem;
}

.tiq-score-strong {
  background: #e7fbf0;
  border: 1px solid #c5edd9;
  color: #0f5a39;
}

.tiq-score-mid {
  background: #effbf5;
  border: 1px solid #d6f4e5;
  color: #156745;
}

.tiq-score-soft {
  background: #fff6df;
  border: 1px solid #f7df9d;
  color: #815800;
}

.tiq-mini-chip {
  background: #f2f1eb;
  border-radius: 999px;
  color: #42463f;
  display: inline-block;
  font-family: "Inter", sans-serif;
  font-size: 0.76rem;
  font-weight: 600;
  padding: 0.27rem 0.58rem;
}

.tiq-metric-card {
  border: 1px solid var(--tiq-border);
  border-radius: 24px;
  box-shadow: 0 10px 26px rgba(21, 21, 21, 0.05);
  overflow: hidden;
  padding: 1.05rem 1.1rem 1.15rem;
  position: relative;
}

.tiq-metric-card-top {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.7rem;
}

.tiq-metric-label {
  color: #676b63;
  font-family: "Inter", sans-serif;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-bottom: 0.5rem;
  text-transform: uppercase;
}

.tiq-metric-value {
  color: var(--tiq-charcoal);
  font-family: "Outfit", sans-serif;
  font-size: 2.2rem;
  font-weight: 700;
  line-height: 1.05;
}

.tiq-metric-icon {
  align-items: center;
  background: linear-gradient(135deg, rgba(0, 201, 117, 0.14), rgba(255, 213, 0, 0.14));
  border: 1px solid rgba(220, 216, 202, 0.95);
  border-radius: 16px;
  color: #0f5a39;
  display: inline-flex;
  flex: 0 0 auto;
  height: 2.8rem;
  justify-content: center;
  width: 2.8rem;
}

.tiq-metric-icon svg {
  fill: none;
  height: 1.35rem;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.85;
  width: 1.35rem;
}

.tiq-metric-card-mint {
  background: linear-gradient(180deg, #e8f8f1 0%, #f3fbf7 100%);
}

.tiq-metric-card-sun {
  background: linear-gradient(180deg, #fff5d6 0%, #fffaf0 100%);
}

.tiq-metric-card-sky {
  background: linear-gradient(180deg, #e7f0fd 0%, #f4f8ff 100%);
}

.tiq-metric-card-ink {
  background: linear-gradient(180deg, #f1f2f4 0%, #fafafa 100%);
}

.tiq-metric-card-sun .tiq-metric-icon {
  background: linear-gradient(135deg, rgba(255, 213, 0, 0.18), rgba(255, 176, 64, 0.12));
  color: #8b5e00;
}

.tiq-metric-card-sky .tiq-metric-icon {
  background: linear-gradient(135deg, rgba(122, 182, 255, 0.2), rgba(215, 237, 255, 0.18));
  color: #2459a6;
}

.tiq-metric-card-ink .tiq-metric-icon {
  background: linear-gradient(135deg, rgba(21, 21, 21, 0.09), rgba(124, 134, 151, 0.1));
  color: #2d3442;
}

.tiq-status-dot {
  animation: tiq-status-pulse 1.6s ease-in-out infinite;
  background: var(--tiq-mint);
  border-radius: 999px;
  box-shadow: 0 0 0 0 rgba(0, 201, 117, 0.3);
  display: inline-block;
  height: 0.55rem;
  width: 0.55rem;
}

.tiq-empty-state {
  background: #ffffff;
  border: 1px dashed #cfcec5;
  border-radius: 22px;
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  padding: 1.4rem 1.2rem;
  text-align: center;
}

.tiq-empty-state-soft {
  background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,246,242,0.96));
  border-style: solid;
  color: #5a5f57;
  line-height: 1.45;
  padding: 1.05rem 1.15rem;
}

.tiq-pagination-anchor {
  display: block;
  min-height: 0.2rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-pagination-anchor) .stButton button {
  align-items: center !important;
  background: #ffffff !important;
  border: 1px solid #ddd8ca !important;
  border-radius: 999px !important;
  color: var(--tiq-charcoal) !important;
  display: inline-flex !important;
  font-family: "Inter", sans-serif !important;
  font-size: 0.9rem !important;
  font-weight: 600 !important;
  height: 2.5rem !important;
  justify-content: center !important;
  min-width: 6.6rem !important;
  padding: 0 1rem !important;
  text-transform: none !important;
  transform: none !important;
  writing-mode: horizontal-tb !important;
}

.tiq-loading-state {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  justify-content: center;
  margin: 12vh auto 0;
  max-width: 32rem;
  min-height: 40vh;
  text-align: center;
}

.tiq-loading-graphic {
  align-items: flex-end;
  display: flex;
  gap: 0.34rem;
  height: 3.4rem;
  justify-content: center;
  position: relative;
  width: 8rem;
}

.tiq-loading-bar {
  animation: tiq-loading-rise 1.35s ease-in-out infinite;
  background: linear-gradient(180deg, rgba(0, 201, 117, 0.9), rgba(0, 201, 117, 0.2));
  border-radius: 999px;
  display: block;
  width: 0.52rem;
}

.tiq-loading-bar-1 {
  animation-delay: 0s;
  height: 1.1rem;
}

.tiq-loading-bar-2 {
  animation-delay: 0.12s;
  height: 1.8rem;
}

.tiq-loading-bar-3 {
  animation-delay: 0.24s;
  height: 2.45rem;
}

.tiq-loading-bar-4 {
  animation-delay: 0.36s;
  height: 1.55rem;
}

.tiq-loading-line {
  animation: tiq-loading-glide 1.5s ease-in-out infinite;
  border-bottom: 2px solid rgba(215, 150, 0, 0.7);
  border-right: 2px solid rgba(215, 150, 0, 0.7);
  height: 1.85rem;
  left: 1.65rem;
  position: absolute;
  top: 0.35rem;
  transform: skewX(-28deg);
  width: 4.8rem;
}

.tiq-loading-copy {
  color: #61665f;
  font-family: "Inter", sans-serif;
  font-size: 0.98rem;
  font-weight: 600;
  line-height: 1.55;
}

@keyframes tiq-loading-rise {
  0%, 100% {
    opacity: 0.45;
    transform: scaleY(0.72);
  }

  50% {
    opacity: 1;
    transform: scaleY(1);
  }
}

@keyframes tiq-loading-glide {
  0%, 100% {
    opacity: 0.45;
    transform: skewX(-28deg) translateY(0);
  }

  50% {
    opacity: 1;
    transform: skewX(-28deg) translateY(-0.18rem);
  }
}

@keyframes tiq-status-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(0, 201, 117, 0.32);
    opacity: 0.9;
  }

  50% {
    box-shadow: 0 0 0 0.38rem rgba(0, 201, 117, 0);
    opacity: 1;
  }
}

.tiq-method-card {
  background: #ffffff;
  border: 1px solid var(--tiq-border);
  border-radius: 30px;
  box-shadow: var(--tiq-card-shadow);
  margin-bottom: 1rem;
  padding: 1.55rem;
}

.tiq-method-title {
  color: var(--tiq-charcoal);
  font-family: "Playfair Display", serif;
  font-size: 1.48rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 0.75rem;
}

.tiq-method-body {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 1rem;
  line-height: 1.78;
}

.tiq-method-body strong {
  color: var(--tiq-charcoal);
}

.tiq-small-note {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 0.84rem;
  line-height: 1.5;
  margin-top: 0.3rem;
}

.tiq-pulse-stat-card {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(230, 228, 221, 0.98);
  border-radius: 18px;
  box-shadow: 0 6px 18px rgba(21, 21, 21, 0.04);
  margin: 0.3rem 0 1.2rem;
  min-height: 5.8rem;
  padding: 0.82rem 0.95rem 0.88rem;
}

.tiq-pulse-stat-label {
  color: #676b63;
  font-family: "Inter", sans-serif;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-bottom: 0.3rem;
  text-transform: uppercase;
}

.tiq-pulse-stat-value {
  color: var(--tiq-charcoal);
  font-family: "Outfit", sans-serif;
  font-size: 1.2rem;
  font-weight: 700;
  line-height: 1.2;
}

.block-container {
  padding-top: 0 !important;
  padding-bottom: 3rem;
  max-width: 100% !important;
  padding-left: 2rem;
  padding-right: 2rem;
}

@media (max-width: 1080px) {
  .tiq-logo-wordmark {
    font-size: 1.42rem;
  }

  .tiq-logo-tagline {
    font-size: 0.6rem;
    letter-spacing: 0.14em;
  }

  div[data-testid="stVerticalBlock"]:has(.tiq-global-nav-anchor) [data-baseweb="segmented-control"] button {
    font-size: 0.88rem !important;
    height: 2.55rem !important;
    padding: 0 0.86rem !important;
  }

  .tiq-page-title {
    font-size: 2.35rem;
    white-space: normal;
  }

  .tiq-status-chip {
    align-items: center;
    font-size: 0.7rem;
    justify-content: center;
    padding: 0.48rem 0.74rem;
  }

  .tiq-pulse-stats {
    grid-template-columns: 1fr;
  }

  .block-container {
    padding-top: 0 !important;
    padding-left: 1rem;
    padding-right: 1rem;
  }
}
</style>
"""
