# AWS Lambda Function - Data Validation & Ingestion

This Lambda function is triggered by S3 events when new CSV files are uploaded. It validates the sensor data and inserts clean records into PostgreSQL RDS.

## Features
- ✅ Automatic S3 event trigger
- ✅ Row-by-row data validation
- ✅ Transaction handling with individual row commits/rollbacks
- ✅ Anomaly detection (impossible temperature values, missing pH)
- ✅ CloudWatch logging for debugging

## Deployment

### Step 1: Add the psycopg2 Lambda Layer

Due to compatibility issues, `psycopg2-binary` must be added as an **AWS Lambda Layer** rather than included in the package.

1. Go to AWS Lambda Console → Layers
2. Create a new layer OR use **Klayers** (public layer repository)
3. Layer ARN (us-east-1, Python 3.12):
   ```
   arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p312-psycopg2-binary:1
   ```
4. Copy this ARN for use in Lambda function configuration

### Step 2: Package the Function

```bash
# Navigate to the lambda_function directory
cd lambda_function

# Install requirements locally (optional, for local testing)
pip install -r requirements.txt

# Create deployment package
zip -r ../lambda_function.zip lambda_function.py
```

### Step 3: Create Lambda Function in AWS

1. AWS Lambda Console → Create Function
2. **Basic Information:**
   - Function name: `BioReactor-Data-Validator`
   - Runtime: Python 3.12
   - Architecture: x86_64

3. **Upload Code:**
   - Upload the `lambda_function.zip` file
   - Handler: `lambda_function.lambda_handler`

4. **Configuration:**
   - **Timeout:** 60 seconds (CSV processing may take time)
   - **Memory:** 256 MB (minimum)
   - **Environment Variables:**
     ```
     DB_HOST = your-rds-endpoint.amazonaws.com
     DB_NAME = postgres
     DB_USER = postgres
     DB_PASS = your_secure_password
     ```

5. **Add Layer:**
   - Layers → Add Layer → AWS Layers
   - Select the psycopg2 layer ARN from Step 1

6. **Add S3 Trigger:**
   - Add Trigger → S3
   - Bucket: `lab-data-intake-2026`
   - Event type: `PUT`
   - Prefix: `raw_data/`

### Step 4: Test the Function

```python
# Test event (use in Lambda Console)
{
  "Records": [
    {
      "s3": {
        "bucket": {
          "name": "lab-data-intake-2026"
        },
        "object": {
          "key": "raw_data/20260302_120000_bioreactor_data_export.csv"
        }
      }
    }
  ]
}
```

### Step 5: Monitor & Debug

1. **CloudWatch Logs:**
   - AWS CloudWatch → Log Groups → `/aws/lambda/BioReactor-Data-Validator`
   - Check for `SUCCESS` or error messages

2. **X-Ray Tracing (optional):**
   - Enable X-Ray to visualize Lambda → S3 → RDS interactions

## Row-by-Row Transaction Handling

This Lambda function implements **individual row commits** to prevent cascading failures:

```python
for row in csv_reader:
    try:
        # Validate and insert individual row
        cur.execute(insert_query, data)
        conn.commit()  # Commit THIS row only
    except Exception as row_err:
        conn.rollback()  # Rollback THIS row only
        continue  # Continue processing next rows
```

**Why this matters:**
- If row 50 has bad data, rows 1-49 are already committed
- One bad reading doesn't fail the entire batch
- Production databases stay healthy with partial successes

## Environment & Security

- ✅ **No hardcoded credentials** - Uses environment variables
- ✅ **VPC Security Group** - Lambda needs database access permissions
- ✅ **IAM Role** - Must allow S3 `GetObject` and CloudWatch Logs writes
- ✅ **SSL/TLS** - Ensure RDS connection uses SSL mode

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `psycopg2 not found` | Layer not attached | Verify Klayers ARN in Lambda configuration |
| `Connection refused` | Security Group blocking | Add Lambda security group to RDS inbound rules |
| `Access Denied` | Insufficient IAM permissions | Attach `AmazonS3ReadOnlyAccess` policy |
| `Timeout` | Large CSV files | Increase timeout to 120-300 seconds |

## Next Steps

- Monitor Lambda execution metrics in CloudWatch
- Set up SNS alerts for Lambda errors
- Create CloudWatch dashboard for data pipeline health
- Add data quality metrics (rows processed, rows failed, processing time)