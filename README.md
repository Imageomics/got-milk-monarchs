# got-milk-monarchs 🥛🦋

Leaf-damage labeling for *Asclepias syriaca* (common milkweed) iNaturalist
images, sampled from TreeOfLife-200M for FloraPalooza 2026.

Everything here is plain Python standard library (3.9+) — no installs needed.

## Quick start (labelers)

1. Get the shared `images/` folder (distributed separately; contains
   `cluster_*/uuid.png`) and your `manifest_<you>.txt`.
2. Run:

   ```bash
   python3 label_app.py images/ --labeler <you> --manifest manifest_<you>.txt
   ```

3. Open http://localhost:8799 and answer **Does this image contain leaf
   damages?** — click or press <kbd>y</kbd> / <kbd>n</kbd> / <kbd>u</kbd>
   (Yes / No / Uninformative).

   - Scroll to zoom (cursor-centered), drag to pan, double-click or
     <kbd>0</kbd> to reset.
   - The app shows the full-resolution iNaturalist original when it can
     (3 attempts), otherwise the local 720px copy — the badge in the header
     tells you which you're seeing.

Labels append to `labels_<you>.tsv` (`filename  label  labeler  timestamp`,
tab-separated). Stop anytime; restarting skips what you've done. When your
manifest is finished the app shows a done page — send your
`labels_<you>.tsv` back.

## Coordinator workflow

```bash
# 1. divide clusters fairly + create the shared overlap set
python3 make_assignments.py images/ --names alice,bob,carol --overlap 75

# 2. distribute: label_app.py, urls.json, manifest_<name>.txt, images/

# 3. when the label files come back, merge + validate + agreement report
python3 merge_labels.py labels_*.tsv --assignments assignments.json
```

`make_assignments.py` bin-packs cluster folders so everyone gets a
near-equal image count, and prepends the same random overlap set to every
manifest. `merge_labels.py` checks label vocabulary, duplicate/out-of-manifest
labels, per-person coverage, and reports percent agreement and Fleiss' kappa
on the overlap set before writing `merged_labels.tsv`.

## Files

| File | What |
|---|---|
| `label_app.py` | the labeling web app (stdlib only) |
| `make_assignments.py` | cluster bin-packing + overlap set → manifests |
| `merge_labels.py` | merge, validate, agreement report |
| `urls.json` | uuid → iNaturalist original URL (1,658 entries — the labeling set) |

Images and label data are intentionally not tracked in git.
