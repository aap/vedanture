#!/usr/bin/env python3
"""
Collect every attested (surface form, morphological features) pair for each
lemma and write paradigms.json.

Output structure:
{
  "agní-": {
    "gramm": ["nominal stem"],
    "forms": [
      {"surface": "agním", "features": {"case": "ACC", "gender": "M", "number": "SG"}, "count": 45},
      ...
    ]
  },
  ...
}
Forms are sorted by descending count.
"""

import json
import glob
from collections import defaultdict, Counter
from pathlib import Path
from lxml import etree

TEI   = "http://www.tei-c.org/ns/1.0"
HERE  = Path(__file__).parent
DATA  = str(HERE / "corpus/c-salt_vedaweb_tei")
OUT   = str(HERE / "paradigms.json")

def T(tag):
    return f"{{{TEI}}}{tag}"


def extract_features(zurich_fs):
    """Return (surface, lemma, gramm, features_tuple) from a zurich_info <fs>."""
    surface, lemma, gramm = None, None, None
    features = {}

    for f in zurich_fs:
        name = f.get("name")
        if name == "surface":
            s = f.find(T("string"))
            surface = s.text.strip() if s is not None and s.text else None
        elif name == "gra_lemma":
            s = f.find(T("string"))
            lemma = s.text.strip() if s is not None and s.text else None
        elif name == "gra_gramm":
            sym = f.find(T("symbol"))
            gramm = sym.get("value") if sym is not None else None
        elif name == "morphosyntax":
            inner = f.find(T("fs"))
            if inner is not None:
                for feat in inner:
                    fname = feat.get("name")
                    sym = feat.find(T("symbol"))
                    if fname and sym is not None:
                        features[fname] = sym.get("value")

    return surface, lemma, gramm, tuple(sorted(features.items()))


def build():
    # lemma -> {"gramm": set, "forms": Counter{(surface, feat_tuple)}}
    paradigms = defaultdict(lambda: {"gramm": set(), "forms": Counter()})

    books = sorted(glob.glob(f"{DATA}/rv_book_*.tei"))
    for i, path in enumerate(books, 1):
        book_num = path.split("rv_book_")[1][:2]
        print(f"  book {book_num} ({i}/{len(books)})…", flush=True)
        # Iterate on <l> token-lines, not <fs> — iterating on <fs> causes the
        # nested <fs type="leipzig_glossing_rules"> to be cleared before its
        # parent <fs type="zurich_info"> is processed.
        XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
        for _, el in etree.iterparse(path, tag=T("l")):
            if "_tokens" not in (el.get(XML_ID) or ""):
                el.clear()
                continue
            for fs in el.findall(T("fs")):
                if fs.get("type") != "zurich_info":
                    continue
                surface, lemma, gramm, feat_tuple = extract_features(fs)
                if not lemma:
                    continue
                p = paradigms[lemma]
                if gramm:
                    p["gramm"].add(gramm)
                if surface:
                    p["forms"][(surface, feat_tuple)] += 1
            el.clear()

    # serialise
    output = {}
    for lemma, data in sorted(paradigms.items()):
        forms = [
            {"surface": surface, "features": dict(ft), "count": count}
            for (surface, ft), count
            in sorted(data["forms"].items(), key=lambda x: -x[1])
        ]
        output[lemma] = {
            "gramm": sorted(data["gramm"]),
            "forms": forms,
        }

    with open(OUT, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_tokens = sum(
        sum(form["count"] for form in v["forms"])
        for v in output.values()
    )
    print(f"\n{len(output)} lemmas, {total_tokens} tokens → {OUT}")


if __name__ == "__main__":
    build()
