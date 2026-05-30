#!/usr/bin/env python3
"""
Build gravity.json — lemma-lemma proximity data for the whole corpus.

For each lemma, stores its top-N neighbours with raw connection counts
kept separate so weights can be tuned without rebuilding:

  v  = verse co-occurrence: both lemmas appear anywhere in the same verse
  p  = pada co-occurrence:  both lemmas appear in the same quarter-line
       (typically a single clause; much stronger syntactic signal)
  m  = morphological congruence: attested forms in the same verse share
       case + number + gender, evidence of NP membership or coordination

A default gravity score is precomputed as
  score = (v + 3·p)·PMI + 5·m
where PMI = max(0, log(P(A∧B) / P(A)·P(B))) at the verse level.
Common words co-occurring by chance get low PMI; the morph component
is left unweighted by PMI because agreement is already a strong signal.
"""

import json, glob, math
from collections import defaultdict
from pathlib import Path
from lxml import etree

TEI    = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
HERE   = Path(__file__).parent
DATA   = str(HERE / "corpus/c-salt_vedaweb_tei")
OUT    = str(HERE / "gravity.json")

TOP_N  = 50   # neighbours kept per lemma


def T(tag):
    return f"{{{TEI}}}{tag}"


def parse_ref_pada(lid):
    """'b01_h001_01_zur_a_tokens' → ('1.1.1', 'a')"""
    parts = lid.split("_")
    book  = int(parts[0][1:])
    hymn  = int(parts[1][1:])
    stan  = int(parts[2])
    pada  = parts[4] if len(parts) > 4 else ""
    return f"{book}.{hymn}.{stan}", pada


def congruent(fa, fb):
    """True when two feature dicts agree in case + number + gender."""
    c = fa.get("case")
    return bool(c and c == fb.get("case")
                   and fa.get("number") == fb.get("number")
                   and fa.get("gender") == fb.get("gender"))


def build():
    # ── pass 1: parse corpus ──────────────────────────────────────────────────
    verse_lemmas = defaultdict(set)           # ref → {lemma, …}
    pada_lemmas  = defaultdict(set)           # (ref, pada) → {lemma, …}
    verse_words  = defaultdict(list)          # ref → [(lemma, features), …]

    for path in sorted(glob.glob(f"{DATA}/rv_book_*.tei")):
        book_num = path.split("rv_book_")[1][:2]
        print(f"  book {book_num}…", flush=True)

        for _, el in etree.iterparse(path, tag=T("l")):
            lid = el.get(XML_ID, "")
            if "_zur_" not in lid or not lid.endswith("_tokens"):
                el.clear()
                continue

            ref, pada = parse_ref_pada(lid)

            for fs in el.findall(T("fs")):
                if fs.get("type") != "zurich_info":
                    continue
                lemma_el = fs.find(f"{T('f')}[@name='gra_lemma']/{T('string')}")
                lemma = lemma_el.text.strip() if lemma_el is not None and lemma_el.text else ""
                if not lemma:
                    continue

                features = {}
                morph_el = fs.find(f"{T('f')}[@name='morphosyntax']/{T('fs')}")
                if morph_el is not None:
                    for feat in morph_el:
                        fname = feat.get("name")
                        sym   = feat.find(T("symbol"))
                        if fname and sym is not None:
                            features[fname] = sym.get("value")

                verse_lemmas[ref].add(lemma)
                pada_lemmas[(ref, pada)].add(lemma)
                verse_words[ref].append((lemma, features))

            el.clear()

    total_verses = len(verse_lemmas)
    print(f"\n  {total_verses} verses parsed")

    # ── pass 2: lemma verse-frequency (for PMI) ───────────────────────────────
    lemma_vfreq = defaultdict(int)
    for lemmas in verse_lemmas.values():
        for lemma in lemmas:
            lemma_vfreq[lemma] += 1

    # ── pass 3: accumulate edge components ───────────────────────────────────
    # canonical key: (a, b) with a ≤ b lexicographically
    edges = defaultdict(lambda: [0, 0, 0])   # [v, p, m]

    print("  verse co-occurrence…", flush=True)
    for lemmas in verse_lemmas.values():
        ls = sorted(lemmas)
        for i, a in enumerate(ls):
            for b in ls[i+1:]:
                edges[(a, b)][0] += 1

    print("  pada co-occurrence…", flush=True)
    for lemmas in pada_lemmas.values():
        ls = sorted(lemmas)
        for i, a in enumerate(ls):
            for b in ls[i+1:]:
                edges[(a, b)][1] += 1

    print("  morphological congruence…", flush=True)
    for words in verse_words.values():
        seen = set()
        for i, (la, fa) in enumerate(words):
            for j in range(i + 1, len(words)):
                lb, fb = words[j]
                if la == lb:
                    continue
                pair = (min(la, lb), max(la, lb))
                if pair not in seen and congruent(fa, fb):
                    edges[pair][2] += 1
                    seen.add(pair)

    # ── pass 4: score and build per-lemma neighbour lists ─────────────────────
    print("  scoring…", flush=True)
    adj = defaultdict(list)

    for (a, b), (v, p, m) in edges.items():
        va = lemma_vfreq.get(a, 1)
        vb = lemma_vfreq.get(b, 1)
        pmi = max(0.0, math.log(v * total_verses / (va * vb))) if v else 0.0
        score = round((v + 3 * p) * pmi + 5 * m, 3)
        rec = {"n": b, "v": v, "p": p, "m": m, "s": score}
        adj[a].append(rec)
        adj[b].append({"n": a, "v": v, "p": p, "m": m, "s": score})

    output = {
        lemma: sorted(nbrs, key=lambda x: -x["s"])[:TOP_N]
        for lemma, nbrs in sorted(adj.items())
    }

    with open(OUT, "w") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    unique_edges = len(edges)
    print(f"\n  {len(output)} lemmas, {unique_edges} unique edges → {OUT}")


if __name__ == "__main__":
    build()
