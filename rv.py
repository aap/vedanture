#!/usr/bin/env python3
"""rv — Ṛgveda explorer

  Navigation
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

  Inventory
    keep <name>   save current place (name optional → inv1, inv2…)
    drop <name>   remove from inventory
    go <name>     navigate to saved place
    inv           list inventory

  Search
    find soma     fuzzy lemma search

  q             quit
"""

import sys, json, csv, unicodedata, difflib
from pathlib import Path
from collections import defaultdict

# optional: chant rendering
try:
    sys.path.insert(0, str(Path.home() / "rgveda_audio"))
    from ghanapati import processline, render_ascii as _render_ascii
    _CHANT_LINES = None   # ref "1.1.1" → [raw_line, ...]

    def _chant_index():
        global _CHANT_LINES
        if _CHANT_LINES is None:
            _CHANT_LINES = defaultdict(list)
            src = Path.home() / "rgveda_audio/rv_lines.txt"
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
        print("  chant module not available (needs ~/rgveda_audio/ghanapati.py)")

try:
    import readline
    readline.parse_and_bind("tab: complete")
    readline.set_history_length(1000)
except ImportError:
    pass

BASE    = Path(__file__).parent
TEI_DIR = BASE / "corpus/c-salt_vedaweb_tei"
HYMN_N  = {1:191,2:43,3:62,4:58,5:87,6:75,7:104,8:103,9:114,10:191}

# ── terminal ──────────────────────────────────────────────────────────────────

B  = "\033[1m"
D  = "\033[2m"
R  = "\033[0m"
HL = "\033[1;33m"    # highlighted form

def b(s):  return f"{B}{s}{R}"
def d(s):  return f"{D}{s}{R}"
def hl(s): return f"{HL}{s}{R}"

# ── data ──────────────────────────────────────────────────────────────────────

_PD = _CD = None
_BC: dict = {}

def paradigms():
    global _PD
    if _PD is None:
        d = {}
        for p in ("nouns","verbs","particles","pronouns"):
            d |= json.loads((BASE/"paradigms"/f"{p}.json").read_text())
        _PD = d
    return _PD

def concordance():
    global _CD
    if _CD is None:
        rows: dict = defaultdict(list)
        with open(BASE/"concordance.tsv") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                rows[row["lemma"]].append(row)
        _CD = dict(rows)
    return _CD

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
                if o.get(f"{GXID[:GXID.index('}')+1]}lang","") == "san-Latn-x-ISO-15919":
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
        lang = o.get(f"{{{GTEI}}}lang","") or o.get("lang","")
        if "ISO-15919" in lang:
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


def _lookup_gra_ids(lemma_str: str) -> list[str]:
    """Return GRA xml:ids for a lemma string."""
    ml  = _ml()
    idx = _gra_idx()
    ids = set()
    norm = _norm(lemma_str)
    for surface, data in ml.items():
        m  = data.get("id_matched")
        dl = data.get("lemma","")
        if m and (_norm(dl) == norm or _norm(surface) == norm):
            ids.update(m if isinstance(m, list) else [m])
    if not ids:
        for eid, entry in idx.items():
            if _norm(_orth_iso(entry)) == norm:
                ids.add(eid)
    return sorted(ids)


def show_gra(lemma_str: str, eid: str | None = None) -> str | None:
    """Display a GRA entry. Returns the eid shown (for state tracking)."""
    idx = _gra_idx()

    if eid is None:
        ids = _lookup_gra_ids(lemma_str)
        if not ids:
            print(f"  {d('no Grassmann entry found for')} {lemma_str}")
            return None
        eid = ids[0]   # show first; multiple homonyms are listed below

    entry = idx.get(eid)
    if entry is None:
        print(f"  {d('entry not found:')} {eid}")
        return None

    orth = _orth_iso(entry)
    n    = entry.get("n","?")
    sense = entry.find(GT("sense"))
    text  = _render_sense(sense) if sense is not None else "(no definition)"

    print(f"\n{b(orth)}  {d('GRA #'+n)}\n")
    for line in text.split("\n"):
        print(f"  {line}")

    # ── neighbouring entries ──────────────────────────────────────────────────
    neighbors = _gra_neighbors(eid, window=3)
    if neighbors:
        print(f"\n  {d('─── nearby ──────────────────────────')}")
        for nn, ne, no, nr, cur in neighbors:
            marker = b("→") if cur else " "
            print(f"  {marker} {d(str(nn)):>10}  {b(no) if cur else no}")

    # ── cross-references in text ──────────────────────────────────────────────
    prose = " ".join(sense.itertext()) if sense is not None else ""
    xrefs = _extract_xrefs(prose)
    if xrefs:
        print(f"\n  {d('─── see also ─────────────────────────')}")
        print("  " + "  ·  ".join(xrefs[:8]))

    print()
    return eid


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
        for src in ("griffith","geldner","macdonell"):
            lg = div.find(f'.//{T("lg")}[@source="{src}"]')
            if lg is not None:
                trans[src] = " ".join(" ".join(l.itertext()).strip()
                                      for l in lg.findall(T("l")))
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

