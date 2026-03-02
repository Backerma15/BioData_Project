import json
import boto3
import psycopg2
import csv
import io
import urllib.parse
import os
from datetime import datetime
import time

# --- DATABASE CONFIG (From Lambda Environment Variables) ---
# These are set in AWS Lambda Console > Configuration > Environment Variables
# This approach follows security best practices (never hardcode credentials!)
DB_HOST = os.environ['DB_HOST']
DB_NAME = os.environ['DB_NAME']
DB_USER = os.environ['DB_USER']
DB_PASS = os.environ['DB_PASS']

def log_audit_event(conn, file_name, s3_location, total_rows, rows_inserted, rows_skipped, 
                    processing_status, error_message=None, processing_duration=0):
    """
    Logs pipeline processing events to lambda_audit_logs table.
    
    This creates an immutable audit trail for compliance and monitoring.
    """
    try:
        cur = conn.cursor()
        audit_query = """
            INSERT INTO lambda_audit_logs 
            (file_name, s3_location, total_rows, rows_inserted, rows_skipped, errors_flagged, 
             processing_status, error_message, processing_duration_seconds)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(audit_query, (
            file_name,
            s3_location,
            total_rows,
            rows_inserted,
            rows_skipped,
            rows_skipped,  # errors_flagged = rows_skipped
            processing_status,
            error_message,
            processing_duration
        ))
        conn.commit()
        cur.close()
        print(f"✅ Audit log recorded for {file_name}")
    except Exception as audit_err:
        print(f"⚠️ Warning: Could not write audit log: {audit_err}")

def lambda_handler(event, context):
    """
    AWS Lambda handler triggered by S3 PUT events.
    
    Event Flow:
    1. Lab simulator uploads CSV to S3 bucket
    2. S3 event triggers this Lambda function
    3. Lambda validates data and inserts into RDS
    4. Audit log records processing metrics
    5. CloudWatch logs track success/failures
    
    Args:
        event: S3 event containing bucket name and object key
        context: Lambda runtime context (unused but required)
    
    Returns:
        statusCode 200: Successful processing
        statusCode 400: Invalid event structure
        statusCode 500: Database or S3 errors
    """
    start_time = time.time()
    s3 = boto3.client('s3')
    processing_status = 'SUCCESS'
    error_message = None
    
    
    try:
        # 1. PARSE S3 EVENT - Extract bucket and file path
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
        print(f"Processing file: s3://{bucket}/{key}")
        
    except KeyError:
        print("ERROR: Event structure not recognized as S3 event.")
        return {'statusCode': 400, 'body': 'Invalid event structure'}
    
    try:
        # 2. DOWNLOAD CSV FROM S3 - Read into memory for processing
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(content))
        print(f"Successfully downloaded {len(content)} bytes from S3.")
        
        # 3. ESTABLISH RDS CONNECTION - Connect to PostgreSQL
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            connect_timeout=10
            # Note: In production, add sslmode='require' for encrypted connections
        )
        cur = conn.cursor()
        print(f"Connected to RDS at {DB_HOST}")
        
        inserted_count = 0
        skipped_count = 0
        
        # 4. ROW-BY-ROW TRANSACTION PROCESSING (CRITICAL FOR DATA INTEGRITY)
        # 
        # WHY ROW-BY-ROW COMMITS?
        # 
        # Without this approach:
        #   - ONE bad row = entire batch fails
        #   - One failed transaction aborts the connection
        #   - Data loss for the entire CSV
        #
        # With row-by-row commits:
        #   - Bad rows are skipped gracefully
        #   - Good rows are persisted immediately
        #   - Failed rows logged without stopping the pipeline
        #
        for row in csv_reader:
            try:
                # --- DATA VALIDATION LAYER ---
                # Skip rows that fail basic sanity checks
                if not row.get('ph') or not row.get('temperature'):
                    print(f"⚠️ Skipping row with missing critical fields: {row.get('batch_id')}")
                    skipped_count += 1
                    continue
                
                # Detect obvious sensor errors (impossible temperatures > 500°C)
                if float(row['temperature']) > 500:
                    print(f"⚠️ Skipping row with impossible temperature: {row['temperature']}°C in {row.get('batch_id')}")
                    skipped_count += 1
                    continue
                
                # --- DATABASE INSERT ---
                insert_query = """
                    INSERT INTO lab_readings 
                    (batch_id, timestamp, ph, temperature, dissolved_oxygen, operator_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                cur.execute(insert_query, (
                    row['batch_id'],
                    row['timestamp'],
                    float(row['ph']),
                    float(row['temperature']),
                    float(row['dissolved_oxygen']),
                    row['operator_id']
                ))
                
                # --- COMMIT THIS INDIVIDUAL ROW ---
                # This is the key difference: commit after EACH row, not after the entire batch
                conn.commit()
                inserted_count += 1
                
            except Exception as row_err:
                # --- ERROR HANDLING FOR INDIVIDUAL ROWS ---
                print(f"❌ Error processing row in batch {row.get('batch_id')}: {row_err}")
                # Rollback only THIS row's transaction, then continue processing
                conn.rollback()
                skipped_count += 1
                continue

        # 5. CLEANUP - Close connections and log results
        cur.close()
        
        # Record audit log
        processing_duration = int(time.time() - start_time)
        log_audit_event(
            conn=conn,
            file_name=key.split('/')[-1],
            s3_location=f"s3://{bucket}/{key}",
            total_rows=inserted_count + skipped_count,
            rows_inserted=inserted_count,
            rows_skipped=skipped_count,
            processing_status=processing_status,
            error_message=error_message,
            processing_duration=processing_duration
        )
        
        conn.close()
        print(f"✅ Processing complete: Inserted={inserted_count}, Skipped={skipped_count}, Duration={processing_duration}s")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {key}',
                'inserted_records': inserted_count,
                'skipped_records': skipped_count,
                'processing_duration_seconds': processing_duration
            })
        }
        
    except psycopg2.Error as db_err:
        print(f"❌ DATABASE ERROR: {db_err}")
        processing_status = 'FAILED'
        error_message = str(db_err)
        processing_duration = int(time.time() - start_time)
        return {
            'statusCode': 500,
            'body': json.dumps('Database connection failed.')
        }
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        processing_status = 'FAILED'
        error_message = str(e)
        return {
            'statusCode': 500,
            'body': json.dumps('Unexpected error during processing.')
        }