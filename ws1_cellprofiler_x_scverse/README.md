# WS1: Analysing CellProfiler output with scverse

**Lead:** [@timtreis](https://github.com/timtreis)

CellProfiler is where most Cell Painting data starts and scverse is where we would like it to end up. The conversion between them gets reimplemented in every lab and has never been specified.

- WS1A) Which export settings are worth recommending? CellProfiler ships two export modules, `ExportToSpreadsheet` and `ExportToDatabase`, and between them they emit very different things depending on configuration. We install CellProfiler and export the same test plate several ways, then compare. This is a domain question rather than a programming one, and it is what everything else here depends on.
- WS1B) What should the object look like? A spec covering which output lands in `.X`, `.obs`, `.var` and `.uns`, how the plate/well/site hierarchy is represented, and how channel and object identity are encoded in feature names. Then `cp2adata` built against it.
- WS1C) How do images and masks fit? The same data as a `SpatialData` object, contributed as a reader to [`spatialdata-io`](https://github.com/scverse/spatialdata-io) rather than a new package. It reuses `cp2adata` for the table so the column parsing exists once.
- WS1D) Can we skip the conversion entirely? An `ExportToAnnData` module writes the object straight out of the pipeline, with metadata still in scope instead of reconstructed from directory names afterwards.

### Decided
- One row per cell. `Cells`, `Cytoplasm` and `Nuclei` are columns of the same observation, not separate objects, because they describe one cell and should be analysed together.
- The compartment lives in the feature name and is parsed into structured `.var` columns alongside family, measurement, channel and parameter. `var_names` stay verbatim as the index so a mis-parse is visible rather than destructive.
- Primary object configurable, defaulting to a join at the cell.
- Global object ID `plate_well_site_objectnumber`. `ImageNumber` is only unique within a run and collides on concatenation.
- Single-cell rows. Aggregation belongs to `pycytominer` or [WS6](../ws6_perturbation_tooling/).
- Home: a new repo under the scverse org.

### Requirements
- [x] Test plate with real plate metadata (below)
- [x] `spatialdata-io` has an established `readers/` pattern to follow
- [x] `CellProfiler-plugins` accepts drop-in modules in `active_plugins/`
- [ ] **The 1:N encoding.** `RelateObjects` lets a cell have two nuclei or none. We keep all of it, probably as `..._nucleus<n>_...`, but that makes the feature space ragged across cells and a fixed `.var` cannot express it. **Settle this first and error loudly on 1:N input until it is settled.**
- [ ] CellProfiler installed on every laptop in the group
- [ ] `scverse/cp2adata` repo created
- [ ] Validator library chosen (pydantic or pandera)

### Deliverable
- `scverse/cp2adata` reading pooled `ExportToSpreadsheet` CSVs and the Cell Painting Gallery per-site layout, with `SPEC.md` and a machine-checkable validator.

### Stretch goal
- A `spatialdata-io` PR and a working `ExportToAnnData` module. Under-staffed, drop them in that order.

## Test dataset

We run CellProfiler ourselves, so what we need is raw images and trustworthy plate metadata.

### Option A — BBBC021, one 96-well plate (839 MB)

```bash
curl -O https://data.broadinstitute.org/bbbc/BBBC021/BBBC021_v1_images_Week1_22123.zip
curl -O https://data.broadinstitute.org/bbbc/BBBC021/BBBC021_v1_image.csv   # 4.0 MB, per-image metadata
curl -O https://data.broadinstitute.org/bbbc/BBBC021/BBBC021_v1_moa.csv     # 4.4 kB, MOA ground truth
```

|                |                                                                                                 |
| -------------- | ----------------------------------------------------------------------------------------------- |
| Plate format   | 96-well, wells `B02`–`G11` — the 60 interior wells, outer ring not imaged                       |
| Fields         | 4 sites/well, 240 fields, 720 16-bit TIFFs                                                      |
| Channels       | 3 — DAPI, Tubulin, Actin                                                                        |
| Perturbations  | 7 compounds including DMSO, 49 compound–dose combinations on this plate                         |
| Phenotypes     | taxol (14 wells), aphidicolin, cytochalasin B, nocodazole (8 wells each)                        |
| Labels         | 5 MOAs over 14 of 49 treatments here; 12 MOAs over 103 treatments dataset-wide                  |

`BBBC021_v1_image.csv` is already CellProfiler-native (`ImageNumber`, `Image_FileName_<Channel>`, `Image_Metadata_Plate_DAPI`, `Image_Metadata_Well_DAPI`, `Replicate`, `Image_Metadata_Compound`, `Image_Metadata_Concentration`), so it converts almost directly into a `LoadData` CSV and then into `.obs`.

MOA labels are sparse: only 104 of 906 compound–dose combinations carry one, and the median plate has 3 MOAs over 6 labelled treatments. `Week1_22123` is above median. `Week3_25421`, `Week3_25441` and `Week3_25461` are the richest at 6 MOAs over 22 of 50 treatments.

⚠️ Three channels, not five. BBBC021 predates the Cell Painting assay (Caie et al. 2010), so a stock 5-channel pipeline will not run on it unmodified. Images © AstraZeneca; cite Caie et al. (2010) and Ljosa et al. (2012). The same images are mirrored as `cpg0010-caie-drugresponse/broad-az/` in the Cell Painting Gallery.

