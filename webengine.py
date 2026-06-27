#!/usr/bin/env python3
"""
Shared web engine for the corpus explorers.

Holds everything that is the same across corpora:
  - the sheet "block" primitives (sp / head / note),
  - the Sheets base class with the lemma-keyed views (paradigm, concordance,
    nearby, stems, search) and the breadcrumb skeleton, all driven by a Corpus,
  - a dependency-free HTTP server (serve()).

A corpus-specific front-end (vedanture.py, gothicweb.py) subclasses Sheets,
sets ROOT_LABEL + self.corpus, and supplies the text-navigation views
(_index, book/chapter or maṇḍala/hymn, _verse, _word), _dict, _nav_path, and
config().  See those files for the concrete wiring.
"""

import json, traceback, urllib.parse
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from explorer import _stem_classes


# ── content primitives ────────────────────────────────────────────────────────

def sp(text, loc=None, cls=None):
    d = {"text": text}
    if loc is not None: d["loc"] = loc
    if cls:             d["cls"] = cls
    return d

def head(text, sub=None):
    d = {"t": "head", "text": text}
    if sub: d["sub"] = sub
    return d

def note(text):
    return {"t": "note", "text": text}


# ── sheet builder base ─────────────────────────────────────────────────────────

class Sheets:
    """Build sheet documents. Subclass: set ROOT_LABEL, assign self.corpus in
    __init__, and implement _index, the text views, _word, _dict, _nav_path, config."""

    ROOT_LABEL = "corpus"
    DICT_LABEL = "dictionary"     # label for the dict link in the word view

    def __init__(self, corpus):
        self.corpus = corpus

    def build(self, loc: dict) -> dict:
        method = getattr(self, "_" + loc.get("kind", "index"), None)
        if method is None:
            return self._doc(loc, loc.get("kind", "?"),
                             [note(f"unknown view: {loc.get('kind')!r}")])
        return method(loc)

    # ── document + breadcrumb ───────────────────────────────────────────────────

    def _doc(self, loc, title, blocks, nav=None):
        return {"loc": loc, "title": title, "path": self._path(loc),
                "blocks": blocks, "nav": nav or {}}

    def _path(self, loc):
        k = loc.get("kind", "index")
        cr = lambda label, l: {"label": label, "loc": l}
        if k == "index":
            return [cr(self.ROOT_LABEL, None)]
        base = [cr(self.ROOT_LABEL, {"kind": "index"})]
        nav = self._nav_path(loc, cr)               # text-navigation crumbs
        if nav is not None:
            return base + nav
        labels = {"paradigm": "par", "concordance": "conc", "dict": "def",
                  "look": "near", "stems": "stems", "search": "find"}
        tail = str(loc.get("lemma") or loc.get("q") or loc.get("arg") or "")
        label = f"{labels.get(k, k)}: {tail}" if tail else labels.get(k, k)
        return base + [cr(label, None)]

    def _nav_path(self, loc, cr):
        """Crumbs after the root for text-navigation kinds; None otherwise."""
        return None

    # ── shared building blocks ──────────────────────────────────────────────────

    def _lemma_nav(self, lemma, current):
        """Cross-links between the four lemma-keyed views (omits the current one)."""
        opts = [
            ("paradigm",    "paradigm",       {"kind": "paradigm",    "lemma": lemma}),
            ("concordance", "concordance",    {"kind": "concordance", "lemma": lemma}),
            ("dict",        self.DICT_LABEL,  {"kind": "dict",        "lemma": lemma}),
            ("look",        "nearby",         {"kind": "look",        "lemma": lemma}),
        ]
        return {"t": "nav", "items": [{"label": lab, "loc": l}
                                      for key, lab, l in opts if key != current]}

    def _word_links(self, lemma, surface):
        return {"t": "links", "items": [
            {"label": "paradigm", "loc": {"kind": "paradigm", "lemma": lemma}},
            {"label": "concordance — this form",
             "loc": {"kind": "concordance", "lemma": lemma, "surface": surface}},
            {"label": "concordance — whole lemma",
             "loc": {"kind": "concordance", "lemma": lemma}},
            {"label": self.DICT_LABEL, "loc": {"kind": "dict", "lemma": lemma}},
            {"label": "nearby (gravity field)", "loc": {"kind": "look", "lemma": lemma}},
        ]}

    def _nearby_blocks(self, lemma, limit=8):
        nbrs = self.corpus.gravity().get(lemma, [])[:limit]
        if not nbrs:
            return []
        return [{"t": "sub", "spans": [sp("nearby")]},
                {"t": "links", "items": [
                    {"label": e["n"], "loc": {"kind": "paradigm", "lemma": e["n"]},
                     "note": f"v={e['v']} p={e['p']} m={e['m']}"} for e in nbrs]}]

    # ── lemma-keyed views (corpus-agnostic) ─────────────────────────────────────

    def _paradigm(self, loc):
        lemma = loc["lemma"]
        C = self.corpus
        pd = C.paradigms().get(lemma, {})
        if not pd:
            return self._doc(loc, lemma, [head(lemma),
                                          self._lemma_nav(lemma, "paradigm"),
                                          note("no paradigm data")])
        gramm = pd.get("gramm", []); sc = pd.get("stem_class", "")
        total = sum(f["count"] for f in pd.get("forms", []))
        sub = "  ·  ".join(x for x in [sc] + gramm if x)
        if total:
            sub += f"  ·  {total} tokens"
        blocks = [head(lemma, sub), self._lemma_nav(lemma, "paradigm")]
        forms = pd.get("forms", [])
        idx = defaultdict(list)

        if "root" in gramm or "verb" in gramm:
            for f in forms:
                ft = f["features"]
                idx[(ft.get("tense", ""), ft.get("mood", ""), ft.get("voice", ""),
                     ft.get("person", ""), ft.get("number", ""))].append(
                        (f["surface"], f["count"]))
            seen = set()
            for t in C.TENSES:
                for m in C.MOODS:
                    for v in C.VOICES:
                        if (t, m, v) in seen or not any(k[:3] == (t, m, v) for k in idx):
                            continue
                        seen.add((t, m, v))
                        label = " ".join(x for x in [C.T_NAME.get(t, t),
                                                     C.M_NAME.get(m, m),
                                                     C.V_NAME.get(v, v)] if x)
                        nums = [n for n in C.NUMBERS
                                if any(k == (t, m, v, p, n) for k in idx for p in C.PERSONS)]
                        pers = [p for p in C.PERSONS
                                if any(k == (t, m, v, p, n) for k in idx for n in C.NUMBERS)]
                        rows = []
                        for p in pers:
                            row = [p or "?"]
                            for n in nums:
                                es = idx.get((t, m, v, p, n), [])
                                row.append(" / ".join(s for s, _ in
                                           sorted(es, key=lambda x: -x[1])[:2]) if es else "—")
                            rows.append(row)
                        blocks.append({"t": "grid", "caption": label,
                                       "head": [""] + nums, "rows": rows})

        elif gramm and "invariable" not in gramm:
            for f in forms:
                ft = f["features"]
                idx[(ft.get("case", ""), ft.get("number", ""),
                     ft.get("gender", ""))].append((f["surface"], f["count"]))
            nums = [n for n in C.NUMBERS if any(k[1] == n for k in idx)]
            rows = []
            for case in C.CASES:
                if not any(k[0] == case for k in idx):
                    continue
                row = [case or "(other)"]
                for n in nums:
                    m2 = []
                    for g in C.GENDERS:
                        m2 += idx.get((case, n, g), [])
                    row.append(" / ".join((f"{sf}({c})" if c > 1 else sf)
                               for sf, c in sorted(m2, key=lambda x: -x[1])[:2]) if m2 else "—")
                rows.append(row)
            blocks.append({"t": "grid", "head": [""] + nums, "rows": rows})

        else:
            rows = [[f["surface"], str(f["count"])] for f in forms[:40]]
            blocks.append({"t": "grid", "head": ["form", "n"], "rows": rows})

        return self._doc(loc, lemma, blocks)

    def _concordance(self, loc):
        lemma = loc["lemma"]; surface = loc.get("surface")
        rows = self.corpus.concordance().get(lemma, [])
        if surface:
            rows = [r for r in rows if r["surface"] == surface]
        rows = sorted(rows, key=lambda r: self.corpus.ref_sort_key(r["ref"]))
        title = f"{surface} (< {lemma})" if surface else lemma
        blocks = [head(title, f"{len(rows)} occurrences"),
                  self._lemma_nav(lemma, "concordance")]
        CAP = 400
        blocks.append({"t": "links", "items": [
            {"label": r["ref"], "loc": {"kind": "verse", "ref": r["ref"]},
             "tag": r["surface"], "note": r.get("text", "")} for r in rows[:CAP]]})
        if len(rows) > CAP:
            blocks.append(note(f"+ {len(rows) - CAP} more not shown"))
        return self._doc(loc, title, blocks)

    def _look(self, loc):
        lemma = loc["lemma"]
        blocks = [head(lemma, "nearest neighbours in the gravity field"),
                  self._lemma_nav(lemma, "look")]
        nbrs = self.corpus.gravity().get(lemma, [])[:int(loc.get("n", 14))]
        if not nbrs:
            blocks.append(note("no gravity data"))
            return self._doc(loc, lemma, blocks)
        mx = nbrs[0]["s"] or 1
        blocks.append({"t": "links", "items": [
            {"label": e["n"], "loc": {"kind": "paradigm", "lemma": e["n"]},
             "note": f"v={e['v']} p={e['p']} m={e['m']}",
             "bar": (e["s"] / mx)} for e in nbrs]})
        return self._doc(loc, f"near {lemma}", blocks)

    def _stems(self, loc):
        arg = loc.get("arg", "")
        pars = self.corpus.paradigms()
        if not arg:
            classes = _stem_classes(pars)
            items = [{"label": scn, "loc": {"kind": "stems", "arg": scn},
                      "note": f"{len(lem)} lemmata"} for scn, lem in classes]
            return self._doc(loc, "stem classes",
                             [head("stem classes"), {"t": "links", "items": items}])
        lemmata = []
        for lemma, pd in pars.items():
            sc = pd.get("stem_class", ""); gramm = pd.get("gramm", [])
            match = (sc == arg
                     or (arg == "root (verb)" and ("root" in gramm or "verb" in gramm) and not sc)
                     or (arg == "particle" and "invariable" in gramm and not sc)
                     or (arg == "pronoun" and "pronoun" in gramm and not sc)
                     or (arg == "other" and not sc
                         and not any(g in gramm for g in ("root", "verb", "invariable", "pronoun"))))
            if match:
                nf = len(pd.get("forms", []))
                tk = sum(f["count"] for f in pd.get("forms", []))
                lemmata.append((lemma, nf, tk))
        lemmata.sort(key=lambda x: (-x[1], -x[2]))
        items = [{"label": l, "loc": {"kind": "paradigm", "lemma": l},
                  "note": f"{nf} forms · {tk} tkn"} for l, nf, tk in lemmata[:200]]
        return self._doc(loc, arg, [head(arg, f"{len(lemmata)} lemmata"),
                                    {"t": "links", "items": items}])

    def _search(self, loc):
        q = loc.get("q", "")
        results = self.corpus.search(q) if q else []
        if not results:
            return self._doc(loc, f"find: {q}",
                             [head(f"find: {q}"), note("nothing found")])
        items = []
        for l, pd in results:
            sc = pd.get("stem_class", ""); gramm = "/".join(pd.get("gramm", []))
            total = sum(f["count"] for f in pd.get("forms", []))
            tag = gramm + (f" {sc}" if sc and sc != "indeclinable" else "")
            items.append({"label": l, "loc": {"kind": "paradigm", "lemma": l},
                          "note": f"{tag} · {total} tokens"})
        return self._doc(loc, f"find: {q}",
                         [head(f"find: {q}", f"{len(results)} results"),
                          {"t": "links", "items": items}])

    # ── front-end config (sidebar + branding) ───────────────────────────────────

    def config(self) -> dict:
        return {"title": self.ROOT_LABEL, "logo": "",
                "search": "find lemma … (/)",
                "index": [{"label": self.ROOT_LABEL, "loc": {"kind": "index"}},
                          {"label": "stem classes", "loc": {"kind": "stems"}}]}


