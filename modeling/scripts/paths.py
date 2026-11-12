"""Paths used by the modeling scripts. Replace the /path/to/ placeholders."""

import os

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# tracked in this repo
LABELS = os.path.join(REPO, "data", "combined_labels_raw.tsv")
TRAINING = os.path.join(REPO, "data", "training_dataset.parquet")
URLS = os.path.join(REPO, "labeling", "urls.json")
FILELIST = os.path.join(REPO, "labeling", "filelist.txt")
SPLITS = os.path.join(REPO, "modeling", "splits.json")
RESULTS = os.path.join(REPO, "modeling", "results")

# inputs outside this repo
EMBEDDINGS = "/path/to/asclepias_syriaca_inat_bioclip2_embeddings.parquet"
CLUSTER_SUMMARY = "/path/to/cluster_summary.csv"
OCCURRENCE_METADATA = "/path/to/leaf_occurrence_metadata.parquet"

# outputs outside this repo
IMAGE_TYPE_PREDICTIONS = "/path/to/image_type_predictions.parquet"
LEAF_SCORES = "/path/to/leaf_damage_scores_all.parquet"
LEAF_ANALYSIS = "/path/to/leaf_damage_analysis_us_ca_2012_2023.parquet"
