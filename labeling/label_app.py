"""Leaf-damage labeling app (stdlib only — runs on any Python 3.9+).

Single-page app: images swap in place with no page reloads, and the next
12 images are prefetched in the background so advancing is instant.
Yes / No / Uninformative buttons (keyboard: y / n / u), back/forward
navigation (arrow keys) to review and fix — answering again overwrites
(the labels file stays append-only; the newest line per image wins).
Labeled images are framed green (Yes), red (No), or gray (Uninformative).

Images come from the high-resolution iNaturalist originals (3 attempts)
with the local file as fallback. In web-only mode (no folder argument,
list from filelist.txt) there is no local fallback and a failed fetch is
reported on screen.

Each answer appends one tab-separated line
    <relative filename>\t<label>\t<labeler>\t<ISO timestamp>
to the labels file. Already-labeled images are skipped on restart.

Usage:
    python3 label_app.py [image_folder] --labeler yourname \
        [--clusters 4 | --clusters cluster_4,cluster_6] \
        [--manifest manifest_yourname.txt] [--filelist filelist.txt] \
        [--urls urls.json] [--labels PATH] [--port 8799] [--host 127.0.0.1]
"""

import argparse
import collections
import datetime
import json
import mimetypes
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EXTS = {".png", ".webp", ".jpg", ".jpeg"}
LABELS = {"Yes", "No", "Uninformative"}