RULE = "─" * 64

CASES   = ["NOM","ACC","INS","DAT","ABL","GEN","LOC","VOC",""]
NUMBERS = ["SG","DU","PL"]
TENSES  = ["PRS","IPRF","AOR","PRF","FUT","COND",""]
MOODS   = ["IND","IMP","SBJV","OPT","INJ","DES",""]
VOICES  = ["ACT","MED","PASS",""]
PERSONS = ["1","2","3",""]
T_NAME  = {"PRS":"present","IPRF":"imperfect","AOR":"aorist","PRF":"perfect",
           "FUT":"future","COND":"conditional","":""}
M_NAME  = {"IND":"indicative","IMP":"imperative","SBJV":"subjunctive",
           "OPT":"optative","INJ":"injunctive","DES":"desiderative","":""}
V_NAME  = {"ACT":"active","MED":"middle","PASS":"passive","":""}


def show_verse(ref, stanza):
    print(f"\n{b(ref)}   {d('—  ' + stanza['lines'][0] if stanza['lines'] else '')}")
    print()
    for line in stanza["lines"]:
        print(f"  {line}")
    print()
    for src, text in stanza["trans"].items():
        print(f"  {d('['+src+']')}  {text}")


def show_words(words):
    if not words: return
    cw = max(len(w["surface"]) for w in words) + 2
    cl = max(len(w["lemma"])   for w in words) + 2
    print()
    for i, w in enumerate(words, 1):
        feat = "  ".join(f"{k}={v}" for k,v in w["feats"].items())
        print(f"  {d(str(i)):>5}  {w['surface']:<{cw}} {d(w['lemma']):<{cl+6}} {feat}")


def show_paradigm(lemma):
    pd    = paradigms().get(lemma, {})
    gramm = pd.get("gramm",[])
    sc    = pd.get("stem_class","")
    total = sum(f["count"] for f in pd.get("forms",[]))
    print(f"\n{b(lemma)}  {d('  ·  '.join(p for p in [sc]+gramm if p))}  {d(str(total)+' tokens')}")
    print(f"  {RULE}")

    forms = pd.get("forms",[])
    idx: dict = defaultdict(list)

    if "root" in gramm:
        for f in forms:
            ft = f["features"]
            idx[(ft.get("tense",""),ft.get("mood",""),ft.get("voice",""),
                 ft.get("person",""),ft.get("number",""))].append((f["surface"],f["count"]))
        seen = set()
        for t in TENSES:
            for m in MOODS:
                for v in VOICES:
                    if (t,m,v) in seen or not any(k[:3]==(t,m,v) for k in idx): continue
                    seen.add((t,m,v))
                    label = " ".join(x for x in [T_NAME[t],M_NAME[m],V_NAME[v]] if x)
                    print(f"\n  {b(label)}")
                    nums  = [n for n in NUMBERS if any(k==(t,m,v,p,n) for k in idx for p in PERSONS)]
                    pers  = [p for p in PERSONS if any(k==(t,m,v,p,n) for k in idx for n in NUMBERS)]
                    cw    = 24
                    print(f"  {'':6}" + "".join(f"  {n:<{cw}}" for n in nums))
                    for p in pers:
                        row = f"  {p or '?':<6}"
                        for n in nums:
                            es   = idx.get((t,m,v,p,n),[])
                            cell = " / ".join(s for s,_ in sorted(es,key=lambda x:-x[1])[:2]) if es else "—"
                            row += f"  {cell:<{cw}}"
                        print(row)

    elif gramm and "invariable" not in gramm:
        for f in forms:
            ft = f["features"]
            idx[(ft.get("case",""),ft.get("number",""),ft.get("gender",""))].append(
                (f["surface"],f["count"]))
        nums = [n for n in NUMBERS if any(k[1]==n for k in idx)]
        cw   = 22
        print(f"\n  {'':8}" + "".join(f"  {n:<{cw}}" for n in nums))
        print(f"  {RULE}")
        for case in CASES:
            if not any(k[0]==case for k in idx): continue
            row = f"  {case or '(other)':<8}"
            for n in nums:
                m2 = []
                for gg in ("","M","F","N"): m2.extend(idx.get((case,n,gg),[]))
                cell = " / ".join(
                    (f"{s}({c})" if c>1 else s)
                    for s,c in sorted(m2,key=lambda x:-x[1])[:2]
                ) if m2 else "—"
                row += f"  {cell:<{cw}}"
            print(row)
    else:
        for f in forms[:30]:
            print(f"  {f['surface']:<22} {d(str(f['count']))}")
    print()


