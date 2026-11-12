"""Frozen splits: 20% holdout plus grouped and stratified CV folds.

Usage: python make_splits.py
"""

import json
import os

import pandas as pd
from sklearn.model_selection import GroupKFold, StratifiedKFold

from paths import FILELIST, SPLITS, TRAINING

SEED = 42
HOLDOUT_TARGET = 0.20


def main():
    df = pd.read_parquet(TRAINING, columns=["uuid", "label"])
    cluster_of = {}
    for line in open(FILELIST):
        line = line.strip()
        if line:
            c, fn = line.split("/", 1)
            cluster_of[os.path.splitext(fn)[0]] = c
    df["cluster"] = df["uuid"].map(cluster_of)
    assert df["cluster"].notna().all(), "uuid missing from filelist"

    stats = df.groupby("cluster")["label"].agg(
        n="size", pos=lambda s: (s == "Yes").sum()
    )
    print("labeled clusters:")
    print(stats.to_string())
    overall_pos = (df["label"] == "Yes").mean()

    # holdout sampled within every (cluster x label) cell
    holdout_uuids = (
        df.groupby(["cluster", "label"], group_keys=False)["uuid"]
        .apply(lambda s: s.sample(n=round(len(s) * HOLDOUT_TARGET), random_state=SEED))
    )
    hold = df["uuid"].isin(set(holdout_uuids))
    print(f"\nholdout: {hold.sum()} rows ({hold.mean():.1%}), "
          f"{(df.loc[hold, 'label'] == 'Yes').mean():.1%} Yes "
          f"(overall {overall_pos:.1%}), all {df.loc[hold, 'cluster'].nunique()} clusters")
    print(df.loc[hold, "cluster"].value_counts().sort_index().to_string())

    train = df[~hold].reset_index(drop=True)
    n_groups = train["cluster"].nunique()
    k = min(5, n_groups)
    print(f"train: {len(train)} rows across {n_groups} clusters -> {k} grouped folds")

    group_folds = {}
    for f, (_, val_idx) in enumerate(
        GroupKFold(n_splits=k).split(train, groups=train["cluster"])
    ):
        for i in val_idx:
            group_folds[train.loc[i, "uuid"]] = f

    strat_folds = {}
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    for f, (_, val_idx) in enumerate(skf.split(train, train["label"])):
        for i in val_idx:
            strat_folds[train.loc[i, "uuid"]] = f

    out = {
        "seed": SEED,
        "positive_class": "Yes",
        "holdout_uuids": sorted(df.loc[hold, "uuid"]),
        "cluster_of": {u: cluster_of[u] for u in df["uuid"]},
        "group_folds": group_folds,
        "strat_folds": strat_folds,
    }
    with open(SPLITS, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {SPLITS}")


if __name__ == "__main__":
    main()
