# WS6: Classical single-cell tooling on morphology data

**Lead:** [@timtreis](https://github.com/timtreis) — co-lead wanted, someone fluent in `pertpy` internals.

`pertpy` was built for transcriptomics, but almost nothing in it is intrinsically about genes: a Cell Painting experiment produces the same shape of object, a perturbation × feature matrix with plate/well/batch structure and negative controls. Calling these functions on morphology is trivial. Knowing which of their assumptions survive is not.

- WS6A) Which parts of the stack transfer? For each capability, decide whether it applies as-is, needs adaptation, or is meaningless on morphology, and whether `scmorph` already does it. Candidates: distance metrics, `Mixscape`, `Augur`, `Milo`, `scGen`/`CPA`, differential expression reinterpreted as differential feature abundance. `Mixscape` is the clearest gap, since guide-efficiency filtering has an obvious optical-pooled-screening analogue that neither `scmorph` nor `pycytominer` offers.
- WS6B) Do the measures of perturbation strength agree? Image-based profiling ranks compounds with mAP (`copairs`), `pertpy` uses distance-based tests (E-distance, MMD), `scmorph` uses Mahalanobis and t-statistic distances to control. Nobody has put the three side by side. Prior work on this data found `copairs` calling ~88 % of Target-2 compounds active while ~30 % of those sat mixed with the DMSO cluster, Mahalanobis separating them far more convincingly, and the `copairs` p-values poorly calibrated.
- WS6C) Does aggregation change the answer? The metrics are defined on aggregated profiles, `pertpy`'s distance tests live at single-cell level, and nobody has checked whether the ranking survives the move. This bears on whether single-cell morphology is worth its storage and compute.
- WS6D) What breaks, and why? Morphology features are correlated, scale-heterogeneous, and engineered rather than counted. No counts means no negative binomial, normalisation is per-plate against DMSO rather than library size, aggregation is to the well rather than a cell type. This means reading `pertpy`'s source to find where those assumptions are baked in.

### Requirements
- [x] Both data levels public and small (below)
- [x] `scmorph` implementations available as comparators
- [ ] **The WS6B decision rule, written down before any numbers are produced.** For example: disagreement if Spearman ρ between two rankings falls below 0.7, or if more than 10 % of compounds are called active by one method and inactive by another. Without it this becomes plots and a shrug.
- [ ] Co-lead who can read `pertpy` source, for WS6D

### Deliverable
- The WS6B benchmark at both levels, one figure, and a named list of compounds where the methods disagree.

### Stretch goal
- The WS6A triage table, and a function that takes an AnnData and returns one. If the metrics genuinely disagree, a blog post or scverse note rather than a paper. Under six people, drop WS6A and keep the benchmark.

## Test dataset

Both levels come from the same plate, so the WS6C comparison is controlled.

```bash
# well level — 384 wells, pycytominer-normalised, 13 MB
aws s3 cp --no-sign-request \
  s3://cellpainting-gallery/cpg0016-jump/source_4/workspace/profiles/2021_04_26_Batch1/BR00117035/BR00117035.parquet .

# single-cell level — per-object CellProfiler output, ~7.8 MB per well-site
aws s3 cp --no-sign-request --recursive \
  s3://cellpainting-gallery/cpg0016-jump/source_4/workspace/analysis/2021_04_26_Batch1/BR00117035/analysis/ \
  ./sc/ --exclude "*" --include "BR00117035-A0[1-3]-*"     # ~30 well-sites, ~250 MB
```

Each well-site directory holds `Cells.csv`, `Cytoplasm.csv` and `Nuclei.csv` at about 2.4 MB each, plus `Image.csv` and `Experiment.csv`. A plate is 3,456 well-sites, so never sync one. [WS1](../ws1_cellprofiler_x_scverse/)'s `cp2adata` will read these into `AnnData`; until it exists, load them directly.

`scmorph.datasets.rohban2017()` is a one-call alternative for a first cell, and WS3 uses the assembled cross-source profiles (`cpg0016-jump-assembled/source_all/…`, 2.8 GB) if this needs to scale past one plate. No GPU needed.

## Reference: what already exists

[`scmorph`](https://github.com/edbiomedai/scmorph) (Wagner, Warden, Khamseh & Beentjes, Edinburgh; [JOSS, Aug 2025](https://joss.theoj.org/papers/10.21105/joss.08324); MIT; v0.4.0) is AnnData-native and has already made many of these adaptation decisions. It is our comparator and a source of prior reasoning, not something we contribute to.

|                      |                                                                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Distances to control | `pp.aggregate_mahalanobis`, `pp.tstat_distance`, `pp.aggregate_ttest`, `pp.aggregate_pc`                                            |
| Hit calling          | `tl.get_ks` (KS statistic)                                                                                                          |
| Feature selection    | `pp.select_features`, `pp.corr_features` — Pearson, Spearman and Chatterjee's ξ (Lin & Han 2023), the last for non-linear correlation |
| Batch correction     | `pp.remove_batch_effects`, `pp.scale_by_batch`                                                                                      |
| Scope limit          | continuous, non-radial features only; trajectory inference shells out to R                                                          |

Its `docs/notebooks/` are worth an hour before designing our comparison. `correlation_comparison`, `why_scone`, `hit_calling` and `scalability` are explicit justifications of method choices, and the cheapest way to avoid a comparison someone has already shown to be uninformative.

`scmorph` shipped Mahalanobis as a first-class method independently of the prior work quoted in WS6B. Two groups converging on the same correction is why WS6B is a real question rather than a tooling exercise.

## Getting Started

- WS6A first if it runs at all, timeboxed to Wednesday afternoon. A triage table is cheap and tells the group where the remaining time should go.
- Start from the 13 MB parquet. It needs no conversion and works even if the cluster does not.
- Write the WS6B decision rule down before producing any numbers.

This workstream suits people who know the single-cell perturbation stack and have never touched Cell Painting. Not knowing the imaging side is an advantage here, since assumption violations are easier to spot from outside.

## Relevant Resources

- [pertpy](https://pertpy.readthedocs.io/) · [scanpy](https://scanpy.readthedocs.io/en/stable/) · [AnnData](https://anndata.readthedocs.io/en/latest/)
- [scmorph](https://github.com/edbiomedai/scmorph) · [docs](https://scmorph.readthedocs.io) · [JOSS paper](https://joss.theoj.org/papers/10.21105/joss.08324)
- [pycytominer](https://pycytominer.readthedocs.io/) · [copairs](https://github.com/cytomining/copairs)
- Lin & Han (2023) — Chatterjee's ξ, implemented as `scmorph.pp.correlation.xim`
