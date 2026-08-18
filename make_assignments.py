"""Divide cluster folders among labelers and generate per-person manifests.

Clusters (immediate subfolders of the image folder) are greedily bin-packed
by image count so everyone gets a near-equal share. On top of their own
clusters, every person also gets the SAME random overlap set for measuring
inter-annotator agreement (see merge_labels.py).

Usage:
    python3 make_assignments.py <image_folder> --names alice,bob,carol \
        [--overlap 75] [--seed 42] [--outdir .]

Writes manifest_<name>.txt (one relative path per line, overlap first) and
assignments.json (the full assignment record).
"""

import argparse
import json
import os
import random

EXTS = {".png", ".webp", ".jpg", ".jpeg"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--names", required=True, help="comma-separated labeler names")
    ap.add_argument("--overlap", type=int, default=75, help="shared images per person for agreement")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()

    folder = os.path.abspath(args.folder)
    names = [n.strip() for n in args.names.split(",") if n.strip()]

    clusters = {}
    for d in sorted(os.listdir(folder)):
        full = os.path.join(folder, d)
        if os.path.isdir(full):
            files = sorted(
                os.path.join(d, f) for f in os.listdir(full)
                if os.path.splitext(f)[1].lower() in EXTS
            )
            if files:
                clusters[d] = files
    if not clusters:
        raise SystemExit("no cluster subfolders with images found")

    # Greedy bin-packing: biggest cluster to the currently lightest person.
    load = {n: 0 for n in names}
    owned = {n: [] for n in names}
    for cname, files in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        lightest = min(names, key=lambda n: load[n])
        owned[lightest].append(cname)
        load[lightest] += len(files)

    all_files = [f for files in clusters.values() for f in files]
    rng = random.Random(args.seed)
    overlap = sorted(rng.sample(all_files, min(args.overlap, len(all_files))))

    record = {"folder": folder, "seed": args.seed, "overlap": overlap, "assignments": {}}
    for n in names:
        own_files = [f for c in sorted(owned[n]) for f in clusters[c]]
        manifest = overlap + [f for f in own_files if f not in set(overlap)]
        path = os.path.join(args.outdir, f"manifest_{n}.txt")
        with open(path, "w") as fh:
            fh.write("\n".join(manifest) + "\n")
        record["assignments"][n] = {"clusters": sorted(owned[n]), "n_own": len(own_files),
                                    "n_total": len(manifest)}
        print(f"{n}: clusters {sorted(owned[n])} -> {len(own_files)} own + "
              f"{len(manifest) - len(own_files)} overlap-only = {len(manifest)} total ({path})")

    with open(os.path.join(args.outdir, "assignments.json"), "w") as fh:
        json.dump(record, fh, indent=2)
    print(f"total images: {len(all_files)}; overlap set: {len(overlap)}")


if __name__ == "__main__":
    main()
