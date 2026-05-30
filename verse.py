#!/usr/bin/env python3
"""Dump the morphological annotation of a Rigveda verse, with concordance.

Usage:  python3 verse.py 1.1.1          show verse with numbered words
        python3 verse.py 1.1.1 3        concordance for word 3 (that surface form)
        python3 verse.py 1.1.1 3.       concordance for the lemma of word 3
"""

import sys, csv
from lxml import etree
from pathlib import Path

TEI  = "http://www.tei-c.org/ns/1.0"
T    = lambda tag: f"{{{TEI}}}{tag}"
HERE = Path(__file__).parent
DATA = str(HERE / "corpus/c-salt_vedaweb_tei")
CONC = HERE / "concordance.tsv"

TRANSLATIONS = ["griffith", "geldner", "macdonell"]


def tei_file(book: int) -> str:
    return f"{DATA}/rv_book_{book:02d}.tei"


def stanza_id(book: int, hymn: int, stanza: int) -> str:
    return f"b{book:02d}_h{hymn:03d}_{stanza:02d}"


def get_f(fs_el, name):
    f = fs_el.find(f".//{T('f')}[@name='{name}']")
    if f is None:
        return None
    s = f.find(T("string"))
    if s is not None:
        return (s.text or "").strip()
    sym = f.find(T("symbol"))
    if sym is not None:
        return sym.get("value", "").strip()
    return (f.text or "").strip() or None


def morph_features(fs_el):
    morph_fs = fs_el.find(f".//{T('fs')}[@type='leipzig_glossing_rules']")
    if morph_fs is None:
        return {}
    return {
        f.get("name", ""): f.find(T("symbol")).get("value", "")
        for f in morph_fs.findall(T("f"))
        if f.find(T("symbol")) is not None
    }


def find_div(root, sid):
    XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
    for d in root.iter(T("div")):
        if d.get(XML_ID) == sid:
            return d
    return None


# ── verse display ─────────────────────────────────────────────────────────────

def get_words(ref: str) -> list[dict]:
    """Parse a verse and return its word list."""
    parts = ref.strip().split(".")
    book, hymn, stanza = (int(p) for p in parts)
    root = etree.parse(tei_file(book)).getroot()
    div  = find_div(root, stanza_id(book, hymn, stanza))
    if div is None:
        sys.exit(f"Stanza {ref} not found")

    words = []
    zur_lg = div.find(f".//{T('lg')}[@source='zurich']")
    if zur_lg is None:
        return words
    for fs in zur_lg.iter(T("fs")):
        if fs.get("type") != "zurich_info":
            continue
        words.append({
            "surface": get_f(fs, "surface") or "?",
            "lemma":   get_f(fs, "gra_lemma") or "?",
            "gramm":   get_f(fs, "gra_gramm") or "?",
            "feats":   morph_features(fs),
        })
    return words


def dump_verse(ref: str) -> list[dict]:
    parts = ref.strip().split(".")
    if len(parts) != 3:
        sys.exit("Usage: verse.py BOOK.HYMN.STANZA")
    book, hymn, stanza = (int(p) for p in parts)

    root = etree.parse(tei_file(book)).getroot()
    div  = find_div(root, stanza_id(book, hymn, stanza))
    if div is None:
        sys.exit(f"Stanza {ref} not found")

    print(f"=== RV {book}.{hymn}.{stanza} ===\n")

    zur_lg = div.find(f".//{T('lg')}[@source='zurich']")
    words  = []
    if zur_lg is not None:
        XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
        half_lines = [l for l in zur_lg.findall(T("l"))
                      if "_tokens" not in (l.get(XML_ID) or "")]
        print("  " + " / ".join(" ".join(l.itertext()).strip() for l in half_lines))
        print()

        for fs in zur_lg.iter(T("fs")):
            if fs.get("type") != "zurich_info":
                continue
            words.append({
                "surface": get_f(fs, "surface") or "?",
                "lemma":   get_f(fs, "gra_lemma") or "?",
                "gramm":   get_f(fs, "gra_gramm") or "?",
                "feats":   morph_features(fs),
            })

        col_w = max((len(w["surface"]) for w in words), default=8) + 2
        col_l = max((len(w["lemma"])   for w in words), default=8) + 2
        num_w = len(str(len(words))) + 1

        print(f"  {'#':<{num_w}} {'form':<{col_w}} {'lemma':<{col_l}} {'class':<16} morphology")
        print(f"  {'-'*num_w} {'-'*col_w} {'-'*col_l} {'-'*16} {'-'*30}")
        for i, w in enumerate(words, 1):
            feat_str = "  ".join(f"{k}={v}" for k, v in w["feats"].items())
            print(f"  {i:<{num_w}} {w['surface']:<{col_w}} {w['lemma']:<{col_l}} {w['gramm']:<16} {feat_str}")

    print()
    for src in TRANSLATIONS:
        lg = div.find(f".//{T('lg')}[@source='{src}']")
        if lg is None:
            continue
        text = " / ".join(" ".join(l.itertext()).strip() for l in lg.findall(T("l")))
        print(f"  [{src}] {text}")

    if words:
        print(f"\n  verse.py {ref} N    concordance for word N (surface form)")
        print(f"  verse.py {ref} N.   concordance for lemma of word N")

    return words


# ── concordance ───────────────────────────────────────────────────────────────

def load_concordance(lemma: str) -> list[dict]:
    rows = []
    with open(CONC, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row["lemma"] == lemma:
                rows.append(row)
    return rows


def show_concordance(ref: str, word_num: int, lemma_mode: bool):
    words = get_words(ref)
    if not (1 <= word_num <= len(words)):
        sys.exit(f"Word number out of range (1–{len(words)})")

    w      = words[word_num - 1]
    surface = w["surface"]
    lemma   = w["lemma"]

    rows = load_concordance(lemma)
    if not rows:
        print(f"No concordance entries for {lemma!r}")
        return

    def ref_sort(r):
        b, h, s = r["ref"].split(".")
        return (int(b), int(h), int(s))

    if lemma_mode:
        label  = f"lemma {lemma}"
        hits   = sorted(rows, key=ref_sort)
    else:
        label  = f"{surface}  (< {lemma})"
        hits   = sorted((r for r in rows if r["surface"] == surface), key=ref_sort)

    print(f"\n  {label}  ·  {len(hits)} occurrence{'s' if len(hits) != 1 else ''}\n")

    col_ref = max(len(r["ref"]) for r in hits) + 1
    for r in hits:
        marker = f"\033[1m{r['surface']}\033[0m" if lemma_mode else r["surface"]
        # in lemma mode, bold the surface so you can scan for form variation
        text = r["text"]
        if lemma_mode and r["surface"] in text:
            text = text.replace(r["surface"], f"\033[1m{r['surface']}\033[0m", 1)
        print(f"  {r['ref']:<{col_ref}}  {r['pada']}   {r['surface']:<22}  {r['text']}")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    if len(args) == 1:
        dump_verse(args[0])
    elif len(args) == 2:
        ref    = args[0]
        num_arg = args[1]
        lemma_mode = num_arg.endswith(".")
        num_str    = num_arg.rstrip(".")
        if not num_str.isdigit():
            sys.exit("Second argument must be a word number (e.g. 3 or 3.)")
        show_concordance(ref, int(num_str), lemma_mode)
    else:
        print(__doc__)
        sys.exit(1)