SHELL = """<!doctype html>
<title>Leaf damage labeling</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee;
         display: flex; flex-direction: column; align-items: center; min-height: 100vh; }
  header { padding: 10px; font-size: 14px; color: #aaa; }
  .img-box { flex: 1; display: flex; align-items: center; justify-content: center;
             overflow: hidden; width: 92vw; height: 70vh; }
  img { max-width: 92vw; max-height: 70vh; border-radius: 6px;
        transform-origin: 0 0; cursor: zoom-in; user-select: none;
        border: 5px solid transparent; box-sizing: border-box; }
  .zoom-hint { font-size: 12px; color: #888; margin-top: 4px; }
  .nav { display: flex; gap: 12px; align-items: center; margin-top: 8px; font-size: 15px; }
  .nav button { font-size: 15px; padding: 6px 14px; border-radius: 6px; border: none;
                background: #2a2a2a; color: #ddd; cursor: pointer; }
  .nav .pos { color: #888; }
  .curlabel { font-weight: 600; }
  .q { font-size: 20px; margin: 12px; }
  .buttons { display: flex; gap: 14px; margin-bottom: 24px; }
  .buttons button { font-size: 18px; padding: 12px 28px; border-radius: 8px;
                    border: none; cursor: pointer; }
  .yes { background: #2e7d32; color: white; }
  .no  { background: #c62828; color: white; }
  .uninf { background: #616161; color: white; }
  kbd { background: #333; border-radius: 4px; padding: 1px 6px; font-size: 13px; }
  #donebox { display: none; text-align: center; margin: 40px; }
</style>
<header><span id="labeler"></span> &middot; <span id="done"></span> labeled &middot;
  <span id="remaining"></span> remaining &middot; <code id="fname"></code>
  &middot; <span id="srcbadge" style="color:#7a7">loading&hellip;</span></header>
<div id="main">
<div class="img-box"><img id="im" alt="specimen image" draggable="false"></div>
<div class="zoom-hint">scroll to zoom &middot; drag to pan &middot; double-click or <kbd>0</kbd> to reset</div>
<div class="nav">
  <button id="prev">&larr; <kbd>&#8592;</kbd></button>
  <span class="pos"><span id="pos"></span> / <span id="total"></span></span>
  <button id="next">&rarr; <kbd>&#8594;</kbd></button>
  <button id="skip">&#9193; next unlabeled</button>
  <span class="curlabel" id="curlabel"></span>
</div>
<div class="q">Does this image contain damage from monarch caterpillars?</div>
<div class="buttons">
  <button class="yes" onclick="label('Yes')">Yes <kbd>y</kbd></button>
  <button class="no" onclick="label('No')">No <kbd>n</kbd></button>
  <button class="uninf" onclick="label('Uninformative')">Uninformative <kbd>u</kbd></button>
</div>
</div>
<div id="donebox"><h1>All done &#127881;</h1>
  <p><span id="donecount"></span> images labeled.</p>
  <p><button class="nav" onclick="review()">review from the start &rarr;</button></p>
</div>
<script>
const CFG = __CONFIG__;
const PREFETCH = 12;
const COLORS = {Yes: '#2e7d32', No: '#c62828', Uninformative: '#9e9e9e'};

const im = document.getElementById('im');
const badge = document.getElementById('srcbadge');
const $ = id => document.getElementById(id);
$('labeler').textContent = CFG.labeler;
$('total').textContent = CFG.total;

let cur = CFG.start;
const items = new Map();      // index -> metadata
const warmed = new Map();     // index -> Image() keeping the fetch warm

async function getItem(i) {
  if (!items.has(i)) {
    const r = await fetch('/api/item?i=' + i);
    items.set(i, await r.json());
  }
  return items.get(i);
}

function warm(i) {
  if (warmed.has(i)) return;
  getItem(i).then(it => {
    const pf = new Image();
    pf.onerror = () => { if (it.local) pf.src = it.local; };
    pf.src = it.hi || it.local;
    warmed.set(i, pf);
  });
}

function prefetchAround(i) {
  for (let j = i + 1; j <= Math.min(CFG.total - 1, i + PREFETCH); j++) warm(j);
  if (i > 0) warm(i - 1);
  for (const k of warmed.keys())            // drop entries far outside the window
    if (k < i - 3 || k > i + PREFETCH + 3) warmed.delete(k);
}

function paint(it) {
  $('fname').textContent = it.fname;
  $('pos').textContent = it.i + 1;
  $('done').textContent = it.done;
  $('remaining').textContent = CFG.total - it.done;
  const c = COLORS[it.label];
  im.style.borderColor = c || 'transparent';
  $('curlabel').textContent = it.label || 'unlabeled';
  $('curlabel').style.color = c || '#888';
}

async function show(i) {
  cur = Math.max(0, Math.min(CFG.total - 1, i));
  const it = await getItem(cur);
  paint(it);
  reset();                                   // zoom reset
  let tries = 0;
  badge.textContent = 'loading\\u2026'; badge.style.color = '#7a7';
  im.style.opacity = 1;
  im.onerror = () => {
    tries++;
    if (it.hi && tries < 3) {
      im.src = it.hi + (it.hi.includes('?') ? '&' : '?') + 'retry=' + tries;
    } else if (it.local && !im.src.endsWith(it.local)) {
      im.src = it.local;
      badge.textContent = 'local' + (it.hi ? ' (high-res failed)' : '');
      badge.style.color = '#ca8';
    } else {
      im.onerror = null;
      im.style.opacity = 0.15;
      badge.textContent = 'image failed to load \\u2014 label Uninformative or navigate on';
      badge.style.color = '#e57373';
    }
  };
  im.onload = () => {
    if (im.src.startsWith(location.origin)) {
      badge.textContent = `local ${im.naturalWidth}\\u00d7${im.naturalHeight}`;
      badge.style.color = '#ca8';
    } else {
      badge.textContent = `iNat original ${im.naturalWidth}\\u00d7${im.naturalHeight}`;
      badge.style.color = '#7a7';
    }
  };
  im.src = it.hi || it.local;
  prefetchAround(cur);
}

async function label(v) {
  const it = await getItem(cur);
  const r = await fetch('/api/label', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({fname: it.fname, label: v, i: cur}),
  });
  const resp = await r.json();
  if (!resp.ok) { alert(resp.error || 'label failed'); return; }
  it.label = v; it.done = resp.done;
  items.forEach(x => { x.done = resp.done; });
  if (resp.next === null) {
    $('main').style.display = 'none';
    $('donebox').style.display = 'block';
    $('donecount').textContent = resp.done;
  } else {
    show(resp.next);
  }
}

async function skip() {
  const r = await fetch('/api/next?after=' + cur);
  const j = await r.json();
  if (j.next !== null) show(j.next);
}

function review() {
  $('donebox').style.display = 'none';
  $('main').style.display = '';
  show(0);
}

$('prev').onclick = () => show(cur - 1);
$('next').onclick = () => show(cur + 1);
$('skip').onclick = skip;

document.addEventListener('keydown', e => {
  if (e.key === '0') { reset(); return; }
  if (e.key === 'ArrowLeft') { show(cur - 1); return; }
  if (e.key === 'ArrowRight') { show(cur + 1); return; }
  const map = {y: 'Yes', n: 'No', u: 'Uninformative'};
  if (map[e.key.toLowerCase()]) label(map[e.key.toLowerCase()]);
});

// --- zoom & pan ---
const box = document.querySelector('.img-box');
let scale = 1, tx = 0, ty = 0, dragging = false, sx = 0, sy = 0;

function apply() {
  im.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
  im.style.cursor = scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'zoom-in';
}
function reset() { scale = 1; tx = 0; ty = 0; apply(); }

box.addEventListener('wheel', e => {
  e.preventDefault();
  const rect = im.getBoundingClientRect();
  const px = (e.clientX - rect.left) / scale;
  const py = (e.clientY - rect.top) / scale;
  const factor = e.deltaY < 0 ? 1.2 : 1 / 1.2;
  const ns = Math.min(12, Math.max(1, scale * factor));
  tx += px * (scale - ns);
  ty += py * (scale - ns);
  scale = ns;
  if (scale === 1) { tx = 0; ty = 0; }
  apply();
}, {passive: false});

im.addEventListener('mousedown', e => {
  if (scale === 1) return;
  dragging = true; sx = e.clientX - tx; sy = e.clientY - ty;
  e.preventDefault(); apply();
});
window.addEventListener('mousemove', e => {
  if (!dragging) return;
  tx = e.clientX - sx; ty = e.clientY - sy; apply();
});
window.addEventListener('mouseup', () => { dragging = false; apply(); });
im.addEventListener('dblclick', e => {
  if (scale === 1) {
    const rect = im.getBoundingClientRect();
    scale = 3;
    tx = (e.clientX - rect.left) * (1 - scale);
    ty = (e.clientY - rect.top) * (1 - scale);
    apply();
  } else reset();
});

if (CFG.all_done) {
  $('main').style.display = 'none';
  $('donebox').style.display = 'block';
  $('donecount').textContent = CFG.done;
} else {
  show(CFG.start);
}
</script>
"""


