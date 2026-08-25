#!/usr/bin/env python3
"""rv — Ṛgveda explorer

  Navigation
    7.            open maṇḍala (book) index
    1.1           open hymn (a place)
    1.1.3         open verse (a place)
    n / p         next / previous verse
    s             back to current hymn
    back / b      previous place in history

  At a verse
    x             show word table
    3             select word 3 (a place)
    par           paradigm (a place)
    conc          concordance for this form (a place)
    lem           concordance for whole lemma (a place)
    def           Grassmann dictionary entry (a place)
    chant         Vedic accent notation
    look          nearby lemmas (gravity field)  ·  look 20 for more
    stems         browse by stem formation  ·  stems a-stem for lemmata

  Inventory
    keep <name>   save current place (name optional → inv1, inv2…)
    drop <name>   remove from inventory
    go <name>     navigate to saved place
    inv           list inventory

  Search
    find soma     fuzzy lemma search

  q             quit
"""

import sys, json, csv
from pathlib import Path
from collections import defaultdict

from explorer import (
    Corpus, S as BaseS,
    b, d, hl, B, D, R, HL, RULE,
    _norm, _push, _goto_lemma,
    show_paradigm, show_concordance, show_stems, show_look,
    load_inventory, save_inventory,
    _wrap, set_wrap_width,
)

# chant rendering — vendored module + data, fully self-contained
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from ghanapati import processline, render_ascii as _render_ascii
    _CHANT_LINES = None   # ref "1.1.1" → [raw_line, ...]

    def _chant_index():
        global _CHANT_LINES
        if _CHANT_LINES is None:
            _CHANT_LINES = defaultdict(list)
            src = Path(__file__).parent / "corpus/chant/rv_lines.txt"
            with open(src) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    num = line.split()[0]           # e.g. "1.001.01a"
                    parts = num.split(".")
                    ref = f"{int(parts[0])}.{int(parts[1])}.{int(parts[2][:2])}"
                    _CHANT_LINES[ref].append(line)
        return _CHANT_LINES

    def show_chant(ref: str) -> None:
        idx = _chant_index()
        lines = idx.get(ref)
        if not lines:
            print(f"  no chant data for {ref}")
            return
        print()
        for raw in lines:
            _, _, _, tones = processline(raw)
            print(_render_ascii(tones, label=raw.split(None, 1)[1].strip()))
            print()

    _CHANT_AVAILABLE = True
except Exception:
    _CHANT_AVAILABLE = False
    def show_chant(ref):
        print("  chant data not available (corpus/chant/rv_lines.txt missing)")

try:
    import readline
    readline.parse_and_bind("tab: complete")
    readline.set_history_length(1000)
except ImportError:
    pass

BASE      = Path(__file__).parent
TEI_DIR   = BASE / "corpus/c-salt_vedaweb_tei"
HYMN_N    = {1:191,2:43,3:62,4:58,5:87,6:75,7:104,8:103,9:114,10:191}
ADDR_PATH = BASE / "corpus/c-salt_vedaweb_sources/rigveda/info/addressees.json"

BOOK_LABEL = {
    1: "first maṇḍala",  2: "Gṛtsamada",     3: "Viśvāmitra",
    4: "Vāmadeva",       5: "Atri",           6: "Bharadvāja",
    7: "Vasiṣṭha",       8: "Kāṇva / misc.",  9: "Soma pavamāna",
   10: "tenth maṇḍala",
}

# ── corpus instance ───────────────────────────────────────────────────────────

_RV_CORPUS = Corpus(BASE, inv_file=Path.home() / ".vedanture_inventory.json")

# convenience wrappers (used by GRA helpers that have no session reference)
def paradigms():   return _RV_CORPUS.paradigms()
def concordance(): return _RV_CORPUS.concordance()
def gravity():     return _RV_CORPUS.gravity()

_ADDR: dict | None = None
_BC:   dict        = {}

def addr():
    global _ADDR
    if _ADDR is None:
        _ADDR = json.loads(ADDR_PATH.read_text())
    return _ADDR

# ── Grassmann dictionary ──────────────────────────────────────────────────────

GRA_PATH  = BASE / "corpus/c-salt_sanskrit_data/sa_de/gra/gra.tei"
ML_PATH   = BASE / "corpus/c-salt_vedaweb_sources/rigveda/info/matched_lemmata.json"
GE_PATH   = BASE / "corpus/c-salt_vedaweb_sources/rigveda/info/grassmann_enum.json"

_GRA_IDX  = None   # xml:id  → <entry> element
_GRA_SEQ  = None   # ordered list of (n, xml:id, orth_iso) for navigation
_ML       = None   # surface → {lemma, id_matched, …}
_GE_REV   = None   # grassmann_seq_num → "book.hymn"

