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
| `url` | iNaturalist original-photo URL; images are not redistributed here, download from this URL |
| `emb` | 768-d float16 BioCLIP 2 embedding |
| `n_annotators` | number of labelers |
| `plant_part` | "has flowers" (KMeans clusters 5/7/8) or "leaf only" |

## Full Image Table

`full_image_table.parquet`. One row per image, all 89,560. `pred_type`
and `p_damage`/`pred_damage` are **model outputs, not ground truth**
(image-type router: 97.8% holdout accuracy; damage probe: PR-AUC 0.746, grouped CV).

Only `p_damage` and `pred_damage` are limited to the 47,005
`pred_type == "leaf"` rows; every other field is populated for all rows.
Source of the occurrence fields: [Image Source, Filters, and Citation](#image-source-filters-and-citation).

| field | description |
|---|---|
| `uuid` | image unique identifier|
| `gbifID` | GBIF occurrence id (one per observation; joins multi-photo records) |
| `url` | iNaturalist original-photo URL; images are not redistributed here, download from this URL |
| `pred_type` | leaf / flower / exclude (predicted) |
| `p_exclude`, `p_flower`, `p_leaf` | image-type probabilities |
| `in_2k_sample` | in the 2k KMeans/labeling sample |
| `p_damage` | predicted caterpillar-damage probability |
| `pred_damage` | Yes / No at threshold 0.502 (F1-optimal) |
| `eventDate`, `year`, `month`, `day` | observation datetime |
| `decimalLatitude`, `decimalLongitude` | coordinates |
| `coordinateUncertaintyInMeters` | GPS uncertainty |
| `countryCode`, `stateProvince` | location |
| `recordedBy` | iNaturalist observer (GBIF `recordedBy`) |
| `rightsHolder` | rights holder of the observation (GBIF `rightsHolder`; equals `recordedBy` for nearly all rows) |
| `occurrence_license` | license of the observation record (CC BY-NC 4.0, CC BY 4.0, or CC0 1.0); the photo's own license is `license` |
| `inat_observation` | iNaturalist observation page URL (GBIF `references`) |
| `md5_original` | MD5 of the original photo file as served at `url`; verifies a re-download byte-for-byte |
| `md5_resized` | MD5 of the 720 px TreeOfLife-200M copy, the image actually embedded and modeled; hashed as the raw uint8 BGR pixel array, see below |
| `license` | per-photo Creative Commons license URL as published to GBIF 87% [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.en), 8% [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.en), 3% [CC0](https://creativecommons.org/publicdomain/zero/1.0/deed.en), rest other CC variants |

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

## Figure Attribution

`umap_lifecycle_figure_medoid_attribution.csv` (12 rows) and
`monarch_umap_k20_medoid_attribution.csv` (20 rows). One row per medoid
image shown in the two cluster infographics in [`figures/`](../figures)
(`umap_lifecycle_figure.png`: milkweed life-cycle clusters from the 2k
sample; `monarch_umap_k20.png`: monarch k=20 clusters from the 10k
`monarch_inat` sample), with the photographer credit needed to reuse the
image. 

| field | description |
|---|---|
| `cluster`, `stage`, `n` | cluster id, life-cycle stage label (milkweed only), cluster size (monarch only) |
| `uuid`, `url`, `source_id` | image id, iNaturalist original-photo URL, GBIF occurrence id |
| `recordedBy`, `rightsHolder`, `media_creator` | observer, rights holder, and photo creator as published to GBIF |
| `license_url` | the photo's own license (what governs image reuse) |
| `gbif_license` | the occurrence record's license |
| `occurrence_url`, `inat_observation` | GBIF occurrence page and iNaturalist observation page |
| `credit` | ready-to-use caption line, e.g. "© name, iNaturalist, CC BY-NC 4.0" |

## Image Source, Filters, and Citation

**No images are redistributed in this repository.** The tables above keep
only identifiers: `uuid` (TreeOfLife-200M image identifier), `gbifID` (GBIF
occurrence id), and `url` (iNaturalist original-photo URL). Images can be
re-downloaded from `url`, and the observation page is
`https://www.gbif.org/occurrence/<gbifID>`. The `md5_original` column of
`full_image_table.parquet` is the MD5 of each original file as downloaded. `md5_resized`
identifies the 720 px resized copy used for BioCLIP family models training and creation of the BioCLIP 2 embeddings used in this project.

All image records and occurrence fields come from one fixed GBIF snapshot [`10.15468/dl.bfv433`](https://doi.org/10.15468/dl.bfv433). It is the snapshot used to build
[TreeOfLife-200M](https://huggingface.co/datasets/imageomics/TreeOfLife-200M):

Every record in that GBIF snapshot subset was published to GBIF by iNaturalist through the
**iNaturalist Research-grade Observations** dataset (GBIF dataset key
`50c9509d-22c7-4a22-a47d-8c48425ef4a7`, DOI
[10.15468/ab3s5x](https://doi.org/10.15468/ab3s5x)).

### Record Selection

How the 89,560 rows of `full_image_table.parquet` and the 45,028-record
analysis subset behind `damage_rate_vs_population.csv` were selected.
"Image records" are rows (one per photo); "observations" are distinct
`gbifID` values (one observation can carry several photos).

| step | selection | image records | observations |
|---|---|---|---|
| 1 | TreeOfLife-200M metadata: `scientific_name = "Asclepias syriaca"`, `data_source = gbif`, `publisher = "iNaturalist.org"`, `basis_of_record = HUMAN_OBSERVATION`, `img_type = "Citizen Science"` | 89,560 | 64,790 |
| 2 | `pred_type = leaf` from the image-type router (drops `flower` category and `exclude` category: pods, seed fluff, senescent plants). Router is a probe on BioCLIP 2 embeddings trained from KMeans cluster labels on the 2k sample. | 47,005 | 36,863 |
| 3 | Occurrence fields joined on `gbifID` from the same snapshot (`eventDate`, `year`, `month`, `day`, `decimalLatitude`, `decimalLongitude`, `coordinateUncertaintyInMeters`, `countryCode`, `stateProvince`, `recordedBy`) | 47,005 | 36,863 |
| 4 | Analysis subset: `countryCode` in {US, CA} and `year` in 2012 to 2023 (matches the population series; all retained records have coordinates) | 45,028 | 35,456 |

The labels in `combined_labels_raw.tsv` and `training_dataset.parquet`
were collected on a random 2,000-record sample from step 1
(`in_2k_sample = true`), clustered into 12 KMeans clusters on BioCLIP 2
embeddings. Clusters of pods, seed fluff, and senescent plants were
excluded and the remaining 8 clusters were labeled Yes / No / Uninformative.


### Downloading the Training Images

Use [`cautious-robot`](https://github.com/Imageomics/cautious-robot)

```bash
pip install cautious-robot
```

The example below fetches the 710 labeled images in
`training_dataset.parquet`. Checksums come
from `full_image_table.parquet`, joined on `uuid`. Keep `uuid` as the
filename stem and take the extension from `url` (`.jpg`, `.jpeg`, or `.png`).

```python
import pandas as pd

t = pd.read_parquet("data/training_dataset.parquet", columns=["uuid", "label", "url"])
f = pd.read_parquet("data/full_image_table.parquet", columns=["uuid", "md5_original", "gbifID", "license"])
t = t.merge(f, on="uuid", validate="one_to_one")
t = t.assign(filename=t.uuid + "." + t.url.str.extract(r"\.([A-Za-z0-9]+)$")[0].str.lower())
t[["filename", "url", "md5_original", "label", "gbifID", "license"]].to_csv("milkweed_images.csv", index=False)
```

```bash
cautious-robot -i milkweed_images.csv -o images -n filename -u url -v md5_original
```

What you get next to the CSV:

| file | contents |
|---|---|
| `images/<uuid>.<ext>` | the downloaded originals |
| `milkweed_images_log.jsonl` | one record per successful request |
| `milkweed_images_error_log.jsonl` | failed or skipped URLs, written only if any occur |
| `milkweed_images_checksums.csv` | `filepath, filename, md5` of every file on disk |
| `milkweed_images_missing.csv` | rows whose filename or MD5 did not match, written only if expected images don't download correctly |

The run ends with a "buddy check" that inner-joins the input CSV with the
checksum CSV on filename and MD5 and reports whether all expected images are
accounted for. Rerunning the same command resumes: files already in the
output directory are skipped. Pass `-s label` to sort the files into
`Yes/` and `No/` subfolders.

### Data Source Citation

```bibtex
@misc{GBIF-DOI,
  doi = {10.15468/DL.BFV433},
  url = {https://doi.org/10.15468/dl.bfv433},
  keywords = {GBIF, biodiversity, species occurrences},
  author = {GBIF.org},
  title = {{GBIF} Occurrence Download},
  publisher = {The Global Biodiversity Information Facility},
  month = {May},
  year = {2024},
  copyright = {Creative Commons Attribution Non Commercial 4.0 International}
}
```

```bibtex
@dataset{treeoflife_200m,
  title = {{T}ree{O}f{L}ife-200{M} (Revision 94bbc0b)}, 
  author = {Jianyang Gu and Samuel Stevens and Elizabeth G Campolongo and Matthew J Thompson and Net Zhang and Jiaman Wu and Andrei Kopanev and Zheda Mai and Alexander E. White and James Balhoff and Wasila M Dahdul and Daniel Rubenstein and Hilmar Lapp and Tanya Berger-Wolf and Wei-Lun Chao and Yu Su},
  year = {2026},
  url = {https://huggingface.co/datasets/imageomics/TreeOfLife-200M},
  doi = {10.57967/hf/8980},
  publisher = {Hugging Face}
}
```

