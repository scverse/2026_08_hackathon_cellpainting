# Biohub OPS data portal: downloading a workable subset

The CZ Biohub OPS Explorer publishes the Leonetti lab optical pooled screen as OME-Zarr on a public S3 bucket. The collection is 3.3 TB and the official CLI downloads whole collections only, so this directory holds two scripts that pull a laptop-sized slice instead.

Data organization and field-level detail live in [SCHEMA.md](SCHEMA.md). The standard itself is [chanzuckerberg/ops-schema](https://github.com/chanzuckerberg/ops-schema).

## Quick start

```bash
uv sync --extra tables

# 44 MB: metadata, perturbation library, single-cell table, embedding, image-store metadata
uv run fetch_ops_artifacts.py --out data

# 100 MB: a 2048 x 2048 window of pixels with two label masks
S=s3://ops-explorer-public/leonetti_ops/ops_data_portal_submission/v2.0.20260724/datasets/Biohub_OPS0001/Biohub_OPS0001.zarr
uv run fetch_ops_subset.py --store $S --well A/1 --field 0 \
  --origin 48000,48000 --size 2048,2048 --levels 0,1 \
  --labels nuclear_seg,cell_seg --out data
```

Both scripts carry [PEP 723](https://peps.python.org/pep-0723/) inline dependencies, so `uv run script.py` works without `uv sync` if you only want one of them. Both take `--dry-run`, which prints the plan and the byte count without downloading. S3 access is anonymous by default; no AWS account is needed.

## What to download

| Tier | Command | Size | What you get |
| --- | --- | --- | --- |
| Tables and metadata | `fetch_ops_artifacts.py` | 44 MB | YAML metadata, `perturbation_library.csv`, `feature_definitions.csv`, `cell_data.parquet` (831,587 cells), `aggregated_data.h5ad` (1052 genes), plus the image store's `zarr.json` tree |
| Pixels, one window | `fetch_ops_subset.py --size 2048,2048 --levels 0,1 --labels nuclear_seg,cell_seg` | 100 MB | 6 channels of real pixels, 828 nuclei and 859 cell masks in that window |
| Pixels, all masks | `fetch_ops_subset.py --size 1024,1024 --levels 0 --labels all` | 23 MB | 6 channels plus all 15 groups under `labels/`, from `nuclear_seg` to the ISS overlays |
| Pixels, whole well | `fetch_ops_subset.py --size 104650,105144 --levels 4 --labels none` | 630 MB | The full stitched well at 16x downsampling, 5.2 um/px, 6 channels. Add about 8 MB per label group |
| Everything | `ops-data download collection <id>` | 3.3 TB | Do not |

One aggregation's image store is 650 GB, so there is no tier between "a window" and "everything". Pick a window.

## The two scripts

### `fetch_ops_artifacts.py`

Downloads one aggregation's flat artifacts and, by default, mirrors the image store's `zarr.json` files (296 files, 0.5 MB). The mirror is enough to open the store hierarchy, read channel and label metadata, and run the OPS validator, which never touches chunk data.

```
--aggregation TEXT          Dataset directory name        [default: Biohub_OPS0001]
--submission TEXT           Submission version prefix     [default: .../v2.0.20260724]
--out PATH                  Output directory              [default: data]
--metadata-mirror /
  --no-metadata-mirror      Mirror the zarr.json tree     [default: mirror]
--anon / --signed           Anonymous S3 access           [default: anon]
--dry-run
```

Datasets are named `Biohub_OPS0001` through `Biohub_OPS0088`. They differ in imaging channels, not in perturbations: all 88 screen the same 1052-gene library.

### `fetch_ops_subset.py`

Copies a spatial window of one well image, plus its label masks, into a self-contained local OME-Zarr plate store. The wells are stitched into single arrays of 104650 x 105144 px, sharded at 13312² with 512² inner chunks, so a windowed read issues ranged GETs for only the inner chunks that intersect the window.

```
--store TEXT                Source plate store, s3:// or local     [required]
--well TEXT                 Well path in the plate                 [default: A/1]
--field TEXT                Field of view in the well              [default: 0]
--origin Y,X                Window origin in level-0 pixels        [default: 0,0]
--size H,W                  Window size in level-0 pixels          [default: 4096,4096]
--levels TEXT               Comma-separated levels, or 'all'       [default: 0]
--labels TEXT               Names, 'all', 'declared', or 'none'    [default: all]
--out PATH                  Output directory                       [required]
--anon / --signed           Anonymous S3 access                    [default: anon]
--dry-run
```

`--labels all` takes every group under `labels/`: the 11 to 12 integer segmentation masks plus the three RGBA overlays (`iss_gene_image`, `iss_guide_image`, `grid_overlay`), which are real data but are not listed in `ome.labels`. Use `--labels declared` for the `ome.labels` set alone, or name groups explicitly. The output's `ome.labels` lists only the declared groups it copied, so the overlays travel alongside without making the store claim they are label images.

The overlays need two accommodations, both handled in the script. They are `(Y, X, 4)` uint8 rather than `(T, C, Z, Y, X)`, so the window is applied to axes 0 and 1. And their level-0 arrays declare five `dimension_names` for three dimensions, which zarr-python rejects on open, so a store wrapper drops the mismatched names on read and the script reports how many arrays it repaired.

`--origin` and `--size` are always in level-0 pixels, whichever levels you ask for. The script divides them down per level, so one window definition gives you a consistent region across the pyramid. The output keeps the plate and well groups with a single well and field, filters `ome.multiscales` to the levels fetched, and appends a `translation` transform recording where the crop came from.

Throughput is latency-bound, roughly 1.5 MB/s, because each inner chunk is its own ranged GET. The 2048² example above took 1m55s. One large window beats many small ones.

## Opening what you downloaded

```python
import zarr, anndata as ad, pandas as pd

plate = zarr.open_group("data/Biohub_OPS0001.zarr", mode="r")
image = plate["A/1/0/0"]          # (T, C, Z, Y, X) float32
nuclei = plate["A/1/0/labels/nuclear_seg/0"]

cells = pd.read_parquet("data/Biohub_OPS0001/cell_data.parquet")
library = pd.read_csv("data/Biohub_OPS0001/metadata/perturbation_library.csv")
atlas = ad.read_h5ad("data/atlas/aggregated_data.h5ad")   # 1052 x 66, obsm X_umap and X_phate
```

`cells.bounding_box` is a string of `(y0, x0, y1, x1)` in stitched-well pixels, which is what you need to crop a cell out of the window you fetched. Check that your window overlaps: the first rows of OPS0001 sit around y=47400, x=400.

## Known quirks

Three things will bite a reader of this data. All are properties of the published stores, not of these scripts.

1. Label pyramid levels 1 and up have no `dimension_names`, so `ome-zarr-models` rejects the label groups and, through them, the parent image group. Level 0 is fine. Affects all 88 stores. Work around it by reading label level 0, or by writing `dimension_names` yourself after download. Separately, the three RGBA overlay arrays declare five dimension names for three dimensions, which stops zarr-python opening them at all; `fetch_ops_subset.py` repairs that on read.
2. `cell_data.parquet` uses 32 retired HGNC symbols (`AARS`, `ADSS`, `ASNA1`, `CARS`, `GARS`, `H2AFX`, and others) where `perturbation_library.csv` uses current ones (`AARS1`, `ADSS2`, `GET3`). A naive join drops those cells. Same 32 in every dataset.
3. There is no `collection_metadata.yaml`, and the aggregations sit under a `datasets/` container rather than at the submission root, so the tree does not match the standard's expected layout. See [SCHEMA.md](SCHEMA.md).

## The official CLI

```bash
uv sync --extra portal-cli
uv run ops-data download collection 3b32c693-a8b6-46d2-8f42-d4511a07f2f7 --dry-run
```

[`biohub-data-cli`](https://github.com/chanzuckerberg/biohub-data-cli) fetches a collection's dataset list from the portal API and downloads every object. It has `-o`, `-y` and `--dry-run` and no filtering, so it is all or nothing. The collection above (`aconcagua`) is a different screen from the one these scripts target and is 3.3 TB.

## Links

- [ops-schema](https://github.com/chanzuckerberg/ops-schema), the OPS data standard, v0.1.0 draft
- [biohub-data-cli](https://github.com/chanzuckerberg/biohub-data-cli)
- [OME-NGFF 0.5](https://ngff.openmicroscopy.org/0.5/) and its [HCS layout](https://ngff.openmicroscopy.org/0.5/#hcs-layout)
- [ome-zarr-models-py](https://github.com/ome-zarr-models/ome-zarr-models-py)