GTEI = "http://www.tei-c.org/ns/1.0"
GT   = lambda s: f"{{{GTEI}}}{s}"
GXID = "{http://www.w3.org/XML/1998/namespace}id"
GXML = "{http://www.w3.org/XML/1998/namespace}"    # xml: attribute namespace

def _gra_load():
    global _GRA_IDX, _GRA_SEQ
    if _GRA_IDX is None:
        from lxml import etree
        root = etree.parse(str(GRA_PATH)).getroot()
        _GRA_IDX = {e.get(GXID): e for e in root.iter(GT("entry"))}
        _GRA_SEQ = []
        for e in sorted(_GRA_IDX.values(), key=lambda x: int(x.get("n","0"))):
            eid   = e.get(GXID,"")
            orth  = ""
            for o in e.findall(f".//{GT('orth')}"):
                if o.get(f"{GXML}lang","") == "san-Latn-x-ISO-15919":
                    orth = o.text or ""; break
            nrefs = len(e.findall(f".//{GT('ref')}"))
            _GRA_SEQ.append((int(e.get("n","0")), eid, orth, nrefs))

def _gra_idx():
    _gra_load()
    return _GRA_IDX

def _gra_seq():
    _gra_load()
    return _GRA_SEQ

def _ml():
    global _ML
    if _ML is None:
        _ML = json.loads(ML_PATH.read_text())
    return _ML

def _ge_rev():
    global _GE_REV
    if _GE_REV is None:
        ge = json.loads(GE_PATH.read_text())
        _GE_REV = {v: k for k, v in ge.items()}
    return _GE_REV


def _ref_to_rv(target: str) -> str:
    """Convert GRA ref target like '#04.028.01' → '4.28.1'."""
    t = target.lstrip("#")
    parts = t.split(".")
    if len(parts) == 3:
        return f"{int(parts[0])}.{int(parts[1])}.{int(parts[2])}"
    return t


def _render_sense(sense_el) -> str:
    """Walk <sense> and produce readable text with ANSI formatting."""
    parts = []
    def walk(el, tail=True):
        # opening text of this element
        if el.text:
            parts.append(" ".join(el.text.split()))
        for child in el:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            rend = child.get("rendition", "")
            if tag == "hi" and "#b" in rend:
                parts.append(b("".join(child.itertext()).strip()))
            elif tag == "hi" and "#i" in rend:
                inner = "".join(child.itertext()).strip()
                parts.append(f"\033[3m{inner}{R}")   # italic
            elif tag == "ref":
                rv = _ref_to_rv(child.get("target",""))
                parts.append(d(f"[{rv}]"))
            elif tag == "lb":
                parts.append("\n  ")
            else:
                walk(child, tail=False)
            if child.tail:
                parts.append(" ".join(child.tail.split()))
    walk(sense_el)
    # collapse whitespace runs but preserve intentional newlines
    text = " ".join(parts)
    text = text.replace("  \n  ", "\n  ").replace(" \n  ", "\n  ")
    # tidy up space before punctuation
    import re
    text = re.sub(r' ([,;.])', r'\1', text)
    return text.strip()


import re as _re

_XREF_PATTERNS = _re.compile(
    r'(?:^|(?<=\s))(?:s\.|vgl\.|cf\.|von|und|oder|siehe)\s+([A-Za-zāīūṭḍṇśṣḥṃáéíóúàèìòùâêîôûñčšžçṙĉ*√\-]+)',
    _re.IGNORECASE
)

def _orth_iso(entry) -> str:
    for o in entry.findall(f".//{GT('orth')}"):
        if "ISO-15919" in o.get(f"{GXML}lang", ""):
            return o.text or ""
    return ""


def _weight_bar(nrefs: int) -> str:
    """Visual weight indicator based on ref count."""
    if   nrefs == 0:  return d("·")
    elif nrefs <  5:  return d("░")
    elif nrefs < 20:  return d("▒")
    elif nrefs < 60:  return d("▓")
    else:             return d("█")


def _gra_neighbors(eid: str, window: int = 3) -> list:
    """Return (n, eid, orth, nrefs, is_current) for entries around eid."""
    seq = _gra_seq()
    pos = next((i for i,(_,e,_,_) in enumerate(seq) if e == eid), None)
    if pos is None:
        return []
    lo, hi = max(0, pos-window), min(len(seq), pos+window+1)
    return [(n, e, o, nr, e == eid) for n,e,o,nr in seq[lo:hi]]


