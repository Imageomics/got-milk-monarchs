"""Merge and validate everyone's label files.

Reads all labels_*.tsv files (or explicit paths), validates them, merges to
one TSV, and reports inter-annotator agreement on the overlap set:
  - labels must be Yes / No / Uninformative
  - duplicate labels by the same person for the same file -> keep last, warn
  - with assignments.json: flags files labeled outside a person's manifest
    and reports per-person coverage
  - files labeled by 2+ people: percent agreement + Fleiss' kappa + a list
    of disagreements

Usage:
    python3 merge_labels.py [labels_*.tsv ...] [--assignments assignments.json] \
        [--out merged_labels.tsv]

Old 2-column files (filename<TAB>label) are accepted; labeler is then taken
from the filename (labels_<name>.tsv) and timestamp is empty.
"""

import argparse
import collections
import glob
import json
import os

VOCAB = {"Yes", "No", "Uninformative"}


def read_file(path):
    default_labeler = os.path.basename(path).removeprefix("labels_").removesuffix(".tsv")
    rows = []
    with open(path) as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                print(f"WARNING {path}:{i}: malformed line skipped")
                continue
            fname, label = parts[0], parts[1]
            labeler = parts[2] if len(parts) > 2 and parts[2] else default_labeler
            ts = parts[3] if len(parts) > 3 else ""
            if label not in VOCAB:
                print(f"WARNING {path}:{i}: bad label {label!r} skipped")
                continue
            rows.append((fname, label, labeler, ts))
    return rows


def fleiss_kappa(votes_per_item):
    """votes_per_item: list of Counters (label -> count), same raters per item."""
    n = votes_per_item[0].total()
    if n < 2 or any(v.total() != n for v in votes_per_item):
        return None  # unequal rater counts; kappa not well-defined here
    N = len(votes_per_item)
    cats = sorted(VOCAB)
    p_cat = {c: sum(v[c] for v in votes_per_item) / (N * n) for c in cats}
    P_i = [(sum(v[c] ** 2 for c in cats) - n) / (n * (n - 1)) for v in votes_per_item]
    P_bar = sum(P_i) / N
    P_e = sum(p ** 2 for p in p_cat.values())
    return (P_bar - P_e) / (1 - P_e) if P_e < 1 else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="label TSVs (default: labels_*.tsv here)")
    ap.add_argument("--assignments", default=None, help="assignments.json from make_assignments.py")
    ap.add_argument("--out", default="merged_labels.tsv")
    args = ap.parse_args()

    paths = args.files or sorted(glob.glob("labels_*.tsv"))
    if not paths:
        raise SystemExit("no label files found")

    # per (labeler, fname) keep the last occurrence
    latest = {}
    dup_count = collections.Counter()
    for p in paths:
        for fname, label, labeler, ts in read_file(p):
            if (labeler, fname) in latest:
                dup_count[labeler] += 1
            latest[(labeler, fname)] = (fname, label, labeler, ts)
    rows = sorted(latest.values())
    for labeler, d in dup_count.items():
        print(f"NOTE: {labeler} relabeled {d} file(s); kept the last label")

    manifests = {}
    if args.assignments:
        with open(args.assignments) as fh:
            rec = json.load(fh)
        outdir = os.path.dirname(os.path.abspath(args.assignments))
        for name in rec["assignments"]:
            with open(os.path.join(outdir, f"manifest_{name}.txt")) as fh:
                manifests[name] = {l.strip() for l in fh if l.strip()}
        for fname, label, labeler, ts in rows:
            if labeler in manifests and fname not in manifests[labeler]:
                print(f"WARNING: {labeler} labeled {fname} outside their manifest")
        print("\ncoverage:")
        done = collections.defaultdict(set)
        for fname, _, labeler, _ in rows:
            done[labeler].add(fname)
        for name, m in sorted(manifests.items()):
            print(f"  {name}: {len(done[name] & m)}/{len(m)}")

    # agreement on files labeled by 2+ people
    by_file = collections.defaultdict(dict)
    for fname, label, labeler, _ in rows:
        by_file[fname][labeler] = label
    multi = {f: v for f, v in by_file.items() if len(v) >= 2}
    if multi:
        agree = [f for f, v in multi.items() if len(set(v.values())) == 1]
        print(f"\noverlap: {len(multi)} files labeled by 2+ people; "
              f"full agreement on {len(agree)} ({100 * len(agree) / len(multi):.0f}%)")
        counts = [collections.Counter(v.values()) for v in multi.values()]
        kappa = fleiss_kappa(counts)
        if kappa is not None:
            print(f"Fleiss' kappa: {kappa:.3f}")
        else:
            print("Fleiss' kappa skipped (unequal rater counts per file)")
        disagreements = sorted(f for f, v in multi.items() if len(set(v.values())) > 1)
        for f in disagreements[:20]:
            print(f"  DISAGREE {f}: " + ", ".join(f"{k}={v}" for k, v in sorted(multi[f].items())))
        if len(disagreements) > 20:
            print(f"  ... and {len(disagreements) - 20} more")

    with open(args.out, "w") as fh:
        fh.write("filename\tlabel\tlabeler\ttimestamp\n")
        for r in rows:
            fh.write("\t".join(r) + "\n")
    print(f"\nmerged {len(rows)} labels from {len(paths)} file(s) -> {args.out}")


if __name__ == "__main__":
    main()
