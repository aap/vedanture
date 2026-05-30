#!/usr/bin/env python3
"""
Build concordance.tsv — one row per token occurrence across the whole corpus.

Columns: lemma  ref  pada  surface  text
Sorted by lemma then ref.
"""

import glob
from pathlib import Path
from lxml import etree

TEI    = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
HERE   = Path(__file__).parent
DATA   = str(HERE / "corpus/c-salt_vedaweb_tei")
OUT    = str(HERE / "concordance.tsv")


def T(tag):
    return f"{{{TEI}}}{tag}"


def parse_ref(lid):
    """'b01_h001_01_zur_a_tokens' → ('1.1.1', 'a')"""
    parts = lid.split("_")          # ['b01', 'h001', '01', 'zur', 'a', 'tokens']
    book   = int(parts[0][1:])
    hymn   = int(parts[1][1:])
    stanza = int(parts[2])
    pada   = parts[4] if len(parts) > 4 else ""
    return f"{book}.{hymn}.{stanza}", pada


rows = []

for path in sorted(glob.glob(f"{DATA}/rv_book_*.tei")):
    book_num = path.split("rv_book_")[1][:2]
    print(f"  book {book_num}…", flush=True)

    pada_text = {}  # pada label → text, saved before the sibling is cleared

    for _, el in etree.iterparse(path, tag=T("l")):
        lid = el.get(XML_ID, "")
        if "_zur_" not in lid:
            el.clear()
            continue

        parts = lid.split("_")
        pada  = parts[4] if len(parts) > 4 else ""

        if not lid.endswith("_tokens"):
            # plain text line — save it before clearing
            pada_text[pada] = "".join(el.itertext()).strip()
            el.clear()
            continue

        ref, _ = parse_ref(lid)
        text   = pada_text.get(pada, "")

        for fs in el.findall(T("fs")):
            if fs.get("type") != "zurich_info":
                continue
            surface_el = fs.find(f".//{T('string')}")
            lemma_el   = fs.find(f"{T('f')}[@name='gra_lemma']/{T('string')}")
            surface = surface_el.text.strip() if surface_el is not None and surface_el.text else ""
            lemma   = lemma_el.text.strip()   if lemma_el   is not None and lemma_el.text   else ""
            if lemma and surface:
                rows.append((lemma, ref, pada, surface, text))

        el.clear()

def ref_key(r):
    book, hymn, stanza = r[1].split(".")
    return (r[0], int(book), int(hymn), int(stanza))

rows.sort(key=ref_key)

with open(OUT, "w") as f:
    f.write("lemma\tref\tpada\tsurface\ttext\n")
    for row in rows:
        f.write("\t".join(row) + "\n")

print(f"\n{len(rows)} tokens → {OUT}")
