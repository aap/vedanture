#!/usr/bin/env python3
"""
vedanture — a web front-end for the Ṛgveda explorer.

A dependency-free HTTP server (stdlib only) that reuses the explorer
engine (rv.py / explorer.py) to build structured "sheet" documents,
rendered in the browser as a horizontal stack of navigable panes.

  python3 vedanture.py            # serve on http://localhost:8000
  python3 vedanture.py 8080       # custom port

A *sheet document* is JSON:
  { loc, title, path:[{label,loc}], nav:{prev,next}, blocks:[...] }

A *location* is a small dict the front-end passes back to navigate:
  {kind:index}                  {kind:paradigm,  lemma}
  {kind:mandala, book}          {kind:concordance, lemma, surface?}
  {kind:hymn, book, hymn}       {kind:dict, lemma? , gra_id?}
  {kind:verse, ref}             {kind:look, lemma}
  {kind:word, ref, word_num}    {kind:stems, arg?}
                                {kind:search, q}
"""

import json, sys, traceback, unicodedata, urllib.parse
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).parent
WEB  = BASE / "web"
INV_FILE = Path.home() / ".vedanture_web_inventory.json"

# Vedic pitch-accent combining marks (stripped for plain saṃhitā display):
#   U+0331 macron below = anudātta · U+030D vertical line above = svarita.
# NFC-compose first so phonemic retroflex ḻ (U+1E3B = l + U+0331) collapses to a
# single char and survives; the accent then sits as a standalone mark on a vowel
# (no precomposed form exists), so removing U+0331/U+030D strips only the accent.
_ACCENT_MARKS = {"̱", "̍"}

def _deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFC", s)
                   if c not in _ACCENT_MARKS)

import rv
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


# ── sheet builder ─────────────────────────────────────────────────────────────

