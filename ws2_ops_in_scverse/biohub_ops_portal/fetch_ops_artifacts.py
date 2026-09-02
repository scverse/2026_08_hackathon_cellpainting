#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["boto3>=1.34", "click>=8.1"]
# ///
"""Download the flat artifacts of one OPS aggregation, plus an optional image-store metadata mirror.

Everything except the image store is small: metadata, the perturbation library, the
single-cell feature table and the aggregated embedding come to roughly 40 MB. The
image store is 650 GB, but its `zarr.json` tree is 1.2 MB and is all a validator or
a structure reader needs. For pixels, use `fetch_ops_subset.py`.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import boto3
import click
from botocore import UNSIGNED
from botocore.config import Config

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("fetch_ops_artifacts")

BUCKET = "ops-explorer-public"
SUBMISSION = "leonetti_ops/ops_data_portal_submission/v2.0.20260724"
ATLAS_FILES = ("aggregated_data.h5ad", "perturbation_library.csv", "feature_definitions.csv")


@dataclass(frozen=True)
class Item:
    key: str
    dest: Path
    size: int


def client(anon: bool):
    config = Config(signature_version=UNSIGNED, max_pool_connections=32) if anon else Config(max_pool_connections=32)
    return boto3.client("s3", config=config)


def list_prefix(s3, bucket: str, prefix: str, suffix: str | None = None) -> list[tuple[str, int]]:
    found = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Size"] == 0:
                continue
            if suffix is None or obj["Key"].endswith(suffix):
                found.append((obj["Key"], obj["Size"]))
    return found


def plan(s3, bucket: str, submission: str, aggregation: str, out: Path, metadata_mirror: bool) -> list[Item]:
    root = f"{submission}/datasets/{aggregation}"
    items = [
        Item(key, out / aggregation / Path(key).relative_to(root), size)
        for key, size in list_prefix(s3, bucket, f"{root}/metadata/")
    ]
    items += [
        Item(f"{root}/cell_data.parquet", out / aggregation / "cell_data.parquet", size)
        for key, size in list_prefix(s3, bucket, f"{root}/cell_data.parquet")
        if key.endswith("cell_data.parquet")
    ]
    items += [
        Item(f"{submission}/atlas/{name}", out / "atlas" / name, size)
        for name in ATLAS_FILES
        for key, size in list_prefix(s3, bucket, f"{submission}/atlas/{name}")
        if key.endswith(name)
    ]
    if metadata_mirror:
        store = f"{root}/{aggregation}.zarr"
        items += [
            Item(key, out / aggregation / Path(key).relative_to(root), size)
            for key, size in list_prefix(s3, bucket, f"{store}/", suffix="zarr.json")
        ]
    return items


def download(s3, bucket: str, item: Item) -> int:
    item.dest.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(bucket, item.key, str(item.dest))
    return item.size


@click.command()
@click.option("--aggregation", default="Biohub_OPS0001", show_default=True, help="Dataset directory name.")
@click.option("--bucket", default=BUCKET, show_default=True)
@click.option("--submission", default=SUBMISSION, show_default=True, help="Prefix of the submission version.")
@click.option("--out", type=click.Path(path_type=Path), default=Path("data"), show_default=True)
@click.option("--metadata-mirror/--no-metadata-mirror", default=True, show_default=True,
              help="Also mirror the image store's zarr.json tree (about 1.2 MB, no pixels).")
@click.option("--anon/--signed", default=True, show_default=True, help="Anonymous S3 access.")
@click.option("--dry-run", is_flag=True, help="Report the plan without downloading.")
def main(
    aggregation: str,
    bucket: str,
    submission: str,
    out: Path,
    metadata_mirror: bool,
    anon: bool,
    dry_run: bool,
) -> None:
    """Download one aggregation's flat artifacts from the Biohub OPS data portal bucket."""
    s3 = client(anon)
    items = plan(s3, bucket, submission, aggregation, out, metadata_mirror)
    if not items:
        raise click.ClickException(f"Nothing found for {aggregation} under s3://{bucket}/{submission}")

    total = sum(item.size for item in items)
    zarr_meta = [item for item in items if item.dest.name == "zarr.json"]
    for item in items:
        if item not in zarr_meta:
            logger.info("  %-52s %8.1f MB", str(item.dest), item.size / 1e6)
    if zarr_meta:
        logger.info("  %-52s %8.1f MB", f"{len(zarr_meta)} zarr.json files", sum(i.size for i in zarr_meta) / 1e6)
    logger.info("total %.1f MB%s", total / 1e6, " (dry run)" if dry_run else "")
    if dry_run:
        return

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda item: download(s3, bucket, item), items))
    logger.info("done -> %s", out)


if __name__ == "__main__":
    main()