class State:
    def __init__(self, folder, labels_path, labeler, urls_json=None, manifest=None,
                 clusters=None, filelist=None):
        self.folder = os.path.abspath(folder) if folder else None
        self.labels_path = labels_path
        self.labeler = labeler
        if self.folder:
            # relative paths always use forward slashes, on every OS, so
            # filelists, manifests, and label files are portable
            on_disk = sorted(
                os.path.relpath(os.path.join(dp, f), self.folder).replace(os.sep, "/")
                for dp, _, fs in os.walk(self.folder)
                for f in fs
                if os.path.splitext(f)[1].lower() in EXTS
            )
        else:  # web-only: image list comes from the filelist, images from URLs
            with open(filelist) as fh:
                on_disk = sorted(line.strip() for line in fh if line.strip())

        if manifest:
            with open(manifest) as fh:
                assigned = [line.strip() for line in fh if line.strip()]
            missing = [f for f in assigned if f not in set(on_disk)]
            if missing:
                print(f"WARNING: {len(missing)} manifest files not available, e.g. {missing[0]}")
            self.files = [f for f in assigned if f in set(on_disk)]
        else:
            self.files = on_disk

        if clusters:
            available = {f.split("/")[0] for f in self.files}
            # accept "4" or "cluster_4"
            want = {c if c in available else f"cluster_{c}" for c in clusters}
            unknown = want - available
            if unknown:
                raise SystemExit(
                    f"unknown cluster(s): {', '.join(sorted(unknown))}; "
                    f"available: {', '.join(sorted(available))}"
                )
            self.files = [f for f in self.files if f.split("/")[0] in want]
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

    def item(self, i):
        fname = self.files[i]
        uuid = os.path.splitext(os.path.basename(fname))[0]
        return {
            "i": i,
            "fname": fname,
            "hi": self.urls.get(uuid, ""),
            "local": f"/img/{urllib.parse.quote(fname)}" if self.folder else "",
            "label": self.labels.get(fname),
            "done": self.done_count(),
        }

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

    def _send(self, data, ctype, code=200, cache=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if cache:
            self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(json.dumps(obj).encode(), "application/json", code)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            start = STATE.next_unlabeled_index()
            cfg = {
                "labeler": STATE.labeler,
                "total": len(STATE.files),
                "start": start if start is not None else 0,
                "all_done": start is None,
                "done": STATE.done_count(),
            }
            page = SHELL.replace("__CONFIG__", json.dumps(cfg))
            self._send(page.encode(), "text/html; charset=utf-8")
        elif path == "/api/item":
            try:
                i = max(0, min(len(STATE.files) - 1, int(qs.get("i", ["0"])[0])))
            except ValueError:
                self._json({"error": "bad index"}, 400)
                return
            self._json(STATE.item(i))
        elif path == "/api/next":
            try:
                after = int(qs.get("after", ["-1"])[0])
            except ValueError:
                after = -1
            self._json({"next": STATE.next_unlabeled_index(after)})
        elif path.startswith("/img/"):
            if STATE.folder is None:
                self._send(b"web-only mode: no local images", "text/plain", 404)
                return
            rel = path[len("/img/"):]
            full = os.path.normpath(os.path.join(STATE.folder, rel))
            if not full.startswith(STATE.folder) or not os.path.isfile(full):
                self._send(b"not found", "text/plain", 404)
                return
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            with open(full, "rb") as fh:
                self._send(fh.read(), ctype, cache=True)
        else:
            self._send(b"not found", "text/plain", 404)

    def do_POST(self):
        if self.path != "/api/label":
            self._json({"ok": False, "error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        fname = form.get("fname", [""])[0]
        label = form.get("label", [""])[0]
        if label not in LABELS:
            self._json({"ok": False, "error": "bad label"}, 400)
            return
        try:
            STATE.record(fname, label)
        except ValueError as e:
            self._json({"ok": False, "error": str(e)}, 400)
            return
        try:
            i = int(form.get("i", ["-1"])[0])
        except ValueError:
            i = -1
        self._json({
            "ok": True,
            "done": STATE.done_count(),
            "next": STATE.next_unlabeled_index(after=i),
        })


def main():
    global STATE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default=None,
                    help="image folder (searched recursively); omit for web-only mode, "
                         "which lists images from --filelist and fetches them from their URLs")
    ap.add_argument("--labeler", required=True, help="your name; recorded with every label")
    ap.add_argument("--filelist", default=None,
                    help="web-only mode: file with one relative image path per line "
                         "(default: filelist.txt next to this script)")
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
    filelist = args.filelist or os.path.join(here, "filelist.txt")
    if not args.folder and not os.path.exists(filelist):
        raise SystemExit(f"web-only mode needs a filelist ({filelist} not found); "
                         "pass an image folder or --filelist")
    if not args.folder and not urls:
        raise SystemExit("web-only mode needs urls.json (no local fallback without it)")

    clusters = [c.strip() for c in args.clusters.split(",")] if args.clusters else None
    STATE = State(args.folder, labels, args.labeler, urls, args.manifest, clusters, filelist)
    src = STATE.folder or f"web-only ({filelist})"
    print(f"{len(STATE.files)} images assigned from {src}")
    per_cluster = collections.Counter(f.split("/")[0] for f in STATE.files)
    done_per = collections.Counter(f.split("/")[0] for f in STATE.files if f in STATE.labels)
    for c in sorted(per_cluster, key=lambda x: (len(x), x)):
        print(f"  {c}: {done_per[c]}/{per_cluster[c]} labeled")
    if STATE.urls:
        print(f"{len(STATE.urls)} high-res URLs loaded")
    print(f"{STATE.done_count()} already labeled; labels append to {labels}")
    print(f"serving on http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
