#!/usr/bin/env python3
"""
Split paradigms.json by part of speech and write to paradigms/.

Files produced:
  paradigms/nouns.json      — nominal stems, with stem_class field
  paradigms/verbs.json      — roots
  paradigms/particles.json  — invariables
  paradigms/pronouns.json   — pronouns

Stem classes are inferred from the lemma suffix (Grassmann dash-notation).
"""

import json, os, re
from pathlib import Path

HERE = Path(__file__).parent
SRC  = str(HERE / "paradigms.json")
OUT  = str(HERE / "paradigms")
os.makedirs(OUT, exist_ok=True)

# Ordered longest-first so -ant- is matched before -an-, etc.
STEM_CLASS_RULES = [
    # vocalic
    (r"ā-$",   "ā-stem"),
    (r"ī-$",   "ī-stem"),
    (r"ū-$",   "ū-stem"),
    (r"a-$",   "a-stem"),
    (r"i-$",   "i-stem"),
    (r"u-$",   "u-stem"),
    # consonant: common suffixes
    (r"ant-$", "ant-stem"),   # present participles, adjectives
    (r"ānt-$", "ant-stem"),
    (r"mat-$", "mat/vat-stem"),
    (r"vat-$", "mat/vat-stem"),
    (r"min-$", "in-stem"),
    (r"vin-$", "in-stem"),
    (r"in-$",  "in-stem"),
    (r"an-$",  "an-stem"),    # rāján-, etc.
    (r"man-$", "an-stem"),
    (r"van-$", "an-stem"),
    (r"as-$",  "as-stem"),
    (r"is-$",  "is-stem"),
    (r"us-$",  "us-stem"),
    (r"ar-$",  "ar/r̥-stem"),
    (r"r̥-$",  "ar/r̥-stem"),
    (r"tar-$", "ar/r̥-stem"),
    (r"aj-$",  "consonant-stem"),
    (r"ac-$",  "consonant-stem"),
    (r"añc-$", "consonant-stem"),
    (r"ij-$",  "consonant-stem"),
    (r"ij-$",  "consonant-stem"),
    (r"t-$",   "consonant-stem"),
    (r"d-$",   "consonant-stem"),
    (r"p-$",   "consonant-stem"),
    (r"k-$",   "consonant-stem"),
    (r"g-$",   "consonant-stem"),
    (r"j-$",   "consonant-stem"),
    (r"h-$",   "consonant-stem"),
    (r"bh-$",  "consonant-stem"),
    (r"dh-$",  "consonant-stem"),
    (r"gh-$",  "consonant-stem"),
    (r"n-$",   "consonant-stem"),
    (r"m-$",   "consonant-stem"),
    (r"r-$",   "consonant-stem"),
    (r"l-$",   "consonant-stem"),
    (r"v-$",   "consonant-stem"),
    (r"ś-$",   "consonant-stem"),
    (r"ṣ-$",   "consonant-stem"),
    (r"s-$",   "consonant-stem"),
    (r"ñc-$",  "consonant-stem"),
    (r"c-$",   "consonant-stem"),
    (r"y-$",   "consonant-stem"),
    (r"ṭ-$",   "consonant-stem"),
]

_PITCH_ACCENTS = {
    "́",  # combining acute  (udātta)
    "̀",  # combining grave  (anudātta)
    "̂",  # combining circumflex
    "̑",  # combining inverted breve (svarita variant)
}

def _deaccent(s: str) -> str:
    """Strip only Vedic pitch-accent combining marks; keep phonemic ones (macron, dot-below…)."""
    import unicodedata
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if c not in _PITCH_ACCENTS
    )
    return unicodedata.normalize("NFC", stripped)  # recompose ā, ī, ū, etc.

def stem_class(lemma: str) -> str:
    # suppletive lemmas (e.g. "gáv- ~ gó-"): classify by first part
    if "~" in lemma:
        lemma = lemma.split("~")[0].strip()
    lemma = _deaccent(lemma)
    for pattern, label in STEM_CLASS_RULES:
        if re.search(pattern, lemma):
            return label
    # no dash → indeclinable or unrecognised
    if lemma.endswith("-"):
        return "unknown-stem"
    return "indeclinable"


def token_count(data):
    return sum(f["count"] for f in data["forms"])


def main():
    paradigms = json.load(open(SRC))

    nouns, verbs, particles, pronouns = {}, {}, {}, {}

    for lemma, data in paradigms.items():
        gramm = data["gramm"]
        if "root" in gramm:
            verbs[lemma] = data
        elif "invariable" in gramm:
            particles[lemma] = data
        elif "pronoun" in gramm:
            pronouns[lemma] = data
        else:  # nominal stem (or empty gramm)
            entry = dict(data)
            entry["stem_class"] = stem_class(lemma)
            nouns[lemma] = entry

    # sort each by descending token frequency
    def by_freq(d):
        return dict(sorted(d.items(), key=lambda kv: -token_count(kv[1])))

    nouns     = by_freq(nouns)
    verbs     = by_freq(verbs)
    particles = by_freq(particles)
    pronouns  = by_freq(pronouns)

    for name, data in [("nouns", nouns), ("verbs", verbs),
                       ("particles", particles), ("pronouns", pronouns)]:
        path = f"{OUT}/{name}.json"
        json.dump(data, open(path, "w"), ensure_ascii=False, indent=2)
        total_tokens = sum(token_count(v) for v in data.values())
        # stem class breakdown for nouns
        if name == "nouns":
            from collections import Counter
            classes = Counter(v["stem_class"] for v in data.values())
            print(f"  {name}: {len(data)} lemmas, {total_tokens} tokens")
            for cls, n in classes.most_common():
                print(f"      {n:5d}  {cls}")
        else:
            print(f"  {name}: {len(data)} lemmas, {total_tokens} tokens")

    print()
    for name in ("nouns", "verbs", "particles", "pronouns"):
        print(f"  → {OUT}/{name}.json")


if __name__ == "__main__":
    main()