# ── HTTP server ────────────────────────────────────────────────────────────────

CTYPE = {".html": "text/html", ".css": "text/css",
         ".js": "application/javascript", ".json": "application/json",
         ".ttf": "font/ttf", ".woff": "font/woff", ".woff2": "font/woff2",
         ".svg": "image/svg+xml"}


def make_handler(sheets: Sheets, web_dir: Path, inv_file: Path):
    web_root = web_dir.resolve()

    def load_inv():
        if inv_file.exists():
            try:
                return json.loads(inv_file.read_text())
            except Exception:
                return {}
        return {}

    def save_inv(d):
        inv_file.write_text(json.dumps(d, ensure_ascii=False, indent=2))

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            textual = any(t in ctype for t in ("json", "html", "css", "javascript", "svg"))
            self.send_response(code)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if textual else ""))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            mark = "" if code < 400 else "  ←"
            print(f"  {code} {self.command:4} {self.path}{mark}", flush=True)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            if u.path == "/api/sheet":
                qs  = urllib.parse.parse_qs(u.query)
                loc = json.loads(qs.get("loc", ["{}"])[0]) or {"kind": "index"}
                try:
                    doc = sheets.build(loc)
                except Exception as e:
                    traceback.print_exc()
                    doc = {"loc": loc, "title": "error", "path": [],
                           "blocks": [note(f"error: {e}")], "nav": {}}
                return self._send(200, doc)
            if u.path == "/api/config":
                return self._send(200, sheets.config())
            if u.path == "/api/inventory":
                return self._send(200, load_inv())
            return self._static(u.path)

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            if u.path == "/api/inventory":
                ln   = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(ln) or "{}")
                inv  = load_inv()
                if data.get("op") == "save":
                    inv[data["name"]] = data["loc"]
                elif data.get("op") == "drop":
                    inv.pop(data.get("name"), None)
                save_inv(inv)
                return self._send(200, inv)
            return self._send(404, {"error": "no API route", "method": "POST",
                                    "path": u.path})

        def _static(self, path):
            if path in ("/", ""):
                path = "/index.html"
            f = (web_dir / path.lstrip("/")).resolve()
            if not str(f).startswith(str(web_root)):
                return self._send(403, f"403 forbidden — path escapes web root: {path!r}\n",
                                  "text/plain")
            if not f.is_file():
                looks_api = "/api/" in path or path.rstrip("/").endswith("/api")
                hint = (
                    "\nThis looks like an /api/ request that fell through to the static\n"
                    "handler — your reverse proxy is not stripping the mount prefix.\n"
                    if looks_api else
                    "\nIf you are serving under a sub-path, the reverse proxy must strip\n"
                    "the prefix before proxying.\n")
                msg = (f"404 not found\n\n"
                       f"  request : {self.command} {self.path}\n"
                       f"  resolved path : {path}\n"
                       f"  looked for    : {f}\n"
                       f"  web root      : {web_root}\n"
                       f"{hint}"
                       f"  nginx: location /<mount>/ {{ proxy_pass http://127.0.0.1:<port>/; }}"
                       f"  (trailing slash on the target strips the prefix)\n")
                return self._send(404, msg, "text/plain")
            self._send(200, f.read_bytes(),
                       CTYPE.get(f.suffix.lower(), "application/octet-stream"))

        def log_message(self, *a):
            pass  # silence the default access log; we log concisely in _send()

    return Handler


def serve(sheets: Sheets, web_dir: Path, inv_file: Path, port=8000, host="127.0.0.1"):
    srv = ThreadingHTTPServer((host, port), make_handler(sheets, web_dir, inv_file))
    print(f"{sheets.ROOT_LABEL} → http://{host}:{port}/   (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
