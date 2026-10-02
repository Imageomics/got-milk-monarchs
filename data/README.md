# Data

*Asclepias syriaca*

## Monarch Population Count Data

`monarch_popn_counts.csv`. Eastern monarch hectare occupancy at
overwintering sites in Mexico. Data from
https://monarchjointventure.org/monarch-biology/population-trends

| field | description |
|---|---|
| `season` | years of population observation at overwintering sites |
| `count` | hectares occupied |
| `image_year` | preceding year, for matching with milkweed damage photos |

## Combined Labeling Records

`combined_labels_raw.tsv`. Raw answers from the labeling app (question:
*"Does this image contain damage from monarch caterpillars?"*), all
annotators, append-only: newest line per filename + labeler wins.

| field | description |
|---|---|
| `filename` | cluster subfolder / image uuid |
| `label` | Yes / No / Uninformative |
| `labeler` | annotator name |
| `timestamp` | UTC label time |

## Model Training Table

`training_dataset.parquet`. Resolved labels used to train the damage
classifiers; 710 rows (426 No / 284 Yes), Uninformative removed.

| field | description |
|---|---|
| `uuid` | image id |
| `label` | Yes / No (newest per labeler, majority across labelers) |
| `url` | iNaturalist original photo |
| `emb` | 768-d float16 BioCLIP 2 embedding |
| `n_annotators` | number of labelers |
| `plant_part` | "has flowers" (KMeans clusters 5/7/8) or "leaf only" |

## Full Image Table

`full_image_table.parquet`. One row per image, all 89,560. `pred_type`
and `p_damage`/`pred_damage` are **model outputs, not ground truth**
(router: 97.8% holdout accuracy; damage probe: PR-AUC 0.746, grouped CV).
Occurrence and damage fields are populated only for the 47,005
`pred_type == "leaf"` rows.

| field | description |
|---|---|
| `uuid` | image id |
| `gbifID` | GBIF occurrence id (one per observation; joins multi-photo records) |
| `url` | iNaturalist original photo |
| `pred_type` | leaf / flower / exclude (predicted) |
| `p_exclude`, `p_flower`, `p_leaf` | image-type probabilities |
| `in_2k_sample` | in the 2k KMeans/labeling sample |
| `p_damage` | predicted caterpillar-damage probability |
| `pred_damage` | Yes / No at threshold 0.502 (F1-optimal) |
| `eventDate`, `year`, `month`, `day` | observation datetime (GBIF 2024-05-01 snapshot) |
| `decimalLatitude`, `decimalLongitude` | coordinates |
| `coordinateUncertaintyInMeters` | GPS uncertainty |
| `countryCode`, `stateProvince`, `elevation` | location |
| `recordedBy` | iNaturalist observer |

## Damage Rate vs Population

`damage_rate_vs_population.csv`. Yearly predicted damage rates (US/CA,
2012-2023) joined to population counts on `year` = `image_year`.
Observation-level: images sharing a `gbifID` count once, damaged if any
image is predicted damaged.

| field | description |
|---|---|
| `year` | image year |
| `season` | overwintering season |
| `n_observations`, `n_images` | yearly sample sizes |
| `damage_rate_obs` | observation-level damage rate (primary) |
| `damage_rate_img` | image-level damage rate |
| `population_ha` | hectares occupied at overwintering sites |

## Milkweed Image Data: Provenance, Filters, and Citation

