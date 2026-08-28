# WS3: Uncertainty quantification for Cell Painting

**Lead:** [@hanyangii](https://github.com/hanyangii)

A classifier trained on Cell Painting features will assign a mechanism of action to any compound you hand it, including compounds whose mechanism it has never seen, and nothing in its output says which calls to trust. Yunhee has a tutorial notebook that trains an MLP on JUMP profiles with [lightning-uq-box](https://github.com/lightning-uq-box/lightning-uq-box) and compares a deterministic classifier against Monte Carlo dropout. That is the starting point.

- WS3A) Which methods are worth the effort? Conformal prediction wraps an already-trained classifier, is post-hoc and cheap, and returns a coverage guarantee. lightning-uq-box needs retraining and gives an epistemic/aleatoric split. Run both on the same model and report what each costs.
- WS3B) Are the uncertainties any good? Calibration (ECE, Brier, NLL), whether uncertainty ranks errors (accuracy–rejection curves), coverage and set size for conformal methods. This needs splits that are not trivially leaky: replicate wells of the same compound must not straddle train and test, and holding out a whole imaging site is harder and more interesting than holding out wells.
- WS3C) Does uncertainty rise where the model should struggle? Batch correction is known to fail across many compounds and several microscope types, some phenotypes are too weak to separate from controls, and MoA annotations are incomplete with many compounds hitting more than one target. If uncertainty tracks those cases it is diagnostically useful.
- WS3D) What should an uncertainty column in `.obs` mean? scverse tools already write per-cell confidence and no two mean the same thing: scArches writes one minus the top kNN vote, CellTypist the maximum of a sigmoid, popV a count of agreeing classifiers, Scyan a log-probability with NaN for rejections. This is the scverse-shaped piece of the workstream.

### Requirements
- [x] Starting notebook, and three labelled datasets at three sizes (below)
- [x] No GPU needed: the 74k-parameter MLP does 300 epochs on 770 wells in ~3 s on a laptop CPU, and all 111,803 wells in ~2 min
- [ ] **A label set with real class sizes.** JUMP-MOA caps at two compounds per class, so you cannot hold a compound out and still have the class. Drug Repurposing Hub ∩ JUMP gives 249 classes with ≥5 compounds.
- [ ] Decide what to do with the 358 compounds carrying several pipe-separated mechanisms, and the 42 % of classes with a single compound
- [ ] Fix the two snags in the notebook: `ad.X.toarray()` fails because `X` from a DataFrame is already dense, and the two models train at different learning rates so they are not a controlled comparison

### Deliverable
- A calibration and coverage comparison of one Bayesian and one conformal method on the same trained model, under a compound-held-out split, plus a proposed convention for the `.obs` column and a helper that produces it from an AnnData with a label column.

### Stretch goal
- The site-held-out split, and whether uncertainty tracks the known batch-correction failures.

## Test dataset

### Option A — JUMP compound profiles, cpg0016 (2.8 GB)

The largest public Cell Painting resource: 803,853 wells over 10 imaging sites, one row per well.

```python
import polars as pl
url = ("https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/"
       "workspace/profiles_assembled/COMPOUND/v1.0/profiles_var_mad_int_featselect_harmony.parquet")
data = pl.scan_parquet(url)
```

|                       |                                                                                                                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Rows                  | one well; 10 sources, 1,713 plates, 115,795 compounds                                                                                                                                           |
| Features              | `X_1 … X_737`, Harmony-corrected embeddings — not named CellProfiler features                                                                                                                   |
| Suffixes              | `var` drop invariant features, `mad` per-plate robust z-score, `int` rank inverse normal transform, `featselect` variance and correlation filtering, `harmony` batch correction keyed on source |
| Interpretable variant | `profiles_var_mad_int.parquet`, 12.1 GB, 3,180 named features — the pair makes a natural experiment for whether uncertainty is a property of the representation or of the correction            |

JUMP ships no MoA annotations, so labels have to come from somewhere else:

|                             | Compounds | Classes | ≥5 compounds | ≥10 |
| --------------------------- | --------- | ------- | ------------ | --- |
| Drug Repurposing Hub ∩ JUMP | 4,159     | 927     | 249          | 116 |
| JUMP-MOA                    | 90        | 47      | 0            | 0   |

`pertpy.metadata.Moa().annotate(adata, query_id="perturbation")` fetches the Repurposing Hub annotations into `.obs["moa"]` and `.obs["target"]` in one call.

⚠️ JUMP-MOA is the label set the notebook uses. Its three-class subset is 5 compounds and 770 wells, one class (DYRK inhibitor) being a single compound, and a random split over wells leaves 100 % of validation compounds and plates in training. See Requirements above.

