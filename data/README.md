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