class RVSheets:
    """Build sheet documents for the Ṛgveda corpus."""

    def build(self, loc: dict) -> dict:
        kind = loc.get("kind", "index")
        method = getattr(self, "_" + kind, None)
        if method is None:
            return self._doc(loc, kind, [note(f"unknown view: {kind!r}")])
        return method(loc)

    # ── document + path ────────────────────────────────────────────────────────

    def _doc(self, loc, title, blocks, nav=None):
        return {"loc": loc, "title": title, "path": self._path(loc),
                "blocks": blocks, "nav": nav or {}}

    def _path(self, loc):
        k = loc.get("kind")
        idx = {"kind": "index"}
        cr  = lambda label, l: {"label": label, "loc": l}
        if k == "index":
            return [cr("Ṛgveda", None)]
        base = [cr("Ṛgveda", idx)]
        if k == "mandala":
            return base + [cr(f"RV {loc['book']}", None)]
        if k in ("hymn", "verse", "word"):
            b, h = self._bh(loc)
            chain = base + [cr(str(b), {"kind": "mandala", "book": b})]
            if k == "hymn":
                return chain + [cr(f"{b}.{h}", None)]
            chain += [cr(f"{b}.{h}", {"kind": "hymn", "book": b, "hymn": h})]
            if k == "verse":
                return chain + [cr(loc["ref"], None)]
            return chain + [cr(loc["ref"], {"kind": "verse", "ref": loc["ref"]}),
                            cr(loc.get("lemma") or "word", None)]
        labels = {"paradigm": "par", "concordance": "conc", "dict": "def",
                  "look": "near", "stems": "stems", "search": "find"}
        tail = str(loc.get("lemma") or loc.get("q") or loc.get("arg") or "")
        return base + [cr(f"{labels.get(k, k)}: {tail}" if tail else labels.get(k, k), None)]

    @staticmethod
    def _bh(loc):
        if loc.get("kind") == "hymn":
            return int(loc["book"]), int(loc["hymn"])
        b, h, _ = loc["ref"].split(".")
        return int(b), int(h)

    def _verse_data(self, ref):
        b, h, _ = ref.split(".")
        stanzas = rv.hymn_stanzas(int(b), int(h))
        for i, (r, st) in enumerate(stanzas):
            if r == ref:
                return i, stanzas, st
        return None, stanzas, None

    # ── chant / saṃhitā staff ──────────────────────────────────────────────────

    _W = {"=": "●", "—": "○", ".": "-"}

    @classmethod
    def _staff_marks(cls, tone, length):
        """tone+length → (top, mid, bot) pitch-row symbols (see ghanapati)."""
        n = cls._W.get(length, "-")
        if tone == "`":            return (n,  "",  "")   # short svarita — high
        if tone == "/":            return (n,  "-", "")   # rising svarita — mid→high
        if tone == "-":            return ("", n,  "")    # udātta/pracaya — mid
        if tone == "_":            return ("", "", n)     # anudātta — low
        if tone in ("`_", "_`_"):  return (n,  "", n)     # svarita + anudātta
        return ("", n, "")                                # fallback — mid

    def samhita_text(self, ref):
        """Recited saṃhitā with tone marks — one hemistich per line, so each
        single daṇḍa ends a line and the verse ends with the double daṇḍa."""
        if not rv._CHANT_AVAILABLE:
            return ""
        hemis = rv._chant_index().get(ref)
        if not hemis:
            return ""
        parts = [raw.split(None, 1)[1] for raw in hemis if len(raw.split(None, 1)) > 1]
        return "\n".join(parts)

    def chant_staff(self, ref):
        """Return saṃhitā hemistichs with per-syllable pitch staffs, or None."""
        if not rv._CHANT_AVAILABLE:
            return None
        hemis = rv._chant_index().get(ref)
        if not hemis:
            return None
        out = []
        for raw in hemis:
            _, text, _, tones = rv.processline(raw)
            cols = [{"seg": seg,
                     "top": (m := self._staff_marks(tone, length))[0],
                     "mid": m[1], "bot": m[2]}
                    for seg, tone, length in tones]
            out.append({"text": text, "cols": cols})
        return out

    # ── textual views ────────────────────────────────────────────────────────

    def _index(self, loc):
        blocks = [head("Ṛgveda", "10 maṇḍalas")]
        items = [{"label": f"RV {n}", "loc": {"kind": "mandala", "book": n},
                  "note": rv.BOOK_LABEL.get(n, "")} for n in range(1, 11)]
        blocks.append({"t": "links", "items": items})
        return self._doc(loc, "Ṛgveda", blocks)

    def _mandala(self, loc):
        book = int(loc["book"])
        data = rv.load_book(book)
        counts = Counter()
        for sid in data:
            parts = sid.split("_")
            if len(parts) >= 2 and parts[1].startswith("h"):
                counts[int(parts[1][1:])] += 1
        ad = rv.addr()
        n_hymns = rv.HYMN_N.get(book, 0)
        blocks = [head(f"RV {book}",
                       f"{rv.BOOK_LABEL.get(book, '')}  ·  {n_hymns} hymns")]
        prev_group = None
        cur = []
        def flush():
            if cur:
                blocks.append({"t": "links", "items": list(cur)})
                cur.clear()
        for hymn_n in range(1, n_hymns + 1):
            info = ad.get(f"{book:02d}.{hymn_n:03d}")
            addressee = info[0][1] if info else "—"
            group     = info[1][1] if info else ""
            if group != prev_group:
                flush()
                prev_group = group
                glabel = group.split(": ", 1)[-1] if ": " in group else group
                if glabel:
                    blocks.append({"t": "sub", "spans": [sp(glabel)]})
            v = counts.get(hymn_n)
            cur.append({"label": f"{book}.{hymn_n}",
                        "loc": {"kind": "hymn", "book": book, "hymn": hymn_n},
                        "note": addressee, "tag": f"{v}v" if v else ""})
        flush()
        return self._doc(loc, f"RV {book}", blocks)

    def _hymn(self, loc):
        b, h = int(loc["book"]), int(loc["hymn"])
        stanzas = rv.hymn_stanzas(b, h)
        blocks = [head(f"RV {b}.{h}", f"{len(stanzas)} verses")]
        items = [{"label": ref, "loc": {"kind": "verse", "ref": ref},
                  "note": (self.samhita_text(ref)
                           or ("\n".join(st["lines"]) if st["lines"] else ""))}
                 for ref, st in stanzas]
        blocks.append({"t": "links", "items": items, "wrap": True})
        return self._doc(loc, f"RV {b}.{h}", blocks)

    def _verse(self, loc):
        ref = loc["ref"]
        i, stanzas, st = self._verse_data(ref)
        if st is None:
            return self._doc(loc, ref, [note(f"verse {ref} not found")])
        blocks = [head(ref)]
        # saṃhitā — the recited form, with per-syllable pitch staff
        staff = self.chant_staff(ref)
        if staff:
            blocks.append({"t": "chant", "hemistichs": staff})
        elif st["lines"]:
            blocks.append({"t": "lines", "items": st["lines"]})
        # translations
        for src, lines in st.get("trans", {}).items():
            blocks.append({"t": "prose", "label": rv._TRANS_LABEL.get(src, src),
                           "spans": [sp(" ".join(lines))]})
        # metric pādas — the analytic line-split the glossing maps to
        if staff and st["lines"]:
            blocks.append({"t": "sub", "spans": [sp("metric pādas")]})
            blocks.append({"t": "lines", "items": st["lines"], "muted": True})
        words = st.get("words", [])
        if words:
            blocks.append({"t": "sub", "spans": [sp(f"{len(words)} words")]})
            blocks.append({"t": "tokens", "items": [
                {"surface": w["surface"], "lemma": w["lemma"],
                 "feat": "  ".join(f"{k}={v}" for k, v in w["feats"].items()),
                 "loc": {"kind": "word", "ref": ref, "word_num": j}}
                for j, w in enumerate(words, 1)]})
        nav = {}
        if i is not None:
            if i > 0:
                nav["prev"] = {"kind": "verse", "ref": stanzas[i - 1][0]}
            if i < len(stanzas) - 1:
                nav["next"] = {"kind": "verse", "ref": stanzas[i + 1][0]}
        return self._doc(loc, ref, blocks, nav=nav)

    def _word(self, loc):
        ref = loc["ref"]; n = int(loc["word_num"])
        i, stanzas, st = self._verse_data(ref)
        words = st.get("words", []) if st else []
        if not (1 <= n <= len(words)):
            return self._doc(loc, ref, [note(f"word {n} not found in {ref}")])
        w = words[n - 1]
        loc = dict(loc); loc["lemma"] = w["lemma"]
        pd = rv.paradigms().get(w["lemma"], {})
        total = sum(f["count"] for f in pd.get("forms", []))
        sc = pd.get("stem_class", "")
        feat = "  ".join(f"{k}={v}" for k, v in w["feats"].items())
        meta = "  ·  ".join(x for x in
                            [sc, feat, f"{total} tokens" if total else ""] if x)
        blocks = [
            {"t": "head", "text": w["surface"], "sub": "→ " + w["lemma"]},
            {"t": "sub", "spans": [sp(meta)]},
            {"t": "links", "items": [
                {"label": "paradigm",
                 "loc": {"kind": "paradigm", "lemma": w["lemma"]}},
                {"label": "concordance — this form",
                 "loc": {"kind": "concordance", "lemma": w["lemma"],
                         "surface": w["surface"]}},
                {"label": "concordance — whole lemma",
                 "loc": {"kind": "concordance", "lemma": w["lemma"]}},
                {"label": "Grassmann dictionary",
                 "loc": {"kind": "dict", "lemma": w["lemma"]}},
                {"label": "nearby (gravity field)",
                 "loc": {"kind": "look", "lemma": w["lemma"]}},
            ]},
        ]
        nbrs = rv.gravity().get(w["lemma"], [])[:8]
        if nbrs:
            blocks.append({"t": "sub", "spans": [sp("nearby")]})
            blocks.append({"t": "links", "items": [
                {"label": e["n"], "loc": {"kind": "paradigm", "lemma": e["n"]},
                 "note": f"v={e['v']} p={e['p']} m={e['m']}"} for e in nbrs]})
        return self._doc(loc, w["surface"], blocks)

    # ── lexical views ────────────────────────────────────────────────────────

    def _lemma_nav(self, lemma, current):
        """Cross-links between the four lemma-keyed views (omits the current one)."""
        opts = [
            ("paradigm",    "paradigm",    {"kind": "paradigm",    "lemma": lemma}),
            ("concordance", "concordance", {"kind": "concordance", "lemma": lemma}),
            ("dict",        "dictionary",  {"kind": "dict",        "lemma": lemma}),
            ("look",        "nearby",      {"kind": "look",        "lemma": lemma}),
        ]
        return {"t": "nav", "items": [{"label": lab, "loc": l}
                                      for key, lab, l in opts if key != current]}

    def _paradigm(self, loc):
        lemma = loc["lemma"]
        C = rv._RV_CORPUS
        pd = rv.paradigms().get(lemma, {})
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
        rows = rv.concordance().get(lemma, [])
        if surface:
            rows = [r for r in rows if r["surface"] == surface]
        rows = sorted(rows, key=lambda r: rv._RV_CORPUS.ref_sort_key(r["ref"]))
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
        nbrs = rv.gravity().get(lemma, [])[:int(loc.get("n", 14))]
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
        pars = rv.paradigms()
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
        results = rv._RV_CORPUS.search(q) if q else []
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

    # ── Grassmann dictionary ──────────────────────────────────────────────────

    def _dict(self, loc):
        eid = loc.get("gra_id")
        lemma = loc.get("lemma", "")
        if eid is None:
            ids = rv._lookup_gra_ids(lemma) if lemma else []
            if not ids:
                return self._doc(loc, lemma,
                                 [head(lemma), note("no Grassmann entry found")])
            eid = ids[0]
        entry = rv._gra_idx().get(eid)
        if entry is None:
            return self._doc(loc, lemma, [note(f"entry not found: {eid}")])
        orth = rv._orth_iso(entry); n = entry.get("n", "?")
        sense = entry.find(rv.GT("sense"))
        corpus_lemmata, tokens = rv._eid_corpus_info(eid)
        loc = dict(loc); loc["gra_id"] = eid
        loc["lemma"] = lemma or (corpus_lemmata[0] if corpus_lemmata else orth)
        sub = f"GRA #{n}" + (f"  ·  {tokens} tokens" if tokens else "")
        blocks = [head(orth, sub)]
        if corpus_lemmata:
            blocks.append({"t": "sub", "spans": [sp("corpus")]})
            blocks.append({"t": "links", "items": [
                {"label": l, "loc": {"kind": "paradigm", "lemma": l}}
                for l in corpus_lemmata]})
        if sense is not None:
            blocks.append({"t": "prose", "spans": self._sense_spans(sense)})
        nav_items = [{"label": no, "loc": {"kind": "dict", "gra_id": ne},
                      "note": f"#{nn}"}
                     for nn, ne, no, nr, cur in rv._gra_neighbors(eid, window=10)
                     if not cur]
        if nav_items:
            blocks.append({"t": "sub", "spans": [sp("nearby")]})
            blocks.append({"t": "links", "items": nav_items})
        prose = " ".join(sense.itertext()) if sense is not None else ""
        xrefs = rv._extract_xrefs(prose)[:8]
        if xrefs:
            blocks.append({"t": "sub", "spans": [sp("see also")]})
            blocks.append({"t": "links", "items": [
                {"label": x, "loc": {"kind": "dict", "lemma": x}} for x in xrefs]})
        return self._doc(loc, orth, blocks)

    def _sense_spans(self, sense_el):
        spans = []
        def add(txt, cls=None, loc=None):
            if txt:
                spans.append(sp(txt, loc, cls))
        def walk(el):
            if el.text:
                add(" ".join(el.text.split()) + " ")
            for child in el:
                tag  = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                rend = child.get("rendition", "")
                if tag == "hi" and "#b" in rend:
                    add("".join(child.itertext()).strip(), cls="b"); add(" ")
                elif tag == "hi" and "#i" in rend:
                    add("".join(child.itertext()).strip(), cls="i"); add(" ")
                elif tag == "ref":
                    r = rv._ref_to_rv(child.get("target", ""))
                    add(r, cls="ref", loc={"kind": "verse", "ref": r})
                elif tag == "lb":
                    spans.append({"br": True})
                else:
                    walk(child)
                if child.tail:
                    add(" ".join(child.tail.split()) + " ")
        walk(sense_el)
        return spans


SHEETS = RVSheets()


# ── inventory ─────────────────────────────────────────────────────────────────

def load_inv():
    if INV_FILE.exists():
        try:
            return json.loads(INV_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_inv(d):
    INV_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2))


# ── HTTP ──────────────────────────────────────────────────────────────────────

CTYPE = {".html": "text/html", ".css": "text/css",
         ".js": "application/javascript", ".json": "application/json",
         ".ttf": "font/ttf", ".woff": "font/woff", ".woff2": "font/woff2",
         ".svg": "image/svg+xml"}

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
                doc = SHEETS.build(loc)
            except Exception as e:
                traceback.print_exc()
                doc = {"loc": loc, "title": "error", "path": [],
                       "blocks": [note(f"error: {e}")], "nav": {}}
            return self._send(200, doc)
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
        web_root = WEB.resolve()
        f = (WEB / path.lstrip("/")).resolve()
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
        self._send(200, f.read_bytes(), CTYPE.get(f.suffix.lower(), "application/octet-stream"))

    def log_message(self, *a):
        pass  # silence the default access log; we log concisely in _send()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"vedanture → http://localhost:{port}   (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
