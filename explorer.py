#!/usr/bin/env python3
"""
Shared corpus explorer engine — language-agnostic.

Provides:
  Corpus   — lazy data loader with configurable paths and feature ordering
  S        — session state (word, history, inventory, last_list)
  show_*   — display functions that operate on session + corpus data
  _push, _goto_lemma, _norm — navigation helpers
"""

import json, csv, unicodedata, difflib
from pathlib import Path
from collections import defaultdict

# ── terminal ──────────────────────────────────────────────────────────────────

B  = "\033[1m"
D  = "\033[2m"
R  = "\033[0m"
HL = "\033[1;33m"

def b(s):  return f"{B}{s}{R}"
def d(s):  return f"{D}{s}{R}"
def hl(s): return f"{HL}{s}{R}"

RULE = "─" * 64

# ── normalization ─────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", s).lower().lstrip("√").rstrip("-~ ").strip()

# ── corpus ────────────────────────────────────────────────────────────────────

class Corpus:
    """
    Lazy loader for the derived corpus data files.

    Subclass and override the class-level feature constants to control
    paradigm display ordering for a specific language.
    """

    # Nominal feature display ordering
    CASES   = ["NOM","ACC","INS","DAT","ABL","GEN","LOC","VOC",""]
    NUMBERS = ["SG","DU","PL"]
    GENDERS = ["M","F","N",""]

    # Verbal feature display ordering
    TENSES  = ["PRS","IPRF","AOR","PRF","FUT","COND",""]
    MOODS   = ["IND","IMP","SBJV","OPT","INJ","DES",""]
    VOICES  = ["ACT","MED","PASS",""]
    PERSONS = ["1","2","3",""]

    # Human-readable labels for verbal features
    T_NAME  = {"PRS":"present","IPRF":"imperfect","AOR":"aorist","PRF":"perfect",
               "FUT":"future","COND":"conditional","":""}
    M_NAME  = {"IND":"indicative","IMP":"imperative","SBJV":"subjunctive",
               "OPT":"optative","INJ":"injunctive","DES":"desiderative","":""}
    V_NAME  = {"ACT":"active","MED":"middle","PASS":"passive","":""}

    def __init__(self, data_dir: Path, inv_file: Path | None = None):
        self._dir      = data_dir
        self._pd: dict | None  = None
        self._cd: dict | None  = None
        self._gd: dict | None  = None
        self.inv_file  = inv_file or (Path.home() / f".{data_dir.name}_inventory.json")

    # ── loaders ───────────────────────────────────────────────────────────────

    def paradigms(self) -> dict:
        if self._pd is None:
            d: dict = {}
            for pos in ("nouns", "verbs", "particles", "pronouns"):
                p = self._dir / "paradigms" / f"{pos}.json"
                if p.exists():
                    d |= json.loads(p.read_text())
            self._pd = d
        return self._pd

    def concordance(self) -> dict:
        if self._cd is None:
            rows: dict = defaultdict(list)
            p = self._dir / "concordance.tsv"
            if p.exists():
                with open(p) as f:
                    for row in csv.DictReader(f, delimiter="\t"):
                        rows[row["lemma"]].append(row)
            self._cd = dict(rows)
        return self._cd

    def gravity(self) -> dict:
        if self._gd is None:
            p = self._dir / "gravity.json"
            self._gd = json.loads(p.read_text()) if p.exists() else {}
        return self._gd

    # ── search ────────────────────────────────────────────────────────────────

    def search(self, query: str, n: int = 15) -> list[tuple[str, dict]]:
        q    = _norm(query)
        all_ = list(self.paradigms().items())
        nm   = {l: _norm(l) for l, _ in all_}
        ex, st, co = [], [], []
        for l, pd in all_:
            v = nm[l]
            if v == q:             ex.append((l, pd))
            elif v.startswith(q):  st.append((l, pd))
            elif q in v:           co.append((l, pd))
        if not (ex or st or co):
            close = set(difflib.get_close_matches(q, nm.values(), n=n, cutoff=0.6))
            fz = sorted(
                [(l, pd) for l, pd in all_ if nm[l] in close],
                key=lambda x: -difflib.SequenceMatcher(None, q, nm[x[0]]).ratio(),
            )
            return fz[:n]
        return (ex + st + co)[:n]

    # ── ref ordering ──────────────────────────────────────────────────────────

    def ref_sort_key(self, ref: str):
        """Sort key for refs. Override for corpora with non-numeric book IDs."""
        try:
            return tuple(int(x) for x in ref.split("."))
        except ValueError:
            parts = ref.split(".")
            try:
                return (parts[0], int(parts[1]), int(parts[2]))
            except (IndexError, ValueError):
                return (ref,)


# ── session state ─────────────────────────────────────────────────────────────

class S:
    def __init__(self, corpus: Corpus):
        self.corpus:    Corpus       = corpus
        self.word:      dict | None  = None
        self.last_list: list         = []
        self.history:   list         = []
        self.inventory: dict         = {}
        self.cur_loc:   dict | None  = None


