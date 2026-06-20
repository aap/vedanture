#!/usr/bin/env python3
"""gothic — Gothic Bible explorer

  Navigation
    books         list all books
    Jn            open book (chapters)
    Jn.3          open chapter
    Jn.3.16       open verse
    n / p         next / previous verse
    back / b      previous place in history

  At a verse
    x             show word table
    3             select word 3
    par           paradigm (a place)
    conc          concordance for this form (a place)
    lem           concordance for whole lemma (a place)
    def           dictionary entry (a place)
    look          nearby lemmas (gravity field)  ·  look 20 for more
    stems         browse by stem formation  ·  stems a-stem for lemmata

  Inventory
    keep <name>   save current place (name optional → inv1, inv2…)
    drop <name>   remove from inventory
    go <name>     navigate to saved place
    inv           list inventory

  Search
    find wulfs    fuzzy lemma search

  q             quit
"""

import sys, json, csv
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

BASE        = Path(__file__).parent
GOTHIC_DIR  = BASE / "corpus/gothic"


# ── Gothic corpus ──────────────────────────────────────────────────────────────

class GothicCorpus(Corpus):
    CASES   = ["NOM","ACC","GEN","DAT","VOC","INS",""]
    NUMBERS = ["SG","PL","DU"]
    GENDERS = ["M","F","N",""]
    TENSES  = ["PRS","PST",""]
    MOODS   = ["IND","IMP","OPT",""]
    VOICES  = ["ACT","PASS",""]
    PERSONS = ["1","2","3",""]
    T_NAME  = {"PRS":"present","PST":"preterite","":""}
    M_NAME  = {"IND":"indicative","IMP":"imperative","OPT":"optative","":""}
    V_NAME  = {"ACT":"active","PASS":"passive","":""}

    def __init__(self):
        super().__init__(GOTHIC_DIR, inv_file=Path.home() / ".gothic_inventory.json")
        self._vi: dict | None = None   # ref → [token_row, ...]
        self._vd: dict | None = None   # ref → verse row
        self._bk: dict | None = None   # books.json

    def books(self) -> dict:
        if self._bk is None:
            self._bk = json.loads((GOTHIC_DIR / "books.json").read_text())
        return self._bk

    def verse_rows(self) -> dict:
        if self._vd is None:
            vd: dict = {}
            with open(GOTHIC_DIR / "verses.tsv") as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    vd[row["ref"]] = row
            self._vd = vd
        return self._vd

    def verse_tokens(self) -> dict:
        if self._vi is None:
            vi: dict = defaultdict(list)
            with open(GOTHIC_DIR / "tokens.tsv") as f:
                for row in csv.DictReader(f, delimiter="\t"):
                    vi[row["ref"]].append(row)
            self._vi = dict(vi)
        return self._vi

    def ref_sort_key(self, ref: str):
        order = self.books().get("order", [])
        parts = ref.split(".")
        book_idx = order.index(parts[0]) if parts[0] in order else 999
        try:
            return (book_idx, int(parts[1]), int(parts[2]))
        except (IndexError, ValueError):
            return (book_idx, 0, 0)

    def attested_chapters(self, book: str) -> list[int]:
        """Chapters that actually have verses in the corpus."""
        prefix = f"{book}."
        seen: set[int] = set()
        for ref in self.verse_rows():
            if ref.startswith(prefix):
                parts = ref.split(".")
                try:
                    seen.add(int(parts[1]))
                except (IndexError, ValueError):
                    pass
        return sorted(seen)

    def chapter_refs(self, book: str, chapter: int) -> list[str]:
        """All verse refs for a given book + chapter, in order."""
        prefix = f"{book}.{chapter}."
        all_refs = sorted(
            {ref for ref in self.verse_rows() if ref.startswith(prefix)},
            key=self.ref_sort_key,
        )
        return all_refs


_CORPUS = GothicCorpus()


# ── session ────────────────────────────────────────────────────────────────────

class S(BaseS):
    def __init__(self):
        super().__init__(_CORPUS)
        self.book:    str  = ""
        self.chapter: int  = 0
        self.refs:    list = []   # ordered refs for current chapter
        self.idx:     int  = -1
        self.words:   list = []   # token rows for current verse

    @property
    def ref(self) -> str | None:
        return self.refs[self.idx] if 0 <= self.idx < len(self.refs) else None


# ── display ────────────────────────────────────────────────────────────────────

