"""Damage probe on all labeled images: majority, kNN, logistic regression and
linear SVM under grouped and stratified CV. Run make_splits.py first.

Usage: python train_probe.py
"""

import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve, roc_auc_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import LinearSVC

from paths import RESULTS, SPLITS, TRAINING

SEED = 42
C_GRID = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
K_GRID = [5, 15, 31]

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#1a1a19", "#6e6d66", "#e5e4dd"


def load():
    with open(SPLITS) as fh:
        sp = json.load(fh)
    df = pd.read_parquet(TRAINING)
    df = df[~df["uuid"].isin(set(sp["holdout_uuids"]))].reset_index(drop=True)
    X = np.stack(df["emb"].to_numpy()).astype(np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    y = (df["label"] == "Yes").to_numpy().astype(int)
    folds = {
        "grouped": df["uuid"].map(sp["group_folds"]).to_numpy(),
        "stratified": df["uuid"].map(sp["strat_folds"]).to_numpy(),
    }
    clusters = df["uuid"].map(sp["cluster_of"]).to_numpy()
    return X, y, folds, clusters


def fold_scores(model_fn, X, y, fold_ids, needs_proba=True):
    out, pooled_y, pooled_s = [], [], []
    for f in sorted(set(fold_ids)):
        tr, va = fold_ids != f, fold_ids == f
        m = model_fn()
        m.fit(X[tr], y[tr])
        if needs_proba:
            s_tr, s_va = m.predict_proba(X[tr])[:, 1], m.predict_proba(X[va])[:, 1]
        else:
            s_tr, s_va = m.decision_function(X[tr]), m.decision_function(X[va])
        # F1 threshold chosen on the training folds only
        prec, rec, thr = precision_recall_curve(y[tr], s_tr)
        f1s = 2 * prec * rec / np.clip(prec + rec, 1e-9, None)
        t = thr[max(0, np.argmax(f1s) - 1)] if len(thr) else 0.5
        out.append({
            "pr_auc": average_precision_score(y[va], s_va),
            "roc_auc": roc_auc_score(y[va], s_va),
            "f1": f1_score(y[va], s_va >= t),
            "f1_at_default": f1_score(y[va], s_va >= (0.5 if needs_proba else 0.0)),
        })
        pooled_y.append(y[va]); pooled_s.append(s_va)
    agg = {k: (float(np.mean([r[k] for r in out])), float(np.std([r[k] for r in out])))
           for k in out[0]}
    return agg, out, np.concatenate(pooled_y), np.concatenate(pooled_s)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    X, y, folds, clusters = load()
    print(f"train set: {len(y)} rows, {y.mean():.1%} Yes")

    results = {}
    c_curves = {}
    best = {}

    for scheme, fid in folds.items():
        res = {}
        prev = float(y.mean())
        res["majority"] = {"pr_auc": (prev, 0.0), "roc_auc": (0.5, 0.0),
                           "f1": (0.0, 0.0), "f1_at_default": (0.0, 0.0)}
        knn_best = None
        for k in K_GRID:
            agg, *_ = fold_scores(
                lambda k=k: KNeighborsClassifier(n_neighbors=k, metric="cosine"),
                X, y, fid)
            if knn_best is None or agg["pr_auc"][0] > knn_best[1]["pr_auc"][0]:
                knn_best = (k, agg)
        res[f"kNN (k={knn_best[0]})"] = knn_best[1]
        curve, lr_best = [], None
        for C in C_GRID:
            agg, per_fold, py, ps = fold_scores(
                lambda C=C: LogisticRegression(C=C, class_weight="balanced",
                                               max_iter=5000, random_state=SEED),
                X, y, fid)
            curve.append((C, *agg["pr_auc"]))
            if lr_best is None or agg["pr_auc"][0] > lr_best[1]["pr_auc"][0]:
                lr_best = (C, agg, per_fold, py, ps)
        c_curves[scheme] = curve
        res[f"logreg (C={lr_best[0]:g})"] = lr_best[1]
        best[scheme] = lr_best
        svm_best = None
        for C in C_GRID:
            agg, *_ = fold_scores(
                lambda C=C: LinearSVC(C=C, class_weight="balanced", max_iter=20000,
                                      random_state=SEED),
                X, y, fid, needs_proba=False)
            if svm_best is None or agg["pr_auc"][0] > svm_best[1]["pr_auc"][0]:
                svm_best = (C, agg)
        res[f"linear SVM (C={svm_best[0]:g})"] = svm_best[1]
        results[scheme] = res
        print(f"\n== {scheme} CV ==")
        for name, agg in res.items():
            print(f"  {name:22s} PR-AUC {agg['pr_auc'][0]:.3f}±{agg['pr_auc'][1]:.3f}  "
                  f"ROC {agg['roc_auc'][0]:.3f}  F1 {agg['f1'][0]:.3f}±{agg['f1'][1]:.3f}")

    # per-cluster breakdown of the best grouped logreg, out-of-fold
    py, ps = best["grouped"][3], best["grouped"][4]
    per_cluster = []
    fid = folds["grouped"]
    order = np.concatenate([np.where(fid == f)[0] for f in sorted(set(fid))])
    cl_pooled = clusters[order]
    for c in sorted(set(cl_pooled)):
        m = cl_pooled == c
        if len(set(py[m])) < 2:
            continue
        per_cluster.append({
            "cluster": c, "n": int(m.sum()), "prevalence": float(py[m].mean()),
            "pr_auc": float(average_precision_score(py[m], ps[m])),
            "roc_auc": float(roc_auc_score(py[m], ps[m])),
        })

    with open(os.path.join(RESULTS, "metrics.json"), "w") as fh:
        json.dump({"results": results, "c_curves": c_curves,
                   "per_cluster": per_cluster, "n_train": len(y),
                   "prevalence": float(y.mean())}, fh, indent=1, default=float)

    lines = [f"# Damage probe, all images (CV on {len(y)} training rows; holdout untouched)\n"]
    for scheme, res in results.items():
        lines += [f"\n## {scheme} CV\n",
                  "| model | PR-AUC | ROC-AUC | F1 (train-chosen thr) | F1 @ default |",
                  "|---|---|---|---|---|"]
        for name, a in res.items():
            lines.append(f"| {name} | {a['pr_auc'][0]:.3f} ± {a['pr_auc'][1]:.3f} "
                         f"| {a['roc_auc'][0]:.3f} ± {a['roc_auc'][1]:.3f} "
                         f"| {a['f1'][0]:.3f} ± {a['f1'][1]:.3f} "
                         f"| {a['f1_at_default'][0]:.3f} ± {a['f1_at_default'][1]:.3f} |")
    gap = (results['stratified'][[k for k in results['stratified'] if k.startswith('logreg')][0]]['pr_auc'][0]
           - results['grouped'][[k for k in results['grouped'] if k.startswith('logreg')][0]]['pr_auc'][0])
    lines += [f"\n**Leakage gap** (stratified − grouped, best logreg PR-AUC): **{gap:+.3f}**\n",
              "\n## Per-cluster (best grouped logreg, out-of-fold predictions)\n",
              "| cluster | n | prevalence | PR-AUC | ROC-AUC |", "|---|---|---|---|---|"]
    for r in per_cluster:
        lines.append(f"| {r['cluster']} | {r['n']} | {r['prevalence']:.2f} "
                     f"| {r['pr_auc']:.3f} | {r['roc_auc']:.3f} |")
    with open(os.path.join(RESULTS, "metrics.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")

    def style(ax):
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
        for s in ["left", "bottom"]:
            ax.spines[s].set_color(GRID)
        ax.grid(True, color=GRID, linewidth=0.6, alpha=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=MUTED, labelsize=9)
        for lbl in ax.get_xticklabels() + ax.get_yticklabels():
            lbl.set_color(MUTED)

    fig, ax = plt.subplots(figsize=(6.4, 4), dpi=150)
    for (scheme, curve), color in zip(c_curves.items(), [BLUE, ORANGE]):
        cs, mean, std = zip(*curve)
        mean, std = np.array(mean), np.array(std)
        ax.plot(cs, mean, color=color, linewidth=2, marker="o", markersize=5,
                label=f"{scheme} CV")
        ax.fill_between(cs, mean - std, mean + std, color=color, alpha=0.12, lw=0)
        ax.annotate(f"{scheme}", xy=(cs[-1], mean[-1]), xytext=(6, 0),
                    textcoords="offset points", color=color, fontsize=9, va="center")
    ax.set_xscale("log")
    ax.set_xlabel("C (inverse regularization strength)", color=INK, fontsize=10)
    ax.set_ylabel("PR-AUC (positive = Yes)", color=INK, fontsize=10)
    ax.set_title("Logistic regression: C search under both CV schemes",
                 color=INK, fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)
    style(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS, "c_search.png"), facecolor="white")

    fig, ax = plt.subplots(figsize=(6.4, 4), dpi=150)
    fid = folds["grouped"]
    C = best["grouped"][0]
    for j, f in enumerate(sorted(set(fid))):
        tr, va = fid != f, fid == f
        m = LogisticRegression(C=C, class_weight="balanced", max_iter=5000,
                               random_state=SEED).fit(X[tr], y[tr])
        s = m.predict_proba(X[va])[:, 1]
        prec, rec, _ = precision_recall_curve(y[va], s)
        ax.plot(rec, prec, color="#86b6ef", linewidth=1, alpha=0.8,
                label="individual folds" if j == 0 else None)
    prec, rec, _ = precision_recall_curve(best["grouped"][3], best["grouped"][4])
    ax.plot(rec, prec, color=BLUE, linewidth=2.2, label=f"pooled folds (C={C:g})")
    ax.axhline(y.mean(), color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.annotate(f"chance = prevalence ({y.mean():.2f})", xy=(0.02, y.mean()),
                xytext=(0, 5), textcoords="offset points", color=MUTED, fontsize=8.5)
    ax.set_xlabel("Recall (Yes)", color=INK, fontsize=10)
    ax.set_ylabel("Precision (Yes)", color=INK, fontsize=10)
    ax.set_title("Precision-recall, best logistic regression (grouped CV)",
                 color=INK, fontsize=11, loc="left")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="lower left")
    style(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS, "pr_curves.png"), facecolor="white")

    print(f"\nwrote metrics.json, metrics.md, c_search.png, pr_curves.png -> {RESULTS}")


if __name__ == "__main__":
    main()
