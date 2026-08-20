#!/usr/bin/env python3
"""altdeutsch — Referenzkorpus Altdeutsch explorer

  Navigation
    groups            list dialect / scribal-school groups
    alem              open a group (works in it)
    Isidor            open a work (sections)
    Isidor.2          open a section (verses)
    Isidor.2.5        go to a verse
    n / p             next / previous verse
    back / b          previous place in history

  At a verse
    x             show word table
    3             select word 3
    par           paradigm (a place)
    conc          concordance for this form (a place)
    lem           concordance for whole lemma (a place)
    def           dictionary entry (a place)
    look          nearby lemmata (gravity field)  ·  look 20 for more

  Inventory
    keep <name>   save current place (name optional → inv1, inv2…)
    drop <name>   remove from inventory
    go <name>     navigate to saved place
    inv           list inventory

  Search
    find quedan   fuzzy lemma search

  q             quit
"""

import sys, re, json, csv
from pathlib import Path
from collections import defaultdict

from explorer import (
    Corpus, S as BaseS,
    b, d, hl, RULE,
    _norm, _push, _goto_lemma,
    show_paradigm, show_concordance, show_stems, show_look,
    load_inventory, save_inventory,
    _wrap, set_wrap_width,
)

try:
    import readline
    readline.parse_and_bind("tab: complete")
    readline.set_history_length(1000)
except ImportError:
    pass

BASE   = Path(__file__).parent
AD_DIR = BASE / "corpus/altdeutsch"


