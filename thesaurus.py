#!/usr/bin/env python3
"""
Vocabulary analysis for a Rigveda book.

Usage:
  python3 thesaurus.py 7            core vocabulary covering 80% of tokens
  python3 thesaurus.py 7 90         adjust coverage threshold to 90%
  python3 thesaurus.py 7 only       lemmata exclusive to this book
  python3 thesaurus.py 7 80 only    both views
"""

import sys, csv, json
from collections import Counter
from pathlib import Path

HERE     = Path(__file__).parent
CONC     = HERE / "concordance.tsv"
PAR_DIR  = HERE / "paradigms"

BOOK_NAMES = {
    1: "first maṇḍala",   2: "Gṛtsamada",    3: "Viśvāmitra",
    4: "Vāmadeva",        5: "Atri",          6: "Bharadvāja",
    7: "Vasiṣṭha",        8: "Kāṇva / misc.", 9: "Soma pavamāna",
   10: "tenth maṇḍala",
}

B = "\033[1m"; D = "\033[2m"; R = "\033[0m"
def b(s): return f"{B}{s}{R}"
def d(s): return f"{D}{s}{R}"


def _load_par_info():
    info = {}
    for pos in ("nouns", "verbs", "particles", "pronouns"):
        p = PAR_DIR / f"{pos}.json"
        if not p.exists(): continue
        for lemma, entry in json.loads(p.read_text()).items():
            sc = entry.get("stem_class", "")
            gr = "/".join(entry.get("gramm", []))
            info[lemma] = sc or gr or pos
    return info


def _bar(frac, width=16):
    n = max(1, round(frac * width))
    return "█" * n + d("░" * (width - n))


def show_coverage(book, pct, book_counts, total_tokens, par_info):
    target = total_tokens * pct / 100
    ranked = sorted(book_counts.items(), key=lambda x: -x[1])

    print(f"\n{b(f'RV book {book}')}  {d(BOOK_NAMES.get(book,''))}  ·  "
          f"{total_tokens} tokens  ·  {len(ranked)} unique lemmata")
    print(f"\n  core vocabulary — {b(str(pct)+'%')} coverage\n")

    print(f"  {'#':>4}  {'lemma':<28} {'type':<18} {'n':>5}  {'cum%':>5}  ")
    print(f"  {'─'*4}  {'─'*28} {'─'*18} {'─'*5}  {'─'*5}  {'─'*16}")

    cumulative = 0
    for rank, (lemma, cnt) in enumerate(ranked, 1):
        cumulative += cnt
        cum_pct = cumulative / total_tokens * 100
        typ = par_info.get(lemma, "")
        bar = _bar(cnt / ranked[0][1])
        print(f"  {rank:>4}.  {b(f'{lemma:<28}')} {d(f'{typ:<18}')} "
              f"{cnt:>5}  {cum_pct:>4.1f}%  {bar}")
        if cumulative >= target:
            remaining = total_tokens - cumulative
            print(f"\n  {d(f'... {len(ranked)-rank} more lemmata covering remaining {100-cum_pct:.1f}% ({remaining} tokens)')}")
            break
    print()


def show_exclusive(book, book_counts, all_counts, par_info, min_count=1):
    exclusive = {l: c for l, c in book_counts.items()
                 if all_counts[l] == c and c >= min_count}
    ranked = sorted(exclusive.items(), key=lambda x: -x[1])

    total_exc = sum(c for _, c in ranked)
    filter_note = f"  {d(f'(min {min_count} tokens shown)')}" if min_count > 1 else ""
    print(f"\n{b(f'RV book {book}')}  {d(BOOK_NAMES.get(book,''))}  ·  "
          f"exclusive lemmata: {b(str(len(ranked)))}  ({total_exc} tokens){filter_note}\n")

    buckets = [
        ("significant  (10+ tokens)", [(l,c) for l,c in ranked if c >= 10]),
        ("notable      (3–9 tokens)",  [(l,c) for l,c in ranked if 3 <= c < 10]),
        ("rare         (1–2 tokens)",  [(l,c) for l,c in ranked if c < 3]),
    ]
    for label, items in buckets:
        if not items: continue
        print(f"  {d(label)}")
        for lemma, cnt in items:
            typ = par_info.get(lemma, "")
            print(f"    {b(f'{lemma:<30}')} {d(f'{typ:<20}')} {cnt:>3} tokens")
        print()


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    book       = int(args[0])
    pct        = 80
    only       = False
    min_count  = 1
    for a in args[1:]:
        if a == "only":            only = True
        elif a.isdigit():          pct  = int(a)
        elif a.startswith("min:"): min_count = int(a[4:])

    if not CONC.exists():
        print("concordance.tsv not found — run build_concordance.py first")
        sys.exit(1)

    book_counts  = Counter()
    all_counts   = Counter()
    with open(CONC) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            lemma = row["lemma"]
            bk    = int(row["ref"].split(".")[0])
            all_counts[lemma] += 1
            if bk == book:
                book_counts[lemma] += 1

    if not book_counts:
        print(f"  no data for book {book}")
        sys.exit(1)

    par_info     = _load_par_info()
    total_tokens = sum(book_counts.values())

    if only:
        show_exclusive(book, book_counts, all_counts, par_info, min_count)
    else:
        show_coverage(book, pct, book_counts, total_tokens, par_info)
        print(d("  tip: thesaurus.py 7 only          book-exclusive lemmata"))
        print(d("       thesaurus.py 7 only min:3     exclusive, 3+ tokens only"))
        print(d("       thesaurus.py 7 90             90% coverage threshold\n"))


if __name__ == "__main__":
    main()
