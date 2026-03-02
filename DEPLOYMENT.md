# Deployment Guide - BioReactor Monitoring Pipeline

This guide covers deploying the complete pipeline to AWS.

## Prerequisites

- AWS Account with appropriate permissions
- Local Python 3.8+ environment
- PostgreSQL client (`psql`) installed
- AWS CLI configured (`aws configure`)

---

## Step 1: Set Up AWS RDS PostgreSQL

### Create RDS Instance
1. **AWS Console** → RDS → Create Database
2. **Engine:** PostgreSQL (version 13+)
3. **DB Instance Class:** `db.t3.micro` (free tier eligible)
4. **Storage:** 20 GB, General Purpose SSD
5. **Database name:** `postgres`
6. **Master username:** `postgres`
7. **Master password:** Strong password (save this!)
8. **Public accessibility:** Yes (for development; restrict in production)
9. **VPC Security Group:** Create new or use existing
   - **Inbound Rule:** PostgreSQL (5432) from your IP + Lambda security group

### Initialize Database Schema
```bash
# Connect to RDS and create tables
psql -h <your-rds-endpoint>.rds.amazonaws.com -U postgres -d postgres -f database_schema.sql

# Verify tables were created
psql -h <your-rds-endpoint>.rds.amazonaws.com -U postgres -d postgres
\dt  # List tables
\q   # Exit
```

---

## Step 2: Set Up AWS S3 Bucket

### Create S3 Bucket
```bash
aws s3 mb s3://lab-data-intake-2026 --region us-east-1
```

### Enable Versioning (Optional)
```bash
aws s3api put-bucket-versioning \
  --bucket lab-data-intake-2026 \
  --versioning-configuration Status=Enabled
```

---

## Step 3: Deploy AWS Lambda Function

### Package the Function
```bash
cd Lambda_function
zip -r ../lambda_function.zip lambda_function.py
cd ..
```

### Create Lambda Function
1. **AWS Console** → Lambda → Create Function
2. **Function name:** `BioReactor-Data-Validator`
3. **Runtime:** Python 3.12
4. **Architecture:** x86_64
5. **Code:** Upload `lambda_function.zip`
6. **Handler:** `lambda_function.lambda_handler`

### Configure Lambda

**Timeout & Memory:**
- Timeout: 60 seconds
- Memory: 256 MB

**Environment Variables:**
```
DB_HOST = your-rds-endpoint.rds.amazonaws.com
DB_NAME = postgres
DB_USER = postgres
DB_PASS = your_secure_password
```

**Attach IAM Policy:**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::lab-data-intake-2026/raw_data/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

**Add Lambda Layer (psycopg2):**
1. Lambda Console → Layers
2. ARN: `arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p312-psycopg2-binary:1`

### Add S3 Event Trigger
1. Lambda Console → Add Trigger
2. **Source:** S3
3. **Bucket:** `lab-data-intake-2026`
4. **Event type:** PUT
5. **Prefix:** `raw_data/`

### Test Lambda
Use the following test event in Lambda Console:
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {"name": "lab-data-intake-2026"},
        "object": {"key": "raw_data/test_20260302_120000_bioreactor_data_export.csv"}
      }
    }
  ]
}
```

---

## Step 4: Deploy Dashboards (Local/On Premise)

### Option A: Local Development
```bash
# Terminal 1 - Bioreactor Dashboard
streamlit run bioreactor_dashboard.py

# Terminal 2 - Audit Dashboard
streamlit run audit_dashboard.py --server.port 8502
```

### Option B: Deploy to Streamlit Cloud
```bash
# Push to GitHub first
git push origin main

# Then in Streamlit Cloud:
1. Connect GitHub repository
2. Select branch: main
3. Set main file: bioreactor_dashboard.py (or audit_dashboard.py)
```

### Option C: Deploy to AWS EC2/ECS
1. Create EC2 instance (Ubuntu 22.04)
2. Install Python & dependencies
3. Configure `.env` file with RDS credentials
4. Run dashboards in screen/tmux sessions
5. Use reverse proxy (nginx) for SSL/TLS

---

## Step 5: Monitor & Test Pipeline

### Test Data Flow
```bash
# Generate mock data and upload to S3
python lab_instrument_simulator.py

# Check CloudWatch logs
aws logs tail /aws/lambda/BioReactor-Data-Validator --follow

# Query RDS to verify data insertion
psql -h <your-rds-endpoint> -U postgres -d postgres \
  -c "SELECT COUNT(*) FROM lab_readings;"
```

### View Dashboards
- **Bioreactor Dashboard:** http://localhost:8501
- **Audit Dashboard:** http://localhost:8502

---

## Security Checklist (Production)

- [ ] RDS database uses encryption at rest
- [ ] RDS is in private VPC subnet (no public access)
- [ ] Security groups restrict access by IP/security group
- [ ] SSL/TLS enabled for all connections (`sslmode=require`)
- [ ] IAM roles follow principle of least privilege
- [ ] `.env` file NOT committed to git
- [ ] AWS credentials rotated regularly
- [ ] CloudWatch alarms configured for Lambda errors
- [ ] RDS automated backups enabled
- [ ] Encryption keys stored in AWS Secrets Manager

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `psycopg2 not found` | Lambda layer not attached; verify Klayers ARN |
| `Connection refused` | RDS security group doesn't allow Lambda; add inbound rule |
| `Access Denied (IAM)` | Lambda execution role missing S3 permissions |
| `Lambda timeout` | Increase timeout to 120 seconds for large CSV files |
| `Dashboard won't connect` | Verify `.env` file has correct RDS credentials |

---

## Next Steps

1. Set up CloudWatch alarms for Lambda failures
2. Create SNS topic for error notifications
3. Implement data retention policies
4. Set up automated RDS backups
5. Monitor costs using AWS Cost Explorer
6. Consider moving dashboards to Streamlit Cloud or ECS for scalability

