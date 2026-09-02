# OPS schema and how the portal data is organized

The OPS data standard is [chanzuckerberg/ops-schema](https://github.com/chanzuckerberg/ops-schema), v0.1.0, draft status. This document summarizes it and records how the published Leonetti submission actually looks, which is not the same thing in every respect. Everything below was read off the bucket, not off the spec.

Read [README.md](README.md) first if you want the download commands.

## The data model

Three levels:

```
Collection                        one per submission, groups the aggregations of one publication
└── Pseudobulk Aggregation        the lab-defined unit: library + single-cell features + image store
    └── Visualization             one or more embeddings of that aggregation, in one aggregated_data.h5ad
```

An aggregation is not necessarily one physical screen run. A lab may pool cells from several runs into one aggregation.

## The eight artifacts

| Artifact | File | Scope | Standard says | In this submission |
| --- | --- | --- | --- | --- |
| [Collection metadata](https://github.com/chanzuckerberg/ops-schema/blob/main/standards/ops/0.1.0/collection-metadata.md) | `collection_metadata.yaml` | collection | required | absent |
| [Experimental metadata](https://github.com/chanzuckerberg/ops-schema/blob/main/standards/ops/0.1.0/experimental-metadata.md) | `experimental_metadata.yaml` | aggregation | required | present, 88 of 88 |
| [Perturbation library](https://github.com/chanzuckerberg/ops-schema/blob/main/standards/ops/0.1.0/perturbation-library.md) | `perturbation_library.csv` | aggregation | required | present, 88 of 88 |
| [scFeature table](https://github.com/chanzuckerberg/ops-schema/blob/main/standards/ops/0.1.0/cell-data.md) | `cell_data.parquet` | aggregation | required | present, 88 of 88 |
| [Zarr images](https://github.com/chanzuckerberg/ops-schema/blob/main/standards/ops/0.1.0/zarr-images.md) | `{aggregation}.zarr` | aggregation | required | present, 88 of 88 |
| [Feature definitions](https://github.com/chanzuckerberg/ops-schema/blob/main/standards/ops/0.1.0/feature-definitions.md) | `feature_definitions.csv` | aggregation | optional | present, 88 of 88 |
| [Aggregated data](https://github.com/chanzuckerberg/ops-schema/blob/main/standards/ops/0.1.0/aggregated-data.md) | `aggregated_data.h5ad` | visualization | required | one, in `atlas/` |
| [Example images](https://github.com/chanzuckerberg/ops-schema/blob/main/standards/ops/0.1.0/example-images.md) | `examples.zarr` | visualization | required | one, in `atlas/` |

## How the files join

```
perturbation_library.csv
    barcode           per-sgRNA primary key, unique within the aggregation
    perturbation_id   stable join key, shared by all sgRNAs targeting one gene
        │
        ├─────────────────────────────┐
        ▼                             ▼
cell_data.parquet             aggregated_data.h5ad
    cell_uid  globally unique     obs index = aggregate_id
    barcode                       obs.perturbation_id
    perturbation_id               uns['observation_unit'] names the grouping columns
        │
        ▼
examples.zarr/{channel_combo}/{perturbation_id}/{barcode}/{N}.zarr
```

In the published data `uns['observation_unit']` is `["perturbation_id"]`, so `aggregate_id` is a bare gene symbol and `examples.zarr` nests two levels below the channel combination.

## Layout on S3

Bucket `s3://ops-explorer-public`, anonymous read. Sizes are measured. Comments mark departures from the standard.

```
leonetti_ops/ops_data_portal_submission/
├── v1.0.20260521/                            // superseded
├── v2.0.20260724/                            // the current submission
│   ├── experimental_metadata.yaml            // 4.2 KB, duplicates a per-dataset file
│   ├── examples_subset.zarr/                 // 336 MB; byte-identical to the atlas copy below
│   ├── atlas/                                // visualization artifacts; standard puts these under an aggregation
│   │   ├── aggregated_data.h5ad              // 801 KB; 1052 obs x 66 var; obsm X_umap, X_phate
│   │   ├── perturbation_library.csv          // 335 KB
│   │   ├── feature_definitions.csv           // 5.1 MB
│   │   ├── examples.zarr/                    // 57 channel_combo / 1052 perturbation / 1-10 barcode / N.zarr
│   │   ├── examples_subset.zarr/             // 3 channel_combo x 5 perturbation, for quick inspection
│   │   └── cell_features/                    // 57 h5ad, 2 GB to 28 GB each; per-cell features, not in the standard
│   └── datasets/                             // container level; the standard has no equivalent
│       └── Biohub_OPS0001 ... Biohub_OPS0088/
│           ├── metadata/
│           │   ├── experimental_metadata.yaml   // 4.2 KB; identical across datasets except title
│           │   ├── perturbation_library.csv     // 335 KB; byte-identical across all 88
│           │   └── feature_definitions.csv      // 357 KB; differs per dataset
│           ├── cell_data.parquet                // ~36 MB; 831,587 rows in OPS0001
│           └── Biohub_OPS00NN.zarr/             // 650 GB, 3,088 objects
├── atlas_reformatted/                        // partial reshape toward the standard
├── atlas_reformatted_map_anno_update_14082026/
└── CROPseq/                                  // 2 h5ad at 281 MB each
```

The 88 datasets screen the same 1052-gene library and differ in what they image. OPS0001 carries `5xUPRE` and `ER, SEC61B`, OPS0044 `lysosome, LysoTracker live-cell dye`, OPS0087 `intermediate filaments, VIM`, OPS0088 an eight-channel Cell Painting panel across two rounds. Channel counts run from 5 to 12. The marker is recorded only in the image store's `channels_metadata`, not in `experimental_metadata.yaml`.

## Inside one image store

OME-NGFF 0.5 HCS plate, Zarr v3, one stitched field of view per well.

```
Biohub_OPS0001.zarr/
├── zarr.json                        // ome.plate: row A, columns 1-3, field_count 1
│                                    // channels_metadata: name, index, channel_type, biological_annotation
└── A/{1,2,3}/0/
    ├── zarr.json                    // ome.multiscales (5 levels), custom_metadata, clims_per_level
    ├── 0/ ... 4/                    // level 0 is [1, 6, 1, 104650, 105144] float32, 0.325 um/px
    │                                // shard 13312^2, inner chunk 512^2, blosc/zstd bitshuffle
    └── labels/
        ├── zarr.json                // ome.labels lists 11 to 12 segmentation groups
        ├── nuclear_seg/             // plus cell_seg, gfp_seg, mcherry_seg, focus3d_tubular_seg,
        │   ├── zarr.json            // phase2d_vesicular_seg, nucleoli_focus3d_seg, ...
        │   └── 0/ ... 4/            // int32, shard 16384^2, inner chunk 512^2, zstd
        └── iss_gene_image/          // also iss_guide_image, grid_overlay: RGBA overlays,
                                     // is_ome_label false, absent from ome.labels by design
```

Axes are `(T, C, Z, Y, X)` with T and Z of length 1. The five levels are 2x downsamples: 0.325, 0.65, 1.3, 2.6 and 5.2 um/px.

Three directories under `labels/` are deliberately not in `ome.labels`: `iss_gene_image` and `iss_guide_image` are RGBA overlays of the in-situ sequencing calls, and `grid_overlay` marks the pre-stitch tile grid. They carry `custom_metadata` with `is_ome_label: false`. The standard says readers ignore anything not listed, so treat them as viewer extras. They are worth having anyway: in a 1024² window at level 0 the guide overlay covers 6.7% of pixels and the gene overlay 4.6%.

The overlays are shaped `(Y, X, 4)` uint8, sharded at 32768² with 1024² inner chunks, and their level-0 arrays declare five `dimension_names` for three dimensions. That last part violates the Zarr v3 spec and makes zarr-python refuse to open them, so any reader needs to repair the metadata first. `fetch_ops_subset.py` does this with a store wrapper.

Each segmentation group carries a `segmentation_metadata` block alongside `ome.multiscales`, with `label_name`, `annotation_type`, `is_ome_label`, the `source_channel` it was computed from, a `biological_annotation`, the segmentation `method` and `version`, and cell counts.

Sharding is why windowed reads work. A 512x512 inner chunk is an addressable byte range inside a 13312x13312 shard, so pulling a window costs the window, not the shard. See `fetch_ops_subset.py`.

## Table schemas as published

### `cell_data.parquet`, 10 columns

Identity and position only. No morphology features: those live in `atlas/cell_features/*.h5ad`.

| Column | Type | Note |
| --- | --- | --- |
| `plate` | string | equals the aggregation name |
| `well_row`, `well_col` | string, int64 | `A`, `1` |
| `tile` | int64 | pre-stitch tile index |
| `x`, `y` | double | centroid in stitched-well pixels |
| `cell_uid` | string | `{plate}_{well}_{tile}_{n}` |
| `barcode` | string | joins `perturbation_library.barcode` |
| `perturbation_id` | string | joins `perturbation_library.perturbation_id` |
| `bounding_box` | string | `"(y0, x0, y1, x1)"` in stitched-well pixels |

`bounding_box` is a string, not a struct, and the order is Y first. In OPS0001 row 0, `x=423.7` sits inside `363..505` and `y=47433.6` inside `47379..47517`.

### `perturbation_library.csv`, 4211 rows

`perturbation_id`, `gene_id` (Ensembl), `gene_symbol`, `barcode`, `role`, `control_type`, `protospacer_sequence`, `protospacer_adjacent_motif`. 4000 targeting rows over 1000 genes, plus 211 control rows in 52 non-targeting groups (`NTC_grp1` and up). 1052 `perturbation_id` values in total. Byte-identical in all 88 datasets.

### `feature_definitions.csv`, 2935 rows

`feature_id`, `feature_name`, `feature_type`, `compartment`, `channel`, `unit`, `software`, `version`. Example row: `cell_area`, shape, cell, um^2, OrganelleProfiler.

### `atlas/aggregated_data.h5ad`, 1052 x 66

`obs` carries `perturbation_id`, `gene_id`, `n_cells`, `n_experiments`, and paper cluster labels at two resolutions. `obsm` has `X_umap` and `X_phate`. `uns` has `observation_unit`, `default_embedding`, `schema_version` 0.1.0, PCA and leiden parameters at 13 resolutions. `var` is 66 consensus PCA components, which are not documented in `feature_definitions.csv`.

## Where the data departs from the standard

The standard's expected tree is:

```
{collection_root}/
├── collection_metadata.yaml
└── {aggregation_name}/
    ├── metadata/{experimental_metadata.yaml, perturbation_library.csv, feature_definitions.csv?}
    ├── cell_data.parquet
    ├── visualizations/{visualization_id}/{aggregated_data.h5ad, examples.zarr}
    └── {aggregation_name}.zarr
```

Differences to plan around:

1. No `collection_metadata.yaml` anywhere in the submission.
2. Aggregations sit under `datasets/`, not at the collection root.
3. No aggregation has a `visualizations/` directory. The single visualization lives in a sibling `atlas/` directory, and its embedding is a consensus across all 88 screens rather than a view of any one of them.
4. Label pyramid levels 1 and up carry no `dimension_names`, so `ome-zarr-models` rejects the label groups and, through them, the parent image group. Level 0 is fine. All 88 stores.
5. `cell_data.parquet` uses 32 retired HGNC symbols where `perturbation_library.csv` uses current ones, so those cells do not join. Same 32 in all 88 datasets: `AARS`, `ADSS`, `ASNA1`, `CARS`, `DARS`, `EPRS`, `GARS`, `HARS`, `H2AFX`, `HIST1H2AI` and others of that kind.
6. Extra files inside the submission: `*.zarr.migration_preflight.json` in 11 datasets, and `cell_data_fixed.parquet` plus `cell_data_schema.yaml` in OPS0043, OPS0077 and OPS0088. In OPS0088 the `_fixed` file is 60 MB against 25 MB for `cell_data.parquet` and nothing marks which is authoritative.

Points 1 to 3 are layout. Points 4 and 5 change what a reader has to do.

## Validating a copy yourself

The standard ships a validator in the same repository. It reads `zarr.json` files only, never chunk data, so the 1.2 MB metadata mirror from `fetch_ops_artifacts.py` validates the same as the 650 GB store.

```bash
uv pip install "ops-schema-validator @ git+https://github.com/chanzuckerberg/ops-schema#subdirectory=validator"
ops-validate data/Biohub_OPS0001/Biohub_OPS0001.zarr -t zarr
ops-validate data/Biohub_OPS0001/metadata/experimental_metadata.yaml -t experimental
```

Artifact types are `collection`, `experimental`, `perturbation`, `features`, `cell-data`, `aggregated` and `zarr`. Omitting `--type` treats the path as a whole submission directory, which needs the standard's layout to work.

Do not point the validator at `atlas/examples.zarr` without a leaf path. Store discovery would walk roughly 57 x 1052 x 4 x 10 crop stores.
