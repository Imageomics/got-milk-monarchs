"""Leaf-damage labeling app (stdlib only — runs on any Python 3.8+).

Serves images from a folder (recursive) one at a time in the browser with
Yes / No / Uninformative buttons (keyboard: y / n / u), scroll-wheel zoom,
drag-to-pan. If a uuid -> URL map is provided, the browser tries the
high-resolution iNaturalist original first (3 attempts) and falls back to
the on-disk image.

Each answer appends one tab-separated line
    <relative filename>\t<label>\t<labeler>\t<ISO timestamp>
to the labels file and advances. Already-labeled images are skipped on
restart, so the app can be stopped and resumed freely.

Navigate back/forward with the arrow buttons (or arrow keys) to review and
fix mistakes: answering again overwrites the previous label (the file stays
append-only; the newest line per image wins). Labeled images are framed
green (Yes), red (No), or gray (Uninformative).

Usage:
    python3 label_app.py <image_folder> --labeler yourname \
        [--clusters 4 | --clusters cluster_4,cluster_6] \
        [--manifest manifest_yourname.txt] [--urls urls.json] \
        [--labels PATH] [--port 8799] [--host 127.0.0.1]

With --manifest, only the listed files (relative paths, one per line) are
shown — this is how per-person cluster assignments are enforced.
With --clusters, only the named cluster subfolder(s) are shown (bare
numbers are accepted); combine with --manifest to label your assignment
one cluster at a time. Restart with a different value to switch cluster —
progress in the labels file is never lost.
"""

import argparse
import collections
import datetime
import html
import json
import mimetypes
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EXTS = {".png", ".webp", ".jpg", ".jpeg"}
LABELS = {"Yes", "No", "Uninformative"}

PAGE = """<!doctype html>
<title>Leaf damage labeling</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee;
         display: flex; flex-direction: column; align-items: center; min-height: 100vh; }}
  header {{ padding: 10px; font-size: 14px; color: #aaa; }}
  .img-box {{ flex: 1; display: flex; align-items: center; justify-content: center;
              overflow: hidden; width: 92vw; height: 70vh; }}
  img {{ max-width: 92vw; max-height: 70vh; border-radius: 6px;
         transform-origin: 0 0; cursor: zoom-in; user-select: none;
         border: 5px solid {border_color}; box-sizing: border-box; }}
  .zoom-hint {{ font-size: 12px; color: #888; margin-top: 4px; }}
  .nav {{ display: flex; gap: 12px; align-items: center; margin-top: 8px; font-size: 15px; }}
  .nav a {{ color: #ddd; background: #2a2a2a; text-decoration: none;
            padding: 6px 14px; border-radius: 6px; }}
  .nav .pos {{ color: #888; }}
  .curlabel {{ font-weight: 600; }}
  .q {{ font-size: 20px; margin: 12px; }}
  .buttons {{ display: flex; gap: 14px; margin-bottom: 24px; }}
  button {{ font-size: 18px; padding: 12px 28px; border-radius: 8px; border: none; cursor: pointer; }}
  .yes {{ background: #2e7d32; color: white; }}
  .no  {{ background: #c62828; color: white; }}
  .uninf {{ background: #616161; color: white; }}
  kbd {{ background: #333; border-radius: 4px; padding: 1px 6px; font-size: 13px; }}
</style>
<header>{labeler} &middot; {progress} labeled &middot; {remaining} remaining &middot; <code>{fname}</code>
  &middot; <span id="srcbadge" style="color:#7a7">loading&hellip;</span></header>
<div class="img-box"><img id="im" alt="specimen image" draggable="false"
  data-hi="{hi_url}" data-local="/img/{fname_url}"></div>
<div class="zoom-hint">scroll to zoom &middot; drag to pan &middot; double-click or <kbd>0</kbd> to reset</div>
<div class="nav">
  <a id="prev" href="/?i={prev_i}">&larr; <kbd>&#8592;</kbd></a>
  <span class="pos">{pos} / {total}</span>
  <a id="next" href="/?i={next_i}">&rarr; <kbd>&#8594;</kbd></a>
  <a href="/">&#9193; next unlabeled</a>
  <span class="curlabel" style="color:{label_color}">{cur_label}</span>
</div>
<div class="q">Does this image contain leaf damages?</div>
<form method="POST" action="/label" class="buttons">
  <input type="hidden" name="fname" value="{fname_attr}">
  <input type="hidden" name="i" value="{i}">
  <button class="yes" name="label" value="Yes">Yes <kbd>y</kbd></button>
  <button class="no" name="label" value="No">No <kbd>n</kbd></button>
  <button class="uninf" name="label" value="Uninformative">Uninformative <kbd>u</kbd></button>
</form>
<script>
document.addEventListener('keydown', e => {{
  if (e.key === '0') {{ reset(); return; }}
  if (e.key === 'ArrowLeft') {{ document.getElementById('prev').click(); return; }}
  if (e.key === 'ArrowRight') {{ document.getElementById('next').click(); return; }}
  const map = {{y: 'Yes', n: 'No', u: 'Uninformative'}};
  const v = map[e.key.toLowerCase()];
  if (!v) return;
  document.querySelector(`button[value=${{v}}]`).click();
}});

// --- image source: try high-res URL up to 3 times, then fall back to disk ---
const im = document.getElementById('im');
const badge = document.getElementById('srcbadge');
const HI = im.dataset.hi, LOCAL = im.dataset.local;
let tries = 0;
im.onerror = () => {{
  tries++;
  if (HI && tries < 3) {{
    im.src = HI + (HI.includes('?') ? '&' : '?') + 'retry=' + tries;
  }} else {{
    im.onerror = null;
    im.src = LOCAL;
    badge.textContent = 'local' + (HI ? ' (high-res failed)' : '');
    badge.style.color = '#ca8';
  }}
}};
im.onload = () => {{
  if (im.src.startsWith(location.origin)) {{
    badge.textContent = `local ${{im.naturalWidth}}×${{im.naturalHeight}}`;
    badge.style.color = '#ca8';
  }} else {{
    badge.textContent = `iNat original ${{im.naturalWidth}}×${{im.naturalHeight}}`;
    badge.style.color = '#7a7';
  }}
}};
im.src = HI || LOCAL;

// --- zoom & pan ---
const box = document.querySelector('.img-box');
let scale = 1, tx = 0, ty = 0, dragging = false, sx = 0, sy = 0;

function apply() {{
  im.style.transform = `translate(${{tx}}px, ${{ty}}px) scale(${{scale}})`;
  im.style.cursor = scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'zoom-in';
}}
function reset() {{ scale = 1; tx = 0; ty = 0; apply(); }}

box.addEventListener('wheel', e => {{
  e.preventDefault();
  const rect = im.getBoundingClientRect();
  const px = (e.clientX - rect.left) / scale;
  const py = (e.clientY - rect.top) / scale;
  const factor = e.deltaY < 0 ? 1.2 : 1 / 1.2;
  const ns = Math.min(12, Math.max(1, scale * factor));
  tx += px * (scale - ns);
  ty += py * (scale - ns);
  scale = ns;
  if (scale === 1) {{ tx = 0; ty = 0; }}
  apply();
}}, {{passive: false}});

im.addEventListener('mousedown', e => {{
  if (scale === 1) return;
  dragging = true; sx = e.clientX - tx; sy = e.clientY - ty;
  e.preventDefault(); apply();
}});
window.addEventListener('mousemove', e => {{
  if (!dragging) return;
  tx = e.clientX - sx; ty = e.clientY - sy; apply();
}});
window.addEventListener('mouseup', () => {{ dragging = false; apply(); }});
im.addEventListener('dblclick', e => {{
  if (scale === 1) {{
    const rect = im.getBoundingClientRect();
    scale = 3;
    tx = (e.clientX - rect.left) * (1 - scale);
    ty = (e.clientY - rect.top) * (1 - scale);
    apply();
  }} else reset();
}});
</script>
"""

