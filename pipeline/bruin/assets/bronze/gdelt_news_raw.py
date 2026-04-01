"""@bruin
name: bronze.gdelt_news_raw
type: python
image: python:3.11
connection: bigquery-default

materialization:
  type: table
  strategy: create+replace

columns:
  - name: ingestion_id
    type: string
    checks:
      - name: not_null
  - name: ingested_at
    type: timestamp
    checks:
      - name: not_null
  - name: source_window_start
    type: timestamp
  - name: source_window_end
    type: timestamp
  - name: source_record_id
    type: string
  - name: document_identifier
    type: string
  - name: source_url
    type: string
  - name: source_name
    type: string
  - name: title
    type: string
  - name: language
    type: string
  - name: published_at
    type: timestamp
  - name: tone_raw
    type: float
  - name: positive_signal_raw
    type: float
  - name: negative_signal_raw
    type: float
  - name: raw_payload
    type: json
@bruin"""

from __future__ import annotations

import os

import pandas as pd


def materialize(**kwargs) -> pd.DataFrame:
    """Return an empty Bronze-shaped dataframe until ingestion is implemented."""
    _ = os.environ.get("BRUIN_START_DATE")
    _ = os.environ.get("BRUIN_END_DATE")

    return pd.DataFrame(
        {
            "ingestion_id": pd.Series(dtype="string"),
            "ingested_at": pd.Series(dtype="datetime64[ns, UTC]"),
            "source_window_start": pd.Series(dtype="datetime64[ns, UTC]"),
            "source_window_end": pd.Series(dtype="datetime64[ns, UTC]"),
            "source_record_id": pd.Series(dtype="string"),
            "document_identifier": pd.Series(dtype="string"),
            "source_url": pd.Series(dtype="string"),
            "source_name": pd.Series(dtype="string"),
            "title": pd.Series(dtype="string"),
            "language": pd.Series(dtype="string"),
            "published_at": pd.Series(dtype="datetime64[ns, UTC]"),
            "tone_raw": pd.Series(dtype="float64"),
            "positive_signal_raw": pd.Series(dtype="float64"),
            "negative_signal_raw": pd.Series(dtype="float64"),
            "raw_payload": pd.Series(dtype="object"),
        }
    )
