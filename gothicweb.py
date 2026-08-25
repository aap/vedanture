#!/usr/bin/env python3
"""
gothicweb — web front-end for the Gothic Bible explorer.

Thin corpus-specific layer over webengine.Sheets: book/chapter/verse/word
navigation and the Gothic lexicon. The verse text (with parallel-manuscript
variants marked) and the token merge are reused straight from gothic.py; the
lemma-keyed views and the HTTP server come from webengine.

  python3 gothicweb.py            # serve on http://localhost:8000
  python3 gothicweb.py 8081       # custom port
"""

import json, sys
from collections import Counter
from pathlib import Path

import gothic
from webengine import Sheets, sp, head, note, serve

BASE = Path(__file__).parent
WEB  = BASE / "web"
INV_FILE = Path.home() / ".gothic_web_inventory.json"


class GothicSheets(Sheets):
    """Sheet documents for the Gothic Bible corpus."""

    ROOT_LABEL = "Gothic"
    DICT_LABEL = "dictionary"

    def __init__(self):
        super().__init__(gothic._CORPUS)

    # ── breadcrumb ──────────────────────────────────────────────────────────────

    def _nav_path(self, loc, cr):
        k = loc["kind"]
        if k == "book":
            return [cr(loc["book"], None)]
        if k in ("chapter", "verse", "word"):
            bk, ch = self._bc(loc)
            chain = [cr(bk, {"kind": "book", "book": bk})]
            if k == "chapter":
                return chain + [cr(f"{bk}.{ch}", None)]
            chain += [cr(f"{bk}.{ch}", {"kind": "chapter", "book": bk, "chapter": ch})]
            if k == "verse":
                return chain + [cr(loc["ref"], None)]
            return chain + [cr(loc["ref"], {"kind": "verse", "ref": loc["ref"]}),
                            cr(loc.get("lemma") or "word", None)]
        return None

    @staticmethod
    def _bc(loc):
        if loc.get("kind") == "chapter":
            return loc["book"], int(loc["chapter"])
        parts = loc["ref"].split(".")
        return parts[0], int(parts[1])

    # ── text views ──────────────────────────────────────────────────────────────

    def _index(self, loc):
        books = self.corpus.books()
        names = books.get("names", {}); order = books.get("order", [])
        present = Counter(ref.split(".")[0] for ref in self.corpus.verse_rows())
        items = []
        for bk in order:
            if bk not in present:
                continue
            n_ch = len(self.corpus.attested_chapters(bk))
            items.append({"label": bk, "loc": {"kind": "book", "book": bk},
                          "note": names.get(bk, bk),
                          "tag": f"{n_ch} ch · {present[bk]} v"})
        credit = note("Text: Project Wulfila, University of Antwerp — Gothic text/dictionary "
                      "in the public domain; annotations freely available for non-commercial "
                      "use with attribution (wulfila.be/project/copyright)")
        return self._doc(loc, "Gothic",
                         [head("Gothic Bible", f"{len(items)} books"),
                          {"t": "links", "items": items}, credit])

    def _book(self, loc):
        bk = loc["book"]
        books = self.corpus.books()
        names = books.get("names", {})
        if bk not in names:
            return self._doc(loc, bk, [note(f"unknown book: {bk}")])
        attested = self.corpus.attested_chapters(bk)
        n_total  = books.get("chapters", {}).get(bk, "?")
        sub = f"{names.get(bk, bk)}  ·  {len(attested)} of {n_total} chapters extant"
        items = [{"label": f"{bk}.{ch}",
                  "loc": {"kind": "chapter", "book": bk, "chapter": ch},
                  "note": f"{len(self.corpus.chapter_refs(bk, ch))} verses"}
                 for ch in attested]
        return self._doc(loc, bk, [head(bk, sub), {"t": "links", "items": items}])

    def _chapter(self, loc):
        bk, ch = loc["book"], int(loc["chapter"])
        refs = self.corpus.chapter_refs(bk, ch)
        if not refs:
            return self._doc(loc, f"{bk}.{ch}", [note(f"no verses for {bk}.{ch}")])
        items = [{"label": ref, "loc": {"kind": "verse", "ref": ref},
                  "note": gothic._annotated_verse_text(ref)} for ref in refs]
        return self._doc(loc, f"{bk}.{ch}",
                         [head(f"{bk}.{ch}", f"{len(refs)} verses"),
                          {"t": "links", "items": items, "wrap": True}])

    def _verse(self, loc):
        ref = loc["ref"]
        row = self.corpus.verse_rows().get(ref)
        if row is None:
            return self._doc(loc, ref, [note(f"verse {ref} not found")])
        blocks = [head(ref),
                  {"t": "lines", "items": [gothic._annotated_verse_text(ref)]}]
        trans = (row.get("translation") or "").strip()
        if trans:
            blocks.append({"t": "prose", "label": "en", "spans": [sp(trans)]})
        words = gothic._merge_verse_tokens(self.corpus.verse_tokens().get(ref, []))
        if words:
            blocks.append({"t": "sub", "spans": [sp(f"{len(words)} words")]})
            blocks.append({"t": "tokens", "items": [
                self._token_item(ref, j, tok) for j, tok in enumerate(words, 1)]})
        # prev / next within the chapter
        bk, ch = ref.split(".")[0], int(ref.split(".")[1])
        refs = self.corpus.chapter_refs(bk, ch)
        nav = {}
        if ref in refs:
            i = refs.index(ref)
            if i > 0:
                nav["prev"] = {"kind": "verse", "ref": refs[i - 1]}
            if i < len(refs) - 1:
                nav["next"] = {"kind": "verse", "ref": refs[i + 1]}
        return self._doc(loc, ref, blocks, nav=nav)

    @staticmethod
    def _feats(tok):
        try:
            return json.loads(tok["features"]) if tok.get("features", "").strip() else {}
        except Exception:
            return {}

    def _token_item(self, ref, j, tok):
        marker = tok.get("_marker", "")
        surf   = tok["surface"] + (f"  {marker}" if marker else "")
        return {"surface": surf, "lemma": tok["lemma"] or "",
                "feat": "  ".join(f"{k}={v}" for k, v in self._feats(tok).items()),
                "loc": {"kind": "word", "ref": ref, "word_num": j}}

    def _word(self, loc):
        ref = loc["ref"]; n = int(loc["word_num"])
        words = gothic._merge_verse_tokens(self.corpus.verse_tokens().get(ref, []))
        if not (1 <= n <= len(words)):
            return self._doc(loc, ref, [note(f"word {n} not found in {ref}")])
        tok   = words[n - 1]
        lemma = tok["lemma"] or ""
        loc   = dict(loc); loc["lemma"] = lemma
        feats = self._feats(tok)
        pd    = self.corpus.paradigms().get(lemma, {})
        total = sum(f["count"] for f in pd.get("forms", []))
        sc    = tok.get("stem_class", "") or pd.get("stem_class", "")
        feat  = "  ".join(f"{k}={v}" for k, v in feats.items())
        meta  = "  ·  ".join(x for x in [sc, feat, f"{total} tokens" if total else ""] if x)
        blocks = [head(tok["surface"], "→ " + (lemma or "?")),
                  {"t": "sub", "spans": [sp(meta)]}]
        if lemma:
            blocks.append(self._word_links(lemma, tok["surface"]))
            blocks += self._nearby_blocks(lemma)
        return self._doc(loc, tok["surface"], blocks)

    # ── lexicon ─────────────────────────────────────────────────────────────────

    def _dict(self, loc):
        lemma = loc.get("lemma", "")
        entry = gothic._lex().get(lemma)
        if entry is None and lemma:                # fuzzy fallback
            res = self.corpus.search(lemma, n=1)
            if res:
                lemma = res[0][0]; entry = gothic._lex().get(lemma)
        loc = dict(loc); loc["lemma"] = lemma
        if entry is None:
            return self._doc(loc, lemma, [head(lemma),
                                          self._lemma_nav(lemma, "dict"),
                                          note("no dictionary entry")])
        pd    = self.corpus.paradigms().get(lemma, {})
        total = sum(f["count"] for f in pd.get("forms", []))
        parts = [x for x in [entry.get("pos", ""), entry.get("stem_class", ""),
                             entry.get("gender", "")] if x]
        if total:
            parts.append(f"{total} tokens")
        blocks = [head(lemma, "  ·  ".join(parts)), self._lemma_nav(lemma, "dict")]
        for lang, key in [("de", "gloss_de"), ("en", "gloss_en"), ("grc", "gloss_grc")]:
            g = entry.get(key, "")
            if g:
                blocks.append({"t": "prose", "label": lang, "spans": [sp(g)]})
        blocks += self._nearby_blocks(lemma, limit=10)
        return self._doc(loc, lemma, blocks)

    # ── front-end config ─────────────────────────────────────────────────────────

    def config(self):
        books = self.corpus.books()
        names = books.get("names", {}); order = books.get("order", [])
        present = {ref.split(".")[0] for ref in self.corpus.verse_rows()}
        items = [{"label": "Gothic", "loc": {"kind": "index"}}]
        for bk in order:
            if bk in present:
                items.append({"label": names.get(bk, bk),
                              "loc": {"kind": "book", "book": bk}, "sub": True})
        items.append({"label": "stem classes", "loc": {"kind": "stems"}})
        return {"title": "Wulfila", "logo": "𐌲",
                "search": "find lemma … (/)", "index": items}


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
    serve(GothicSheets(), WEB, INV_FILE, port)


if __name__ == "__main__":
    main()