def _verse_line(ref: str) -> str:
    row = _CORPUS.verse_rows().get(ref, {})
    return row.get("text", "")


def _annotated_verse_text(ref: str) -> str:
    """
    Verse text with secondary-MS variants marked:
      [word ...]  = word(s) present only in secondary MS (folio gap in primary)
      {a/b}       = word where the two MSS disagree (lex / spelling / form)
    Falls back to plain verse text when there is only one MS for the verse.
    """
    rows = _CORPUS.verse_tokens().get(ref, [])
    if not rows or "ms" not in rows[0]:
        return _verse_line(ref)

    ms_set     = sorted({r["ms"] for r in rows if r.get("ms")})
    primary_ms = ms_set[0] if ms_set else ""

    if len(ms_set) <= 1:
        return _verse_line(ref)

    # Primary word sequence, one surface per position
    prim_by_pos: dict = {}
    for r in rows:
        if r.get("ms") == primary_ms:
            pos = r.get("position", "0")
            if pos not in prim_by_pos:
                prim_by_pos[pos] = r["surface"]

    prim_seq = [prim_by_pos[p]
                for p in sorted(prim_by_pos,
                                key=lambda x: int(x) if x.isdigit() else 0)]
    n = len(prim_seq)

    # insertions[i] = words to show in [...] BEFORE prim_seq[i]; [n] = at end
    insertions: list = [[] for _ in range(n + 1)]
    overrides:  dict = {}   # i → '{a/b}' replacement for prim_seq[i]

    for sec_ms in ms_set[1:]:
        sec_by_pos: dict = {}
        for r in rows:
            if r.get("ms") == sec_ms:
                pos = r.get("position", "0")
                if pos not in sec_by_pos:
                    sec_by_pos[pos] = r

        sec_seq = sorted(sec_by_pos.values(),
                         key=lambda r: int(r.get("position","0"))
                         if r.get("position","0").isdigit() else 0)

        primary_idx = 0
        for r in sec_seq:
            var = r.get("variation", "0")
            if var == "1":
                primary_idx += 1
            elif var == "6":
                insertions[min(primary_idx, n)].append(r["surface"])
            elif var in ("2","3","4","8","9","10","11","12"):
                if primary_idx < n and primary_idx not in overrides:
                    overrides[primary_idx] = f"{{{prim_seq[primary_idx]}/{r['surface']}}}"
                primary_idx += 1
            # var=5 (different language), var=7 (punctuation only): skip

    parts: list[str] = []
    for i, word in enumerate(prim_seq):
        if insertions[i]:
            parts.append(f"[{' '.join(insertions[i])}]")
        parts.append(overrides.get(i, word))
    if insertions[n]:
        parts.append(f"[{' '.join(insertions[n])}]")

    return " ".join(parts)


def show_verse(s: S) -> None:
    ref  = s.ref
    text = _annotated_verse_text(ref)
    print(f"\n{b(ref)}\n")
    print(_wrap(text))
    trans = _CORPUS.verse_rows().get(ref, {}).get("translation", "").strip()
    if trans:
        import textwrap as _tw
        from explorer import WRAP_WIDTH
        prefix_vis = 7   # "  [en]  " visible
        cont_ind   = " " * prefix_vis
        parts      = _tw.wrap(trans, width=max(20, WRAP_WIDTH - prefix_vis)) or [trans]
        print()
        print(f"  {d('[en]')}  {parts[0]}")
        for part in parts[1:]:
            print(f"  {cont_ind}{part}")
    print()


def _merge_verse_tokens(rows: list) -> list:
    """
    Merge parallel manuscript tokens for display.
    Keeps all tokens from the primary (lowest-numbered) manuscript.
    From secondary manuscripts, only keeps tokens where variation != '1'
    (i.e. readings that differ from or are absent in the primary).
    Adds '_marker' to secondary tokens: '†' if missing from primary, else '[B]' etc.
    Falls back to simple dedup if no 'ms' column (old corpus format).
    """
    if not rows or 'ms' not in rows[0]:
        seen: set = set()
        out = []
        for r in rows:
            key = (r['surface'], r['lemma'], r.get('pos',''), r.get('features',''))
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

    ms_set     = sorted({r['ms'] for r in rows if r.get('ms')})
    primary_ms = ms_set[0] if ms_set else ''
    ms_label   = {m: chr(64 + i + 1) for i, m in enumerate(ms_set)}  # A, B, C...

    out = []
    for r in rows:
        ms  = r.get('ms', '')
        var = r.get('variation', '0')
        if ms == primary_ms:
            out.append(r)
        elif var != '1':
            row = dict(r)
            row['_marker'] = '†' if var == '6' else f"[{ms_label.get(ms,'?')}]"
            out.append(row)
    return out


