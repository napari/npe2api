#!/usr/bin/env python3
"""
Delete preview R2 bucket and Worker.

For local development, create a .env file with:
    CLOUDFLARE_ACCOUNT_ID=your_account_id
    CLOUDFLARE_API_TOKEN=your_api_token
    R2_ACCESS_KEY_ID=your_access_key
    R2_SECRET_ACCESS_KEY=your_secret_key

Usage:
    python -m npe2api.preview_cleanup pr-123
"""

import argparse
import os
import subprocess

import boto3

# Load .env file if it exists (for local development)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use environment variables only


def delete_r2_bucket(bucket_name: str) -> None:
    """
    Delete an R2 bucket and all its contents.

    Args:
        bucket_name: Name of the R2 bucket to delete
    """
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    access_key_id = os.environ["R2_ACCESS_KEY_ID"]
    secret_access_key = os.environ["R2_SECRET_ACCESS_KEY"]

    session = boto3.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )

    s3 = session.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
    )

    try:
        # Need to delete all objects before deleting the bucket
        print(f"Deleting objects from bucket: {bucket_name}")
        paginator = s3.get_paginator("list_objects_v2")
        object_count = 0
        for page in paginator.paginate(Bucket=bucket_name):
            if "Contents" in page:
                objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                s3.delete_objects(Bucket=bucket_name, Delete={"Objects": objects})
                object_count += len(objects)

        if object_count > 0:
            print(f"  Deleted {object_count} objects")

        s3.delete_bucket(Bucket=bucket_name)
        print(f"✓ Deleted R2 bucket: {bucket_name}")

    except s3.exceptions.NoSuchBucket:
        print(f"⚠ Bucket does not exist: {bucket_name}")
    except Exception as e:
        print(f"✗ Error deleting bucket: {e}")
        raise


def delete_worker(worker_name: str) -> None:
    """
    Delete a Cloudflare Worker.

    Args:
        worker_name: Name of the worker to delete (e.g., npe2api-pr-123)
    """
    try:
        print(f"Deleting worker: {worker_name}")
        subprocess.run(
            ["pywrangler", "delete", worker_name, "--force"],
            check=True,
            env={**os.environ},
        )
        print(f"✓ Deleted Worker: {worker_name}")
    except subprocess.CalledProcessError as e:
        print(f"⚠ Error deleting worker: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Delete preview R2 bucket and Worker"
    )
    parser.add_argument(
        "env_name",
        type=str,
        help="Environment name (e.g., pr-123)",
    )

    args = parser.parse_args()

    worker_name = f"npe2api-{args.env_name}"
    bucket_name = f"npe2api-{args.env_name}"

    print(f"🧹 Cleaning up preview deployment for environment: {args.env_name}")

    delete_worker(worker_name)
    delete_r2_bucket(bucket_name)

    print(f"\n✓ Cleanup complete for environment: {args.env_name}")


if __name__ == "__main__":
    main()