DONE_PAGE = """<!doctype html>
<title>Leaf damage labeling</title>
<body style="font-family:system-ui;background:#111;color:#eee;display:flex;
             align-items:center;justify-content:center;height:100vh">
<div style="text-align:center"><h1>All done &#127881;</h1><p>{n} images labeled.<br>
Labels file: <code>{labels}</code></p>
<p><a href="/?i=0" style="color:#7a7">review from the start &rarr;</a></p></div>
"""


class State:
    def __init__(self, folder, labels_path, labeler, urls_json=None, manifest=None, clusters=None):
        self.folder = os.path.abspath(folder)
        self.labels_path = labels_path
        self.labeler = labeler
        on_disk = sorted(
            os.path.relpath(os.path.join(dp, f), self.folder)
            for dp, _, fs in os.walk(self.folder)
            for f in fs
            if os.path.splitext(f)[1].lower() in EXTS
        )
        if manifest:
            with open(manifest) as fh:
                assigned = [line.strip() for line in fh if line.strip()]
            missing = [f for f in assigned if f not in set(on_disk)]
            if missing:
                print(f"WARNING: {len(missing)} manifest files not on disk, e.g. {missing[0]}")
            self.files = [f for f in assigned if f in set(on_disk)]
        else:
            self.files = on_disk

        if clusters:
            available = {f.split(os.sep)[0] for f in self.files}
            # accept "4" or "cluster_4"
            want = {c if c in available else f"cluster_{c}" for c in clusters}
            unknown = want - available
            if unknown:
                raise SystemExit(
                    f"unknown cluster(s): {', '.join(sorted(unknown))}; "
                    f"available: {', '.join(sorted(available))}"
                )
            self.files = [f for f in self.files if f.split(os.sep)[0] in want]
        self.file_set = set(self.files)

        self.urls = {}
        if urls_json:
            with open(urls_json) as fh:
                self.urls = json.load(fh)

        # fname -> current label; file is append-only, newest line wins
        self.labels = {}
        if os.path.exists(labels_path):
            with open(labels_path) as fh:
                for line in fh:
                    if line.strip():
                        parts = line.rstrip("\n").split("\t")
                        if len(parts) >= 2:
                            self.labels[parts[0]] = parts[1]

    def done_count(self):
        return sum(1 for f in self.files if f in self.labels)

    def next_unlabeled_index(self, after=-1):
        """First unlabeled index > after, else first unlabeled anywhere, else None."""
        n = len(self.files)
        for i in list(range(after + 1, n)) + list(range(0, after + 1)):
            if self.files[i] not in self.labels:
                return i
        return None

    def record(self, fname, label):
        if fname not in self.file_set:
            raise ValueError(f"unknown file: {fname}")
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(self.labels_path, "a") as fh:
            fh.write(f"{fname}\t{label}\t{self.labeler}\t{ts}\n")
            fh.flush()
        self.labels[fname] = label