def _extract_xrefs(text: str) -> list[str]:
    """Pull potential cross-reference words from sense prose."""
    raw = _XREF_PATTERNS.findall(text)
    # clean up: strip leading *, numbers, dashes
    out = []
    for w in raw:
        w = w.strip("*1234567890-,.;")
        if len(w) > 1:
            out.append(w)
    return list(dict.fromkeys(out))  # deduplicate, preserve order


def _lemma_norms(lemma_str: str) -> set[str]:
    """All normalised forms to try — handles '√foo- ~ √bar-' compound lemmas."""
    parts = [lemma_str] + (lemma_str.split(" ~ ") if " ~ " in lemma_str else [])
    return {_norm(p) for p in parts if _norm(p)}


# Reverse indices over matched_lemmata + GRA, built once. Without these every
# lemma→entry lookup rescans all 32k matched-lemmata, which makes a full static
# export (10k lemmas) take ~17 min; with them it is near-instant.
_ML_NORM_IDS = None   # _norm(lemma|surface) → set(eid)
_EID_INFO    = None   # eid → (corpus_lemmata, total_token_count)
_GRA_ORTH_IDS = None  # _norm(orth_iso) → set(eid)

def _ml_indices():
    global _ML_NORM_IDS, _EID_INFO
    if _ML_NORM_IDS is None:
        norm_ids   = defaultdict(set)
        eid_lemmas = defaultdict(list)
        eid_seen   = defaultdict(set)
        for surface, data in _ml().items():
            m = data.get("id_matched")
            if not m:
                continue
            eids = m if isinstance(m, list) else [m]
            dl   = data.get("lemma", "")
            for key in (_norm(dl), _norm(surface)):
                if key:
                    norm_ids[key].update(eids)
            for eid in eids:
                if dl and dl not in eid_seen[eid]:
                    eid_seen[eid].add(dl)
                    eid_lemmas[eid].append(dl)
        pars = paradigms()
        eid_info = {}
        for eid, lems in eid_lemmas.items():
            total = sum(sum(f["count"] for f in pars.get(l, {}).get("forms", []))
                        for l in lems)
            eid_info[eid] = (lems, total)
        _ML_NORM_IDS, _EID_INFO = dict(norm_ids), eid_info
    return _ML_NORM_IDS, _EID_INFO


def _gra_orth_index():
    global _GRA_ORTH_IDS
    if _GRA_ORTH_IDS is None:
        d = defaultdict(set)
        for eid, entry in _gra_idx().items():
            k = _norm(_orth_iso(entry))
            if k:
                d[k].add(eid)
        _GRA_ORTH_IDS = dict(d)
    return _GRA_ORTH_IDS


def _lookup_gra_ids(lemma_str: str) -> list[str]:
    """Return GRA xml:ids for a lemma string."""
    norm_ids, _ = _ml_indices()
    norms = _lemma_norms(lemma_str)
    ids   = set()
    for nkey in norms:
        ids |= norm_ids.get(nkey, set())
    if not ids:
        orth_ids = _gra_orth_index()
        for nkey in norms:
            ids |= orth_ids.get(nkey, set())
    return sorted(ids)


def _eid_corpus_info(eid: str) -> tuple[list[str], int]:
    """Return (corpus_lemmata, total_token_count) for a GRA entry id.

    Multiple corpus lemmata can map to the same GRA entry (e.g. variant
    spellings treated as one dictionary headword).
    """
    _, eid_info = _ml_indices()
    return eid_info.get(eid, ([], 0))


def _eid_to_corpus_lemma(eid: str) -> str:
    lemmata, _ = _eid_corpus_info(eid)
    return lemmata[0] if lemmata else ""


def _eid_corpus_count(eid: str) -> int:
    _, total = _eid_corpus_info(eid)
    return total