def show_words(words: list) -> None:
    if not words: return
    cw = max(len(w["surface"]) for w in words) + 2
    cl = max((len(w["lemma"])  for w in words if w["lemma"]), default=4) + 2
    print()
    for i, w in enumerate(words, 1):
        try:
            feats = json.loads(w["features"]) if w.get("features","").strip() else {}
        except Exception:
            feats = {}
        feat   = "  ".join(f"{k}={v}" for k,v in feats.items())
        sc     = w.get("stem_class","")
        tag    = f"  {d('('+sc+')')}" if sc else ""
        marker = w.get('_marker', '')
        mktag  = f"  {d(marker)}" if marker else ""
        print(f"  {d(str(i)):>5}  {w['surface']:<{cw}} {d(w['lemma'] or '?'):<{cl+6}}{tag}{mktag}  {feat}")
    print()


def _loc_str(loc: dict) -> str:
    k = loc.get("kind","?")
    if k == "book":      return f"Gothic {loc['book']}"
    if k == "chapter":   return f"Gothic {loc['book']}.{loc['chapter']}"
    if k == "verse":     return f"Gothic {loc['ref']}"
    if k == "word":      return f"Gothic {loc['ref']} [{loc.get('lemma','')}]"
    if k == "paradigm":  return f"par: {loc['lemma']}"
    if k == "concordance":
        sf = loc.get("surface"); l = loc["lemma"]
        return f"conc: {sf} (< {l})" if sf else f"conc: {l}"
    if k == "dict":      return f"def: {loc['lemma']}"
    return str(loc)


# ── navigation ─────────────────────────────────────────────────────────────────

def go_index(s: S) -> None:
    bk    = _CORPUS.books()
    names = bk.get("names", {})
    order = bk.get("order", [])
    vrows = _CORPUS.verse_rows()
    from collections import Counter
    book_verses: Counter = Counter()
    for ref in vrows:
        book_verses[ref.split(".")[0]] += 1
    print(f"\n  {b('Gothic corpus')}  ·  {len(book_verses)} books\n")
    actions = []
    for book in order:
        if book not in book_verses:
            continue
        n_v   = book_verses[book]
        n_ch  = len(_CORPUS.attested_chapters(book))
        name  = names.get(book, book)
        rank  = len(actions) + 1
        print(f"  {rank:>3}.  {b(book):<{8+len(b(''))}}  {name:<28}  {d(str(n_ch)+' ch  '+str(n_v)+' v')}")
        actions.append(lambda s, bk=book: go_book(s, bk))
    print()
    s.last_list = actions


def go_book(s: S, book: str) -> None:
    bk    = _CORPUS.books()
    names = bk.get("names", {})
    chaps = bk.get("chapters", {})
    if book not in names:
        print(f"  unknown book: {book}")
        return
    _push(s, {"kind": "book", "book": book})
    s.book = book
    attested = _CORPUS.attested_chapters(book)
    n_total  = chaps.get(book, "?")
    frag_note = d(f"  ({len(attested)} of {n_total} chapters extant)") if attested else ""
    print(f"\n{b(book)}  {d(names.get(book, book))}{frag_note}\n")
    actions = []
    for ch in attested:
        refs = _CORPUS.chapter_refs(book, ch)
        rank = len(actions) + 1
        print(f"  {rank:>3}.  {b(f'{book}.{ch}'):<{12+len(b(''))}}  {d(str(len(refs))+' verses')}")
        actions.append(lambda s, bk=book, ch=ch: go_chapter(s, bk, ch))
    print()
    s.last_list = actions


def go_chapter(s: S, book: str, chapter: int) -> None:
    refs = _CORPUS.chapter_refs(book, chapter)
    if not refs:
        print(f"  no verses found for {book}.{chapter}")
        return
    _push(s, {"kind": "chapter", "book": book, "chapter": chapter})
    s.book, s.chapter, s.refs, s.idx = book, chapter, refs, -1
    s.words, s.word = [], None
    print(f"\n{b(f'{book}.{chapter}')}  {d(str(len(refs))+' verses')}\n")
    for ref in refs:
        print(f"  {b(ref)}")
        print(_wrap(_annotated_verse_text(ref), indent="    "))
        print()

    print(d("  type a verse number (e.g. 3), or n to step through"))
    s.last_list = [lambda s, i=i: go_verse(s, i) for i in range(len(refs))]


