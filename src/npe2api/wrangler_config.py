#!/usr/bin/env python3
"""
Generate wrangler configuration files.

Usage:
    uv run -m npe2api.wrangler_config --prod
    uv run -m npe2api.wrangler_config --preview 123
"""

import argparse
import json
from pathlib import Path

BASE_CONFIG = {
    "$schema": "node_modules/wrangler/config-schema.json",
    "main": "src/npe2api/worker.py",
    "compatibility_date": "2025-11-02",
    "compatibility_flags": ["python_workers", "python_dedicated_snapshot"],
    "observability": {"enabled": True},
    "python_modules": {
        "excludes": [
            "**/*.pyc",
            "**/__pycache__",
            "**/bigquery.py",
            "**/fetch_manifests.py",
            "**/find_by_classifier.py",
            "**/preview_cleanup.py",
            "**/reindex.py",
            "**/upload_to_r2.py",
            "**/wrangler_config.py",
            "**/_network.py",
        ]
    },
}


def create_production_config() -> None:
    """Create production wrangler configuration."""
    config = BASE_CONFIG.copy()
    config.update(
        {
            "name": "npe2api",
            "r2_buckets": [
                {
                    "binding": "BUCKET",
                    "bucket_name": "npe2api",
                    "remote": True,  # Enable remote binding for local dev
                }
            ],
        }
    )

    output_path = Path("wrangler.jsonc")
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Created {output_path}")
    print("  Worker name: npe2api")
    print("  Bucket name: npe2api")


def create_preview_config(pr_number: int) -> None:
    """
    Create preview wrangler configuration for PR deployments.

    Args:
        pr_number: Pull request number
    """
    bucket_name = f"npe2api-pr-{pr_number}"
    worker_name = f"npe2api-pr-{pr_number}"

    config = BASE_CONFIG.copy()
    config.update(
        {
            "name": worker_name,
            "r2_buckets": [
                {
                    "binding": "BUCKET",
                    "bucket_name": bucket_name,
                    "remote": True,  # Enable remote binding for local dev
                }
            ],
        }
    )

    output_path = Path("wrangler.jsonc")
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Created {output_path} for PR #{pr_number}")
    print(f"  Worker name: {worker_name}")
    print(f"  Bucket name: {bucket_name}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate wrangler configuration files"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--prod",
        action="store_true",
        help="Generate production config (wrangler.jsonc)",
    )
    group.add_argument(
        "--preview",
        type=int,
        metavar="PR_NUMBER",
        help="Generate preview config for PR number (wrangler.preview.jsonc)",
    )

    args = parser.parse_args()

    if args.prod:
        create_production_config()
    elif args.preview:
        create_preview_config(args.preview)


if __name__ == "__main__":
    main()
