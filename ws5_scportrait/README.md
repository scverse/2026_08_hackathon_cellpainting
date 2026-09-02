# WS5: AI-driven single-cell image phenotyping with scPortrait

**Lead:** [@nik-as](https://github.com/nik-as)

[scPortrait](https://github.com/MannLabs/scPortrait) takes raw microscopy to a per-cell AnnData: `.h5sc` holds a `(cells, channels, height, width)` tensor in `obsm`. Input images and masks sit in an intermediate `SpatialData` store.

- WS5A Agentic AI workflows
	- We will expose the scPortrait workflow to AI agents, enabling end-to-end single-cell image dataset generation from raw microscopy data. Because scPortrait already abstracts this into `stitching`, `segmentation` and `extraction` steps it is an ideal platform to build agentic workflows.
- WS5B Interactive visualization
	- scPortrait defines the AnnData-based `.h5sc` single-cell image storage format. Based on this, we will build a lightweight visualizer of single-cell images on top of image embeddings. FACS-data-like gating will allow visual exploration of datasets.
- WS5C Additional segmentation workflows
	- Implement recent segmentation methods such as segment-anything for microscopy [(SAM)](https://www.nature.com/articles/s41592-024-02580-4)

### Requirements
- [x] Ready-made data ships with the package
- [x] OpenPhenom, CellFlux and MorphoDiff publish weights
- [x] **Pick one of A/B/C on Wednesday morning.** Three directions is one team's worth of scope only if two are dropped.
- [ ] Decide what "the agent's choices were good" means before building WS5C

### Deliverable
- A raw image to `.h5sc` pipeline running on CODEX or Claude Code

### Stretch goal
- Include stitching or featurization

## Getting Started

```bash
pip install scportrait          # Apache-2.0, Python >=3.11, Linux/macOS
```

```python
import scportrait
scportrait.data.autophagosome_h5sc()   # ready-made .h5sc pair, autophagy stimulated/unstimulated
scportrait.data.dataset_1()            # ~44 MB raw images, the walkthrough dataset
scportrait.data.dataset_stitching_example() # A raw image dataset
```

- Work through [A Walk Through The scPortrait Ecosystem](https://mannlabs.github.io/scPortrait/pages/tutorials.html) and the deep-learning tutorial, which builds a PyTorch dataloader straight off a `.h5sc`.
- Read `Project` in `src/scportrait/pipeline/project.py` — `.sdata`, `.h5sc`, and `load_input_from_* → segment → extract → featurize → select` are the whole surface. Extension is by subclassing plus a top-level YAML key named after your class; there is no plugin system.
- `ConvNeXtFeaturizer` (`pipeline/featurization.py`) is a ~110-line template for wiring a new backbone in, and the cleanest thing to copy for WS5A.
- Everything downstream is an AnnData, so scanpy, pertpy and the rest of scverse apply once you have features.

## Reference

### Where scPortrait is today

v1.8.0 on PyPI (May 2026), 110 stars, Apache-2.0, preprint [Mädler, Schmacke et al. 2025](https://doi.org/10.1101/2025.09.22.677590). Segmentation uses Cellpose (pinned `<4`; a `cpsam` adapter is open as PR #406). Featurizers: `CellFeaturizer` (intensity and shape statistics), `MLClusterClassifier` and `EnsembleClassifier` (inference from Lightning checkpoints), `ConvNeXtFeaturizer` (2048-d HuggingFace ConvNeXt embeddings). In-tree models include VGG variants, a convolutional autoencoder and `VAEBase`; one pretrained checkpoint ships.

### What exists elsewhere, and how usable it is

| For  | Option                                                                                   | Usability                                                            |
| ---- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| WS5A | [OpenPhenom](https://huggingface.co/recursionpharma/OpenPhenom)                            | easiest win: channel-agnostic MAE, 1/4/6/11 channels, loads in three lines. Non-commercial licence |
| WS5A | [CellFlux](https://github.com/yuhui-zh15/CellFlux) (MIT, flow matching) · [MorphoDiff](https://github.com/bowang-lab/MorphoDiff) (Apache-2.0, latent diffusion) | both publish weights                                                  |
| WS5A | [IMPA](https://github.com/theislab/IMPA)                                                   | by a scPortrait co-author, but no licence file and dormant since Jan 2025 |
| WS5B | [napari-spatialdata](https://github.com/scverse/napari-spatialdata)                        | hover-highlight and lasso on the scatter widget, no crop gallery      |
| WS5B | [Vitessce](https://github.com/vitessce/vitessce-python) · [TissUUmaps](https://github.com/TissUUmaps/TissUUmaps) | Vitessce needs an on-disk store; TissUUmaps reads `.h5ad` incl. `obsm["X_umap"]` directly |
| WS5C | [napari-mcp](https://github.com/royerlab/napari-mcp)                                       | shortest path to a demo, lists Claude Code as a supported client      |
| WS5C | [bia-bob](https://github.com/haesleinhuepf/bia-bob) · [anndata-mcp](https://github.com/biocontext-ai/anndata-mcp) · [scmcphub](https://github.com/scmcphub) | mature Jupyter copilot with local Ollama; MCP servers covering parts of scverse |

Read before claiming an agent works: [MicroVQA](https://jmhb0.github.io/microvqa) (expert microscopy VQA, best models ~53 %) and [arXiv:2608.05266](https://arxiv.org/abs/2608.05266), which finds agent performance on microscopy benchmarks does not generalise to unseen tasks.

## Relevant Resources

- [scPortrait](https://github.com/MannLabs/scPortrait) · [docs](https://mannlabs.github.io/scPortrait/) · [notebooks](https://github.com/MannLabs/scPortrait-notebooks) · [preprint](https://doi.org/10.1101/2025.09.22.677590)
- [SpatialData](https://spatialdata.scverse.org/) · [napari-spatialdata](https://github.com/scverse/napari-spatialdata)
- [OpenPhenom](https://huggingface.co/recursionpharma/OpenPhenom) · [CellFlux](https://github.com/yuhui-zh15/CellFlux) · [MorphoDiff](https://github.com/bowang-lab/MorphoDiff)
- [napari-mcp](https://github.com/royerlab/napari-mcp) · [bia-bob](https://github.com/haesleinhuepf/bia-bob) · [BioContextAI registry](https://github.com/biocontext-ai/registry)