def show_gra(lemma_str: str, eid: str | None = None) -> tuple[str | None, list, list]:
    """Display a GRA entry.  Returns (eid, nearby_eids, xref_lemmas)."""
    idx = _gra_idx()

    if eid is None:
        ids = _lookup_gra_ids(lemma_str)
        if not ids:
            print(f"  {d('no Grassmann entry found for')} {lemma_str}")
            return None, [], []
        eid = ids[0]

    entry = idx.get(eid)
    if entry is None:
        print(f"  {d('entry not found:')} {eid}")
        return None, [], []

    orth              = _orth_iso(entry)
    n                 = entry.get("n","?")
    sense             = entry.find(GT("sense"))
    text              = _render_sense(sense) if sense is not None else "(no definition)"
    corpus_lemmata, tokens = _eid_corpus_info(eid)
    tok_str = f"  ·  {d(str(tokens)+' tokens')}" if tokens else ""

    print(f"\n{b(orth)}  {d('GRA #'+n)}{tok_str}")
    if corpus_lemmata:
        print(f"  {d('corpus:')}  {'  ·  '.join(b(l) for l in corpus_lemmata)}")
    print()
    for line in text.split("\n"):
        print(f"  {line}")

    # ── sequential neighbours (two-column) ────────────────────────────────────
    neighbors   = _gra_neighbors(eid, window=10)
    nearby_eids = []
    if neighbors:
        print(f"\n  {d('─── nearby ──────────────────────────')}")
        nav = []
        for nn, ne, no, nr, cur in neighbors:
            if cur:
                print(f"  {'→':>5}  {nn:>6}  {b(no)}")
            else:
                nav.append((nn, ne, no))
        nearby_eids = [ne for _, ne, _ in nav]
        half = (len(nav) + 1) // 2
        col  = 36
        for row in range(half):
            ln, _, lo = nav[row]
            ls = f"  {row+1:>3}.  {ln:>6}  {lo}"
            if row + half < len(nav):
                rn, _, ro = nav[row + half]
                ri = row + half + 1
                rs = f"  {ri:>3}.  {rn:>6}  {ro}"
                print(f"{ls:<{col}}{rs}")
            else:
                print(ls)

    # ── cross-references ──────────────────────────────────────────────────────
    prose = " ".join(sense.itertext()) if sense is not None else ""
    xrefs = _extract_xrefs(prose)[:8]
    if xrefs:
        offset = len(nearby_eids) + 1
        print(f"\n  {d('─── see also ─────────────────────────')}")
        for j, xref in enumerate(xrefs, offset):
            print(f"  {j:>3}.   {xref}")

    print()
    return eid, nearby_eids, xrefs


def _goto_gra(s, eid=None, lemma=None, push=True):
    """Navigate to a GRA entry by eid or lemma string, updating s.last_list.

    s.word is only updated when a real GRA entry is found; it is left
    unchanged on lookup failure so the caller's corpus-lemma context
    (par, lem, conc) keeps working.
    """
    if push:
        _push(s, {"kind": "dict", "lemma": lemma or eid or ""})
    else:
        s.cur_loc = {"kind": "dict", "lemma": lemma or eid or ""}
    gid, nbr_eids, xref_lemmas = show_gra(lemma or "", eid)
    if gid:
        s.cur_loc["gra_id"] = gid
        corpus_lemma = lemma or _eid_to_corpus_lemma(gid)
        if corpus_lemma:
            s.word = {"surface": corpus_lemma, "lemma": corpus_lemma, "gramm": "", "feats": {}}
    # on lookup failure gid is None — s.word intentionally unchanged
    s.last_list = (
        [lambda s, e=ne: _goto_gra(s, eid=e)   for ne in nbr_eids] +
        [lambda s, l=xl: _goto_gra(s, lemma=l) for xl in xref_lemmas]
    )


# ── RV text ───────────────────────────────────────────────────────────────────

TEI = "http://www.tei-c.org/ns/1.0"
T   = lambda s: f"{{{TEI}}}{s}"
XID = "{http://www.w3.org/XML/1998/namespace}id"

def load_book(n: int) -> dict:
    if n in _BC: return _BC[n]
    from lxml import etree
    root = etree.parse(str(TEI_DIR/f"rv_book_{n:02d}.tei")).getroot()
    out  = {}
    for div in root.iter(T("div")):
        if div.get("type") != "stanza": continue
        sid = div.get(XID,"")
        zur = div.find(f'.//{T("lg")}[@source="zurich"]')
        if zur is None: continue
        lines = [" ".join(l.itertext()).strip() for l in zur.findall(T("l"))
                 if "_tokens" not in (l.get(XID) or "")]
        trans = {}
        for src in ("grassmann","geldner","griffith"):
            lg = div.find(f'.//{T("lg")}[@source="{src}"]')
            if lg is not None:
                tlines = [" ".join("".join(l.itertext()).split()) for l in lg.findall(T("l"))]
                tlines = [ln for ln in tlines if ln]
                if tlines:
                    trans[src] = tlines
        words = []
        for fs in zur.iter(T("fs")):
            if fs.get("type") != "zurich_info": continue
            def g(name, _fs=fs):
                f = _fs.find(f'.//{T("f")}[@name="{name}"]')
                if f is None: return ""
                s = f.find(T("string"))
                if s is not None: return (s.text or "").strip()
                sym = f.find(T("symbol"))
                return sym.get("value","") if sym is not None else ""
            feats = {}
            mf = fs.find(f'.//{T("fs")}[@type="leipzig_glossing_rules"]')
            if mf is not None:
                for f in mf.findall(T("f")):
                    sym = f.find(T("symbol"))
                    if sym is not None: feats[f.get("name","")] = sym.get("value","")
            words.append({"surface":g("surface"),"lemma":g("gra_lemma"),
                          "gramm":g("gra_gramm"),"feats":feats})
        out[sid] = {"lines":lines,"trans":trans,"words":words}
    _BC[n] = out
    return out

