import csv
import random
import os
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import NoCredentialsError

# --- CONFIGURATION ---
FILE_NAME = "bioreactor_data_export.csv"
S3_BUCKET_NAME = "lab-data-intake-2026" 

def generate_mock_lab_data(filename, num_records=100):
    """
    Simulates a bioreactor outputting sensor readings.
    Includes: ph, temperature, and dissolved oxygen.
    """
    print(f"Generating {num_records} records for {filename}...")
    
    # Updated headers to match the Streamlit app and Database logic
    headers = ['batch_id', 'timestamp', 'ph', 'temperature', 'dissolved_oxygen', 'operator_id']
    
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        
        base_time = datetime.now()
        # Create a unique Batch ID for this specific "run"
        current_batch = f"BATCH-{random.randint(100, 999)}"
        
        for i in range(1, num_records + 1):
            # Advance time by 5 minutes for each reading
            timestamp = (base_time + timedelta(minutes=i*5)).strftime('%Y-%m-%d %H:%M:%S')
            
            # --- SENSOR SIMULATION ---
            # pH: Usually 6.8 to 7.4 for cell culture
            ph = round(random.uniform(7.0, 7.2), 2)
            
            # Temperature: Stable around 37°C
            temperature = round(random.uniform(36.8, 37.2), 1)
            
            # Dissolved Oxygen: 0% to 100% (Usually kept high, ~80-90%)
            dissolved_oxygen = round(random.uniform(80.0, 95.0), 1)
            
            operator_id = random.choice(['OP-01', 'OP-02', 'OP-03'])
            
            # --- INJECT ANOMALIES (For Dashboard Alerts) ---
            if random.random() < 0.03:
                temperature = round(random.uniform(38.5, 40.0), 1) # Overheating
            if random.random() < 0.03:
                ph = round(random.uniform(5.5, 6.5), 2) # Acidification
            if random.random() < 0.02:
                dissolved_oxygen = round(random.uniform(10.0, 30.0), 1) # Low oxygen crash

            writer.writerow([current_batch, timestamp, ph, temperature, dissolved_oxygen, operator_id])
            
    print(f"Data generation complete. Batch: {current_batch}")

def upload_to_aws_s3(local_file, bucket_name, s3_file_name):
    """
    Securely uploads the local CSV to an AWS S3 bucket.
    """
    print(f"Initiating upload to S3 bucket: {bucket_name}...")
    s3_client = boto3.client('s3')
    
    try:
        s3_client.upload_file(local_file, bucket_name, s3_file_name)
        print(f"SUCCESS: {local_file} uploaded to {bucket_name}/{s3_file_name}")
    except FileNotFoundError:
        print("ERROR: The file was not found locally.")
    except NoCredentialsError:
        print("ERROR: AWS credentials not available. Run 'aws configure'.")
    except Exception as e:
         print(f"An unexpected error occurred: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # Generate 100 records
    generate_mock_lab_data(FILE_NAME, num_records=100)
    
    # Create a unique key in S3
    timestamped_s3_name = f"raw_data/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{FILE_NAME}"
    
    # Upload
    upload_to_aws_s3(FILE_NAME, S3_BUCKET_NAME, timestamped_s3_name)