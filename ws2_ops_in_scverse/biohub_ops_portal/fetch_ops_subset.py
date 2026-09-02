#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["zarr>=3.1", "s3fs>=2024.6", "click>=8.1", "numpy>=2.0"]
# ///
"""Fetch a spatial window of one OPS well image, with its label masks, into a local OME-Zarr store.

The source stores are stitched whole-well arrays (one field of view runs to
hundreds of GB), sharded with 512x512 inner chunks. Reading a window pulls only
the inner chunks that intersect it, so the download scales with the window, not
the well.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import click
import numpy as np
import zarr
from zarr.storage import FsspecStore, LocalStore, WrapperStore

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("fetch_ops_subset")

INNER_CHUNK = 512
MAX_SHARD = 4096
RGBA_MAX = 4


class RepairDimensionNames(WrapperStore):
    """Drop `dimension_names` when its length does not match the array's rank.

    The RGBA overlay arrays under `labels/` (iss_gene_image, iss_guide_image,
    grid_overlay) are 3-dimensional but declare five dimension names, which
    zarr-python rejects outright. Repairing the metadata on read is the only way
    to open them.
    """

    def __init__(self, store) -> None:
        super().__init__(store)
        self.repaired: set[str] = set()

    async def get(self, key: str, prototype, byte_range=None):
        buffer = await self._store.get(key, prototype, byte_range)
        if buffer is None or byte_range is not None or not key.endswith("zarr.json"):
            return buffer
        document = json.loads(buffer.to_bytes())
        names = document.get("dimension_names")
        if document.get("node_type") != "array" or names is None:
            return buffer
        if len(names) == len(document["shape"]):
            return buffer
        self.repaired.add(key)
        document.pop("dimension_names")
        return prototype.buffer.from_bytes(json.dumps(document).encode())


@dataclass(frozen=True)
class Window:
    """Pixel window in level-0 Y/X coordinates."""

    y0: int
    x0: int
    height: int
    width: int

    def scaled(self, factor: int, extent_y: int, extent_x: int) -> tuple[slice, slice]:
        y0 = min(self.y0 // factor, extent_y)
        x0 = min(self.x0 // factor, extent_x)
        y1 = min(y0 + max(-(-self.height // factor), 1), extent_y)
        x1 = min(x0 + max(-(-self.width // factor), 1), extent_x)
        return slice(y0, y1), slice(x0, x1)


def open_source(uri: str, anon: bool) -> zarr.Group:
    if uri.startswith("s3://"):
        options = {"anon": True} if anon else None
        store = FsspecStore.from_url(uri, storage_options=options, read_only=True)
    else:
        store = LocalStore(uri, read_only=True)
    return zarr.open_group(store=RepairDimensionNames(store), mode="r")


def spatial_axes(array: zarr.Array) -> tuple[int, int]:
    """Return the (Y, X) axis positions of an array.

    Image and segmentation arrays are (T, C, Z, Y, X). The RGBA overlays are
    (Y, X, 4) with no usable dimension names, so fall back on the trailing
    channel.
    """
    names = array.metadata.dimension_names
    if names and len(names) == array.ndim and "Y" in names and "X" in names:
        return names.index("Y"), names.index("X")
    if array.ndim == 3 and array.shape[-1] <= RGBA_MAX:
        return 0, 1
    return array.ndim - 2, array.ndim - 1


def level_paths(group: zarr.Group) -> list[str]:
    """Pyramid level names, from ome.multiscales when declared, else the array members."""
    multiscales = group.attrs.get("ome", {}).get("multiscales")
    if multiscales:
        return [dataset["path"] for dataset in multiscales[0]["datasets"]]
    levels = [name for name, node in group.members() if isinstance(node, zarr.Array)]
    return sorted(levels, key=lambda name: (len(name), name))


def filtered_attrs(attrs: dict, keep: list[str], origin_um: dict[str, float]) -> dict:
    """Copy group attributes, narrowing ome.multiscales to the levels being fetched."""
    out = json.loads(json.dumps(attrs))
    multiscales = out.get("ome", {}).get("multiscales")
    if not multiscales:
        return out
    axes = [axis["name"] for axis in multiscales[0]["axes"]]
    datasets = []
    for dataset in multiscales[0]["datasets"]:
        if dataset["path"] not in keep:
            continue
        transforms = list(dataset["coordinateTransformations"])
        translation = [origin_um.get(axis, 0.0) for axis in axes]
        if any(translation):
            transforms.append({"type": "translation", "translation": translation})
        datasets.append({**dataset, "coordinateTransformations": transforms})
    multiscales[0]["datasets"] = datasets
    return out


def shard_shape(chunk: tuple[int, ...], shape: tuple[int, ...], y: int, x: int) -> tuple[int, ...] | None:
    span = min(MAX_SHARD, shape[y], shape[x])
    if span <= INNER_CHUNK:
        return None
    span -= span % INNER_CHUNK
    return tuple(span if axis in (y, x) else size for axis, size in enumerate(chunk))


def copy_window(src: zarr.Array, dst_group: zarr.Group | None, name: str, window: Window, factor: int) -> int:
    y, x = spatial_axes(src)
    ys, xs = window.scaled(factor, src.shape[y], src.shape[x])
    selection = tuple(ys if axis == y else xs if axis == x else slice(None) for axis in range(src.ndim))
    shape = tuple(
        ys.stop - ys.start if axis == y else xs.stop - xs.start if axis == x else size
        for axis, size in enumerate(src.shape)
    )
    nbytes = int(np.prod(shape)) * src.dtype.itemsize
    logger.info(
        "  level %-2s y=%d:%d x=%d:%d  shape=%s  %.1f MB uncompressed",
        name, ys.start, ys.stop, xs.start, xs.stop, shape, nbytes / 1e6,
    )
    if dst_group is None:
        return nbytes

    chunk = tuple(
        min(INNER_CHUNK, size) if axis in (y, x) else min(src.chunks[axis], size)
        for axis, size in enumerate(shape)
    )
    names = src.metadata.dimension_names
    dst = dst_group.create_array(
        name=name,
        shape=shape,
        dtype=src.dtype,
        chunks=chunk,
        shards=shard_shape(chunk, shape, y, x),
        dimension_names=names if names and len(names) == len(shape) else None,
    )
    dst[...] = src[selection]
    return nbytes


def resolve_labels(labels_group: zarr.Group | None, requested: str) -> tuple[list[str], list[str]]:
    """Return (group names to copy, group names declared in ome.labels)."""
    if labels_group is None:
        return [], []
    declared = list(labels_group.attrs.get("ome", {}).get("labels", []))
    present = [name for name, node in labels_group.members() if isinstance(node, zarr.Group)]
    ordered = declared + sorted(name for name in present if name not in declared)
    if requested == "all":
        return ordered, declared
    if requested == "declared":
        return declared, declared
    names = [name.strip() for name in requested.split(",") if name.strip()]
    unknown = [name for name in names if name not in ordered]
    if unknown:
        raise click.ClickException(f"No such group under labels/: {unknown}. Available: {ordered}")
    return names, declared


def x_extent(group: zarr.Group, level: str) -> int:
    array = group[level]
    return array.shape[spatial_axes(array)[1]]


@click.command()
@click.option("--store", required=True, help="Source plate store, e.g. s3://bucket/prefix/plate.zarr")
@click.option("--well", default="A/1", show_default=True, help="Well path within the plate.")
@click.option("--field", default="0", show_default=True, help="Field of view within the well.")
@click.option("--origin", default="0,0", show_default=True, help="Window origin as Y,X in level-0 pixels.")
@click.option("--size", default="4096,4096", show_default=True, help="Window size as height,width in level-0 pixels.")
@click.option("--levels", default="0", show_default=True, help="Comma-separated pyramid levels, or 'all'.")
@click.option("--labels", default="all", show_default=True,
              help="Comma-separated group names, 'all' for every group under labels/, "
                   "'declared' for only those in ome.labels, or 'none'.")
@click.option("--out", type=click.Path(path_type=Path), required=True, help="Output directory.")
@click.option("--anon/--signed", default=True, show_default=True, help="Anonymous S3 access.")
@click.option("--dry-run", is_flag=True, help="Report the plan without downloading.")
def main(
    store: str,
    well: str,
    field: str,
    origin: str,
    size: str,
    levels: str,
    labels: str,
    out: Path,
    anon: bool,
    dry_run: bool,
) -> None:
    """Copy a window of one well image plus its labels into a local OME-Zarr plate store."""
    y0, x0 = (int(value) for value in origin.split(","))
    height, width = (int(value) for value in size.split(","))
    window = Window(y0=y0, x0=x0, height=height, width=width)

    src_plate = open_source(store.rstrip("/"), anon)
    src_image = src_plate[f"{well}/{field}"]
    image_attrs = dict(src_image.attrs)
    available = level_paths(src_image)
    keep = available if levels == "all" else [value.strip() for value in levels.split(",")]
    unknown = [level for level in keep if level not in available]
    if unknown:
        raise click.ClickException(f"Level(s) {unknown} not in multiscales. Available: {available}")

    multiscale = image_attrs["ome"]["multiscales"][0]
    axes = [axis["name"] for axis in multiscale["axes"]]
    scale = multiscale["datasets"][0]["coordinateTransformations"][0]["scale"]
    origin_um = {"Y": y0 * scale[axes.index("Y")], "X": x0 * scale[axes.index("X")]}

    src_labels = src_image["labels"] if "labels" in src_image else None
    label_names, declared = ([], []) if labels == "none" else resolve_labels(src_labels, labels)

    dst_root = out / Path(store.rstrip("/")).name
    logger.info("source  %s", store)
    logger.info("window  y=%d:%d x=%d:%d at level 0", y0, y0 + height, x0, x0 + width)
    logger.info("levels  %s of %s", keep, available)
    logger.info("labels  %d group(s), %d of them declared in ome.labels", len(label_names), len(declared))
    logger.info("target  %s", dst_root)

    dst_image = dst_labels = None
    if not dry_run:
        root = zarr.open_group(dst_root, mode="w", zarr_format=3)
        plate_attrs = json.loads(json.dumps(dict(src_plate.attrs)))
        plate = plate_attrs["ome"]["plate"]
        row, column = well.split("/")
        plate["wells"] = [entry for entry in plate["wells"] if entry["path"] == well]
        plate["rows"] = [entry for entry in plate["rows"] if entry["name"] == row]
        plate["columns"] = [entry for entry in plate["columns"] if entry["name"] == column]
        for entry in plate["wells"]:
            entry["rowIndex"] = 0
            entry["columnIndex"] = 0
        plate["field_count"] = 1
        root.attrs.update(plate_attrs)

        dst_well = root.create_group(well)
        well_attrs = json.loads(json.dumps(dict(src_plate[well].attrs)))
        well_attrs["ome"]["well"]["images"] = [
            image for image in well_attrs["ome"]["well"]["images"] if image["path"] == field
        ]
        dst_well.attrs.update(well_attrs)

        dst_image = dst_well.create_group(field)
        dst_image.attrs.update(filtered_attrs(image_attrs, keep, origin_um))
        if label_names:
            dst_labels = dst_image.create_group("labels")
            labels_attrs = json.loads(json.dumps(dict(src_labels.attrs)))
            labels_attrs["ome"]["labels"] = [name for name in label_names if name in declared]
            dst_labels.attrs.update(labels_attrs)

    total = 0
    logger.info("image")
    base = x_extent(src_image, available[0])
    for level in keep:
        total += copy_window(src_image[level], dst_image, level, window, round(base / x_extent(src_image, level)))

    for name in label_names:
        source_group = src_labels[name]
        group_levels = level_paths(source_group)
        wanted = [level for level in group_levels if level in keep]
        logger.info("label %s%s", name, "" if name in declared else "  (not in ome.labels)")
        if not wanted:
            logger.info("  no level in %s; skipped", keep)
            continue
        dst_label = None
        if dst_labels is not None:
            dst_label = dst_labels.create_group(name)
            dst_label.attrs.update(filtered_attrs(dict(source_group.attrs), wanted, origin_um))
        base = x_extent(source_group, group_levels[0])
        for level in wanted:
            factor = round(base / x_extent(source_group, level))
            total += copy_window(source_group[level], dst_label, level, window, factor)

    repaired = getattr(src_plate.store, "repaired", set())
    if repaired:
        logger.info("repaired dimension_names on %d source array(s) while reading", len(repaired))
    logger.info("total %.1f MB uncompressed%s", total / 1e6, " (dry run)" if dry_run else "")


if __name__ == "__main__":
    main()
