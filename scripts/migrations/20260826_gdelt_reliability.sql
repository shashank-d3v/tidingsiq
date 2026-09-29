ALTER TABLE `__PROJECT_ID__.bronze.gdelt_news_raw`
ADD COLUMN IF NOT EXISTS bronze_run_expected_file_count INT64,
ADD COLUMN IF NOT EXISTS bronze_run_downloaded_file_count INT64,
ADD COLUMN IF NOT EXISTS bronze_run_missing_file_count INT64,
ADD COLUMN IF NOT EXISTS bronze_run_is_complete BOOL,
ADD COLUMN IF NOT EXISTS bronze_run_is_backfill BOOL,
ADD COLUMN IF NOT EXISTS bronze_run_low_volume BOOL,
ADD COLUMN IF NOT EXISTS bronze_run_baseline_average_accepted_row_count FLOAT64,
ADD COLUMN IF NOT EXISTS bronze_run_low_volume_threshold FLOAT64;

ALTER TABLE `__PROJECT_ID__.gold.pipeline_run_metrics`
ADD COLUMN IF NOT EXISTS latest_bronze_source_window_start TIMESTAMP,
ADD COLUMN IF NOT EXISTS latest_bronze_source_window_end TIMESTAMP,
ADD COLUMN IF NOT EXISTS latest_bronze_ingestion_expected_file_count INT64,
ADD COLUMN IF NOT EXISTS latest_bronze_ingestion_downloaded_file_count INT64,
ADD COLUMN IF NOT EXISTS latest_bronze_ingestion_missing_file_count INT64,
ADD COLUMN IF NOT EXISTS latest_bronze_ingestion_is_complete BOOL,
ADD COLUMN IF NOT EXISTS latest_bronze_ingestion_low_volume BOOL,
ADD COLUMN IF NOT EXISTS consecutive_complete_low_volume_run_count INT64;

-- Source-fetch outcomes are independent of article rows, including 0/4 windows.
CREATE TABLE IF NOT EXISTS `__PROJECT_ID__.bronze.gdelt_ingestion_attempts` (
  ingestion_id STRING,
  latest_ingested_at TIMESTAMP,
  source_window_start TIMESTAMP,
  source_window_end TIMESTAMP,
  accepted_row_count INT64,
  malformed_ratio FLOAT64,
  expected_file_count INT64,
  downloaded_file_count INT64,
  missing_file_count INT64,
  is_complete BOOL,
  is_backfill BOOL,
  low_volume BOOL
)
PARTITION BY DATE(latest_ingested_at);
