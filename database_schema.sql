-- BioReactor Monitoring System - Database Schema
-- Run this script in your RDS PostgreSQL instance to create tables

-- Main lab readings table
CREATE TABLE IF NOT EXISTS lab_readings (
    reading_id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    ph DECIMAL(5, 2) NOT NULL,
    temperature DECIMAL(5, 2) NOT NULL,
    dissolved_oxygen DECIMAL(5, 2) NOT NULL,
    operator_id VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log table - tracks all file processing events
CREATE TABLE IF NOT EXISTS lambda_audit_logs (
    log_id SERIAL PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_name VARCHAR(255) NOT NULL,
    s3_location VARCHAR(500),
    total_rows INT DEFAULT 0,
    rows_inserted INT DEFAULT 0,
    rows_skipped INT DEFAULT 0,
    errors_flagged INT DEFAULT 0,
    processing_status VARCHAR(20) CHECK (processing_status IN ('SUCCESS', 'PARTIAL', 'FAILED')),
    error_message TEXT,
    processing_duration_seconds INT
);


-- Optional: Create a view for easy dashboard queries
CREATE OR REPLACE VIEW batch_summary AS
SELECT 
    batch_id,
    COUNT(*) as total_readings,
    MIN(timestamp) as batch_start,
    MAX(timestamp) as batch_end,
    ROUND(AVG(temperature)::NUMERIC, 2) as avg_temperature,
    ROUND(AVG(ph)::NUMERIC, 2) as avg_ph,
    ROUND(AVG(dissolved_oxygen)::NUMERIC, 2) as avg_dissolved_oxygen,
    COUNT(CASE WHEN temperature > 38.0 OR temperature < 36.0 THEN 1 END) as temp_anomalies,
    COUNT(CASE WHEN ph < 6.8 OR ph > 7.5 THEN 1 END) as ph_anomalies,
    COUNT(CASE WHEN dissolved_oxygen < 25 THEN 1 END) as oxygen_anomalies
FROM lab_readings
GROUP BY batch_id
ORDER BY batch_end DESC;

-- View for pipeline monitor dashboard
CREATE OR REPLACE VIEW pipeline_health AS
SELECT 
    DATE(processed_at) as process_date,
    COUNT(*) as files_processed,
    SUM(total_rows) as total_records_processed,
    SUM(rows_inserted) as records_inserted,
    SUM(rows_skipped) as records_skipped,
    SUM(errors_flagged) as total_errors,
    ROUND(100.0 * SUM(rows_inserted) / NULLIF(SUM(total_rows), 0), 2) as success_rate_percent,
    COUNT(CASE WHEN processing_status = 'SUCCESS' THEN 1 END) as successful_files,
    COUNT(CASE WHEN processing_status = 'FAILED' THEN 1 END) as failed_files
FROM lambda_audit_logs
WHERE processing_status IN ('SUCCESS', 'PARTIAL')
GROUP BY DATE(processed_at)
ORDER BY process_date DESC;
