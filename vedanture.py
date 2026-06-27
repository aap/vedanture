#!/usr/bin/env python3
"""
vedanture — web front-end for the Ṛgveda explorer.

Thin corpus-specific layer over webengine.Sheets: the maṇḍala/hymn/verse/word
navigation, the chant (saṃhitā pitch staff), and the Grassmann dictionary.
The lemma-keyed views and the HTTP server live in webengine.

  python3 vedanture.py            # serve on http://localhost:8000
  python3 vedanture.py 8080       # custom port
"""

import sys
from collections import Counter
from pathlib import Path

import rv
from webengine import Sheets, sp, head, note, serve

BASE = Path(__file__).parent
WEB  = BASE / "web"
INV_FILE = Path.home() / ".vedanture_web_inventory.json"


class RVSheets(Sheets):
    """Sheet documents for the Ṛgveda corpus."""

    ROOT_LABEL = "Ṛgveda"
    DICT_LABEL = "Grassmann dictionary"

    def __init__(self):
        super().__init__(rv._RV_CORPUS)

    # ── breadcrumb (text-navigation crumbs) ─────────────────────────────────────

    def _nav_path(self, loc, cr):
        k = loc["kind"]
        if k == "mandala":
            return [cr(f"RV {loc['book']}", None)]
        if k in ("hymn", "verse", "word"):
            b, h = self._bh(loc)
            chain = [cr(str(b), {"kind": "mandala", "book": b})]
            if k == "hymn":
                return chain + [cr(f"{b}.{h}", None)]
            chain += [cr(f"{b}.{h}", {"kind": "hymn", "book": b, "hymn": h})]
            if k == "verse":
                return chain + [cr(loc["ref"], None)]
            return chain + [cr(loc["ref"], {"kind": "verse", "ref": loc["ref"]}),
                            cr(loc.get("lemma") or "word", None)]
        return None

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

    # ── chant / saṃhitā staff ────────────────────────────────────────────────────

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
        """saṃhitā hemistichs with per-syllable pitch staffs, or None."""
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

    # ── text views ────────────────────────────────────────────────────────────

    def _index(self, loc):
        items = [{"label": f"RV {n}", "loc": {"kind": "mandala", "book": n},
                  "note": rv.BOOK_LABEL.get(n, "")} for n in range(1, 11)]
        return self._doc(loc, "Ṛgveda",
                         [head("Ṛgveda", "10 maṇḍalas"), {"t": "links", "items": items}])

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
        items = [{"label": ref, "loc": {"kind": "verse", "ref": ref},
                  "note": (self.samhita_text(ref)
                           or ("\n".join(st["lines"]) if st["lines"] else ""))}
                 for ref, st in stanzas]
        return self._doc(loc, f"RV {b}.{h}",
                         [head(f"RV {b}.{h}", f"{len(stanzas)} verses"),
                          {"t": "links", "items": items, "wrap": True}])

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
        blocks = [head(w["surface"], "→ " + w["lemma"]),
                  {"t": "sub", "spans": [sp(meta)]},
                  self._word_links(w["lemma"], w["surface"]),
                  *self._nearby_blocks(w["lemma"])]
        return self._doc(loc, w["surface"], blocks)

    # ── Grassmann dictionary ─────────────────────────────────────────────────────

    def _dict(self, loc):
        eid = loc.get("gra_id")
        lemma = loc.get("lemma", "")
        if eid is None:
            ids = rv._lookup_gra_ids(lemma) if lemma else []
            if not ids:
                return self._doc(loc, lemma, [head(lemma),
                                              self._lemma_nav(lemma, "dict"),
                                              note("no Grassmann entry found")])
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

    # ── front-end config ─────────────────────────────────────────────────────────

    def config(self):
        items = [{"label": "Ṛgveda", "loc": {"kind": "index"}}]
        items += [{"label": f"RV {n}", "loc": {"kind": "mandala", "book": n}, "sub": True}
                  for n in range(1, 11)]
        items.append({"label": "stem classes", "loc": {"kind": "stems"}})
        return {"title": "Vedanture", "logo": "वेद",
                "search": "find lemma … (/)", "index": items}


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
    serve(RVSheets(), WEB, INV_FILE, port)


if __name__ == "__main__":
    main()