STATE = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _html(self, body, code=200):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        if path == "/":
            qs = urllib.parse.parse_qs(parsed.query)
            n = len(STATE.files)
            if "i" in qs:
                try:
                    i = max(0, min(n - 1, int(qs["i"][0])))
                except ValueError:
                    i = 0
            else:
                i = STATE.next_unlabeled_index()
                if i is None:
                    self._html(DONE_PAGE.format(n=STATE.done_count(),
                                                labels=html.escape(STATE.labels_path)))
                    return
            fname = STATE.files[i]
            uuid = os.path.splitext(os.path.basename(fname))[0]
            cur = STATE.labels.get(fname)
            colors = {"Yes": "#2e7d32", "No": "#c62828", "Uninformative": "#9e9e9e"}
            done = STATE.done_count()
            self._html(PAGE.format(
                labeler=html.escape(STATE.labeler),
                progress=done,
                remaining=n - done,
                fname=html.escape(fname),
                fname_url=urllib.parse.quote(fname),
                fname_attr=html.escape(fname, quote=True),
                hi_url=html.escape(STATE.urls.get(uuid, ""), quote=True),
                i=i, pos=i + 1, total=n,
                prev_i=max(0, i - 1), next_i=min(n - 1, i + 1),
                border_color=colors.get(cur, "transparent"),
                label_color=colors.get(cur, "#888"),
                cur_label=html.escape(cur) if cur else "unlabeled",
            ))
        elif path.startswith("/img/"):
            rel = path[len("/img/"):]
            full = os.path.normpath(os.path.join(STATE.folder, rel))
            if not full.startswith(STATE.folder) or not os.path.isfile(full):
                self._html("not found", 404)
                return
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            with open(full, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        else:
            self._html("not found", 404)

    def do_POST(self):
        if self.path != "/label":
            self._html("not found", 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        fname = form.get("fname", [""])[0]
        label = form.get("label", [""])[0]
        if label not in LABELS:
            self._html("bad label", 400)
            return
        try:
            STATE.record(fname, label)
        except ValueError:
            self._html("unknown file", 400)
            return
        try:
            i = int(form.get("i", ["-1"])[0])
        except ValueError:
            i = -1
        nxt = STATE.next_unlabeled_index(after=i)
        self.send_response(303)
        self.send_header("Location", "/" if nxt is None else f"/?i={nxt}")
        self.end_headers()


def main():
    global STATE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="image folder (searched recursively)")
    ap.add_argument("--labeler", required=True, help="your name; recorded with every label")
    ap.add_argument("--manifest", default=None, help="only label files listed here (one relative path per line)")
    ap.add_argument("--clusters", default=None,
                    help="comma-separated cluster(s) to label, e.g. '4' or 'cluster_4,cluster_6'")
    ap.add_argument("--urls", default=None, help="urls.json mapping uuid -> high-res source URL")
    ap.add_argument("--labels", default=None, help="labels file (default: labels_<labeler>.tsv next to this script)")
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    labels = args.labels or os.path.join(here, f"labels_{args.labeler}.tsv")
    urls = args.urls if args.urls else (
        os.path.join(here, "urls.json") if os.path.exists(os.path.join(here, "urls.json")) else None
    )
    clusters = [c.strip() for c in args.clusters.split(",")] if args.clusters else None
    STATE = State(args.folder, labels, args.labeler, urls, args.manifest, clusters)
    print(f"{len(STATE.files)} images assigned in {STATE.folder}")
    per_cluster = collections.Counter(f.split(os.sep)[0] for f in STATE.files)
    done_per = collections.Counter(f.split(os.sep)[0] for f in STATE.files if f in STATE.labels)
    for c in sorted(per_cluster, key=lambda x: (len(x), x)):
        print(f"  {c}: {done_per[c]}/{per_cluster[c]} labeled")
    if STATE.urls:
        print(f"{len(STATE.urls)} high-res URLs loaded")
    print(f"{STATE.done_count()} already labeled; labels append to {labels}")
    print(f"serving on http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
