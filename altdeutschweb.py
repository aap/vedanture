#!/usr/bin/env python3
"""
altdeutschweb — web front-end for the Referenzkorpus Altdeutsch explorer.

Thin corpus-specific layer over webengine.Sheets: adds one navigation level
in front of the usual work/section/verse/word (dialect / scribal-school
group), reusing the shared lemma-keyed views, lexicon, and HTTP server from
webengine.py / altdeutsch.py.

  python3 altdeutschweb.py            # serve on http://localhost:8000
  python3 altdeutschweb.py 8082       # custom port
"""

import json, sys
from collections import Counter
from pathlib import Path

import altdeutsch
from webengine import Sheets, sp, head, note, serve

BASE = Path(__file__).parent
WEB  = BASE / "web"
INV_FILE = Path.home() / ".altdeutsch_web_inventory.json"


class AltdeutschSheets(Sheets):
    """Sheet documents for the Referenzkorpus Altdeutsch."""

    ROOT_LABEL = "Altdeutsch"
    DICT_LABEL = "dictionary"

    def __init__(self):
        super().__init__(altdeutsch._CORPUS)

    # ── breadcrumb ────────────────────────────────────────────────────────────

    def _group_label(self, key: str) -> str:
        for g in self.corpus.works().get("groups", []):
            if g["key"] == key:
                return g["label"]
        return key

    def _nav_path(self, loc, cr):
        k = loc["kind"]
        if k == "group":
            return [cr(self._group_label(loc["group"]), None)]
        if k not in ("work", "section", "verse", "word"):
            return None

        wid = loc["work"] if "work" in loc else loc["ref"].split(".")[0]
        w = self.corpus.works().get("works", {}).get(wid, {})
        gkey = w.get("group", "")
        chain = [cr(self._group_label(gkey), {"kind": "group", "group": gkey})]
        if k == "work":
            return chain + [cr(wid, None)]
        chain += [cr(wid, {"kind": "work", "work": wid})]

        sec = loc["section"] if "section" in loc else loc["ref"].split(".")[1]
        if k == "section":
            return chain + [cr(f"{wid}.{sec}", None)]
        chain += [cr(f"{wid}.{sec}", {"kind": "section", "work": wid, "section": sec})]

        if k == "verse":
            return chain + [cr(loc["ref"], None)]
        return chain + [cr(loc["ref"], {"kind": "verse", "ref": loc["ref"]}),
                        cr(loc.get("lemma") or "word", None)]

    # ── text views ────────────────────────────────────────────────────────────

    def _index(self, loc):
        wk = self.corpus.works()
        groups = wk.get("groups", [])
        works  = wk.get("works", {})
        counts = Counter(w["group"] for w in works.values())
        items = [{"label": g["label"], "loc": {"kind": "group", "group": g["key"]},
                  "note": g["key"], "tag": f"{counts.get(g['key'], 0)} works"}
                 for g in groups if counts.get(g["key"])]
        return self._doc(loc, "Altdeutsch",
                         [head("Referenzkorpus Altdeutsch",
                               f"{len(works)} works  ·  {len(items)} dialect groups"),
                          {"t": "links", "items": items}])

    def _group(self, loc):
        key = loc["group"]
        wk = self.corpus.works()
        label = self._group_label(key)
        works = {wid: w for wid, w in wk.get("works", {}).items() if w["group"] == key}
        if not works:
            return self._doc(loc, label, [note(f"unknown group: {key}")])
        items = [{"label": wid, "loc": {"kind": "work", "work": wid},
                  "note": w["title"],
                  "tag": "  ·  ".join(x for x in [w.get("time", ""),
                                                  f"{len(w.get('sections', []))} sections"] if x)}
                 for wid, w in sorted(works.items(), key=lambda kv: altdeutsch._work_sort_key(kv[1]))]
        return self._doc(loc, label, [head(label, f"{len(items)} works"),
                                      {"t": "links", "items": items, "wrap": True}])

    def _work(self, loc):
        wid = loc["work"]
        w = self.corpus.works().get("works", {}).get(wid)
        if w is None:
            return self._doc(loc, wid, [note(f"unknown work: {wid}")])
        sections = w.get("sections", [])
        if len(sections) == 1:      # nothing to choose — go straight in
            return self._section({"kind": "section", "work": wid, "section": sections[0]})
        sub = "  ·  ".join(x for x in [wid, w.get("form", ""), w.get("depository", ""),
                                       w.get("time", "")] if x)
        items = [{"label": f"{wid}.{sec}",
                  "loc": {"kind": "section", "work": wid, "section": sec},
                  "note": f"{len(self.corpus.section_refs(wid, sec))} verses"}
                 for sec in w.get("sections", [])]
        return self._doc(loc, wid, [head(w["title"], sub),
                                    {"t": "links", "items": items, "wrap": True}])

    def _section(self, loc):
        wid, sec = loc["work"], loc["section"]
        refs = self.corpus.section_refs(wid, sec)
        if not refs:
            return self._doc(loc, f"{wid}.{sec}", [note(f"no verses for {wid}.{sec}")])
        w     = self.corpus.works().get("works", {}).get(wid, {})
        title = w.get("title", wid)
        items = [{"label": ref.rsplit(".", 1)[-1], "loc": {"kind": "verse", "ref": ref},
                  "note": self.corpus.verse_rows().get(ref, {}).get("text", "")}
                 for ref in refs]
        nav = {}
        prv = self.corpus.adjacent_section(wid, sec, -1)
        nxt = self.corpus.adjacent_section(wid, sec, +1)
        if prv:
            nav["prev"] = {"kind": "section", "work": wid, "section": prv}
        if nxt:
            nav["next"] = {"kind": "section", "work": wid, "section": nxt}
        return self._doc(loc, f"{wid}.{sec}",
                         [head(title, f"{wid}.{sec}  ·  {len(refs)} verses"),
                          {"t": "links", "items": items, "wrap": True}], nav=nav)

    def _verse(self, loc):
        ref = loc["ref"]
        row = self.corpus.verse_rows().get(ref)
        if row is None:
            return self._doc(loc, ref, [note(f"verse {ref} not found")])
        wid   = ref.split(".")[0]
        title = self.corpus.works().get("works", {}).get(wid, {}).get("title", wid)
        blocks = [head(title, ref), {"t": "lines", "items": [row.get("text", "")]}]
        par = (row.get("parallel") or "").strip()
        if par:
            blocks.append({"t": "prose", "label": "lat", "spans": [sp(par)]})
        words = self.corpus.verse_tokens().get(ref, [])
        if words:
            blocks.append({"t": "sub", "spans": [sp(f"{len(words)} words")]})
            blocks.append({"t": "tokens", "items": [
                self._token_item(ref, j, tok) for j, tok in enumerate(words, 1)]})
        nav = {}
        prv = self.corpus.adjacent_verse_ref(ref, -1)
        nxt = self.corpus.adjacent_verse_ref(ref, +1)
        if prv:
            nav["prev"] = {"kind": "verse", "ref": prv}
        if nxt:
            nav["next"] = {"kind": "verse", "ref": nxt}
        return self._doc(loc, ref, blocks, nav=nav)

    @staticmethod
    def _feats(tok):
        try:
            return json.loads(tok["features"]) if tok.get("features", "").strip() else {}
        except Exception:
            return {}

    def _token_item(self, ref, j, tok):
        return {"surface": tok["surface"], "lemma": tok["lemma"] or "",
                "feat": "  ".join(f"{k}={v}" for k, v in self._feats(tok).items()),
                "loc": {"kind": "word", "ref": ref, "word_num": j}}

    def _word(self, loc):
        ref = loc["ref"]; n = int(loc["word_num"])
        words = self.corpus.verse_tokens().get(ref, [])
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

    # ── lexicon ───────────────────────────────────────────────────────────────

    def _dict(self, loc):
        lemma = loc.get("lemma", "")
        entry = altdeutsch._lex().get(lemma)
        if entry is None and lemma:                # fuzzy fallback
            res = self.corpus.search(lemma, n=1)
            if res:
                lemma = res[0][0]; entry = altdeutsch._lex().get(lemma)
        loc = dict(loc); loc["lemma"] = lemma
        if entry is None:
            return self._doc(loc, lemma, [head(lemma),
                                          self._lemma_nav(lemma, "dict"),
                                          note("no dictionary entry")])
        pd    = self.corpus.paradigms().get(lemma, {})
        total = sum(f["count"] for f in pd.get("forms", []))
        parts = [x for x in [entry.get("pos", ""), entry.get("stem_class", "")] if x]
        if total:
            parts.append(f"{total} tokens")
        blocks = [head(lemma, "  ·  ".join(parts)), self._lemma_nav(lemma, "dict")]
        gloss = entry.get("gloss_de", "")
        if gloss:
            blocks.append({"t": "prose", "label": "de", "spans": [sp(gloss)]})
        blocks += self._nearby_blocks(lemma, limit=10)
        return self._doc(loc, lemma, blocks)

    # ── front-end config ─────────────────────────────────────────────────────────

    def config(self):
        wk = self.corpus.works()
        items = [{"label": "Altdeutsch", "loc": {"kind": "index"}}]
        for g in wk.get("groups", []):
            items.append({"label": g["label"],
                          "loc": {"kind": "group", "group": g["key"]}, "sub": True})
        items.append({"label": "stem classes", "loc": {"kind": "stems"}})
        return {"title": "Altdeutsch", "logo": "ð",
                "search": "find lemma … (/)", "index": items}


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
    serve(AltdeutschSheets(), WEB, INV_FILE, port)


if __name__ == "__main__":
    main()