# ── roman numerals / natural ordering ───────────────────────────────────────

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman_to_int(s: str) -> int | None:
    s = s.upper()
    if not s or any(ch not in _ROMAN_VALUES for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VALUES[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


def _part_key(s: str):
    """Sort key for one ref segment: bridge verses (s1, s2, ...) first,
    then numeric/roman values in natural order, then everything else
    (filename-derived section ids) alphabetically."""
    if s.startswith("s") and s[1:].isdigit():
        return (0, int(s[1:]), "")
    if s.isdigit():
        return (1, int(s), "")
    r = _roman_to_int(s)
    if r is not None:
        return (1, r, "")
    return (2, 0, s)


# ── corpus ───────────────────────────────────────────────────────────────────

class AltdeutschCorpus(Corpus):
    CASES   = ["NOM", "ACC", "DAT", "GEN", "ABL", "VOC", ""]
    NUMBERS = ["SG", "PL", "DU"]
    GENDERS = ["M", "F", "N", ""]
    TENSES  = ["PRS", "PST", "PRF", ""]
    MOODS   = ["IND", "SUBJ", "IMP", "INF", ""]
    VOICES  = ["ACT", "DEP", ""]
    PERSONS = ["1", "2", "3", ""]
    T_NAME  = {"PRS": "present", "PST": "past", "PRF": "perfect", "": ""}
    M_NAME  = {"IND": "indicative", "SUBJ": "subjunctive", "IMP": "imperative",
               "INF": "infinitive", "": ""}
    V_NAME  = {"ACT": "active", "DEP": "deponent", "": ""}

    def __init__(self):
        super().__init__(AD_DIR, inv_file=Path.home() / ".altdeutsch_inventory.json")
        self._vi: dict | None = None
        self._vd: dict | None = None
        self._wk: dict | None = None

    def works(self) -> dict:
        if self._wk is None:
            self._wk = json.loads((AD_DIR / "works.json").read_text())
        return self._wk

    def verse_rows(self) -> dict:
        if self._vd is None:
            vd: dict = {}
            with open(AD_DIR / "verses.tsv") as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    vd[row["ref"]] = row
            self._vd = vd
        return self._vd

    def verse_tokens(self) -> dict:
        if self._vi is None:
            vi: dict = defaultdict(list)
            with open(AD_DIR / "tokens.tsv") as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    vi[row["ref"]].append(row)
            self._vi = dict(vi)
        return self._vi

    def ref_sort_key(self, ref: str):
        parts = ref.split(".")
        work = parts[0]
        section = parts[1] if len(parts) > 1 else ""
        verse = parts[2] if len(parts) > 2 else ""
        return (work, _part_key(section), _part_key(verse))

    def section_refs(self, work: str, section: str) -> list[str]:
        """All verse refs for a work + section, in natural reading order
        (verse ids aren't reliably sortable — roman numerals, bridge ids,
        filename fallbacks — so we preserve source row order instead)."""
        prefix = f"{work}.{section}."
        return [ref for ref in self.verse_rows() if ref.startswith(prefix)]

    def adjacent_section(self, work: str, section: str, delta: int) -> str | None:
        """The next/previous section id in works.json's stored order
        (already chronological/numeric-aware — see _section_sort_key in
        build_altdeutsch.py), or None past either end."""
        sections = self.works().get("works", {}).get(work, {}).get("sections", [])
        try:
            i = sections.index(section)
        except ValueError:
            return None
        j = i + delta
        return sections[j] if 0 <= j < len(sections) else None

    def adjacent_verse_ref(self, ref: str, delta: int) -> str | None:
        """The next/previous verse ref, crossing into the adjacent section
        of the same work at a section boundary. None past the last/first
        verse of the whole work."""
        work, section = ref.split(".")[0], ref.split(".")[1]
        refs = self.section_refs(work, section)
        try:
            i = refs.index(ref)
        except ValueError:
            return None
        j = i + delta
        if 0 <= j < len(refs):
            return refs[j]
        nxt = self.adjacent_section(work, section, delta)
        if nxt is None:
            return None
        nxt_refs = self.section_refs(work, nxt)
        if not nxt_refs:
            return None
        return nxt_refs[0] if delta > 0 else nxt_refs[-1]


_CORPUS = AltdeutschCorpus()


# ── session ────────────────────────────────────────────────────────────────────

class S(BaseS):
    def __init__(self):
        super().__init__(_CORPUS)
        self.group:   str  = ""
        self.work:    str  = ""
        self.section: str  = ""
        self.refs:    list = []
        self.idx:     int  = -1
        self.words:   list = []

    @property
    def ref(self) -> str | None:
        return self.refs[self.idx] if 0 <= self.idx < len(self.refs) else None


# ── display ────────────────────────────────────────────────────────────────────

def show_verse(s: S) -> None:
    ref  = s.ref
    row  = _CORPUS.verse_rows().get(ref, {})
    text = row.get("text", "")
    print(f"\n{b(ref)}\n")
    print(_wrap(text))
    par = row.get("parallel", "").strip()
    if par:
        import textwrap as _tw
        from explorer import WRAP_WIDTH
        prefix_vis = 8
        cont_ind   = " " * prefix_vis
        parts      = _tw.wrap(par, width=max(20, WRAP_WIDTH - prefix_vis)) or [par]
        print()
        print(f"  {d('[lat]')}  {parts[0]}")
        for part in parts[1:]:
            print(f"  {cont_ind}{part}")
    print()


def show_words(words: list) -> None:
    if not words:
        return
    cw = max(len(w["surface"]) for w in words) + 2
    cl = max((len(w["lemma"]) for w in words if w["lemma"]), default=4) + 2
    print()
    for i, w in enumerate(words, 1):
        try:
            feats = json.loads(w["features"]) if w.get("features", "").strip() else {}
        except Exception:
            feats = {}
        feat = "  ".join(f"{k}={v}" for k, v in feats.items())
        sc   = w.get("stem_class", "")
        tag  = f"  {d('(' + sc + ')')}" if sc else ""
        print(f"  {d(str(i)):>5}  {w['surface']:<{cw}} {d(w['lemma'] or '?'):<{cl+6}}{tag}  {feat}")
    print()


def _loc_str(loc: dict) -> str:
    k = loc.get("kind", "?")
    if k == "group":      return f"Altdeutsch {loc['group']}"
    if k == "work":       return f"Altdeutsch {loc['work']}"
    if k == "section":    return f"Altdeutsch {loc['work']}.{loc['section']}"
    if k == "verse":      return f"Altdeutsch {loc['ref']}"
    if k == "word":       return f"Altdeutsch {loc['ref']} [{loc.get('lemma', '')}]"
    if k == "paradigm":   return f"par: {loc['lemma']}"
    if k == "concordance":
        sf = loc.get("surface"); l = loc["lemma"]
        return f"conc: {sf} (< {l})" if sf else f"conc: {l}"
    if k == "dict":       return f"def: {loc['lemma']}"
    return str(loc)


# ── navigation ─────────────────────────────────────────────────────────────────

def go_index(s: S) -> None:
    wk     = _CORPUS.works()
    groups = wk.get("groups", [])
    works  = wk.get("works", {})
    counts: dict[str, int] = defaultdict(int)
    for w in works.values():
        counts[w["group"]] += 1
    print(f"\n  {b('Referenzkorpus Altdeutsch')}  ·  {len(works)} works  ·  {len(groups)} groups\n")
    actions = []
    for g in groups:
        n = counts.get(g["key"], 0)
        if not n:
            continue
        rank = len(actions) + 1
        print(f"  {rank:>3}.  {b(g['key']):<{6+len(b(''))}}  {g['label']:<40}  {d(str(n)+' works')}")
        actions.append(lambda s, gk=g["key"]: go_group(s, gk))
    print()
    s.last_list = actions


def format_time(time_str: str) -> str:
    """A rough, human-legible century label for list views — '9. Jh.'
    rather than the raw source field ('9.1', '8-9', 'M: 9.2; C: 10.2',
    ...), which otherwise reads as a bare, unexplained number next to a
    section count. Approximate by design, like the dating itself (see
    parse_time in build_altdeutsch.py) — the half-century/manuscript
    detail is dropped here, still visible on the work's own page."""
    centuries = sorted({int(c) for c in re.findall(r"(\d+)(?:\.\d)?", time_str or "")})
    if not centuries:
        return ""
    if len(centuries) == 1:
        return f"{centuries[0]}. Jh."
    return f"{centuries[0]}.–{centuries[-1]}. Jh."


def _work_sort_key(w: dict):
    """Chronological where a date is known (approximate — see time_sort in
    build_altdeutsch.py), undated works last, alphabetical within either."""
    ts = w.get("time_sort")
    return (0, ts, w["title"]) if ts is not None else (1, 0.0, w["title"])


def go_group(s: S, key: str) -> None:
    wk     = _CORPUS.works()
    groups = {g["key"]: g["label"] for g in wk.get("groups", [])}
    if key not in groups:
        print(f"  unknown group: {key}")
        return
    _push(s, {"kind": "group", "group": key})
    s.group = key
    works = {wid: w for wid, w in wk.get("works", {}).items() if w["group"] == key}
    print(f"\n{b(key)}  {d(groups[key])}  ·  {len(works)} works\n")
    actions = []
    for wid, w in sorted(works.items(), key=lambda kv: _work_sort_key(kv[1])):
        n_sec = len(w.get("sections", []))
        rank  = len(actions) + 1
        title = w["title"]
        time  = format_time(w.get("time", ""))
        tag   = f"{n_sec} sections" if n_sec > 1 else ""
        print(f"  {rank:>3}.  {b(wid):<{20+len(b(''))}}  {title:<38}  {hl(time):<10}  {d(tag)}")
        actions.append(lambda s, wid=wid: go_work(s, wid))
    print()
    s.last_list = actions


def go_work(s: S, work_id: str) -> None:
    wk = _CORPUS.works()
    w  = wk.get("works", {}).get(work_id)
    if w is None:
        print(f"  unknown work: {work_id}")
        return
    sections = w.get("sections", [])
    if len(sections) == 1:          # nothing to choose — go straight in
        go_section(s, work_id, sections[0])
        return
    _push(s, {"kind": "work", "work": work_id})
    s.group, s.work = w["group"], work_id
    meta = "  ·  ".join(x for x in [w.get("form", ""), w.get("depository", ""), w.get("time", "")] if x)
    print(f"\n{b(work_id)}  {d(w['title'])}")
    if meta:
        print(f"  {d(meta)}")
    print()
    actions = []
    for sec in sections:
        n_v  = len(_CORPUS.section_refs(work_id, sec))
        rank = len(actions) + 1
        print(f"  {rank:>4}.  {b(f'{work_id}.{sec}'):<{28+len(b(''))}}  {d(str(n_v)+' verses')}")
        actions.append(lambda s, sec=sec: go_section(s, work_id, sec))
    print()
    s.last_list = actions


def go_section(s: S, work_id: str, section: str) -> None:
    refs = _CORPUS.section_refs(work_id, section)
    if not refs:
        print(f"  no verses found for {work_id}.{section}")
        return
    _push(s, {"kind": "section", "work": work_id, "section": section})
    s.work, s.section, s.refs, s.idx = work_id, section, refs, -1
    s.words, s.word = [], None
    print(f"\n{b(f'{work_id}.{section}')}  {d(str(len(refs))+' verses')}\n")
    for i, ref in enumerate(refs, 1):
        tail = ref.rsplit(".", 1)[-1]
        print(f"  {b(str(i)+'.'):<5} {d(tail)}")
        print(_wrap(_CORPUS.verse_rows().get(ref, {}).get("text", ""), indent="    "))
        print()
    print(d("  type a verse number (e.g. 3), or n to step through"))
    s.last_list = [lambda s, i=i: go_verse(s, i) for i in range(len(refs))]


def go_verse(s: S, idx: int, _push_loc: bool = True) -> None:
    s.idx   = idx
    s.words = _CORPUS.verse_tokens().get(s.ref, [])
    s.word  = None
    s.last_list = []
    loc = {"kind": "verse", "ref": s.ref}
    if _push_loc: _push(s, loc)
    else: s.cur_loc = loc
    show_verse(s)
    print(d(f"  {len(s.words)} words  ·  x to expand  ·  n/p next/prev"))


def step_verse(s: S, delta: int) -> None:
    """Move to the next/previous verse, crossing into the adjacent
    section of the same work at a section boundary (e.g. Monseer
    Fragmente I -> II) rather than stopping there."""
    new_idx = s.idx + delta
    if 0 <= new_idx < len(s.refs):
        go_verse(s, new_idx)
        return
    nxt_section = _CORPUS.adjacent_section(s.work, s.section, delta)
    if nxt_section is None:
        print("  beginning of work" if delta < 0 else "  end of work")
        return
    refs = _CORPUS.section_refs(s.work, nxt_section)
    if not refs:
        print("  beginning of work" if delta < 0 else "  end of work")
        return
    s.section, s.refs = nxt_section, refs
    go_verse(s, 0 if delta > 0 else len(refs) - 1)


def pick_word(s: S, n: int, _push_loc: bool = True) -> None:
    if not (1 <= n <= len(s.words)):
        print(f"  word {n} out of range (1–{len(s.words)})")
        return
    tok = s.words[n-1]
    s.word = {
        "surface": tok["surface"],
        "lemma":   tok["lemma"],
        "gramm":   tok.get("pos", ""),
        "feats":   json.loads(tok["features"]) if tok.get("features", "").strip() else {},
    }
    try:
        feats = json.loads(tok["features"]) if tok.get("features", "").strip() else {}
    except Exception:
        feats = {}
    loc = {"kind": "word", "ref": s.ref, "word_num": n,
           "lemma": tok["lemma"], "surface": tok["surface"]}
    if _push_loc: _push(s, loc)
    else: s.cur_loc = loc
    feat  = "  ".join(f"{k}={v}" for k, v in feats.items())
    pd    = _CORPUS.paradigms().get(tok["lemma"], {})
    total = sum(f["count"] for f in pd.get("forms", []))
    sc    = tok.get("stem_class", "") or pd.get("stem_class", "")
    print(f"\n  {hl(tok['surface'])}  →  {b(tok['lemma'] or '?')}"
          + (f"  {d('('+sc+')')}" if sc else "")
          + (f"  ·  {d(feat)}" if feat else "")
          + f"  ·  {d(str(total)+' tokens')}")
    print(d("  par · conc · lem · def · look"))
    nbrs = _CORPUS.gravity().get(tok["lemma"], [])[:6]
    if nbrs:
        items = "  ".join(f"{d(str(i)+'.')} {b(e['n'])}" for i, e in enumerate(nbrs, 1))
        print(f"  {d('nearby:')}  {items}")
        s.last_list = [lambda s, l=e["n"]: _goto_lemma(s, l) for e in nbrs]
    else:
        s.last_list = []


def goto_location(s: S, loc: dict) -> None:
    k = loc.get("kind")
    if k == "group":
        go_group(s, loc["group"])
    elif k == "work":
        go_work(s, loc["work"])
    elif k == "section":
        go_section(s, loc["work"], loc["section"])
    elif k == "verse":
        ref = loc["ref"]
        parts = ref.split(".")
        wid, sec = parts[0], parts[1]
        if wid != s.work or sec != s.section:
            refs = _CORPUS.section_refs(wid, sec)
            s.work, s.section, s.refs = wid, sec, refs
        idx = next((i for i, r in enumerate(s.refs) if r == ref), None)
        if idx is not None:
            go_verse(s, idx, _push_loc=False)
    elif k == "word":
        goto_location(s, {"kind": "verse", "ref": loc["ref"]})
        pick_word(s, loc["word_num"], _push_loc=False)
    elif k == "paradigm":
        show_paradigm(s, loc["lemma"])
        s.word = {"surface": loc["lemma"], "lemma": loc["lemma"], "gramm": "", "feats": {}}
        s.cur_loc = loc
    elif k == "concordance":
        rows = show_concordance(s, loc["lemma"], loc.get("surface"))
        s.cur_loc = loc
        s.last_list = [lambda s, ref=r["ref"]: goto_location(s, {"kind": "verse", "ref": ref})
                       for r in rows]
    elif k == "dict":
        show_def(s, loc.get("lemma", ""))


# ── lexicon ────────────────────────────────────────────────────────────────────

_LEX: dict | None = None


def _lex() -> dict:
    global _LEX
    if _LEX is None:
        _LEX = json.loads((AD_DIR / "lexicon.json").read_text())
    return _LEX


def show_def(s: S, lemma: str) -> None:
    lex = _lex()
    entry = lex.get(lemma)
    if entry is None:
        results = _CORPUS.search(lemma, n=1)
        if results:
            lemma = results[0][0]
            entry = lex.get(lemma)
    if entry is None:
        print(f"  no dictionary entry for {lemma!r}")
        return

    _push(s, {"kind": "dict", "lemma": lemma})
    s.cur_loc["lemma"] = lemma
    s.word = {"surface": lemma, "lemma": lemma, "gramm": entry.get("pos", ""), "feats": {}}

    sc    = entry.get("stem_class", "")
    pos   = entry.get("pos", "")
    gloss = entry.get("gloss_de", "")
    pd    = _CORPUS.paradigms().get(lemma, {})
    total = sum(f["count"] for f in pd.get("forms", []))
    tok_str = f"  ·  {d(str(total)+' tokens')}" if total else ""

    tag = "  ·  ".join(x for x in [pos, sc] if x)
    print(f"\n{b(lemma)}  {d(tag)}{tok_str}")
    if gloss: print(f"  {d('[de]')}  {gloss}")
    print()

    nbrs = _CORPUS.gravity().get(lemma, [])[:10]
    if nbrs:
        print(f"  {d('nearby:')}")
        half = (len(nbrs) + 1) // 2
        col  = 36
        for i in range(half):
            la = f"  {i+1:>3}.  {b(nbrs[i]['n'])}"
            if i + half < len(nbrs):
                ri = i + half + 1
                ra = f"  {ri:>3}.  {b(nbrs[i+half]['n'])}"
                print(f"{la:<{col}}{ra}")
            else:
                print(la)
        print()
        s.last_list = [lambda s, l=e["n"]: _goto_lemma(s, l) for e in nbrs]
    else:
        s.last_list = []


# ── ref parsing ────────────────────────────────────────────────────────────────

# Several works have short (1-2 letter) sigla — C, H, L, P, W, ... — that
# collide with this REPL's own single-letter shortcuts (p = previous verse,
# w = word table, l = lemma concordance, c = concordance, h = help). A bare
# command exactly matching one of these must stay a shortcut, never a work
# lookup, or e.g. 'p' would silently teleport to the work "P" (Petruslied)
# instead of stepping back a verse. Ref-like commands (anything with a dot,
# e.g. 'P.1') are unaffected — those can never collide with a bare verb.
_RESERVED_VERBS = {
    "q", "quit", "exit", "groups", "index", "toc", "works",
    "n", "next", "p", "prev", "previous", "r", "read",
    "x", "expand", "words", "w",
    "par", "paradigm", "conc", "concordance", "c", "lem", "lemma", "l",
    "def", "dict", "look", "stems", "stem", "sc",
    "back", "b", "keep", "k", "bookmark", "save", "load",
    "drop", "remove", "del", "delete", "go", "visit", "inv", "inventory", "i",
    "find", "search", "f", "help", "h", "?",
}


def _parse_ref(cmd: str) -> tuple[str, str, str] | None:
    """'Isidor.2.5' → ('Isidor','2','5')  ·  'Isidor.2' → ('Isidor','2','')  ·  'Isidor' → ('Isidor','','')"""
    parts = cmd.split(".")
    if len(parts) == 1 and parts[0].lower() in _RESERVED_VERBS:
        return None
    wk_map  = {w.lower(): w for w in _CORPUS.works().get("works", {})}
    work_id = wk_map.get(parts[0].lower())
    if work_id is None:
        return None
    sections = _CORPUS.works()["works"][work_id].get("sections", [])
    sec_map  = {sec.lower(): sec for sec in sections}
    section  = sec_map.get(parts[1].lower(), parts[1]) if len(parts) > 1 and parts[1] else ""
    verse    = parts[2] if len(parts) > 2 else ""
    return work_id, section, verse


GROUP_KEYS = {g[0] for g in [
    ("as",), ("anfrk",), ("bair",), ("alem",), ("ofrk",), ("srhfrk",), ("rhfrk",), ("mfrk",), ("unloc",),
]}


# ── REPL ───────────────────────────────────────────────────────────────────────

def handle(cmd: str, s: S) -> bool:
    cmd = cmd.strip()
    if not cmd: return True

    if cmd.lower() in GROUP_KEYS:
        go_group(s, cmd.lower())
        return True

    parsed = _parse_ref(cmd)
    if parsed:
        wid, sec, vs = parsed
        if vs:
            refs = _CORPUS.section_refs(wid, sec)
            idx  = next((i for i, r in enumerate(refs) if r == f"{wid}.{sec}.{vs}"), None)
            if idx is not None:
                s.work, s.section, s.refs = wid, sec, refs
                go_verse(s, idx)
            else:
                print(f"  verse {wid}.{sec}.{vs} not found")
        elif sec:
            go_section(s, wid, sec)
        else:
            go_work(s, wid)
        return True

    if cmd.isdigit():
        n = int(cmd)
        if s.last_list:
            if 1 <= n <= len(s.last_list):
                s.last_list[n-1](s)
            else:
                print(f"  {n} out of range (1–{len(s.last_list)})")
        elif s.ref:
            print(d("  type x to expand words, then a number to select"))
        else:
            go_index(s)
        return True

    tok  = cmd.split(None, 1)
    verb = tok[0].lower()
    rest = tok[1] if len(tok) > 1 else ""

    if verb in ("q", "quit", "exit"): return False

    elif verb in ("groups", "index", "toc", "works"):
        go_index(s)

    elif verb in ("n", "next"):
        step_verse(s, +1)

    elif verb in ("p", "prev", "previous"):
        step_verse(s, -1)

    elif verb in ("r", "read"):
        if s.ref: show_verse(s)
        else: print("  no verse open")

    elif verb in ("x", "expand", "words", "w"):
        if s.words:
            show_words(s.words)
            s.last_list = [lambda s, n=n: pick_word(s, n) for n in range(1, len(s.words)+1)]
            print(d(f"  type a number to select a word (1–{len(s.words)})"))
        elif s.ref:
            s.words = _CORPUS.verse_tokens().get(s.ref, [])
            if s.words:
                show_words(s.words)
                s.last_list = [lambda s, n=n: pick_word(s, n) for n in range(1, len(s.words)+1)]
                print(d(f"  type a number to select a word (1–{len(s.words)})"))
        else:
            print("  no verse open — navigate to one first")

    elif verb.isdigit() or (verb == "w" and rest.isdigit()):
        n = int(rest if verb == "w" else verb)
        if s.ref: pick_word(s, n)
        else: print("  no verse open")

    elif verb in ("par", "paradigm"):
        if s.word:
            _push(s, {"kind": "paradigm", "lemma": s.word["lemma"]})
            show_paradigm(s, s.word["lemma"])
        else: print("  select a word first (x, then a number)")

    elif verb in ("conc", "concordance", "c"):
        if s.word:
            _push(s, {"kind": "concordance", "lemma": s.word["lemma"], "surface": s.word["surface"]})
            rows = show_concordance(s, s.word["lemma"], s.word["surface"])
            s.last_list = [lambda s, ref=r["ref"]:
                           goto_location(s, {"kind": "verse", "ref": ref}) for r in rows]
        else: print("  select a word first")

    elif verb in ("lem", "lemma", "l"):
        if s.word:
            _push(s, {"kind": "concordance", "lemma": s.word["lemma"]})
            rows = show_concordance(s, s.word["lemma"])
            s.last_list = [lambda s, ref=r["ref"]:
                           goto_location(s, {"kind": "verse", "ref": ref}) for r in rows]
        else: print("  select a word first")

    elif verb in ("def", "dict"):
        target = rest or (s.word["lemma"] if s.word else None)
        if not target: print("  select a word first, or: def quedan")
        else: show_def(s, target)

    elif verb in ("look",):
        n_show = int(rest) if rest.isdigit() else 10
        lemma  = (None if rest.isdigit() else rest) or (s.word["lemma"] if s.word else None)
        if not lemma: print("  select a word first, or: look quedan  /  look 20")
        else: show_look(s, lemma, n_show)

    elif verb in ("stems", "stem", "sc"):
        show_stems(s, rest)

    elif verb in ("back", "b"):
        if s.history:
            loc = s.history.pop()
            s.cur_loc = None
            goto_location(s, loc)
        else:
            print("  nothing to go back to")

    elif verb in ("keep", "k", "bookmark"):
        if not s.cur_loc: print("  nothing to save yet")
        else:
            if not rest:
                n = 1
                while f"inv{n}" in s.inventory: n += 1
                rest = f"inv{n}"
            s.inventory[rest] = s.cur_loc.copy()
            print(f"  saved: {b(rest)} → {_loc_str(s.cur_loc)}")

    elif verb in ("save",):
        save_inventory(s)
        print(f"  inventory saved ({len(s.inventory)} items → {s.corpus.inv_file})")

    elif verb in ("load",):
        load_inventory(s)

    elif verb in ("drop", "remove", "del", "delete"):
        if not rest: print("  usage: drop <name>")
        elif rest not in s.inventory: print(f"  {rest!r} not in inventory")
        else:
            del s.inventory[rest]
            print(f"  dropped: {rest}")

    elif verb in ("go", "visit"):
        if not rest: print("  usage: go <name>  (see: inv)")
        elif rest not in s.inventory: print(f"  {rest!r} not in inventory  (see: inv)")
        else: goto_location(s, s.inventory[rest])

    elif verb in ("inv", "inventory", "i"):
        if not s.inventory:
            print("  inventory is empty  (use: keep <name>)")
        else:
            print()
            for name, loc in s.inventory.items():
                print(f"  {b(name):<24}  {_loc_str(loc)}")
            print()

    elif verb in ("find", "search", "f"):
        if not rest: print("  usage: find <query>"); return True
        results = s.corpus.search(rest)
        if not results:
            print(f"  nothing found for {rest!r}")
        else:
            print()
            for i, (l, pd) in enumerate(results, 1):
                sc    = pd.get("stem_class", "")
                gramm = "/".join(pd.get("gramm", []))
                total = sum(f["count"] for f in pd.get("forms", []))
                tag   = gramm + (f" {sc}" if sc else "")
                print(f"  {i:>3}.  {b(l):<32} {d(tag):<28} {total} tokens")
            print()
            s.last_list = [lambda s, l=l: _goto_lemma(s, l) for l, _ in results]

    elif verb in ("help", "h", "?"):
        print(__doc__)

    else:
        results = s.corpus.search(cmd)
        if results and _norm(results[0][0]) == _norm(cmd):
            _goto_lemma(s, results[0][0])
        elif results:
            print(f"\n  did you mean:")
            for i, (l2, pd2) in enumerate(results[:6], 1):
                total = sum(f["count"] for f in pd2.get("forms", []))
                print(f"  {i:>3}.  {b(l2):<32} {total} tokens")
            print()
            s.last_list = [lambda s, l=l: _goto_lemma(s, l) for l, _ in results[:6]]
        else:
            print(f"  {d(repr(cmd))} — unknown  (h for help)")

    return True


def main():
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--width" and i+1 < len(args) and args[i+1].isdigit():
            set_wrap_width(int(args[i+1]))
        elif a.startswith("--width=") and a[8:].isdigit():
            set_wrap_width(int(a[8:]))

    print(f"\n{b('Altdeutsch Explorer')}")
    print(d("  groups  to list dialects  ·  Isidor.2.5  to open a verse  ·  find quedan  to search\n"))
    s = S()
    load_inventory(s)
    tty = sys.stdout.isatty()
    while True:
        ref = s.ref or (f"{s.work}.{s.section}" if s.work else "")
        lm  = f" [{s.word['lemma']}]" if s.word else ""
        prompt = f"{d(ref+lm)} › " if tty else ""
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not handle(line, s):
            break
    save_inventory(s)


if __name__ == "__main__":
    main()