Other things to know: the parquet is a single row group, so a filtered scan still pulls most of 2.8 GB — download once and cache the subset. 84 % of the JUMP-MOA-labelled subset is DMSO.

### Option B — LINCS Cell Painting, cpg0004 (20 MB)

1,571 compounds in A549 at six doses, one lab, two batches, MoA-annotated from the Repurposing Hub (Way et al. 2022). Enough compounds per class for compound-held-out evaluation, and small enough to iterate on.

```bash
git clone --depth 1 https://github.com/broadinstitute/lincs-cell-painting
# consensus/2016_04_01_a549_48hr_batch1/*_consensus_modz_feature_select_dmso.csv.gz   one row per compound-dose
# metadata/moa/repurposing_info_external_moa_map_resolved.tsv                          labels
```

Well-level spherized profiles (383 MB, Git LFS) are there if replicates are needed rather than consensus.

### Option C — BBBC021 per-well profiles (2.9 MB)

632 wells × 516 CellProfiler features (Ljosa et al. 2013), 12 MoA classes, the classic leave-one-compound-out benchmark. Same images as WS1's Option A, so the two workstreams can share ground truth. Half its MoA assignments were made visually.

```bash
curl -O https://data.broadinstitute.org/bbbc/BBBC021/BBBC021_v1_moa.csv
curl -LO https://github.com/cytomining/cytominergallery/raw/master/inst/extdata/ljosa_jbiomolscreen_2013_per_well_mean.csv.gz
```

## Reference: the starting notebook, and what exists elsewhere

The notebook loads the cpg0016 parquet, joins JUMP-MOA labels through `broad_babel`, builds an `AnnData` of 111,803 × 737, subsets to three MoAs (770 wells), runs PCA, then trains `DeterministicClassification` and `MCDropoutClassification` on a 737 → 100 → 3 MLP with dropout 0.2 and 25 MC samples. `predict_step` returns `pred` and `pred_uct`; the last two figures are uncertainty per class split by correctness, and an uncertainty surface over a PCA grid.

This has barely been attempted on Cell Painting. The one published example is Ha et al. 2024, who calibrated an MLP ensemble with Mondrian conformal prediction to get an explicit "uncertain" class — internal Janssen data, binary task, no code. Nothing in the field reports calibration error or ensemble variance, and the 2026 field review does not mention uncertainty at all. What is used instead answers a different question: anomaly scores against DMSO, or permutation p-values on retrieval (`copairs`). Conformal prediction has a decade of use in cheminformatics and is cheap and post-hoc, which makes it the obvious thing to try alongside the Bayesian methods; `conformalized_single_cell_annotator` already established an AnnData convention for it, `obs["prediction_sets_0.05"]`. A fuller survey with citations is in `tasks/uq_cellpainting_plan.md`.

## Getting Started

- lightning-uq-box 0.3.0 needs Python ≥ 3.12 and pulls torch, lightning, gpytorch and laplace-torch — use the CPU torch index. Add `anndata`, `scanpy`, `polars`, `scikit-learn`, and `mapie` or `torchcp`.
- Run the notebook unchanged first so everyone has seen the baseline. Then change one thing at a time and keep the model fixed: group the split by compound, then by source, add a calibration metric, add a conformal wrapper around the same trained model.
- Move to a label set with real class sizes once the machinery works — three classes and five compounds cannot tell us whether anything generalises.
- Whatever survives should end up as a function that takes an AnnData and returns one.

This workstream suits people who do ML and want a well-posed evaluation problem. The dataset section below will save you a day; read it before downloading anything.

## Relevant Resources

- [lightning-uq-box](https://lightning-uq-box.readthedocs.io/) · [MAPIE](https://mapie.readthedocs.io/) · [TorchCP](https://github.com/ml-stat-Sustech/TorchCP)
- [JUMP datasets](https://github.com/jump-cellpainting/datasets) · [lincs-cell-painting](https://github.com/broadinstitute/lincs-cell-painting) · [BBBC021](https://bbbc.broadinstitute.org/BBBC021)
- [pertpy metadata](https://pertpy.readthedocs.io/en/latest/api/metadata_index.html) · [copairs](https://github.com/cytomining/copairs)
- [Ha et al. 2024](https://doi.org/10.1038/s41598-024-75401-5) — conformal prediction on Cell Painting
- [Theunissen et al. 2024](https://doi.org/10.1093/bioinformatics/btae128) — reject options and accuracy–rejection curves
- [Arevalo et al. 2024](https://doi.org/10.1038/s41467-024-50613-5) — where batch correction fails
