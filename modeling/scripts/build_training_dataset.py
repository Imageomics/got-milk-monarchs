"""Resolve raw labels and join BioCLIP 2 embeddings into the training table.

Usage: python build_training_dataset.py
"""

import json
import os
from collections import Counter

import pandas as pd

from paths import EMBEDDINGS, LABELS, TRAINING, URLS

FLOWER_CLUSTERS = {"cluster_5", "cluster_7", "cluster_8"}
# raw labels from this time on were added after the training table was built
LABEL_CUTOFF = "2026-08-19T00:00:00Z"


def main():
    # newest line per (labeler, filename) wins
    latest = {}
    with open(LABELS) as fh:
        next(fh)
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if (len(parts) >= 4 and parts[1] in {"Yes", "No", "Uninformative"}
                    and parts[3] < LABEL_CUTOFF):
                latest[(parts[2], parts[0])] = parts[:4]

    votes_of = {}
    for fname, label, labeler, ts in latest.values():
        votes_of.setdefault(fname, []).append((label, ts))

    # majority across labelers, ties go to the most recent label
    rows = []
    for fname, votes in votes_of.items():
        top = Counter(v[0] for v in votes).most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            label = max(votes, key=lambda v: v[1])[0]
        else:
            label = top[0][0]
        cluster, name = fname.split("/", 1)
        rows.append({
            "uuid": os.path.splitext(name)[0],
            "label": label,
            "n_annotators": len(votes),
            "plant_part": "has flowers" if cluster in FLOWER_CLUSTERS else "leaf only",
        })
    lab = pd.DataFrame(rows)
    print(f"{len(lab)} labeled images")
    print(lab["label"].value_counts().to_string())
    lab = lab[lab["label"] != "Uninformative"].reset_index(drop=True)

    with open(URLS) as fh:
        lab["url"] = lab["uuid"].map(json.load(fh))
    emb = pd.read_parquet(EMBEDDINGS, columns=["uuid", "emb"])
    out = lab.merge(emb, on="uuid", how="left")
    assert out["emb"].notna().all(), "uuid missing from embeddings"
    assert out["url"].notna().all(), "uuid missing from urls.json"

    out = out[["uuid", "label", "url", "emb", "n_annotators", "plant_part"]]
    out.to_parquet(TRAINING, index=False)
    print(f"wrote {len(out)} rows -> {TRAINING}")
    print(out.groupby("plant_part")["label"].value_counts().to_string())


if __name__ == "__main__":
    main()
