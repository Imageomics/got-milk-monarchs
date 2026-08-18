# Leaf-Damage Label Interface

Label milkweed (*Asclepias syriaca*) iNaturalist images as **Yes / No /
Uninformative** for leaf damage. One image at a time, in your browser.

## What you need

- Python 3.9+ (standard library only — nothing to install)
- This folder: `label_app.py`, `urls.json`, `filelist.txt`, and (if assigned)
  your `manifest_<you>.txt`
- Optional: the shared `images/` folder (`cluster_*/uuid.png`) — only needed
  for offline work; otherwise images stream from iNaturalist

## Start

All commands run from this `labeling/` folder. Easiest — **web-only mode**,
no images to download (needs internet):

```bash
cd labeling
python3 label_app.py --labeler <you> --clusters 4
```

Or with the local `images/` folder (works offline, and is the fallback when
an iNat fetch fails):

```bash
python3 label_app.py path/to/images/ --labeler <you> --clusters 4
```

then open **http://localhost:8799**.

Common options:

```bash
--clusters 4                # label only cluster_4 (bare number or full name)
--clusters cluster_6,10     # several clusters
--manifest manifest_me.txt  # only your assigned images
--port 8799                 # change if the port is taken
```

Work cluster-by-cluster and restart with a different `--clusters` when you
finish one — progress is never lost.

## Labeling

- Click **Yes / No / Uninformative**, or press <kbd>y</kbd> / <kbd>n</kbd> / <kbd>u</kbd>
- Scroll to zoom, drag to pan, double-click or <kbd>0</kbd> to reset
- ← / → (buttons or arrow keys) to go back and fix a mistake — answering
  again overwrites; labeled images are framed green (Yes), red (No),
  gray (Uninformative)
- The header badge shows whether you see the iNat original (high-res,
  3 attempts) or the local 720px fallback; in web-only mode a failed fetch
  says so instead

## Output

Labels append to `labels_<you>.tsv` — one line per image:
`filename ⇥ label ⇥ labeler ⇥ timestamp`. Stop anytime; restarting skips
what's done. When finished, send this file back.

## Coordinator

```bash
python3 make_assignments.py path/to/images/ --names alice,bob,carol --overlap 75
python3 merge_labels.py labels_*.tsv --assignments assignments.json
```

`make_assignments.py` splits clusters evenly and adds a shared overlap set;
`merge_labels.py` validates everything and reports agreement (Fleiss' kappa)
before writing `merged_labels.tsv`.