def hymn_stanzas(book, hymn):
    d   = load_book(book)
    pfx = f"b{book:02d}_h{hymn:03d}_"
    res = [(f"{book}.{hymn}.{int(k.split('_')[2])}", v)
           for k,v in d.items() if k.startswith(pfx)]
    return sorted(res, key=lambda x: int(x[0].split(".")[2]))

# ── rendering ─────────────────────────────────────────────────────────────────


_TRANS_LABEL = {"grassmann": "graßmann", "geldner": "geldner", "griffith": "griffith"}
_TRANS_W = max(len(f"[{v}]") for v in _TRANS_LABEL.values())

def show_verse(ref, stanza):
    print(f"\n{b(ref)}   {d('—  ' + stanza['lines'][0] if stanza['lines'] else '')}")
    print()
    for line in stanza["lines"]:
        print(f"  {line}")
    print()
    for src, lines in stanza["trans"].items():
        import textwrap as _tw
        from explorer import WRAP_WIDTH
        label      = f"[{_TRANS_LABEL.get(src, src)}]"
        pad        = " " * (_TRANS_W - len(label))
        prefix_vis = 2 + _TRANS_W + 2          # visible chars before content
        cont_ind   = " " * prefix_vis
        full       = " ".join(lines)
        parts      = _tw.wrap(full, width=max(20, WRAP_WIDTH - prefix_vis)) or [full]
        print(f"  {d(label)}{pad}  {parts[0]}")
        for part in parts[1:]:
            print(f"  {cont_ind}{part}")


def show_words(words):
    if not words: return
    cw = max(len(w["surface"]) for w in words) + 2
    cl = max(len(w["lemma"])   for w in words) + 2
    print()
    for i, w in enumerate(words, 1):
        feat = "  ".join(f"{k}={v}" for k,v in w["feats"].items())
        print(f"  {d(str(i)):>5}  {w['surface']:<{cw}} {d(w['lemma']):<{cl+6}} {feat}")




# ── state & REPL ──────────────────────────────────────────────────────────────

class S(BaseS):
    def __init__(self):
        super().__init__(_RV_CORPUS)
        self.book:      int  = 0
        self.hymn:      int  = 0
        self.verses:    list = []
        self.idx:       int  = -1
        self.words:     list = []
        self.word_num:  int  = 0

    @property
    def ref(self):
        return self.verses[self.idx][0] if 0 <= self.idx < len(self.verses) else None

    @property
    def stanza(self):
        return self.verses[self.idx][1] if 0 <= self.idx < len(self.verses) else None


# ── location helpers ──────────────────────────────────────────────────────────


def _goto_ref(s, ref):
    bk, hy = int(ref.split(".")[0]), int(ref.split(".")[1])
    if bk != s.book or hy != s.hymn:
        go_hymn(s, bk, hy)
    idx = next((i for i,(r,_) in enumerate(s.verses) if r == ref), None)
    if idx is not None:
        go_verse(s, idx)


def _loc_str(loc: dict) -> str:
    k = loc.get("kind","?")
    if k == "hymn":        return f"RV {loc['book']}.{loc['hymn']}"
    if k == "verse":       return f"RV {loc['ref']}"
    if k == "word":        return f"RV {loc['ref']} [{loc['lemma']}]"
    if k == "paradigm":    return f"par: {loc['lemma']}"
    if k == "concordance":
        s = loc.get("surface"); l = loc["lemma"]
        return f"conc: {s} (< {l})" if s else f"conc: {l}"
    if k == "dict":        return f"def: {loc['lemma']}"
    if k == "chant":       return f"chant: {loc['ref']}"
    return str(loc)


def goto_location(s, loc: dict):
    """Navigate to a saved location without pushing to history."""
    k = loc.get("kind")
    if k == "hymn":
        go_hymn(s, loc["book"], loc["hymn"], _push_loc=False)
    elif k == "verse":
        ref = loc["ref"]
        bk, hy = int(ref.split(".")[0]), int(ref.split(".")[1])
        if bk != s.book or hy != s.hymn:
            go_hymn(s, bk, hy, _push_loc=False)
        idx = next((i for i,(r,_) in enumerate(s.verses) if r == ref), None)
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
        s.last_list = [lambda s, ref=r["ref"]: _goto_ref(s, ref) for r in rows]
    elif k == "dict":
        _goto_gra(s, eid=loc.get("gra_id"), lemma=loc.get("lemma"), push=False)
    elif k == "chant":
        show_chant(loc["ref"])
        s.cur_loc = loc