All *Asclepias syriaca* images and their occurrence metadata come from a single fixed GBIF snapshot, not from a live GBIF or iNaturalist query. The snapshot is the one used to build [TreeOfLife-200M](https://huggingface.co/datasets/imageomics/TreeOfLife-200M):

> GBIF occurrence download of 2024-05-01, filter `occurrenceStatus = PRESENT`, DOI [10.15468/dl.bfv433](https://doi.org/10.15468/dl.bfv433) (download key `0009558-240425142415019`, 2,932,007,107 records from 73,180 datasets, licensed CC BY-NC 4.0).

Every record we use was published to GBIF by iNaturalist through the **iNaturalist Research-grade Observations** dataset (GBIF dataset key `50c9509d-22c7-4a22-a47d-8c48425ef4a7`, DOI [10.15468/ab3s5x](https://doi.org/10.15468/ab3s5x)). That dataset is versioned continuously and its listed alternative identifiers do not reach back to May 2024, so the snapshot DOI above is the citable, fixed reference; the iNaturalist dataset is cited as the originating publisher.

### Filtering chain

Counts are images (one GBIF occurrence can carry several photos; `source_id` / `gbifID` identifies the observation).

| Step | Filter | Images | Observations |
|---|---|---|---|
| 1 | TreeOfLife-200M records with `scientific_name = "Asclepias syriaca"`, `data_source = gbif`, `publisher = "iNaturalist.org"`, `basis_of_record = HUMAN_OBSERVATION`, `img_type = "Citizen Science"` | 89,560 | 64,790 |
| 2 | Image-type router keeps `leaf` (drops `flower` and `exclude`, e.g. pods, seed fluff, senescent plants). Router is a probe on BioCLIP 2 embeddings trained from k-means cluster labels on a 2,000-image sample. | 47,005 | 36,863 |
| 3 | Join occurrence fields by `gbifID` from the same snapshot: `eventDate`, `year`, `month`, `day`, `startDayOfYear`, `decimalLatitude`, `decimalLongitude`, `coordinateUncertaintyInMeters`, `countryCode`, `stateProvince`, `recordedBy` | 47,005 | 36,863 |
| 4 | Analysis set: `countryCode ∈ {US, CA}` and `2012 ≤ year ≤ 2023` (matches the population series below; all retained records have coordinates) | 45,028 | 35,456 |

Leaf-damage labels (`labeling/`) were collected on the 2,000-image sample from step 1, clustered into 12 k-means clusters on BioCLIP 2 embeddings; clusters of pods, seed fluff, and senescent plants were excluded and the remaining 8 clusters were labeled Yes / No / Uninformative.

### License note

The TreeOfLife-200M compilation is CC0, but individual iNaturalist photos carry their own licenses (CC0, CC BY, or CC BY-NC), and the GBIF download as a whole is CC BY-NC 4.0. Per-image license and photographer attribution are available through each record's `source_url` / iNaturalist observation page.

### How to cite

Suggested text for a data-availability statement:

> Milkweed (*Asclepias syriaca*) images and occurrence metadata were taken from the TreeOfLife-200M dataset (Gu et al., 2025, 2026), which was built from the GBIF occurrence snapshot of 1 May 2024 (GBIF.org, 2024; https://doi.org/10.15468/dl.bfv433). We retained only iNaturalist Research-grade human observations (iNaturalist contributors, 2024; https://doi.org/10.15468/ab3s5x) with `img_type = Citizen Science`, classified as leaf images, located in the United States or Canada, and observed between 2012 and 2023 (45,028 images from 35,456 observations).

```bibtex
@misc{gbif_download_bfv433,
  author    = {{GBIF.org}},
  title     = {{GBIF} Occurrence Download},
  year      = {2024},
  month     = may,
  day       = {1},
  doi       = {10.15468/dl.bfv433},
  url       = {https://doi.org/10.15468/dl.bfv433},
  note      = {Download key 0009558-240425142415019; filter occurrenceStatus = PRESENT}
}

@misc{inaturalist_research_grade,
  author    = {{iNaturalist contributors} and {iNaturalist}},
  title     = {{iNaturalist} Research-grade Observations},
  publisher = {iNaturalist.org},
  year      = {2024},
  doi       = {10.15468/ab3s5x},
  url       = {https://doi.org/10.15468/ab3s5x},
  note      = {Occurrence dataset accessed via GBIF.org in the 2024-05-01 snapshot, https://doi.org/10.15468/dl.bfv433}
}

@dataset{treeoflife_200m,
  title     = {{T}ree{O}f{L}ife-200{M} (Revision 94bbc0b)},
  author    = {Jianyang Gu and Samuel Stevens and Elizabeth G Campolongo and Matthew J Thompson and Net Zhang and Jiaman Wu and Andrei Kopanev and Zheda Mai and Alexander E. White and James Balhoff and Wasila M Dahdul and Daniel Rubenstein and Hilmar Lapp and Tanya Berger-Wolf and Wei-Lun Chao and Yu Su},
  year      = {2026},
  url       = {https://huggingface.co/datasets/imageomics/TreeOfLife-200M},
  doi       = {10.57967/hf/8980},
  publisher = {Hugging Face}
}

@inproceedings{gu2025bioclip2,
  author    = {Gu, Jianyang and Stevens, Sam and Campolongo, Elizabeth and Thompson, Matthew and Zhang, Net and Wu, Jiaman and Kopanev, Andrei and Mai, Zheda and White, Alexander and Balhoff, James and Dahdul, Wasila and Rubenstein, Daniel and Lapp, Hilmar and Berger-Wolf, Tanya and Chao, Wei-Lun (Harry) and Su, Yu},
  title     = {{BioCLIP} 2: Emergent Properties from Scaling Hierarchical Contrastive Learning},
  booktitle = {Advances in Neural Information Processing Systems},
  volume    = {38},
  pages     = {102778--102811},
  publisher = {Curran Associates, Inc.},
  year      = {2025},
  url       = {https://proceedings.neurips.cc/paper_files/paper/2025/file/94da80cbfe870c1db958c88a8a27018c-Paper-Conference.pdf}
}
```

The monarch population series above should be cited separately to Monarch Joint Venture (https://monarchjointventure.org/monarch-biology/population-trends).
