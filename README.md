# scverse × cellpainting 2026 — workstreams

**September 2–4, 2026 · Max Delbrück Center (MDC), Campus Berlin-Buch**

The working repository for the hackathon. Each workstream has a README with its open questions, requirements, deliverable, datasets and how to get started.

Event information, programme and registration live at **[scverse.org/cellpainting2026](https://scverse.org/cellpainting2026)** ([source](https://github.com/scverse/cellpainting2026)).

## Workstreams

| | Workstream | Lead |
|---|---|---|
| **WS1** | [Analysing CellProfiler output with scverse](ws1_cellprofiler_x_scverse) — how CellProfiler should export, a specified single-cell AnnData object and the `cp2adata` reader for it, a CellProfiler reader for `spatialdata-io`, and an `ExportToAnnData` plugin | [@timtreis](https://github.com/timtreis) |
| **WS2** | [Optical pooled screens in scverse](ws2_ops_in_scverse) — how to represent sequencing cycles and plate-scale screens so images, masks and the per-cell table live in one object | [@LucaMarconato](https://github.com/LucaMarconato) |
| **WS3** | [Uncertainty quantification for Cell Painting](ws3_uq_in_cellprofiling) — which UQ methods work on morphological profiles, whether their uncertainties can be trusted, and how to expose them in AnnData | [@hanyangii](https://github.com/hanyangii) |
| **WS4** | [Cross-modal integration of morphology and transcriptomics](ws4_multiomics) — aligning Cell Painting profiles with matched transcriptomics, and what each modality adds. Work happens in a [separate repository](https://github.com/Arkkienkeli/hackathon_crossmodal_stream) | [@Arkkienkeli](https://github.com/Arkkienkeli) |
| **WS5** | [AI-driven single-cell image phenotyping with scPortrait](ws5_scportrait) — generative models of cell morphology, interactive exploration of image-based phenotypes, agentic image-processing workflows | [@nik-as](https://github.com/nik-as) |
| **WS6** | [Classical single-cell tooling on morphology data](ws6_perturbation_tooling) — which parts of the single-cell perturbation stack transfer to morphological profiles, and whether the competing measures of perturbation strength agree | [@timtreis](https://github.com/timtreis) |

You will work on **one** workstream for the event. Teams form on Wednesday morning and then work in their own repositories; this one is for orientation and shared material.

## Before you travel

- **Download your workstream's data before you arrive.** Several datasets are hundreds of MB to a few GB, and the first morning is not the time to discover that.
- **Compute:** cloud instances with Jupyter, CPU and GPU, on a dedicated network at the venue. External accounts cannot be provisioned before the event, so anything you want to run on day one should also run on your laptop. Most workstreams are laptop-sized by design.
- ⚠️ **Windows:** scPortrait (WS5) and SCALLOPS (WS2) are Linux/macOS only. WSL or a VM if that is your machine.
- **WS1 participants install CellProfiler**, so do it before you fly if you can.

Each workstream README ends with a note on who it suits. Domain expertise matters as much as software development here — WS1 in particular opens with a question that needs people who run CellProfiler in practice, and no code at all.

## Team repositories

Teams create their own repository on Wednesday and add it here.

| Workstream | Team repository |
|---|---|
| WS1 | |
| WS2 | [scverse/sp-ops](https://github.com/scverse/sp-ops) |
| WS3 | |
| WS4 | [Arkkienkeli/hackathon_crossmodal_stream](https://github.com/Arkkienkeli/hackathon_crossmodal_stream) |
| WS5 | |
| WS6 | |

## Contact

- Email: cellpainting2026@scverse.org
- Zulip: [#2026-09: hackathon-cellpainting](https://scverse.zulipchat.com/#narrow/channel/591503-2026-09.3A-hackathon-cellpainting)