def go_mandala(s, book):
    """Show the hymn index for a whole book — addressee, group, verse count."""
    n_hymns = HYMN_N.get(book, 0)
    label   = BOOK_LABEL.get(book, "")

    # verse counts: count stanza keys in the book cache if already loaded,
    # otherwise derive from concordance (no extra file load needed)
    verse_counts = {}
    if book in _BC:
        from collections import Counter
        cntr = Counter()
        for sid in _BC[book]:
            parts = sid.split("_")
            if len(parts) >= 2:
                cntr[int(parts[1][1:])] += 1
        verse_counts = dict(cntr)
    else:
        from collections import Counter
        cntr  = Counter()
        seen  = set()
        for rows in concordance().values():
            for r in rows:
                ref = r["ref"]
                if ref not in seen:
                    parts = ref.split(".")
                    if int(parts[0]) == book:
                        seen.add(ref)
                        cntr[int(parts[1])] += 1
        verse_counts = dict(cntr)

    ad   = addr()
    loc  = {"kind": "hymn", "book": book, "hymn": 0}
    _push(s, loc)

    print(f"\n{b(f'RV {book}')}  {d(label)}  ·  {n_hymns} hymns\n")

    actions     = []
    prev_group  = None
    for hymn_n in range(1, n_hymns + 1):
        key  = f"{book:02d}.{hymn_n:03d}"
        info = ad.get(key)
        if info:
            addressee = info[0][1]   # English
            group_str = info[1][1]   # e.g. "2. group: hymns to Indra"
        else:
            addressee, group_str = "—", ""

        # group header when group changes
        if group_str != prev_group:
            prev_group = group_str
            # strip leading "N. group: " prefix
            glabel = group_str.split(": ", 1)[-1] if ": " in group_str else group_str
            print(f"  {d('── '+glabel+' '+'─'*max(0,46-len(glabel)))}")

        v = verse_counts.get(hymn_n, "?")
        v_str = f"{v}v" if isinstance(v, int) else "?"
        rank  = len(actions) + 1
        print(f"  {rank:>4}.  {b(f'{book}.{hymn_n}'):<{8+len(b(''))}}  "
              f"{addressee:<32}  {d(v_str)}")
        actions.append(lambda s, bk=book, hy=hymn_n: go_hymn(s, bk, hy))

    print()
    s.cur_loc  = {"kind": "hymn", "book": book, "hymn": 0}
    s.last_list = actions


def go_hymn(s, book, hymn, _push_loc=True):
    if book not in HYMN_N or not (1 <= hymn <= HYMN_N[book]):
        print(f"  no such hymn: {book}.{hymn}")
        return
    loc = {"kind": "hymn", "book": book, "hymn": hymn}
    if _push_loc: _push(s, loc)
    else: s.cur_loc = loc
    print(f"  {d('loading…')}", end="\r", flush=True)
    s.verses = hymn_stanzas(book, hymn)
    s.book, s.hymn, s.idx = book, hymn, -1
    s.words, s.word = [], None
    n = len(s.verses)
    print(f"\n{b(f'RV {book}.{hymn}')}  {d(str(n)+' verses')}\n")
    for ref, st in s.verses:
        print(f"  {b(ref)}")
        for line in st['lines']:
            print(f"    {line}")
        print()
    print(d("  type a verse number (e.g. 3), or n to step through"))
    s.last_list = [lambda s, i=i: go_verse(s, i) for i in range(len(s.verses))]


def go_verse(s, idx, _push_loc=True):
    s.idx       = idx
    s.words     = s.stanza.get("words",[]) if s.stanza else []
    s.word      = None
    s.last_list = []
    loc = {"kind": "verse", "ref": s.ref}
    if _push_loc: _push(s, loc)
    else: s.cur_loc = loc
    show_verse(s.ref, s.stanza)
    print(d(f"  {len(s.words)} words  ·  x to expand  ·  n/p next/prev"))


