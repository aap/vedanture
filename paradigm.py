#!/usr/bin/env python3
"""Display the attested paradigm for a lemma.

Usage:  python3 paradigm.py agni       search, jump to paradigm if unambiguous
        python3 paradigm.py agni?      always show numbered match list
        python3 paradigm.py agni? 3    show paradigm for match #3
        python3 paradigm.py √gam-      exact lemma (accents optional)
"""

import sys, json, unicodedata, difflib
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent / "paradigms"

# ── canonical ordering ────────────────────────────────────────────────────────

CASES   = ["NOM", "ACC", "INS", "DAT", "ABL", "GEN", "LOC", "VOC"]
NUMBERS = ["SG", "DU", "PL"]
GENDERS = ["M", "F", "N"]

TENSES  = ["PRS", "IPRF", "AOR", "PRF", "FUT", "COND", ""]
MOODS   = ["IND", "IMP", "SBJV", "OPT", "INJ", "DES", ""]
VOICES  = ["ACT", "MED", "PASS", ""]
PERSONS = ["1", "2", "3", ""]

TENSE_NAME  = {"PRS": "present", "IPRF": "imperfect", "AOR": "aorist",
               "PRF": "perfect", "FUT": "future", "COND": "conditional", "": ""}
MOOD_NAME   = {"IND": "indicative", "IMP": "imperative", "SBJV": "subjunctive",
               "OPT": "optative", "INJ": "injunctive", "DES": "desiderative", "": ""}
VOICE_NAME  = {"ACT": "active", "MED": "middle", "PASS": "passive", "": ""}


# ── search helpers ────────────────────────────────────────────────────────────

