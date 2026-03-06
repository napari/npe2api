#!/usr/bin/env python3
"""
Upload generated JSON files to R2 bucket.

Reads all JSON files from public/ directory and uploads them to R2.
Uses R2_BUCKET_NAME environment variable to support both production and preview buckets.

For local development, create a .env file with:
    CLOUDFLARE_ACCOUNT_ID=your_account_id
    R2_ACCESS_KEY_ID=your_access_key
    R2_SECRET_ACCESS_KEY=your_secret_key
    R2_BUCKET_NAME=npe2api

Usage:
    uv run -m npe2api.upload_to_r2
"""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3

# Load .env file if it exists (for local development)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use environment variables only


def calculate_md5(file_path: Path) -> str:
    """Calculate MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def needs_upload(s3, bucket_name: str, key: str, file_path: Path) -> bool:
    """Check if file needs to be uploaded by comparing MD5 with R2 ETag."""
    try:
        response = s3.head_object(Bucket=bucket_name, Key=key)
        # R2 ETag is the MD5 hash wrapped in quotes
        remote_etag = response["ETag"].strip('"')
        local_md5 = calculate_md5(file_path)
        return remote_etag != local_md5
    except s3.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return True  # File doesn't exist, needs upload
        raise


def upload_file(s3, bucket_name: str, file_path: Path, public_dir: Path) -> tuple[str, bool]:
    """Upload a single file to R2 if it has changed."""
    key = str(file_path.relative_to(public_dir))

    # Check if upload is needed
    if not needs_upload(s3, bucket_name, key, file_path):
        return key, False  # Skipped

    # Determine content type
    content_type = "application/json"
    if key.endswith(".html"):
        content_type = "text/html"
    elif key.endswith(".json"):
        content_type = "application/json"

    s3.upload_file(
        str(file_path),
        bucket_name,
        key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=3600",
        },
    )
    return key, True  # Uploaded


def upload_to_r2():
    """Sync all JSON files from public/ directory to R2, removing stale files."""
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    access_key_id = os.environ["R2_ACCESS_KEY_ID"]
    secret_access_key = os.environ["R2_SECRET_ACCESS_KEY"]
    bucket_name = os.environ.get("R2_BUCKET_NAME", "npe2api")

    session = boto3.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )

    s3 = session.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
    )

    # Create bucket if it doesn't exist
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"Using bucket: {bucket_name}")
    except s3.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404":
            print(f"Bucket '{bucket_name}' not found, creating...")
            s3.create_bucket(Bucket=bucket_name)
            print(f"✓ Created bucket: {bucket_name}")
        else:
            raise

    # Upload all files from public/ directory
    public_dir = Path("public")
    if not public_dir.exists():
        print(f"Error: {public_dir} directory does not exist")
        return

    # Collect all JSON files to upload
    files_to_process = [f for f in public_dir.rglob("*.json") if f.is_file()]
    local_keys = {str(f.relative_to(public_dir)) for f in files_to_process}
    print(f"Processing {len(files_to_process)} JSON files...")

    uploaded_count = 0
    skipped_count = 0

    # Upload files in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(upload_file, s3, bucket_name, file_path, public_dir): file_path
            for file_path in files_to_process
        }

        for future in as_completed(futures):
            key, was_uploaded = future.result()
            if was_uploaded:
                print(f"✓ Uploaded: {key}")
                uploaded_count += 1
            else:
                print(f"⊝ Skipped (unchanged): {key}")
                skipped_count += 1

    # Delete files from R2 that no longer exist locally
    print("\nChecking for stale files in R2...")
    remote_keys = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name):
        if "Contents" in page:
            for obj in page["Contents"]:
                key = obj["Key"]
                # Only track JSON files (to avoid deleting non-managed files)
                if key.endswith(".json"):
                    remote_keys.add(key)

    stale_keys = remote_keys - local_keys
    deleted_count = 0

    if stale_keys:
        print(f"Found {len(stale_keys)} stale files to delete...")
        for key in stale_keys:
            s3.delete_object(Bucket=bucket_name, Key=key)
            print(f"✗ Deleted: {key}")
            deleted_count += 1
    else:
        print("No stale files found")

    print("")
    print(f"Uploaded {uploaded_count} files, skipped {skipped_count} (unchanged), deleted {deleted_count} (stale)")
    print(f"  Bucket: {bucket_name}")


if __name__ == "__main__":
    upload_to_r2()