def _push(s: S, loc: dict) -> None:
    if s.cur_loc:
        s.history.append(s.cur_loc)
    s.cur_loc = loc


def _goto_lemma(s: S, lemma: str) -> None:
    _push(s, {"kind": "paradigm", "lemma": lemma})
    s.word = {"surface": lemma, "lemma": lemma, "gramm": "", "feats": {}}
    show_paradigm(s, lemma)


# ── paradigm display ──────────────────────────────────────────────────────────

def show_paradigm(s: S, lemma: str) -> None:
    corpus = s.corpus
    pd     = corpus.paradigms().get(lemma, {})
    gramm  = pd.get("gramm", [])
    sc     = pd.get("stem_class", "")
    total  = sum(f["count"] for f in pd.get("forms", []))
    print(f"\n{b(lemma)}  {d('  ·  '.join(p for p in [sc]+gramm if p))}  {d(str(total)+' tokens')}")
    print(f"  {RULE}")

    forms = pd.get("forms", [])
    idx: dict = defaultdict(list)

    if "root" in gramm or "verb" in gramm:
        for f in forms:
            ft = f["features"]
            key = (ft.get("tense",""), ft.get("mood",""), ft.get("voice",""),
                   ft.get("person",""), ft.get("number",""))
            idx[key].append((f["surface"], f["count"]))
        seen: set = set()
        for t in corpus.TENSES:
            for m in corpus.MOODS:
                for v in corpus.VOICES:
                    if (t,m,v) in seen or not any(k[:3]==(t,m,v) for k in idx):
                        continue
                    seen.add((t,m,v))
                    label = " ".join(x for x in [corpus.T_NAME.get(t,t),
                                                  corpus.M_NAME.get(m,m),
                                                  corpus.V_NAME.get(v,v)] if x)
                    print(f"\n  {b(label)}")
                    nums = [n for n in corpus.NUMBERS
                            if any(k==(t,m,v,p,n) for k in idx for p in corpus.PERSONS)]
                    pers = [p for p in corpus.PERSONS
                            if any(k==(t,m,v,p,n) for k in idx for n in corpus.NUMBERS)]
                    cw = 24
                    print(f"  {'':6}" + "".join(f"  {n:<{cw}}" for n in nums))
                    for p in pers:
                        row = f"  {p or '?':<6}"
                        for n in nums:
                            es   = idx.get((t,m,v,p,n), [])
                            cell = " / ".join(
                                s for s,_ in sorted(es, key=lambda x: -x[1])[:2]
                            ) if es else "—"
                            row += f"  {cell:<{cw}}"
                        print(row)

    elif gramm and "invariable" not in gramm:
        for f in forms:
            ft = f["features"]
            idx[(ft.get("case",""), ft.get("number",""), ft.get("gender",""))].append(
                (f["surface"], f["count"]))
        nums = [n for n in corpus.NUMBERS if any(k[1]==n for k in idx)]
        cw   = 22
        print(f"\n  {'':8}" + "".join(f"  {n:<{cw}}" for n in nums))
        print(f"  {RULE}")
        for case in corpus.CASES:
            if not any(k[0]==case for k in idx):
                continue
            row = f"  {case or '(other)':<8}"
            for n in nums:
                m2 = []
                for gg in corpus.GENDERS:
                    m2.extend(idx.get((case, n, gg), []))
                cell = " / ".join(
                    (f"{sf}({c})" if c > 1 else sf)
                    for sf, c in sorted(m2, key=lambda x: -x[1])[:2]
                ) if m2 else "—"
                row += f"  {cell:<{cw}}"
            print(row)

    else:
        for f in forms[:30]:
            print(f"  {f['surface']:<22} {d(str(f['count']))}")
    print()


# ── concordance display ───────────────────────────────────────────────────────

def show_concordance(s: S, lemma: str, surface: str | None = None) -> list:
    corpus = s.corpus
    rows   = corpus.concordance().get(lemma, [])
    if surface:
        rows  = [r for r in rows if r["surface"] == surface]
        title = (f"{hl(surface)}  {d('(< '+lemma+')')}  ·  "
                 f"{b(str(len(rows)))} occurrences  {d('lem = all forms')}")
    else:
        title = f"{b('lemma '+lemma)}  ·  {b(str(len(rows)))} occurrences"
    rows = sorted(rows, key=lambda r: corpus.ref_sort_key(r["ref"]))
    print(f"\n  {title}\n")
    col = max((len(r["ref"]) for r in rows), default=5) + 1
    for i, r in enumerate(rows, 1):
        pada = r.get("pada", "").strip()
        pada_col = f"  {pada}" if pada else ""
        print(f"  {i:>4}.  {d(r['ref']):<{col+8}}{pada_col}   {hl(r['surface']):<24}  {r['text']}")
    print()
    return rows


# ── gravity / look ────────────────────────────────────────────────────────────

