"""Image-type router (exclude / flower / leaf): multinomial logistic regression
trained on the KMeans cluster labels of the 2k sample, applied to all images.

Usage: python image_type_filter.py
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, train_test_split

from paths import CLUSTER_SUMMARY, EMBEDDINGS, IMAGE_TYPE_PREDICTIONS

SEED = 42
C_GRID = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
TYPE_OF = {**{c: "exclude" for c in [0, 2, 9, 11]},
           **{c: "flower" for c in [5, 7, 8]},
           **{c: "leaf" for c in [1, 3, 4, 6, 10]}}
CLASSES = ["exclude", "flower", "leaf"]


def main():
    cs = pd.read_csv(CLUSTER_SUMMARY)
    cs["uuid"] = cs["file_name"].str.replace(".webp", "", regex=False)
    cs["image_type"] = cs["cluster"].map(TYPE_OF)
    assert cs["image_type"].notna().all(), "unmapped cluster present"
    print(cs["image_type"].value_counts().to_string())

    emb = pd.read_parquet(EMBEDDINGS, columns=["uuid", "emb"])
    E = np.stack(emb["emb"].to_numpy()).astype(np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    idx_of = {u: i for i, u in enumerate(emb["uuid"])}

    rows = cs["uuid"].map(idx_of)
    assert rows.notna().all(), "sample uuid missing from embeddings"
    X = E[rows.astype(int).to_numpy()]
    y = cs["image_type"].to_numpy()

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y,
                                          random_state=SEED)
    best = None
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    for C in C_GRID:
        accs = []
        for tr, va in skf.split(Xtr, ytr):
            m = LogisticRegression(C=C, max_iter=5000, random_state=SEED,
                                   class_weight="balanced").fit(Xtr[tr], ytr[tr])
            accs.append((m.predict(Xtr[va]) == ytr[va]).mean())
        if best is None or np.mean(accs) > best[1]:
            best = (C, float(np.mean(accs)))
    C = best[0]
    print(f"\nbest C = {C:g} (CV accuracy {best[1]:.3f})")

    m = LogisticRegression(C=C, max_iter=5000, random_state=SEED,
                           class_weight="balanced").fit(Xtr, ytr)
    pred = m.predict(Xte)
    print(f"\nholdout (n={len(yte)}):")
    print(classification_report(yte, pred, digits=3))
    print("confusion (rows=true, cols=pred, order " + "/".join(CLASSES) + "):")
    print(confusion_matrix(yte, pred, labels=CLASSES))

    # refit on the full sample, then score every image
    m = LogisticRegression(C=C, max_iter=5000, random_state=SEED,
                           class_weight="balanced").fit(X, y)
    proba = m.predict_proba(E)
    order = [list(m.classes_).index(c) for c in CLASSES]
    out = pd.DataFrame({
        "uuid": emb["uuid"],
        "pred_type": m.classes_[np.argmax(proba, axis=1)],
        "p_exclude": np.round(proba[:, order[0]], 4),
        "p_flower": np.round(proba[:, order[1]], 4),
        "p_leaf": np.round(proba[:, order[2]], 4),
    })
    sample_map = dict(zip(cs["uuid"], cs["cluster"]))
    out["in_2k_sample"] = out["uuid"].isin(sample_map)
    out["kmeans_cluster"] = out["uuid"].map(sample_map).astype("Int64")
    out.to_parquet(IMAGE_TYPE_PREDICTIONS, index=False)
    print(f"\nfull-pool predictions ({len(out)} rows):")
    print(out["pred_type"].value_counts().to_string())
    print(f"wrote {IMAGE_TYPE_PREDICTIONS}")


if __name__ == "__main__":
    main()
