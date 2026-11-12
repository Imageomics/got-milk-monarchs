"""Separate damage probes for leaf-only and flower images, same procedure as
train_probe.py on each subset. Run make_splits.py first.

Usage: python per_part_probe.py
"""

import json
import os

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve, roc_auc_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import LinearSVC

from paths import RESULTS, SPLITS, TRAINING

SEED = 42
C_GRID = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
K_GRID = [5, 15, 31]


def fold_scores(model_fn, X, y, fold_ids, needs_proba=True):
    out, skipped = [], 0
    for f in sorted(set(fold_ids)):
        tr, va = fold_ids != f, fold_ids == f
        # single-class folds cannot be scored
        if len(set(y[va])) < 2 or len(set(y[tr])) < 2:
            skipped += 1
            continue
        m = model_fn()
        m.fit(X[tr], y[tr])
        if needs_proba:
            s_tr, s_va = m.predict_proba(X[tr])[:, 1], m.predict_proba(X[va])[:, 1]
        else:
            s_tr, s_va = m.decision_function(X[tr]), m.decision_function(X[va])
        prec, rec, thr = precision_recall_curve(y[tr], s_tr)
        f1s = 2 * prec * rec / np.clip(prec + rec, 1e-9, None)
        t = thr[max(0, np.argmax(f1s) - 1)] if len(thr) else 0.5
        out.append({
            "pr_auc": average_precision_score(y[va], s_va),
            "roc_auc": roc_auc_score(y[va], s_va),
            "f1": f1_score(y[va], s_va >= t),
        })
    agg = {k: (float(np.mean([r[k] for r in out])), float(np.std([r[k] for r in out])))
           for k in out[0]}
    return agg, len(out), skipped


def main():
    os.makedirs(RESULTS, exist_ok=True)
    with open(SPLITS) as fh:
        sp = json.load(fh)
    df = pd.read_parquet(TRAINING)
    df = df[~df["uuid"].isin(set(sp["holdout_uuids"]))].reset_index(drop=True)
    E = np.stack(df["emb"].to_numpy()).astype(np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True)

    lines = ["# Separate damage models per plant part (positive = Yes)\n",
             "Same procedure as train_probe.py on each subset; grouped folds",
             "restricted to the subset's clusters; single-class folds skipped.\n"]
    for part in ["leaf only", "has flowers"]:
        sub = (df["plant_part"] == part).to_numpy()
        X, y = E[sub], (df.loc[sub, "label"] == "Yes").to_numpy().astype(int)
        folds = {
            "grouped": df.loc[sub, "uuid"].map(sp["group_folds"]).to_numpy(),
            "stratified": df.loc[sub, "uuid"].map(sp["strat_folds"]).to_numpy(),
        }
        n_clusters = df.loc[sub, "uuid"].map(sp["cluster_of"]).nunique()
        print(f"\n#### {part}: {len(y)} rows, {y.mean():.1%} Yes, {n_clusters} clusters")
        lines.append(f"\n## {part} ({len(y)} rows, {y.mean():.1%} Yes, {n_clusters} clusters)\n")
        for scheme, fid in folds.items():
            res = {}
            res["majority"] = ({"pr_auc": (float(y.mean()), 0.0), "roc_auc": (0.5, 0.0),
                                "f1": (0.0, 0.0)}, len(set(fid)), 0)
            best = None
            for k in K_GRID:
                r = fold_scores(lambda k=k: KNeighborsClassifier(n_neighbors=k,
                                                                 metric="cosine"), X, y, fid)
                if best is None or r[0]["pr_auc"][0] > best[1][0]["pr_auc"][0]:
                    best = (f"kNN (k={k})", r)
            res[best[0]] = best[1]
            best = None
            for C in C_GRID:
                r = fold_scores(lambda C=C: LogisticRegression(
                    C=C, class_weight="balanced", max_iter=5000, random_state=SEED),
                    X, y, fid)
                if best is None or r[0]["pr_auc"][0] > best[1][0]["pr_auc"][0]:
                    best = (f"logreg (C={C:g})", r)
            res[best[0]] = best[1]
            best = None
            for C in C_GRID:
                r = fold_scores(lambda C=C: LinearSVC(
                    C=C, class_weight="balanced", max_iter=20000, random_state=SEED),
                    X, y, fid, needs_proba=False)
                if best is None or r[0]["pr_auc"][0] > best[1][0]["pr_auc"][0]:
                    best = (f"linear SVM (C={C:g})", r)
            res[best[0]] = best[1]

            lines += [f"\n### {scheme} CV\n",
                      "| model | PR-AUC | ROC-AUC | F1 | folds | skipped |",
                      "|---|---|---|---|---|---|"]
            print(f"  == {scheme} ==")
            for name, (agg, nf, sk) in res.items():
                lines.append(f"| {name} | {agg['pr_auc'][0]:.3f} ± {agg['pr_auc'][1]:.3f} "
                             f"| {agg['roc_auc'][0]:.3f} ± {agg['roc_auc'][1]:.3f} "
                             f"| {agg['f1'][0]:.3f} ± {agg['f1'][1]:.3f} | {nf} | {sk} |")
                note = f" ({sk} skipped)" if sk else ""
                print(f"    {name:20s} PR-AUC {agg['pr_auc'][0]:.3f}±{agg['pr_auc'][1]:.3f}  "
                      f"ROC {agg['roc_auc'][0]:.3f}  F1 {agg['f1'][0]:.3f}{note}")

    with open(os.path.join(RESULTS, "per_part_metrics.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\nwrote per_part_metrics.md -> {RESULTS}")


if __name__ == "__main__":
    main()