def go_verse(s: S, idx: int, _push_loc: bool = True) -> None:
    s.idx   = idx
    s.words = _merge_verse_tokens(_CORPUS.verse_tokens().get(s.ref, []))
    s.word  = None
    s.last_list = []
    loc = {"kind": "verse", "ref": s.ref}
    if _push_loc: _push(s, loc)
    else: s.cur_loc = loc
    show_verse(s)
    print(d(f"  {len(s.words)} words  ·  x to expand  ·  n/p next/prev"))


def pick_word(s: S, n: int, _push_loc: bool = True) -> None:
    if not (1 <= n <= len(s.words)):
        print(f"  word {n} out of range (1–{len(s.words)})")
        return
    tok = s.words[n-1]
    s.word = {
        "surface": tok["surface"],
        "lemma":   tok["lemma"],
        "gramm":   tok.get("pos",""),
        "feats":   json.loads(tok["features"]) if tok.get("features","").strip() else {},
    }
    try:
        feats = json.loads(tok["features"]) if tok.get("features","").strip() else {}
    except Exception:
        feats = {}
    loc = {"kind": "word", "ref": s.ref, "word_num": n,
           "lemma": tok["lemma"], "surface": tok["surface"]}
    if _push_loc: _push(s, loc)
    else: s.cur_loc = loc
    feat  = "  ".join(f"{k}={v}" for k,v in feats.items())
    pd    = _CORPUS.paradigms().get(tok["lemma"], {})
    total = sum(f["count"] for f in pd.get("forms", []))
    sc    = tok.get("stem_class","") or pd.get("stem_class","")
    print(f"\n  {hl(tok['surface'])}  →  {b(tok['lemma'])}"
          + (f"  {d('('+sc+')')}" if sc else "")
          + f"  ·  {d(feat)}"
          + f"  ·  {d(str(total)+' tokens')}")
    print(d("  par · conc · lem · def · look"))
    nbrs = _CORPUS.gravity().get(tok["lemma"], [])[:6]
    if nbrs:
        items = "  ".join(f"{d(str(i)+'.')} {b(e['n'])}" for i,e in enumerate(nbrs, 1))
        print(f"  {d('nearby:')}  {items}")
        s.last_list = [lambda s, l=e["n"]: _goto_lemma(s, l) for e in nbrs]
    else:
        s.last_list = []


def goto_location(s: S, loc: dict) -> None:
    k = loc.get("kind")
    if k == "book":
        go_book(s, loc["book"])
    elif k == "chapter":
        go_chapter(s, loc["book"], loc["chapter"])
    elif k == "verse":
        ref = loc["ref"]
        parts = ref.split(".")
        bk, ch = parts[0], int(parts[1])
        if bk != s.book or ch != s.chapter:
            refs = _CORPUS.chapter_refs(bk, ch)
            s.book, s.chapter, s.refs = bk, ch, refs
        idx = next((i for i,r in enumerate(s.refs) if r == ref), None)
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
        s.last_list = [lambda s, ref=r["ref"]: goto_location(s, {"kind":"verse","ref":ref})
                       for r in rows]
    elif k == "dict":
        show_def(s, loc.get("lemma",""))


# ── lexicon ────────────────────────────────────────────────────────────────────

_LEX: dict | None = None

def _lex() -> dict:
    global _LEX
    if _LEX is None:
        _LEX = json.loads((GOTHIC_DIR / "lexicon.json").read_text())
    return _LEX


