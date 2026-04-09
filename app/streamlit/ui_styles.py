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
}

html, body, [class*="css"]  {
  color: var(--tiq-charcoal);
}

.stApp {
  background: var(--tiq-offwhite);
  color: var(--tiq-charcoal);
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
  padding: 0.75rem 0.9rem;
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

.tiq-logo {
  align-items: center;
  display: flex;
  margin-bottom: 1rem;
  transition: all 180ms ease;
}

.tiq-logo-expanded {
  gap: 0.95rem;
}

.tiq-logo-collapsed {
  gap: 0;
  justify-content: center;
  margin-bottom: 0;
}

.tiq-logo-mark-wrap {
  position: relative;
}

.tiq-logo-mark {
  align-items: center;
  background: linear-gradient(135deg, #18ef8d 0%, #9be71f 48%, #ffd500 100%);
  border-radius: 1.2rem;
  box-shadow: 0 14px 26px rgba(0, 201, 117, 0.2);
  color: #ffffff;
  display: flex;
  font-family: "Outfit", sans-serif;
  font-size: 1.85rem;
  font-weight: 800;
  height: 5rem;
  justify-content: center;
  letter-spacing: -0.06em;
  width: 5rem;
}

.tiq-logo-collapsed .tiq-logo-mark {
  border-radius: 1rem;
  font-size: 1.55rem;
  height: 3.25rem;
  width: 3.25rem;
}

.tiq-logo-sparkle {
  align-items: center;
  background: #ffffff;
  border-radius: 999px;
  box-shadow: 0 8px 18px rgba(21, 21, 21, 0.08);
  color: var(--tiq-amber);
  display: flex;
  font-size: 0.9rem;
  font-weight: 900;
  height: 1.4rem;
  justify-content: center;
  position: absolute;
  right: -0.28rem;
  top: -0.28rem;
  width: 1.4rem;
}

.tiq-logo-collapsed .tiq-logo-sparkle {
  font-size: 0.72rem;
  height: 1.15rem;
  right: -0.18rem;
  top: -0.18rem;
  width: 1.15rem;
}

.tiq-logo-copy {
  display: flex;
  flex-direction: column;
  gap: 0.22rem;
  line-height: 1;
  transform-origin: left center;
  transition: all 180ms ease;
}

.tiq-logo-wordmark {
  color: var(--tiq-charcoal);
  font-family: "Outfit", sans-serif;
  font-size: 2.25rem;
  font-weight: 800;
  letter-spacing: -0.06em;
  white-space: nowrap;
}

.tiq-logo-wordmark span {
  color: var(--tiq-mint);
}

.tiq-logo-tagline {
  color: #9aa1af;
  font-family: "Inter", sans-serif;
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 0.34em;
  margin-left: 0.12rem;
  text-transform: uppercase;
  white-space: nowrap;
}

.tiq-logo-collapsed .tiq-logo-copy {
  opacity: 0;
  pointer-events: none;
  transform: scale(0.92);
  width: 0;
}

div[data-testid="stVerticalBlock"]:has(.tiq-main-expand-anchor) button {
  align-items: center;
  background: #ffffff;
  border: 1px solid var(--tiq-border);
  border-radius: 999px;
  box-shadow: var(--tiq-card-shadow);
  color: var(--tiq-charcoal);
  display: inline-flex;
  font-family: "Inter", sans-serif;
  font-size: 0.9rem;
  font-weight: 700;
  gap: 0.35rem;
  padding: 0.2rem 0.85rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-logo-expanded) button {
  align-items: center;
  background: #ffffff;
  border: 1px solid var(--tiq-border);
  border-radius: 999px;
  box-shadow: none;
  color: var(--tiq-charcoal);
  display: inline-flex;
  font-family: "Inter", sans-serif;
  font-size: 0.9rem;
  font-weight: 700;
  gap: 0.35rem;
  margin-bottom: 0.85rem;
  padding: 0.2rem 0.85rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-main-expand-anchor) {
  margin-top: 0.7rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-logo-collapsed) {
  margin-top: 0.3rem;
}

div[data-testid="stVerticalBlock"]:has(.tiq-logo-expanded) {
  margin-bottom: 0.25rem;
}

.tiq-page-title {
  color: var(--tiq-charcoal);
  font-family: "Playfair Display", serif;
  font-size: 3.35rem;
  font-weight: 700;
  letter-spacing: -0.045em;
  line-height: 1.02;
  margin: 0 0 1.4rem;
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
  font-size: 1.9rem;
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

.tiq-card {
  background: #ffffff;
  border: 1px solid var(--tiq-border);
  border-radius: 28px;
  box-shadow: var(--tiq-card-shadow);
  margin-bottom: 1rem;
  padding: 1.45rem 1.55rem;
}

.tiq-card-compact {
  min-height: 195px;
}

.tiq-card-headline {
  color: var(--tiq-charcoal);
  display: block;
  font-family: "Playfair Display", serif;
  font-size: 1.42rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.26;
  margin: 0.9rem 0 1rem;
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
  background: #ffffff;
  border: 1px solid var(--tiq-border);
  border-radius: 26px;
  box-shadow: var(--tiq-card-shadow);
  padding: 1.15rem 1.2rem;
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
  font-size: 2.1rem;
  font-weight: 700;
}

.tiq-status-card {
  background: #f5faf7;
  border: 1px solid var(--tiq-border);
  border-radius: 22px;
  margin-top: 1rem;
  padding: 1rem 1rem 0.95rem;
}

.tiq-status-label {
  color: #676b63;
  font-family: "Inter", sans-serif;
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-bottom: 0.45rem;
  text-transform: uppercase;
}

.tiq-status-line {
  align-items: center;
  color: #0f5a39;
  display: flex;
  font-family: "Inter", sans-serif;
  font-size: 0.9rem;
  font-weight: 600;
  gap: 0.45rem;
}

.tiq-status-dot {
  background: var(--tiq-mint);
  border-radius: 999px;
  display: inline-block;
  height: 0.55rem;
  width: 0.55rem;
}

.tiq-status-detail {
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  font-size: 0.84rem;
  margin-top: 0.45rem;
}

.tiq-empty-state {
  background: #ffffff;
  border: 1px dashed #cfcec5;
  border-radius: 28px;
  color: var(--tiq-slate);
  font-family: "Inter", sans-serif;
  padding: 2.5rem 1.4rem;
  text-align: center;
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

.block-container {
  padding-top: 1.4rem;
  padding-bottom: 3rem;
}
</style>
"""
