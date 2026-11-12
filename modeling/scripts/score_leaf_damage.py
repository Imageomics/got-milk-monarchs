"""Final leaf damage model: refit on all leaf-only labels, score every image
the router calls leaf, then keep US/CA records from 2012 to 2023.
Run image_type_filter.py first.

Usage: python score_leaf_damage.py
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve

from paths import (EMBEDDINGS, IMAGE_TYPE_PREDICTIONS, LEAF_ANALYSIS, LEAF_SCORES,
                   OCCURRENCE_METADATA, TRAINING)

SEED = 42
C = 10.0  # best grouped-CV value from per_part_probe.py
KEEP = ["uuid", "source_id", "gbifID", "p_damage", "pred_damage", "eventDate",
        "year", "month", "day", "decimalLatitude", "decimalLongitude",
        "coordinateUncertaintyInMeters", "countryCode", "stateProvince", "recordedBy"]


def main():
    lab = pd.read_parquet(TRAINING)
    lab = lab[lab["plant_part"] == "leaf only"]
    Xl = np.stack(lab["emb"].to_numpy()).astype(np.float32)
    Xl /= np.linalg.norm(Xl, axis=1, keepdims=True)
    yl = (lab["label"] == "Yes").to_numpy().astype(int)
    print(f"training rows: {len(yl)} leaf-labeled ({yl.mean():.1%} Yes)")
    model = LogisticRegression(C=C, class_weight="balanced", max_iter=5000,
                               random_state=SEED).fit(Xl, yl)

    # F1-optimal threshold on the training labels
    prec, rec, thr = precision_recall_curve(yl, model.predict_proba(Xl)[:, 1])
    f1s = 2 * prec * rec / np.clip(prec + rec, 1e-9, None)
    t = float(thr[max(0, np.argmax(f1s) - 1)])
    print(f"threshold: {t:.3f}")

    pred = pd.read_parquet(IMAGE_TYPE_PREDICTIONS)
    leaf_uuids = set(pred.loc[pred["pred_type"] == "leaf", "uuid"])
    emb = pd.read_parquet(EMBEDDINGS, columns=["uuid", "emb"])
    emb = emb[emb["uuid"].isin(leaf_uuids)].reset_index(drop=True)
    X = np.stack(emb["emb"].to_numpy()).astype(np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    scores = pd.DataFrame({"uuid": emb["uuid"],
                           "p_damage": np.round(model.predict_proba(X)[:, 1], 4)})
    scores["pred_damage"] = np.where(scores["p_damage"] >= t, "Yes", "No")
    print(f"scored {len(scores)} leaf images; predicted damaged: "
          f"{(scores['pred_damage'] == 'Yes').mean():.1%}")

    md = pd.read_parquet(OCCURRENCE_METADATA)
    df = scores.merge(md, on="uuid", how="left")
    in_geo = df["countryCode"].isin(["US", "CA"])
    in_time = pd.to_numeric(df["year"], errors="coerce").between(2012, 2023)
    print(f"\nleaf images total:      {len(df)}")
    print(f"outside US/Canada:      {(~in_geo).sum()}")
    print(f"outside 2012 to 2023:   {(~in_time).sum()}")
    print(f"outside both:           {((~in_geo) & (~in_time)).sum()}")
    print(f"kept:                   {(in_geo & in_time).sum()}")

    df[KEEP].to_parquet(LEAF_SCORES, index=False)
    final = df.loc[in_geo & in_time, KEEP]
    final.to_parquet(LEAF_ANALYSIS, index=False)
    print(f"\nanalysis set damage rate: {(final['pred_damage'] == 'Yes').mean():.1%}")
    print(f"wrote {LEAF_SCORES}\nwrote {LEAF_ANALYSIS}")


if __name__ == "__main__":
    main()