def show_def(s: S, lemma: str) -> None:
    lex = _lex()
    entry = lex.get(lemma)
    if entry is None:
        # fuzzy fallback
        results = _CORPUS.search(lemma, n=1)
        if results:
            lemma  = results[0][0]
            entry  = lex.get(lemma)
    if entry is None:
        print(f"  no dictionary entry for {lemma!r}")
        return

    _push(s, {"kind": "dict", "lemma": lemma})
    s.cur_loc["lemma"] = lemma
    s.word = {"surface": lemma, "lemma": lemma, "gramm": entry.get("pos",""), "feats": {}}

    sc      = entry.get("stem_class","")
    pos     = entry.get("pos","")
    gender  = entry.get("gender","")
    gloss   = entry.get("gloss_de","") or entry.get("gloss_en","")
    gloss_e = entry.get("gloss_en","")
    gloss_g = entry.get("gloss_grc","")
    pd      = _CORPUS.paradigms().get(lemma, {})
    total   = sum(f["count"] for f in pd.get("forms", []))
    tok_str = f"  ·  {d(str(total)+' tokens')}" if total else ""

    tag = "  ·  ".join(x for x in [pos, sc, gender] if x)
    print(f"\n{b(lemma)}  {d(tag)}{tok_str}")
    if gloss:   print(f"  {d('[de]')}  {gloss}")
    if gloss_e: print(f"  {d('[en]')}  {gloss_e}")
    if gloss_g: print(f"  {d('[grc]')} {gloss_g}")
    print()

    # nearby in gravity
    nbrs = _CORPUS.gravity().get(lemma, [])[:10]
    if nbrs:
        max_s = nbrs[0]["s"] or 1
        print(f"  {d('nearby:')}")
        half = (len(nbrs)+1)//2
        col  = 36
        for i in range(half):
            la = f"  {i+1:>3}.  {b(nbrs[i]['n'])}"
            if i+half < len(nbrs):
                ri = i+half+1
                ra = f"  {ri:>3}.  {b(nbrs[i+half]['n'])}"
                print(f"{la:<{col}}{ra}")
            else:
                print(la)
        print()
        s.last_list = [lambda s, l=e["n"]: _goto_lemma(s, l) for e in nbrs]
    else:
        s.last_list = []


# ── ref parsing ────────────────────────────────────────────────────────────────

def _parse_ref(cmd: str) -> tuple[str,int,int] | None:
    """'Jn.3.16' → ('Jn', 3, 16)  ·  'Jn.3' → ('Jn', 3, 0)  ·  'Jn' → ('Jn', 0, 0)"""
    parts  = cmd.split(".")
    bk_map = {b.lower(): b for b in _CORPUS.books().get("names", {})}
    bk     = bk_map.get(parts[0].lower())
    if bk is None:
        return None
    try:
        ch = int(parts[1]) if len(parts) > 1 else 0
        vs = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    return bk, ch, vs


# ── REPL ───────────────────────────────────────────────────────────────────────

