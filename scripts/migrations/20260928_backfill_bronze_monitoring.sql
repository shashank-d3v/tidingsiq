-- Render ${PROJECT_ID} before execution; one-time scan replaces recurring JSON scans.
UPDATE `${PROJECT_ID}.bronze.gdelt_news_raw` t
SET bronze_run_is_complete = COALESCE(t.bronze_run_is_complete, r.files >= 4),
    bronze_run_downloaded_file_count = COALESCE(t.bronze_run_downloaded_file_count, r.files),
    bronze_run_expected_file_count = COALESCE(t.bronze_run_expected_file_count, 4),
    bronze_run_missing_file_count = COALESCE(t.bronze_run_missing_file_count, GREATEST(4-r.files,0)),
    bronze_run_accepted_row_count = COALESCE(t.bronze_run_accepted_row_count, r.accepted),
    bronze_run_malformed_ratio = COALESCE(t.bronze_run_malformed_ratio, r.malformed)
FROM (
 SELECT ingestion_id, COUNT(DISTINCT JSON_VALUE(raw_payload, '$.gkg_source_file')) files,
 COALESCE(MAX(bronze_run_accepted_row_count), MAX(SAFE_CAST(JSON_VALUE(raw_payload, '$.bronze_run_accepted_row_count') AS INT64)), COUNT(*)) accepted,
 COALESCE(MAX(bronze_run_malformed_ratio), MAX(SAFE_CAST(JSON_VALUE(raw_payload, '$.bronze_run_malformed_ratio') AS FLOAT64)), 0.0) malformed
 FROM `${PROJECT_ID}.bronze.gdelt_news_raw` GROUP BY ingestion_id
) r
WHERE t.ingestion_id=r.ingestion_id AND (t.bronze_run_is_complete IS NULL OR t.bronze_run_malformed_ratio IS NULL);
