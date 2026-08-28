# WS2: Optical pooled screens in scverse

**Lead:** [@LucaMarconato](https://github.com/LucaMarconato)

An OPS experiment pairs a phenotypic imaging round with several rounds of in-situ sequencing that assign a guide to every cell, so the natural target is one `SpatialData` object holding images, masks and the per-cell table. Nobody does this today: every OPS toolkit ships its own storage layer, and SpatialData has no notion of a sequencing cycle.

- WS2A) How should sequencing cycles be represented? SpatialData images are `(c, y, x)` or `(c, z, y, x)`, so there is no cycle axis, and each cycle carries its own registration transform. Three options exist in the wild: stack cycles into the channel axis as `cycle03_G`, one image element per cycle sharing a coordinate system, or the OME-NGFF plate spec's one image per acquisition per well.
- WS2B) What happens at screen scale? A 384-well plate at 12 cycles is thousands of image elements before tiles, and the plate/well hierarchy has no representation in SpatialData at all — element names cannot contain a slash.
- WS2C) Which scverse tools earn their place once the data is in? `squidpy.experimental.im.calculate_image_features` for cp_measure features, pertpy and copairs for guide-level statistics, spatialdata-plot and napari-spatialdata for inspection. Is the round trip better than what the OPS pipelines already do?

### Requirements
- [x] A small screen with phenotype round, sequencing cycles and guide library (Option A)
- [x] SCALLOPS storage layer is ~1,000 lines across ~50 call sites, small enough to replace in three days
- [ ] **Confirm SCALLOPS co-installs with `spatialdata`.** It needs Python ≥ 3.12 and pulls tensorflow, itk-elastix and stardist. First thing to find out.
- [ ] Decide where the code lands: a `spatialdata-io` reader, a SCALLOPS storage backend, or a new package

### Deliverable
- A SpatialData representation of one OPS tile series that survives a full SCALLOPS run, plus a written verdict on WS2A with the constraints that forced it.

### Stretch goal
- SCALLOPS reading and writing a SpatialData store, with its own test suite passing against it.

⚠️ SCALLOPS and scPortrait are Linux/macOS only. Windows users cannot run this workstream natively.

## Test dataset

### Option A — SCALLOPS `feldman_2019_small()` (~756 MB)

[SCALLOPS](https://github.com/Genentech/scallops) is Genentech's OPS toolkit and the most complete open pipeline. It ships a small dataset its CLI, tests and notebooks already run on.

```python
from scallops.datasets import feldman_2019_small
path = feldman_2019_small()   # pooch download on first call
```

|          |                                                                                                                                                                                                                          |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Content  | 2 tiles (A1 Tile-102, Tile-103) × 9 sequencing cycles, one phenotype acquisition, `barcodes.csv`                                                                                                                         |
| Source   | Feldman et al. 2019, HeLa p65 translocation screen                                                                                                                                                                       |
| Pipeline | the [example commands](https://scallops.readthedocs.io/en/latest/example_commands.html) run illumination correction → stitching → elastix registration → segmentation → spot detection → base calling → features → merge |

### Option B — Brieflow small test data (1.4 GB)

```bash
curl -L -o small_test_data.zip https://zenodo.org/records/15276612/files/small_test_data.zip
```

ND2 files from the Cheeseman lab: 1 plate, wells A1 and A2, 3 sequencing tiles × 11 cycles, 3 phenotype tiles, a 20,445-guide library. Runs through the [Brieflow](https://github.com/cheeseman-lab/brieflow) Snakemake workflow in ~15 minutes, producing TIFFs and parquet rather than zarr. A useful second layout for what a general reader must cope with.

### Option C — cpg0021-periscope, a few tiles (Cell Painting Gallery)

A genome-wide screen (Ramezani et al. 2025) in A549 and HeLa: 12 cycles, 316 tiles per well at 10×, over 1,000 at 20×. For the WS2B scale questions.

```bash
# one 10x sequencing tile, cycle 1 (22 MB); loop n=1..12 for the full series
aws s3 cp --no-sign-request \
  "s3://cellpainting-gallery/cpg0021-periscope/broad/images/20200805_A549_WG_Screen/images/CP186A/10X_c1-SBS-1/Well1_Point1_0000_ChannelDAPI,Cy3,A594,Cy5,Cy7_Seq0000.nd2" .
```

Sequencing images live under `10X_c{n}-SBS-{n}/`, phenotype under `20X_CP_{plate}/`. The dataset is 56 TB, so pull tiles, never a plate.

### Option D — CZI OPS data portal

Not usable yet. `chanzuckerberg/ops-schema` scopes raw acquisition images out, and the CZ Biohub OPS Explorer is alpha with no download surfaced (checked 2026-08-28).

## Reference: how cycles are stored today

|                | Cycles                                                                                                                         | Registration                                          | Per-cell table                                   |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- | ------------------------------------------------ |
| SCALLOPS       | `xr.DataArray (t, c, z, y, x)`, cycle on `t` — also used for phenotype modality and for real time in live imaging              | elastix affine + B-spline, text files beside the data | parquet; AnnData-Zarr from `merge --format zarr` |
| Fractal / ngio | one OME-Zarr image per acquisition inside the well (`plate.zarr/B/03/0`, `/1`, …) — the NGFF plate spec's own mechanism        | translations in a per-field ROI table                 | tables under `image.zarr/tables/`                |
| Brieflow       | `(cycle, channel, y, x)` TIFF per tile                                                                                         | applied eagerly, not stored                           | parquet with `cell_barcode_0`, `gene_symbol_0`   |
| spatialdata-io | MACSima stacks rounds into channels (`R3 DAPI`) and records the mapping in a table; the ISS reader takes one pre-aligned stack | one transform per element                             | `TableModel`                                     |

Constraints that shape the answer to WS2A: transforms are per element, so two channels of the same image cannot be aligned differently; `sdata.attrs` takes arbitrary JSON at the root; one table can annotate many label elements via `(region, instance_id)`. OME-NGFF itself allows at most one time axis and one channel-or-custom axis in at most five dimensions.

Background reading: [spatialdata#247](https://github.com/scverse/spatialdata/issues/247) (time axis, closed as not planned), [#398](https://github.com/scverse/spatialdata/issues/398) (nested hierarchies), [spatialdata-io#159](https://github.com/scverse/spatialdata-io/issues/159) (rounds and channels), [ome/ngff#441](https://github.com/ome/ngff/issues/441) (multiple image types per field). A longer survey with citations is in `tasks/ops_spatialdata_plan.md`.

## Getting Started

- Install SCALLOPS and run the example commands on Option A unmodified, keeping the output as a reference.
- Read `scallops/experiment/elements.py` and `scallops/zarr_io.py`. One concrete way into WS2A and WS2B: make SCALLOPS write and read a SpatialData store, splitting and re-stacking the `t` axis at the storage boundary so its processing code is untouched, then run its test suite against the result.
- Everything that has to be worked around is a finding. Collect them as issues with reproducers, not only as code.

This workstream suits people who run OPS, and anyone who wants to stress-test SpatialData against a format it was not designed for.

## Relevant Resources

- [SCALLOPS](https://scallops.readthedocs.io/)
- [SpatialData](https://spatialdata.scverse.org/)
- [OME-NGFF](https://ngff.openmicroscopy.org/0.5/)
- [ngio](https://github.com/BioVisionCenter/ngio)
- [squidpy](https://squidpy.readthedocs.io/) · [pertpy](https://pertpy.readthedocs.io/) · [copairs](https://github.com/cytomining/copairs)
- [Feldman et al. 2019](https://doi.org/10.1016/j.cell.2019.09.016)
