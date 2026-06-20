#!/usr/bin/env python3
"""
Build derived corpus files from tokens.tsv + verses.tsv.

Usage:
  python3 build_corpus.py corpus/gothic

Produces in the same directory:
  paradigms/nouns.json
  paradigms/verbs.json
  paradigms/particles.json
  paradigms/pronouns.json
  concordance.tsv
  gravity.json
"""

import csv, json, math, sys
from collections import defaultdict, Counter
from pathlib import Path

TOP_N = 50

POS_FILE = {
    "noun":  "nouns",
    "adj":   "nouns",
    "name":  "nouns",
    "num":   "nouns",
    "verb":  "verbs",
    "pron":  "pronouns",
    "adv":   "particles",
    "prep":  "particles",
    "conj":  "particles",
    "ptcl":  "particles",
    "interj":"particles",
}

GRAMM_TAG = {
    "nouns":     "nominal stem",
    "verbs":     "verb",
    "pronouns":  "pronoun",
    "particles": "invariable",
}


def congruent(fa, fb):
    c = fa.get("case")
    return bool(c and c == fb.get("case")
                   and fa.get("number") == fb.get("number")
                   and fa.get("gender") == fb.get("gender"))


def build(corpus_dir: Path):
    tokens_path = corpus_dir / "tokens.tsv"
    verses_path = corpus_dir / "verses.tsv"

    if not tokens_path.exists():
        print(f"  tokens.tsv not found in {corpus_dir}"); sys.exit(1)

    # ── pass 1: read tokens ───────────────────────────────────────────────────
    print("  reading tokens…", flush=True)

    paradigm_data: dict[str, dict] = {}    # lemma → {file, stem_class, forms Counter}
    verse_lemmas  = defaultdict(set)
    verse_words   = defaultdict(list)      # ref → [(lemma, features), ...]

    # Track primary manuscript per verse to avoid double-counting var=1 tokens
    verse_primary_ms: dict = {}   # ref → primary (lowest) ms
    verse_seen_pos:   dict = defaultdict(set)  # ref → set of (ms, position) seen

    with open(tokens_path) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            lemma   = row["lemma"].strip()
            surface = row["surface"].strip()
            pos     = row["pos"].strip()
            sc      = row["stem_class"].strip()
            if not lemma or not surface:
                continue

            try:
                feats = json.loads(row["features"]) if row["features"].strip() else {}
            except json.JSONDecodeError:
                feats = {}

            ref      = row["ref"]
            ms       = row.get("ms", "")
            position = row.get("position", "")
            variation = row.get("variation", "0")

            # Determine primary manuscript for this verse on first encounter
            if ms and ref not in verse_primary_ms:
                verse_primary_ms[ref] = ms
            primary_ms = verse_primary_ms.get(ref, "")

            # Skip identical (var=1) tokens from secondary manuscripts
            if ms and ms != primary_ms and variation == "1":
                continue

            # paradigms accumulation
            file_key = POS_FILE.get(pos, "particles")
            if lemma not in paradigm_data:
                paradigm_data[lemma] = {
                    "file":       file_key,
                    "stem_class": sc,
                    "pos":        pos,
                    "forms":      Counter(),
                    "feat_map":   {},
                }
            entry = paradigm_data[lemma]
            feat_key = json.dumps(feats, sort_keys=True)
            key = (surface, feat_key)
            entry["forms"][key] += 1
            if feat_key not in entry["feat_map"]:
                entry["feat_map"][feat_key] = feats
            if sc and not entry["stem_class"]:
                entry["stem_class"] = sc

            # gravity inputs
            verse_lemmas[ref].add(lemma)
            verse_words[ref].append((lemma, feats))

    total_verses = len(verse_lemmas)
    print(f"  {total_verses} verses, {len(paradigm_data)} lemmata")

    # ── build paradigms ───────────────────────────────────────────────────────
    print("  building paradigms…", flush=True)

    buckets: dict[str, dict] = {"nouns": {}, "verbs": {}, "particles": {}, "pronouns": {}}
    for lemma, entry in paradigm_data.items():
        fk = entry["file"]
        gramm_tag = GRAMM_TAG[fk]
        forms_list = []
        for (surface, feat_key), count in entry["forms"].most_common():
            forms_list.append({
                "surface":  surface,
                "features": entry["feat_map"][feat_key],
                "count":    count,
            })
        out = {"gramm": [gramm_tag], "forms": forms_list}
        if entry["stem_class"]:
            out["stem_class"] = entry["stem_class"]
        buckets[fk][lemma] = out

    par_dir = corpus_dir / "paradigms"
    par_dir.mkdir(exist_ok=True)
    for fname, data in buckets.items():
        (par_dir / f"{fname}.json").write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        )
        print(f"    {fname}.json — {len(data)} lemmata")

    # ── build concordance ─────────────────────────────────────────────────────
    print("  building concordance…", flush=True)

    verse_text = {}
    if verses_path.exists():
        with open(verses_path) as f:
            for row in csv.DictReader(f, delimiter="\t"):
                verse_text[row["ref"]] = row.get("text", "")

    conc_rows = []
    with open(tokens_path) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            lemma   = row["lemma"].strip()
            surface = row["surface"].strip()
            ref     = row["ref"]
            if not lemma or not surface:
                continue
            conc_rows.append({
                "lemma":   lemma,
                "ref":     ref,
                "pada":    "",
                "surface": surface,
                "text":    verse_text.get(ref, ""),
            })

    conc_rows.sort(key=lambda r: r["lemma"])
    conc_path = corpus_dir / "concordance.tsv"
    with open(conc_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["lemma","ref","pada","surface","text"],
                           delimiter="\t")
        w.writeheader()
        w.writerows(conc_rows)
    print(f"    concordance.tsv — {len(conc_rows)} rows")

    # ── build gravity ─────────────────────────────────────────────────────────
    print("  verse co-occurrence…", flush=True)

    lemma_vfreq = defaultdict(int)
    for lemmas in verse_lemmas.values():
        for l in lemmas:
            lemma_vfreq[l] += 1

    edges = defaultdict(lambda: [0, 0, 0])   # [v, p, m]

    for lemmas in verse_lemmas.values():
        ls = sorted(lemmas)
        for i, a in enumerate(ls):
            for blem in ls[i+1:]:
                edges[(a, blem)][0] += 1

    print("  morphological congruence…", flush=True)
    for words in verse_words.values():
        seen: set = set()
        for i, (la, fa) in enumerate(words):
            for j in range(i+1, len(words)):
                lb, fb = words[j]
                if la == lb:
                    continue
                pair = (min(la,lb), max(la,lb))
                if pair not in seen and congruent(fa, fb):
                    edges[pair][2] += 1
                    seen.add(pair)

    print("  scoring…", flush=True)
    adj: dict = defaultdict(list)
    for (a, blem), (v, p, m) in edges.items():
        va  = lemma_vfreq.get(a, 1)
        vb  = lemma_vfreq.get(blem, 1)
        pmi = max(0.0, math.log(v * total_verses / (va * vb))) if v else 0.0
        score = round((v + 3*p) * pmi + 5*m, 3)
        rec = {"n": blem, "v": v, "p": p, "m": m, "s": score}
        adj[a].append(rec)
        adj[blem].append({"n": a, "v": v, "p": p, "m": m, "s": score})

    output = {
        lemma: sorted(nbrs, key=lambda x: -x["s"])[:TOP_N]
        for lemma, nbrs in sorted(adj.items())
    }
    grav_path = corpus_dir / "gravity.json"
    grav_path.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    print(f"    gravity.json — {len(output)} lemmata, {len(edges)} edges")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    build(Path(sys.argv[1]))