def show_concordance(lemma, surface=None):
    rows = concordance().get(lemma, [])
    if surface:
        rows  = [r for r in rows if r["surface"] == surface]
        title = f"{hl(surface)}  {d('(< '+lemma+')')}  ·  {b(str(len(rows)))} occurrences  {d('lem = all forms')}"
    else:
        title = f"{b('lemma '+lemma)}  ·  {b(str(len(rows)))} occurrences"
    rows = sorted(rows, key=lambda r: tuple(int(x) for x in r["ref"].split(".")))
    print(f"\n  {title}\n")
    col = max((len(r["ref"]) for r in rows), default=5) + 1
    for r in rows:
        print(f"  {d(r['ref']):<{col+8}}  {r['pada']}   {hl(r['surface']):<24}  {r['text']}")
    print()


# ── search ────────────────────────────────────────────────────────────────────

def _norm(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", s).lower().lstrip("√").rstrip("-~ ").strip()

def search(query, n=15):
    q   = _norm(query)
    all_= list(paradigms().items())
    nm  = {l: _norm(l) for l,_ in all_}
    ex, st, co, fz = [], [], [], []
    for l, pd in all_:
        v = nm[l]
        if v == q:           ex.append((l,pd))
        elif v.startswith(q): st.append((l,pd))
        elif q in v:          co.append((l,pd))
    if not (ex or st or co):
        close = set(difflib.get_close_matches(q, nm.values(), n=n, cutoff=0.6))
        fz = sorted([(l,pd) for l,pd in all_ if nm[l] in close],
                    key=lambda x: -difflib.SequenceMatcher(None,q,nm[x[0]]).ratio())
    return (ex+st+co+fz)[:n]


# ── state & REPL ──────────────────────────────────────────────────────────────

class S:
    def __init__(self):
        self.book = self.hymn = 0
        self.verses:    list      = []
        self.idx:       int       = -1
        self.words:     list      = []
        self.word:      dict|None = None
        self.word_num:  int       = 0
        self.expanded:  bool      = False
        self.history:   list      = []   # back-stack of location dicts
        self.inventory: dict      = {}   # name → location dict
        self.cur_loc:   dict|None = None # where we are now

    @property
    def ref(self):
        return self.verses[self.idx][0] if 0 <= self.idx < len(self.verses) else None

    @property
    def stanza(self):
        return self.verses[self.idx][1] if 0 <= self.idx < len(self.verses) else None


# ── location helpers ──────────────────────────────────────────────────────────

def _push(s, loc: dict):
    """Record current location in history before navigating away."""
    if s.cur_loc:
        s.history.append(s.cur_loc)
    s.cur_loc = loc


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
        b, h = int(ref.split(".")[0]), int(ref.split(".")[1])
        if b != s.book or h != s.hymn:
            go_hymn(s, b, h, _push_loc=False)
        idx = next((i for i,(r,_) in enumerate(s.verses) if r == ref), None)
        if idx is not None:
            go_verse(s, idx, _push_loc=False)
    elif k == "word":
        goto_location(s, {"kind": "verse", "ref": loc["ref"]})
        pick_word(s, loc["word_num"], _push_loc=False)
    elif k == "paradigm":
        show_paradigm(loc["lemma"])
        s.cur_loc = loc
    elif k == "concordance":
        show_concordance(loc["lemma"], loc.get("surface"))
        s.cur_loc = loc
    elif k == "dict":
        show_gra(loc["lemma"], loc.get("gra_id"))
        s.cur_loc = loc
    elif k == "chant":
        show_chant(loc["ref"])
        s.cur_loc = loc


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
    s.words, s.word, s.expanded = [], None, False
    n = len(s.verses)
    print(f"\n{b(f'RV {book}.{hymn}')}  {d(str(n)+' verses')}\n")
    for ref, st in s.verses:
        print(f"  {b(ref)}")
        for line in st['lines']:
            print(f"    {line}")
        print()
    print(d("  type a verse number (e.g. 3), or n to step through"))


def go_verse(s, idx, _push_loc=True):
    s.idx      = idx
    s.words    = s.stanza.get("words",[]) if s.stanza else []
    s.word     = None
    s.expanded = False
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
    print(d("  par · conc · lem"))


def handle(cmd: str, s: S) -> bool:
    cmd = cmd.strip()
    if not cmd: return True

    parts = cmd.split(".")
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

    # bare number → word selection (after x) or verse navigation (at hymn level)
    if cmd.isdigit():
        n = int(cmd)
        if s.expanded and s.words:
            pick_word(s, n)
        elif s.verses:
            if 1 <= n <= len(s.verses):
                go_verse(s, n-1)
            else:
                print(f"  verse out of range (1–{len(s.verses)})  ·  use x first to select words")
        else:
            print("  open a hymn first (e.g. 1.1)")
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
            s.idx, s.expanded, s.word = -1, False, None
            s.cur_loc = {"kind": "hymn", "book": s.book, "hymn": s.hymn}
            n = len(s.verses)
            print(f"\n{b(f'RV {s.book}.{s.hymn}')}  {d(str(n)+' verses')}\n")
            for ref, st in s.verses:
                print(f"  {b(ref)}")
                for line in st['lines']:
                    print(f"    {line}")
                print()
        else:
            print("  no hymn open")

    elif verb in ("x","expand","words","w"):
        if s.words:
            show_words(s.words)
            s.expanded = True
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
            show_paradigm(s.word["lemma"])
        else: print("  select a word first (x, then a number)")

    elif verb in ("conc","concordance","c"):
        if s.word:
            _push(s, {"kind": "concordance", "lemma": s.word["lemma"], "surface": s.word["surface"]})
            show_concordance(s.word["lemma"], s.word["surface"])
        else: print("  select a word first")

    elif verb in ("lem","lemma","l"):
        if s.word:
            _push(s, {"kind": "concordance", "lemma": s.word["lemma"]})
            show_concordance(s.word["lemma"])
        else: print("  select a word first")

    elif verb in ("chant","acc","melody"):
        if s.ref:
            _push(s, {"kind": "chant", "ref": s.ref})
            show_chant(s.ref)
        else: print("  open a verse first")

    elif verb in ("def","dict","gra","d"):
        target = rest or (s.word["lemma"] if s.word else None)
        if target:
            _push(s, {"kind": "dict", "lemma": target})
            gra_id = show_gra(target)
            if gra_id: s.cur_loc["gra_id"] = gra_id
        else: print("  select a word first, or: def soma")

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
        print(f"  inventory saved ({len(s.inventory)} items → {INV_FILE})")

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
        results = search(rest)
        if not results:
            print(f"  nothing found for {rest!r}")
        else:
            print()
            for i,(l,pd) in enumerate(results, 1):
                sc    = pd.get("stem_class","")
                gramm = "/".join(pd.get("gramm",[]))
                total = sum(f["count"] for f in pd.get("forms",[]))
                tag   = gramm + (f" {sc}" if sc and sc!="indeclinable" else "")
                print(f"  {d(str(i)+'.'):>6}  {b(l):<30} {d(tag):<26} {total} tokens")
            print(d("\n  type a lemma to look it up directly"))

    elif verb in ("help","h","?"):
        print(__doc__)

    else:
        # try as direct lemma lookup
        results = search(cmd)
        if results and _norm(results[0][0]) == _norm(cmd):
            l, _ = results[0]
            s.word = {"surface":l, "lemma":l, "gramm":"", "feats":{}}
            show_paradigm(l)
        elif results:
            print(f"\n  did you mean one of:")
            for l2,pd2 in results[:6]:
                print(f"    {b(l2):<34} {sum(f['count'] for f in pd2.get('forms',[]))} tokens")
        else:
            print(f"  {d(repr(cmd))} — unknown  (h for help)")

    return True


INV_FILE = Path.home() / ".vedanture_inventory.json"

def load_inventory(s: S) -> None:
    if INV_FILE.exists():
        try:
            s.inventory = json.loads(INV_FILE.read_text())
            if s.inventory:
                print(d(f"  inventory loaded ({len(s.inventory)} items — type inv to see)"))
        except Exception:
            pass

def save_inventory(s: S) -> None:
    if s.inventory:
        INV_FILE.write_text(json.dumps(s.inventory, ensure_ascii=False, indent=2))


def main():
    print(f"\n{b('Ṛgveda Explorer')}")
    print(d("  1.1  to open the first hymn  ·  find soma  to search  ·  h for help\n"))
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
