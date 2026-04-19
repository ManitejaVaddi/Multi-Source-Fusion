import os
from pathlib import Path

import boto3


BASE_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = BASE_DIR / "cloud_samples" / "s3_osint_batch.json"


def main():
    bucket = os.getenv("AWS_S3_BUCKET")
    prefix = os.getenv("AWS_S3_PREFIX", "osint/")
    region = os.getenv("AWS_DEFAULT_REGION") or None

    if not bucket:
      raise SystemExit("Set AWS_S3_BUCKET before running this script.")

    key = f"{prefix.rstrip('/')}/s3_osint_batch.json" if prefix else "s3_osint_batch.json"
    client = boto3.client("s3", region_name=region)
    client.upload_file(str(SAMPLE_FILE), bucket, key)
    print(f"Uploaded {SAMPLE_FILE.name} to s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