def _normalise(s: str) -> str:
    """Lowercase, strip accents, trailing dash, leading √ — for fuzzy matching."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # strip all combining
    s = unicodedata.normalize("NFC", s)
    return s.lower().lstrip("√").rstrip("-~ ").strip()


_DATA: dict[str, dict] = {}  # pos → {lemma → data}, loaded once

def _load_all() -> dict[str, dict]:
    if not _DATA:
        for pos in ("nouns", "verbs", "particles", "pronouns"):
            _DATA[pos] = json.loads((BASE / f"{pos}.json").read_text())
    return _DATA


def _all_lemmas() -> list[tuple[str, str]]:
    """Return [(lemma, pos), …] across all POS files."""
    return [
        (lemma, pos)
        for pos, entries in _load_all().items()
        for lemma in entries
    ]


def search(query: str) -> list[tuple[str, str]]:
    """
    Return a ranked list of (lemma, pos) matching query.
    Priority: exact → exact-normalised → starts-with → contains → difflib fuzzy.
    """
    all_lemmas = _all_lemmas()
    q = _normalise(query)

    exact, starts, contains, fuzzy = [], [], [], []
    norm_map = {lemma: _normalise(lemma) for lemma, _ in all_lemmas}

    for lemma, pos in all_lemmas:
        n = norm_map[lemma]
        if lemma == query or n == q:
            exact.append((lemma, pos))
        elif n.startswith(q):
            starts.append((lemma, pos))
        elif q in n:
            contains.append((lemma, pos))

    if not (exact or starts or contains):
        close = difflib.get_close_matches(q, norm_map.values(), n=10, cutoff=0.6)
        close_set = set(close)
        fuzzy = [(l, p) for l, p in all_lemmas if norm_map[l] in close_set]
        fuzzy.sort(key=lambda lp: difflib.SequenceMatcher(None, q, norm_map[lp[0]]).ratio(), reverse=True)

    return exact + starts + contains + fuzzy


def load_exact(lemma: str) -> tuple[str | None, dict | None]:
    for pos, entries in _load_all().items():
        if lemma in entries:
            return pos, entries[lemma]
    return None, None


def token_count(data) -> int:
    return sum(f["count"] for f in data["forms"])


# ── shared helpers ────────────────────────────────────────────────────────────

def cell(forms):
    """Format a list of (surface, count) into a cell string."""
    if not forms:
        return "—"
    return "  /  ".join(
        f"{s} ({n})" if n > 1 else s
        for s, n in sorted(forms, key=lambda x: -x[1])
    )


def header(title: str):
    print(f"\n  \033[1m{title}\033[0m")


def rule(w=72):
    print("  " + "─" * w)


# ── noun / pronoun display ────────────────────────────────────────────────────

def show_nominal(lemma, data, pos):
    # index: (case, number, gender) → [(surface, count)]
    idx = defaultdict(list)
    for f in data["forms"]:
        ft = f["features"]
        case   = ft.get("case", "")
        number = ft.get("number", "")
        gender = ft.get("gender", "")
        idx[(case, number, gender)].append((f["surface"], f["count"]))

    # detect which genders are present
    genders_present = sorted({k[2] for k in idx}, key=lambda g: GENDERS.index(g) if g in GENDERS else 9)
    # detect which cases are present
    cases_present = [c for c in CASES if any(k[0] == c for k in idx)]
    # "" case = unannotated (often vocative without explicit VOC tag)
    if any(k[0] == "" for k in idx):
        cases_present.append("")

    title_parts = [lemma]
    if pos == "nouns":
        title_parts.append(data.get("stem_class", ""))
    title_parts.append(" / ".join(data.get("gramm", [])))
    print("\n" + "  " + "  ·  ".join(p for p in title_parts if p))
    rule()

    col = 22  # width of each number column

    # separate genderless forms (enclitics etc.) from gendered ones
    genders_tagged   = [g for g in genders_present if g]
    has_genderless   = any(k[2] == "" for k in idx)

    # decide: show one merged table or per-gender tables
    show_per_gender = len(genders_tagged) > 1

    def _table(filter_g, label=None):
        if label:
            header(label)
        nums_here = [n for n in NUMBERS if any(k[1] == n and (not filter_g or k[2] == filter_g) for k in idx)]
        if not nums_here:
            return
        hdr = f"  {'':8}"
        for num in nums_here:
            hdr += f"  {num:<{col}}"
        print(hdr)
        rule()
        for case in cases_present:
            row = f"  {(case or '(unannotated)'):<8}"
            any_col = False
            for num in nums_here:
                if filter_g:
                    merged = idx.get((case, num, filter_g), [])
                else:
                    merged = []
                    for gg in ["", "M", "F", "N"]:
                        merged.extend(idx.get((case, num, gg), []))
                row += f"  {cell(merged):<{col}}"
                any_col = True
            if any_col:
                print(row)

    if show_per_gender:
        for g in genders_tagged:
            _table(g, {"M": "masculine", "F": "feminine", "N": "neuter"}.get(g, g))
        if has_genderless:
            header("(no gender tagged)")
            nums_here = [n for n in NUMBERS if any(k[1] == n and k[2] == "" for k in idx)]
            hdr = f"  {'':8}" + "".join(f"  {n:<{col}}" for n in nums_here)
            print(hdr)
            rule()
            for case in cases_present:
                row = f"  {(case or '(unannotated)'):<8}"
                any_col = False
                for num in nums_here:
                    merged = idx.get((case, num, ""), [])
                    row += f"  {cell(merged):<{col}}"
                    any_col = any_col or bool(merged)
                if any_col:
                    print(row)
    else:
        _table("")  # merge all genders — no genuine gender variation

    total = sum(f["count"] for f in data["forms"])
    print(f"\n  {total} tokens total")


# ── verb display ──────────────────────────────────────────────────────────────

def show_verb(lemma, data):
    # index: (tense, mood, voice, person, number) → [(surface, count)]
    idx = defaultdict(list)
    for f in data["forms"]:
        ft = f["features"]
        key = (ft.get("tense",""), ft.get("mood",""), ft.get("voice",""),
               ft.get("person",""), ft.get("number",""))
        idx[key].append((f["surface"], f["count"]))

    print(f"\n  {lemma}  ·  " + " / ".join(data.get("gramm", [])))
    rule()

    col = 22
    # group by (tense, mood, voice)
    tmv_seen = []
    for t in TENSES:
        for m in MOODS:
            for v in VOICES:
                if any(k[:3] == (t, m, v) for k in idx):
                    tmv_seen.append((t, m, v))

    for (t, m, v) in tmv_seen:
        parts = [x for x in [TENSE_NAME.get(t, t), MOOD_NAME.get(m, m), VOICE_NAME.get(v, v)] if x]
        header(" ".join(parts) if parts else "(unannotated)")

        # which persons and numbers appear in this section
        persons_here = [p for p in PERSONS if any(k == (t,m,v,p,n) for k in idx for n in NUMBERS)]
        numbers_here = [n for n in NUMBERS if any(k == (t,m,v,p,n) for k in idx for p in PERSONS)]

        hdr = f"  {'':6}"
        for n in numbers_here:
            hdr += f"  {n:<{col}}"
        print(hdr)

        for p in persons_here:
            label = f"  {p or '?':<6}"
            row = label
            for n in numbers_here:
                forms = idx.get((t, m, v, p, n), [])
                row += f"  {cell(forms):<{col}}"
            print(row)

    # non-finite / unannotated forms
    nonfinite = [(f["surface"], f["features"], f["count"]) for f in data["forms"]
                 if not f["features"].get("person") and not f["features"].get("case")
                 and not f["features"].get("number")]
    if nonfinite:
        header("non-finite / unannotated")
        for s, ft, n in sorted(nonfinite, key=lambda x: -x[2]):
            feat = "  ".join(f"{k}={v}" for k, v in ft.items())
            print(f"  {'':6}  {s}  ({n})" + (f"  [{feat}]" if feat else ""))

    total = sum(f["count"] for f in data["forms"])
    print(f"\n  {total} tokens total")


# ── particle display ──────────────────────────────────────────────────────────

def show_particle(lemma, data):
    print(f"\n  {lemma}  ·  invariable")
    rule()
    total = 0
    for f in data["forms"]:
        feat = "  ".join(f"{k}={v}" for k, v in f["features"].items())
        tag = f"  [{feat}]" if feat else ""
        print(f"  {f['count']:5d}  {f['surface']}{tag}")
        total += f["count"]
    print(f"\n  {total} tokens total")


# ── main ──────────────────────────────────────────────────────────────────────

POS_LABEL = {"nouns": "nominal stem", "verbs": "root",
             "particles": "invariable", "pronouns": "pronoun"}

def show(lemma, pos, data):
    if pos in ("nouns", "pronouns"):
        show_nominal(lemma, data, pos)
    elif pos == "verbs":
        show_verb(lemma, data)
    else:
        show_particle(lemma, data)


def print_list(query: str, results: list):
    print(f"\n  {len(results)} lemmas found for {query!r}:\n")
    for i, (lemma, pos) in enumerate(results, 1):
        _, data = load_exact(lemma)
        total = token_count(data)
        sc = data.get("stem_class", "")
        tag = POS_LABEL[pos] + (f", {sc}" if sc and sc != "indeclinable" else "")
        print(f"  {i:3}.  {lemma:<28}  {tag:<22}  {total} tokens")
    print(f"\n  Run: python3 paradigm.py {query}? N")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    arg = args[0]
    force_list = arg.endswith("?")
    if force_list:
        arg = arg[:-1]

    # ── query? N — search and pick Nth result, no state ───────────────────────
    if force_list and len(args) == 2 and args[1].isdigit():
        results = search(arg)
        if not results:
            print(f"No lemmas found for {arg!r}.")
            sys.exit(1)
        idx = int(args[1]) - 1
        if not (0 <= idx < len(results)):
            print(f"Number out of range (1–{len(results)}).")
            sys.exit(1)
        lemma, pos = results[idx]
        _, data = load_exact(lemma)
        show(lemma, pos, data)
        return

    # ── query? — always show list ─────────────────────────────────────────────
    if force_list:
        results = search(arg)
        if not results:
            print(f"No lemmas found for {arg!r}.")
            sys.exit(1)
        print_list(arg, results)
        return

    # ── plain query — jump to paradigm if unambiguous ─────────────────────────
    results = search(arg)
    if not results:
        print(f"No lemmas found for {arg!r}.")
        sys.exit(1)

    if len(results) == 1:
        lemma, pos = results[0]
        _, data = load_exact(lemma)
        show(lemma, pos, data)
        return

    first_norm = _normalise(results[0][0])
    if first_norm == _normalise(arg) and (len(results) < 2 or _normalise(results[1][0]) != first_norm):
        lemma, pos = results[0]
        _, data = load_exact(lemma)
        show(lemma, pos, data)
        return

    print_list(arg, results)


if __name__ == "__main__":
    main()
