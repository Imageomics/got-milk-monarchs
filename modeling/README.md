# Damage Modeling

Scripts that train and apply the two models behind the predictions in
[`data/`](../data). Both are logistic regressions on L2-normalized
BioCLIP 2 embeddings (768-d); no image model is trained.

- **Image-type router**: leaf / flower / exclude, trained on the KMeans
  cluster labels of the 2k sample.
- **Damage classifier**: Yes / No caterpillar damage, trained on our manual
  labels of leaf-only images and applied to images the router calls leaf.

## Usage

```bash
pip install numpy pandas pyarrow scikit-learn matplotlib
cd modeling/scripts
```

Paths inside this repo resolve automatically; set the `/path/to/`
placeholders (the capitalized names below) in `scripts/paths.py` first.
Run the steps in order.

### 1. Training table

Resolve the raw labels and join their embeddings. Optional, since the output
is already tracked
([Model Training Table](../data/README.md#model-training-table)).

```bash
python build_training_dataset.py
```

The script reads `data/combined_labels_raw.tsv`, `labeling/urls.json` and
`EMBEDDINGS`, and writes `data/training_dataset.parquet`. For each image it
keeps each labeler's newest label, ignores the six labels dated after
2026-08-18 (they were added after the table was built), and drops images
labeled Uninformative. This leaves 710 rows (426 No, 284 Yes).

### 2. Evaluation

Cross-validate the damage classifier on folds grouped by cluster.

```bash
python make_splits.py
python train_probe.py
python per_part_probe.py
```

`make_splits.py` sets aside a 20% holdout (140 rows) and assigns the other
570 rows to two sets of 5 folds: one grouped by cluster, and one stratified
by label for comparison. It saves the assignment to `modeling/splits.json`.
The two probes print scores for each model they compare (majority baseline,
kNN, logistic regression, linear SVM) and save them under
`modeling/results/`. These outputs are created when the scripts run; they
are not tracked in the repo. Under grouped CV, expect PR-AUC 0.698 and
ROC-AUC 0.754 on all images, and PR-AUC 0.746 and ROC-AUC 0.785 on leaf-only
images (logistic regression, C = 10). The holdout is set aside and has not
been scored.

### 3. Prediction

Route every image by type, then score the leaf images for damage.

```bash
python image_type_filter.py
python score_leaf_damage.py
```

`image_type_filter.py` reads `CLUSTER_SUMMARY` and `EMBEDDINGS` and writes
`IMAGE_TYPE_PREDICTIONS` for all 89,560 images. Expect accuracy 0.978 on a
held-out 20% of the 2k sample, and 47,005 images predicted leaf.
`score_leaf_damage.py` refits the damage classifier on all 488 leaf-only
labels, scores those 47,005 images at threshold 0.502 and joins
`OCCURRENCE_METADATA`. It writes `LEAF_SCORES` (all 47,005 images) and
`LEAF_ANALYSIS` (the 45,028 US and Canada records from 2012 to 2023).
`IMAGE_TYPE_PREDICTIONS` and `LEAF_SCORES` are published as the `pred_type`,
`p_damage` and `pred_damage` columns of the
[Full Image Table](../data/README.md#full-image-table); `LEAF_ANALYSIS` is
the analysis subset in
[Record Selection](../data/README.md#record-selection).

## External Inputs

| name | contents |
|---|---|
| `EMBEDDINGS` | parquet with `uuid` and `emb` for all 89,560 images |
| `CLUSTER_SUMMARY` | csv with `file_name` (`<uuid>.webp`) and `cluster` (0 to 11) for the 2k sample |
| `OCCURRENCE_METADATA` | parquet with one row per leaf image: `uuid`, `source_id` (equal to `gbifID`), and the `gbifID`, date, location and `recordedBy` fields of the [Full Image Table](../data/README.md#full-image-table) |