def show_look(s: S, lemma: str, n: int = 10) -> None:
    nbrs = s.corpus.gravity().get(lemma, [])
    if not nbrs:
        print(f"  no gravity data for {lemma}  (run build_gravity.py first)")
        return
    nbrs   = nbrs[:n]
    max_sc = nbrs[0]["s"] or 1
    print(f"\n  {b(lemma)}  —  nearest {len(nbrs)}\n")
    for i, e in enumerate(nbrs, 1):
        bw  = min(20, max(1, int(e["s"] / max_sc * 20)))
        bar = "▏" * bw + " " * (20 - bw)
        print(f"  {i:>3}.  {d(bar)}  {b(e['n']):<32}  "
              + d(f"v={e['v']} p={e['p']} m={e['m']}"))
    print()
    s.last_list = [lambda s, l=e["n"]: _goto_lemma(s, l) for e in nbrs]


# ── stem browser ──────────────────────────────────────────────────────────────

def _stem_classes(paradigms_dict: dict) -> list[tuple[str, list[str]]]:
    """Return [(class_name, [lemma, ...]), ...] sorted by lemma count desc."""
    buckets: dict[str, list[str]] = defaultdict(list)
    for lemma, pd in paradigms_dict.items():
        sc    = pd.get("stem_class", "")
        gramm = pd.get("gramm", [])
        if sc:
            buckets[sc].append(lemma)
        elif "root" in gramm or "verb" in gramm:
            buckets["root (verb)"].append(lemma)
        elif "invariable" in gramm:
            buckets["particle"].append(lemma)
        elif "pronoun" in gramm:
            buckets["pronoun"].append(lemma)
        else:
            buckets["other"].append(lemma)
    return sorted(buckets.items(), key=lambda x: -len(x[1]))


def show_stems(s: S, arg: str = "") -> None:
    all_pars = s.corpus.paradigms()
    N_SHOW   = 40

    if not arg:
        classes = _stem_classes(all_pars)
        print(f"\n  {b('stem classes')}\n")
        print(f"  {'':>4}  {'class':<22}  {'lemmata':>7}  {'max forms':>9}  {'median':>6}")
        print(f"  {'─'*4}  {'─'*22}  {'─'*7}  {'─'*9}  {'─'*6}")
        actions = []
        for i, (sc, lemmata) in enumerate(classes, 1):
            fc = sorted([len(all_pars[l].get("forms", [])) for l in lemmata], reverse=True)
            median_fc = fc[len(fc) // 2]
            print(f"  {i:>4}.  {b(sc):<{22+len(b(''))}}  {len(lemmata):>7}  "
                  f"{fc[0]:>9}  {d(str(median_fc)):>{6+len(d(''))}}")
            actions.append(lambda s, sc=sc: show_stems(s, sc))
        print()
        s.last_list = actions
        return

    lemmata = []
    for lemma, pd in all_pars.items():
        sc    = pd.get("stem_class", "")
        gramm = pd.get("gramm", [])
        match = (sc == arg
                 or (arg == "root (verb)"  and ("root" in gramm or "verb" in gramm) and not sc)
                 or (arg == "particle"     and "invariable" in gramm and not sc)
                 or (arg == "pronoun"      and "pronoun" in gramm and not sc)
                 or (arg == "other"        and not sc
                     and not any(g in gramm for g in ("root","verb","invariable","pronoun"))))
        if match:
            n_forms = len(pd.get("forms", []))
            tokens  = sum(f["count"] for f in pd.get("forms", []))
            lemmata.append((lemma, n_forms, tokens))

    lemmata.sort(key=lambda x: (-x[1], -x[2]))
    total  = len(lemmata)
    shown  = lemmata[:N_SHOW]
    max_fc = shown[0][1] if shown else 1

    print(f"\n  {b(arg)}  ·  {total} lemmata  ·  sorted by attested forms\n")
    col = 28
    for i, (lemma, n_forms, tokens) in enumerate(shown, 1):
        bw  = max(1, round(n_forms / max_fc * 14))
        bar = "█" * bw + d("░" * (14 - bw))
        print(f"  {i:>4}.  {b(lemma):<{col+len(b(''))}}  {bar}  "
              f"{n_forms:>3} forms  {d(str(tokens)+' tkn')}")
    if total > N_SHOW:
        print(d(f"\n  … {total - N_SHOW} more (showing top {N_SHOW})"))
    print()
    s.last_list = [lambda s, l=lemma: _goto_lemma(s, l) for lemma, _, _ in shown]


# ── inventory ─────────────────────────────────────────────────────────────────

def load_inventory(s: S) -> None:
    p = s.corpus.inv_file
    if p.exists():
        try:
            s.inventory = json.loads(p.read_text())
            if s.inventory:
                print(d(f"  inventory loaded ({len(s.inventory)} items — type inv to see)"))
        except Exception:
            pass


def save_inventory(s: S) -> None:
    if s.inventory:
        s.corpus.inv_file.write_text(
            json.dumps(s.inventory, ensure_ascii=False, indent=2)
        )