def handle(cmd: str, s: S) -> bool:
    cmd = cmd.strip()
    if not cmd: return True

    # ref navigation: Jn  /  Jn.3  /  Jn.3.16  (case-insensitive book)
    parsed = _parse_ref(cmd)
    if parsed:
        bk, ch, vs = parsed
        if vs:
            refs = _CORPUS.chapter_refs(bk, ch)
            idx  = next((i for i,r in enumerate(refs)
                         if r == f"{bk}.{ch}.{vs}"), None)
            if idx is not None:
                s.book, s.chapter, s.refs = bk, ch, refs
                go_verse(s, idx)
            else:
                print(f"  verse {bk}.{ch}.{vs} not found")
        elif ch:
            go_chapter(s, bk, ch)
        else:
            go_book(s, bk)
        return True

    # bare number → last list
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

    if verb in ("q","quit","exit"): return False

    elif verb in ("books","index","toc"):
        go_index(s)

    elif verb in ("n","next"):
        if s.idx < len(s.refs)-1: go_verse(s, s.idx+1)
        else: print("  end of chapter")

    elif verb in ("p","prev","previous"):
        if s.idx > 0: go_verse(s, s.idx-1)
        else: print("  beginning of chapter")

    elif verb in ("r","read"):
        if s.ref: show_verse(s)
        else: print("  no verse open")

    elif verb in ("x","expand","words","w"):
        if s.words:
            show_words(s.words)
            s.last_list = [lambda s, n=n: pick_word(s, n) for n in range(1, len(s.words)+1)]
            print(d(f"  type a number to select a word (1–{len(s.words)})"))
        elif s.ref:
            s.words = _merge_verse_tokens(_CORPUS.verse_tokens().get(s.ref, []))
            if s.words:
                show_words(s.words)
                s.last_list = [lambda s, n=n: pick_word(s, n)
                               for n in range(1, len(s.words)+1)]
                print(d(f"  type a number to select a word (1–{len(s.words)})"))
        else:
            print("  no verse open — navigate to one first")

    elif verb.isdigit() or (verb == "w" and rest.isdigit()):
        n = int(rest if verb == "w" else verb)
        if s.ref: pick_word(s, n)
        else: print("  no verse open")

    elif verb in ("par","paradigm"):
        if s.word:
            _push(s, {"kind": "paradigm", "lemma": s.word["lemma"]})
            show_paradigm(s, s.word["lemma"])
        else: print("  select a word first (x, then a number)")

    elif verb in ("conc","concordance","c"):
        if s.word:
            _push(s, {"kind":"concordance","lemma":s.word["lemma"],"surface":s.word["surface"]})
            rows = show_concordance(s, s.word["lemma"], s.word["surface"])
            s.last_list = [lambda s, ref=r["ref"]:
                           goto_location(s, {"kind":"verse","ref":ref}) for r in rows]
        else: print("  select a word first")

    elif verb in ("lem","lemma","l"):
        if s.word:
            _push(s, {"kind": "concordance", "lemma": s.word["lemma"]})
            rows = show_concordance(s, s.word["lemma"])
            s.last_list = [lambda s, ref=r["ref"]:
                           goto_location(s, {"kind":"verse","ref":ref}) for r in rows]
        else: print("  select a word first")

    elif verb in ("def","dict","d"):
        target = rest or (s.word["lemma"] if s.word else None)
        if not target: print("  select a word first, or: def wulfs")
        else: show_def(s, target)

    elif verb in ("look",):
        n_show = int(rest) if rest.isdigit() else 10
        lemma  = (None if rest.isdigit() else rest) or (s.word["lemma"] if s.word else None)
        if not lemma: print("  select a word first, or: look wulfs  /  look 20")
        else: show_look(s, lemma, n_show)

    elif verb in ("stems","stem","sc"):
        show_stems(s, rest)

    elif verb in ("back","b"):
        if s.history:
            loc = s.history.pop()
            s.cur_loc = None
            goto_location(s, loc)
        else:
            print("  nothing to go back to")

    elif verb in ("keep","k","bookmark"):
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

    elif verb in ("drop","remove","del","delete"):
        if not rest: print("  usage: drop <name>")
        elif rest not in s.inventory: print(f"  {rest!r} not in inventory")
        else:
            del s.inventory[rest]
            print(f"  dropped: {rest}")

    elif verb in ("go","visit"):
        if not rest: print("  usage: go <name>  (see: inv)")
        elif rest not in s.inventory: print(f"  {rest!r} not in inventory  (see: inv)")
        else: goto_location(s, s.inventory[rest])

    elif verb in ("inv","inventory","i"):
        if not s.inventory:
            print("  inventory is empty  (use: keep <name>)")
        else:
            print()
            for name, loc in s.inventory.items():
                print(f"  {b(name):<24}  {_loc_str(loc)}")
            print()

    elif verb in ("find","search","f"):
        if not rest: print("  usage: find <query>"); return True
        results = s.corpus.search(rest)
        if not results:
            print(f"  nothing found for {rest!r}")
        else:
            print()
            for i,(l,pd) in enumerate(results, 1):
                sc    = pd.get("stem_class","")
                gramm = "/".join(pd.get("gramm",[]))
                total = sum(f["count"] for f in pd.get("forms",[]))
                tag   = gramm + (f" {sc}" if sc else "")
                print(f"  {i:>3}.  {b(l):<32} {d(tag):<28} {total} tokens")
            print()
            s.last_list = [lambda s, l=l: _goto_lemma(s, l) for l,_ in results]

    elif verb in ("help","h","?"):
        print(__doc__)

    else:
        results = s.corpus.search(cmd)
        if results and _norm(results[0][0]) == _norm(cmd):
            _goto_lemma(s, results[0][0])
        elif results:
            print(f"\n  did you mean:")
            for i,(l2,pd2) in enumerate(results[:6], 1):
                total = sum(f["count"] for f in pd2.get("forms",[]))
                print(f"  {i:>3}.  {b(l2):<32} {total} tokens")
            print()
            s.last_list = [lambda s, l=l: _goto_lemma(s, l) for l,_ in results[:6]]
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

    print(f"\n{b('Gothic Explorer')}")
    print(d("  books  to list texts  ·  Jn.19.3  to open a verse  ·  find wulfs  to search\n"))
    s = S()
    load_inventory(s)
    tty = sys.stdout.isatty()
    while True:
        ref = s.ref or (f"{s.book}.{s.chapter}" if s.book else "")
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
