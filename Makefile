PYTHON ?= python3
STREAMLIT_VENV ?= app/streamlit/.venv
STREAMLIT_BIN := $(STREAMLIT_VENV)/bin/streamlit
STREAMLIT_PYTHON := $(STREAMLIT_VENV)/bin/python
STREAMLIT_PORT ?= 8501
TIDINGSIQ_GCP_PROJECT ?=
TIDINGSIQ_GOLD_TABLE ?=

export TIDINGSIQ_GCP_PROJECT
export TIDINGSIQ_GOLD_TABLE

.PHONY: streamlit streamlit-install

streamlit: $(STREAMLIT_BIN)
	$(STREAMLIT_BIN) run app/streamlit/app.py \
		--server.headless true \
		--server.port $(STREAMLIT_PORT) \
		--browser.gatherUsageStats false

streamlit-install: $(STREAMLIT_BIN)

$(STREAMLIT_BIN): app/streamlit/requirements.txt
	$(PYTHON) -m venv $(STREAMLIT_VENV)
	$(STREAMLIT_PYTHON) -m pip install --upgrade pip
	$(STREAMLIT_PYTHON) -m pip install -r app/streamlit/requirements.txt