def pick_word(s, n, _push_loc=True):
    if not (1 <= n <= len(s.words)):
        print(f"  word {n} out of range (1–{len(s.words)})")
        return
    s.word     = s.words[n-1]
    s.word_num = n
    w          = s.word
    loc = {"kind": "word", "ref": s.ref, "word_num": n,
           "lemma": w["lemma"], "surface": w["surface"]}
    if _push_loc: _push(s, loc)
    else: s.cur_loc = loc
    feat   = "  ".join(f"{k}={v}" for k,v in w["feats"].items())
    pd     = paradigms().get(w["lemma"],{})
    total  = sum(f["count"] for f in pd.get("forms",[]))
    sc     = pd.get("stem_class","")
    print(f"\n  {hl(w['surface'])}  →  {b(w['lemma'])}"
          + (f"  {d('('+sc+')')}" if sc else "")
          + f"  ·  {d(feat)}"
          + f"  ·  {d(str(total)+' tokens')}")
    print(d("  par · conc · lem · def · look"))
    nbrs = gravity().get(w["lemma"], [])[:6]
    if nbrs:
        items = "  ".join(f"{d(str(i)+'.')} {b(e['n'])}" for i,e in enumerate(nbrs, 1))
        print(f"  {d('nearby:')}  {items}")
        s.last_list = [lambda s, l=e["n"]: _goto_lemma(s, l) for e in nbrs]
    else:
        s.last_list = []