### Option B — real 5-channel Cell Painting, one well (~110 MB)

```bash
aws s3 cp --no-sign-request --recursive \
  s3://cellpainting-gallery/cpg0036-EU-OS-bioactives/FMP/images/2023_02_15_Batch1_U2OS/images/U2OSB1001R1__2023-02-15T15_21_49-Measurement_1/Images/ \
  ./raw/ --exclude "*" --include "r01c01*-ch[1-5]*"
```

Filenames are `r<row>c<col>f<field>p<plane>-ch<channel>sk1fk1fl1.tiff`, so subsetting is a glob. Never sync a plate: `cpg0036` is 26 GB (13,824 TIFFs) and `cpg0016`/`cpg0000` are 67 GB (27,648). `cpg0036` is EU-OPENSCREEN bioactives from FMP, both co-organisers of this hackathon.

### Pipelines

Neither source ships one we can use as-is. Start from `cpg0000-jump-pilot/source_4/workspace/pipelines/` or [`2023_Cimini_NatureProtocols`](https://github.com/carpenter-singh-lab/2023_Cimini_NatureProtocols). Adapting a 5-channel pipeline down to BBBC021's 3 channels is a small task worth deciding on early.

## Reference: what the output looks like at scale

The Cell Painting Gallery publishes the full CellProfiler chain next to the images, and requires contributed datasets to use it (`analysis`, `backend`, `load_data_csv`, `metadata`, `profiles` under `workspace/`). Measured for `cpg0016-jump/source_4`, batch `2021_04_26_Batch1`, plate `BR00117035`, 384-well with 9 sites:

| Level                  | Path under `workspace/`                                                                                                       | Size              |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| Pipeline input         | `load_data_csv/<batch>/<plate>/load_data_with_illum.csv`                                                                        | 8.5 MB            |
| Per-object CSVs        | `analysis/<batch>/<plate>/analysis/<plate>-<well>-<site>/` → `Cells.csv` 2.5 MB, `Cytoplasm.csv` 2.4, `Nuclei.csv` 2.4, `Image.csv` 0.11, `Experiment.csv` 0.36, plus outline PNGs | ~7.8 MB per well-site |
| Merged single-cell     | `backend/<batch>/<plate>/<plate>.sqlite`                                                                                        | 16.4 GB           |
| Aggregated wells       | `backend/<batch>/<plate>/<plate>.csv`                                                                                           | 55.8 MB           |
| Normalised profiles    | `profiles/<batch>/<plate>/<plate>.parquet`                                                                                      | 13.2 MB           |

That table is the shape of the problem: three per-object tables keyed on object number, one per-image table, the plate/well/site hierarchy in directory names rather than in the files, and two aggregation levels layered on top.

There are three shapes in the wild and a useful spec spans them. A naive local run writes `<prefix>_Cells.csv` pooled over the whole run, or one SQLite with `Per_Image`/`Per_Object`, with plate identity only inside `Image_Metadata_*` columns. The Gallery layout puts the hierarchy in directory names. Downstream tooling reads aggregated `backend/*.csv` and pycytominer `profiles/*.parquet`. The invariant is the object tables plus a plate/well/site key, except the key moves between the filesystem and the columns depending on who ran it.

For WS1D, the introspection already exists: every module implements `get_measurement_columns(pipeline)` and `pipeline.get_measurement_columns()` aggregates them. `ExportToDatabase` builds its entire SQL schema this way, `exporttospreadsheet.py:683` picks its columns the same way, and `pipeline.get_provider_dictionary("objectgroup")` enumerates upstream object names. Modules accumulate in `run(workspace)` and write once in `post_run(workspace)`.

⚠️ The hard part of WS1D is distributed writes. CellProfiler processes image sets one at a time and, at plate scale, across parallel workers. A database takes incremental inserts; `AnnData` wants a whole matrix. Either accumulate in memory, which is fine for one plate and hopeless for a screen, or write zarr-backed incrementally.

## Getting Started

- WS1A → WS1B → WS1D is a dependency chain. `cp2adata` works on all existing CellProfiler output, version-independent, while the plugin only helps data generated after people adopt it. Once the spec exists, `ExportToAnnData` reduces to wiring it into `post_run`.
- Install CellProfiler first thing and export the test plate a few ways. Comparing real outputs answers most of WS1A.
- Settle the 1:N encoding before writing the reader.
- WS1C can start in parallel once the `.var`/`.obs` contract is fixed.
- Worth an hour first: `pycytominer` for the incumbent conventions, and `spatialdata-io`'s readers as the pattern to follow.

This workstream suits anyone who runs CellProfiler in practice. WS1A needs practitioner judgement and no code. No machine learning anywhere.

## Relevant Resources

- [CellProfiler](https://cellprofiler.org/) · [CellProfiler-plugins](https://github.com/CellProfiler/CellProfiler-plugins)
- [AnnData](https://anndata.readthedocs.io/en/latest/) · [scanpy](https://scanpy.readthedocs.io/en/stable/) · [SpatialData](https://spatialdata.scverse.org/) · [spatialdata-io](https://github.com/scverse/spatialdata-io)
- [pycytominer](https://pycytominer.readthedocs.io/) · [BBBC021](https://bbbc.broadinstitute.org/BBBC021) · [Cell Painting Gallery](https://broadinstitute.github.io/cellpainting-gallery/)
