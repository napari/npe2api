#!/usr/bin/env python3
"""
Generate wrangler configuration files.

Usage:
    python -m npe2api.wrangler_config --prod
    python -m npe2api.wrangler_config --preview 123

After generating the config, deploy with:
    pywrangler deploy

Or run locally with:
    pywrangler dev --remote
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
        ]
    },
}


def create_production_config() -> None:
    """Create production wrangler configuration."""
    config = BASE_CONFIG.copy()
    config["name"] = "npe2api"
    config["r2_buckets"] = [
        {
            "binding": "BUCKET",
            "bucket_name": "npe2api",
            "remote": True,  # Enable remote binding for local dev
        }
    ]

    output_path = Path("wrangler.jsonc")
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Created {output_path}")
    print("  Worker name: npe2api")
    print("  Bucket name: npe2api")
    print("  Deploy with: wrangler deploy")


def create_preview_config(env_name: str) -> None:
    """
    Create preview wrangler configuration for PR deployments.

    Creates a completely separate worker for the preview environment.

    Args:
        env_name: Environment name for the preview (e.g., pr-123)
    """
    worker_name = f"npe2api-{env_name}"
    bucket_name = f"npe2api-{env_name}"

    config = BASE_CONFIG.copy()
    config["name"] = worker_name
    config["r2_buckets"] = [
        {
            "binding": "BUCKET",
            "bucket_name": bucket_name,
            "remote": True,
        }
    ]

    output_path = Path("wrangler.jsonc")
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Created {output_path} for preview deployment")
    print(f"  Worker name: {worker_name}")
    print(f"  Bucket name: {bucket_name}")
    print("  Deploy with: pywrangler deploy")


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
        type=str,
        help="Generate preview config with suffix (e.g., --preview pr-123)",
    )

    args = parser.parse_args()

    if args.prod:
        create_production_config()
    elif args.preview:
        create_preview_config(args.preview)


if __name__ == "__main__":
    main()