def handle(cmd: str, s: S) -> bool:
    cmd = cmd.strip()
    if not cmd: return True

    parts = cmd.split(".")
    # mandala ref  7.
    if len(parts) == 2 and parts[0].isdigit() and parts[1] == "":
        n = int(parts[0])
        if 1 <= n <= 10: go_mandala(s, n)
        else: print(f"  book {n} doesn't exist (1–10)")
        return True

    # verse ref  1.1.3
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        b_, h_, sv = int(parts[0]), int(parts[1]), int(parts[2])
        if b_ != s.book or h_ != s.hymn:
            go_hymn(s, b_, h_)
        idx = next((i for i,(r,_) in enumerate(s.verses) if r==f"{b_}.{h_}.{sv}"), None)
        if idx is not None: go_verse(s, idx)
        else: print(f"  verse {cmd} not found")
        return True

    # hymn ref  1.1
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        go_hymn(s, int(parts[0]), int(parts[1]))
        return True

    # bare number → select from whatever was last listed
    if cmd.isdigit():
        n = int(cmd)
        if s.last_list:
            if 1 <= n <= len(s.last_list):
                s.last_list[n-1](s)
            else:
                print(f"  {n} out of range (1–{len(s.last_list)})")
        elif s.stanza:
            print(d("  type x to expand words, then a number to select"))
        elif 1 <= n <= 10:
            go_mandala(s, n)
        else:
            print("  type a book number (1–10) to open a maṇḍala")
        return True

    tok  = cmd.split(None, 1)
    verb = tok[0].lower()
    rest = tok[1] if len(tok) > 1 else ""

    if verb in ("q","quit","exit"): return False

    elif verb in ("n","next"):
        if s.stanza is None and s.verses:
            go_verse(s, 0)
        elif s.idx < len(s.verses)-1:
            go_verse(s, s.idx+1)
        else:
            print("  end of hymn")

    elif verb in ("p","prev","previous"):
        if s.idx > 0:
            go_verse(s, s.idx-1)
        else:
            print("  beginning of hymn")

    elif verb in ("r","read"):
        if s.stanza: show_verse(s.ref, s.stanza)
        else: print("  no verse open")

    elif verb in ("s","sukta","hymn"):
        if s.book:
            s.idx, s.word = -1, None
            s.cur_loc = {"kind": "hymn", "book": s.book, "hymn": s.hymn}
            n = len(s.verses)
            print(f"\n{b(f'RV {s.book}.{s.hymn}')}  {d(str(n)+' verses')}\n")
            for ref, st in s.verses:
                print(f"  {b(ref)}")
                for line in st['lines']:
                    print(f"    {line}")
                print()
            s.last_list = [lambda s, i=i: go_verse(s, i) for i in range(len(s.verses))]
        else:
            print("  no hymn open")

    elif verb in ("x","expand","words","w"):
        if s.words:
            show_words(s.words)
            s.last_list = [lambda s, n=n: pick_word(s, n) for n in range(1, len(s.words)+1)]
            print(d(f"  type a number to select a word (1–{len(s.words)})"))
        else:
            print("  no verse open — try n")

    # word selection by number after expand: "w 3" or standalone after expand
    elif verb.isdigit() or (verb == "w" and rest.isdigit()):
        n = int(rest if verb == "w" else verb)
        if s.stanza: pick_word(s, n)
        else: print("  no verse open")

    elif verb in ("par","paradigm"):
        if s.word:
            _push(s, {"kind": "paradigm", "lemma": s.word["lemma"]})
            show_paradigm(s, s.word["lemma"])
        else: print("  select a word first (x, then a number)")

    elif verb in ("conc","concordance","c"):
        if s.word:
            _push(s, {"kind": "concordance", "lemma": s.word["lemma"], "surface": s.word["surface"]})
            rows = show_concordance(s, s.word["lemma"], s.word["surface"])
            s.last_list = [lambda s, ref=r["ref"]: _goto_ref(s, ref) for r in rows]
        else: print("  select a word first")

    elif verb in ("lem","lemma","l"):
        if s.word:
            _push(s, {"kind": "concordance", "lemma": s.word["lemma"]})
            rows = show_concordance(s, s.word["lemma"])
            s.last_list = [lambda s, ref=r["ref"]: _goto_ref(s, ref) for r in rows]
        else: print("  select a word first")

    elif verb in ("chant","acc","melody"):
        if s.ref:
            _push(s, {"kind": "chant", "ref": s.ref})
            show_chant(s.ref)
        else: print("  open a verse first")

    elif verb in ("def","dict","gra","d"):
        target = rest or (s.word["lemma"] if s.word else None)
        if not target:
            print("  select a word first, or: def soma  /  def 10727")
        elif rest.isdigit():
            seq = _gra_seq()
            n   = int(rest)
            eid = next((eid for nn,eid,_,_ in seq if nn == n), None)
            if eid: _goto_gra(s, eid=eid)
            else:   print(f"  GRA #{rest} not found")
        else:
            _goto_gra(s, lemma=target)

    elif verb in ("look",):
        n_show = int(rest) if rest.isdigit() else 10
        lemma  = (None if rest.isdigit() else rest) or (s.word["lemma"] if s.word else None)
        if not lemma:
            print("  select a word first, or: look soma  /  look 20")
        else:
            show_look(s, lemma, n_show)

    elif verb in ("stems","stem","sc"):
        show_stems(s, rest)

    elif verb in ("back","b"):
        if s.history:
            loc = s.history.pop()
            s.cur_loc = None   # cleared so goto_location sets it fresh
            goto_location(s, loc)
        else:
            print("  nothing to go back to")

    elif verb in ("keep","k","bookmark"):
        if not s.cur_loc:
            print("  nothing to save yet")
        else:
            if not rest:
                # auto-name: inv1, inv2, …
                n = 1
                while f"inv{n}" in s.inventory:
                    n += 1
                rest = f"inv{n}"
            s.inventory[rest] = s.cur_loc.copy()
            print(f"  saved: {b(rest)} → {_loc_str(s.cur_loc)}")

    elif verb in ("save",):
        save_inventory(s)
        print(f"  inventory saved ({len(s.inventory)} items → {s.corpus.inv_file})")

    elif verb in ("load",):
        load_inventory(s)

    elif verb in ("drop","remove","del","delete"):
        if not rest:
            print("  usage: drop <name>")
        elif rest not in s.inventory:
            print(f"  {rest!r} not in inventory")
        else:
            del s.inventory[rest]
            print(f"  dropped: {rest}")

    elif verb in ("go","visit"):
        if not rest:
            print("  usage: go <name>  (see: inv)")
        elif rest not in s.inventory:
            print(f"  {rest!r} not in inventory  (see: inv)")
        else:
            goto_location(s, s.inventory[rest])

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
                tag   = gramm + (f" {sc}" if sc and sc!="indeclinable" else "")
                print(f"  {i:>3}.  {b(l):<32} {d(tag):<28} {total} tokens")
            print()
            s.last_list = [lambda s, l=l: _goto_lemma(s, l) for l,_ in results]

    elif verb in ("help","h","?"):
        print(__doc__)

    else:
        # try as direct lemma lookup
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

    print(f"\n{b('Ṛgveda Explorer')}")
    print(d("  1.1  to open the first hymn  ·  find soma  to search  ·  h for help"))
    print(d("  Text: VedaWeb / C-SALT project, University of Cologne — CC-licensed,"))
    print(d("  terms per source · vedaweb.uni-koeln.de\n"))
    s = S()
    load_inventory(s)
    tty = sys.stdout.isatty()
    while True:
        loc = s.ref or (f"{s.book}.{s.hymn}" if s.book else "")
        wrd = f"  [{s.word['lemma']}]" if s.word else ""
        prompt = f"\n{loc}{wrd} › " if loc else "\n› "
        try:
            cmd = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not tty:
            print(cmd)   # echo command so tee captures it
        if not handle(cmd, s):
            break
    save_inventory(s)


if __name__ == "__main__":
    main()
