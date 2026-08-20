#!/usr/bin/env python3
"""
build_altdeutsch — convert the Referenzkorpus Altdeutsch (DDD-AD v1.2)
Excel export into corpus/altdeutsch/{tokens.tsv, verses.tsv, lexicon.json,
works.json}.  See docs/altdeutsch_spec.md for the target format.

Usage:
  python3 build_altdeutsch.py [--src DIR] [--out DIR]

  --src  source Excel tree (default: /u/aap/lib/ad/excel/DDD-AD-1.2)
  --out  output directory  (default: corpus/altdeutsch)
"""

import sys, re, json, csv, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict, Counter

DEFAULT_SRC = Path("/u/aap/lib/ad/excel/DDD-AD-1.2")
DEFAULT_OUT = Path(__file__).parent / "corpus" / "altdeutsch"

# ── minimal stdlib .xlsx reader ─────────────────────────────────────────────
# No openpyxl/pandas available (externally-managed env blocks pip install);
# a plain zipfile + ElementTree reader over sharedStrings.xml + sheet1.xml
# is all we need for flat data sheets.

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
T_TAG = f"{{{NS}}}t"
ROW_TAG = f"{{{NS}}}row"
V_TAG = f"{{{NS}}}v"
IS_TAG = f"{{{NS}}}is"
SI_TAG = f"{{{NS}}}si"


def _col_to_idx(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def read_xlsx_rows(path: Path) -> list[list[str | None]]:
    """One list per row, each padded to the sheet's max column width.
    Cells are addressed by column letter, not row-relative position —
    rows are ragged (trailing blank cells are simply absent)."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{{{NS}}}si"):
                shared.append("".join(t.text or "" for t in si.iter(T_TAG)))
        sheet_names = sorted(n for n in names if n.startswith("xl/worksheets/") and n.endswith(".xml"))
        if not sheet_names:
            return []
        sheet = ET.fromstring(z.read(sheet_names[0]))
        raw_rows: list[dict[int, str | None]] = []
        max_idx = -1
        for row in sheet.iter(ROW_TAG):
            cells: dict[int, str | None] = {}
            for c in row:
                ref = c.get("r")
                if not ref:
                    continue
                idx = _col_to_idx(ref)
                ctype = c.get("t")
                v = c.find(V_TAG)
                val = v.text if v is not None else None
                if ctype == "s" and val is not None:
                    val = shared[int(val)]
                elif ctype == "inlineStr":
                    isnode = c.find(IS_TAG)
                    val = "".join(t.text or "" for t in isnode.iter(T_TAG)) if isnode is not None else ""
                cells[idx] = val
                max_idx = max(max_idx, idx)
            raw_rows.append(cells)
        width = max_idx + 1
        return [[cells.get(i) for i in range(width)] for cells in raw_rows]


HEADER_SYNONYMS = {"infection": "inflection"}


def header_map(header_row: list[str | None]) -> dict[str, int]:
    hm: dict[str, int] = {}
    for i, h in enumerate(header_row):
        if not h:
            continue
        h = HEADER_SYNONYMS.get(h, h)
        if h not in hm:          # duplicate column name → first occurrence wins
            hm[h] = i
    return hm


# ── .meta reader ─────────────────────────────────────────────────────────────

def read_meta(path: Path) -> dict[str, str]:
    d: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


# ── dialect / scribal-school groups ──────────────────────────────────────────
# Ordered roughly north to south (approximate — dialect regions don't line up
# on neat latitude bands, this just avoids e.g. Bairisch/Alemannisch, the two
# southernmost groups, sitting near the top).

GROUPS = [
    ("as",     "Altsächsisch"),
    ("anfrk",  "Altniederfränkisch"),
    ("mfrk",   "Mittelfränkisch"),
    ("rhfrk",  "Rheinfränkisch"),
    ("ofrk",   "Ostfränkisch (Fulda)"),
    ("srhfrk", "(Süd-)Rheinfränkisch (Weißenburg)"),
    ("bair",   "Bairisch"),
    ("alem",   "Alemannisch (St. Gallen / Reichenau)"),
    ("unloc",  "Unlokalisiert"),
]

# The source .meta occasionally has a `language` field that fights its own
# (language_area, dialect) pair — most reliably for the Wachtendonck Psalms,
# tagged language=as. (Old Saxon) but language_area=obd., dialect=mfrk., a
# self-contradictory combination (mfrk. is a Mitteldeutsch dialect, not
# Oberdeutsch). Standard historical-linguistic classification treats this
# text as Altniederfränkisch; verified this is the only work in the corpus
# with an internally inconsistent area/dialect pair (see conversation record
# for the audit), so this is a narrow, documented correction, not a general
# rule that could paper over other cases.
GROUP_OVERRIDES = {
    "Altniederfränkische Psalmen": "anfrk",
}


def group_key(meta: dict[str, str]) -> str:
    title = meta.get("text", "").strip()
    if title in GROUP_OVERRIDES:
        return GROUP_OVERRIDES[title]
    lang = meta.get("language", "")
    la = meta.get("language_area", "")
    di = meta.get("dialect", "")
    # language_area/dialect are the fields meant for dialect geography —
    # check them before falling back to the coarser `language` prefix, else
    # e.g. language="as.ags" (Sächsisches Taufgelöbnis) would shadow its own
    # correctly-set language_area="anfrk."
    if la == "anfrk.":
        return "anfrk"
    if la == "nd.":
        return "as"
    if la == "obd.":
        return {"bair.": "bair", "alem.": "alem", "ofrk.": "ofrk", "srhfrk.": "srhfrk"}.get(di, "unloc")
    if la == "md.":
        return {"rhfrk.": "rhfrk", "mfrk.": "mfrk"}.get(di, "unloc")
    if lang.startswith("as."):
        return "as"
    if lang.startswith("anfrk"):
        return "anfrk"
    return "unloc"


def parse_time(time_str: str) -> float | None:
    """'9.1' -> 9.1 (century 9, first half — sorts before 9.2) · '8-9' -> 8.0
    (range: sort by its start) · '10' -> 10.0 · 'M: 9.2; C: 10.2' -> 9.2 (the
    first/earliest date mentioned, for multi-manuscript works like Heliand).
    None if the field is empty or has no recognizable date."""
    if not time_str:
        return None
    m = re.search(r"(\d+)(?:\.(\d))?", time_str)
    if not m:
        return None
    century = int(m.group(1))
    half = int(m.group(2)) if m.group(2) else 0
    return century + half * 0.1


# ── pos mapping ───────────────────────────────────────────────────────────────

def map_pos(raw: str | None) -> str:
    p = (raw or "").split("¦")[0].strip()
    if p in ("$.", "$,", "$("):
        return "punct"
    if p.startswith("NE"):
        return "name"
    if p.startswith("NA"):
        return "noun"
    if p.startswith("ADJ"):
        return "adj"
    if p.startswith(("VV", "VA", "VM")):
        return "verb"
    if p.startswith(("PPER", "DPOS", "DD", "DI", "PI", "PW", "PRF")):
        return "pron"
    if p.startswith(("ADV", "DW", "PAV")):
        return "adv"
    if p.startswith("AP"):
        return "prep"
    if p.startswith("KO"):
        return "conj"
    if p.startswith("PTK"):
        return "ptcl"
    if p.startswith("CARD"):
        return "num"
    if p.startswith("ITJ"):
        return "interj"
    return ""


# ── inflection decoder ────────────────────────────────────────────────────────

GENDER_MAP = {"MASC": "M", "FEM": "F", "NEUT": "N"}
TENSE_MAP = {"PRES": "PRS", "PAST": "PST", "PERF": "PRF"}
CASE_SET = {"NOM", "ACC", "DAT", "GEN", "ABL", "VOC"}
NUMBER_SET = {"SG", "PL", "DU"}
PERSON_SET = {"1", "2", "3"}
MOOD_SET = {"IND", "SUBJ", "IMP"}
VOICE_SET = {"ACT", "DEP"}
DEGREE_SET = {"POS", "COMP", "SUP"}
STRENGTH_SET = {"ST", "WK"}


def decode_inflection(raw: str | None) -> dict:
    raw = (raw or "").split("¦")[0].strip()
    if not raw:
        return {}
    feats: dict[str, str] = {}
    for tok in raw.split("_"):
        tok = tok.rstrip("?").strip()
        if not tok:
            continue
        if tok in GENDER_MAP:
            feats["gender"] = GENDER_MAP[tok]
        elif tok in CASE_SET:
            feats["case"] = tok
        elif tok in NUMBER_SET:
            feats["number"] = tok
        elif tok in PERSON_SET:
            feats["person"] = tok
        elif tok in TENSE_MAP:
            feats["tense"] = TENSE_MAP[tok]
        elif tok in MOOD_SET:
            feats["mood"] = tok
        elif tok in VOICE_SET:
            feats["voice"] = tok
        elif tok in DEGREE_SET:
            feats["degree"] = tok
        elif tok in STRENGTH_SET:
            feats["strength"] = tok
    return feats


def build_features(pos_raw: str | None, inflection_raw: str | None) -> dict:
    feats = decode_inflection(inflection_raw)
    p = (pos_raw or "").split("¦")[0].strip()
    if p.startswith(("VVINF", "VAINF", "VMINF")):
        feats.setdefault("mood", "INF")
    elif p.startswith(("VVPP", "VAPP", "VMPP")):
        feats.setdefault("tense", "PST")
        feats.setdefault("voice", "ACT")
    elif p.startswith(("VVPS", "VAPS", "VMPS")):
        feats.setdefault("tense", "PRS")
        feats.setdefault("voice", "ACT")
    return feats


def _sanitize_section(s: str) -> str:
    return s.replace(".", "-").replace(" ", "-")


def _first_alt(s: str) -> str:
    """This corpus joins ambiguous/alternative readings with '¦' in many
    columns (pos, posLemma, lemma, inflectionClass, translation) — take
    the first reading as canonical, consistently, everywhere."""
    return s.split("¦")[0].strip() if s else s


def _natural_key(path: Path):
    """Numeric-aware sort key so 'T_Tat2' sorts before 'T_Tat10'
    (plain string sort would put T_Tat100 right after T_Tat10)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman_to_int(s: str) -> int | None:
    s = s.upper()
    if not s or any(ch not in _ROMAN_VALUES for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VALUES[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def _section_sort_key(sec: str):
    """Sections are plain numbers ('1', '2', ...), roman numerals (e.g.
    Monseer Fragmente's 'I'..'XLI' — plain string sort would put 'II'
    before 'IX' before 'V'), or filename-derived ids where chapter-based
    numbering collided across the work (see compute_sections). Numeric
    and roman forms sort by value; anything else falls back to alphabetic
    so the order stays at least deterministic."""
    if sec.isdigit():
        return (0, int(sec), "")
    r = _roman_to_int(sec)
    if r is not None:
        return (0, r, "")
    return (1, 0, sec)


# ── work discovery ────────────────────────────────────────────────────────────

class WorkGroup:
    def __init__(self, work_id: str, meta: dict, files: list[Path]):
        self.work_id = work_id
        self.meta = meta
        self.files = files   # sorted xlsx paths


def find_meta_for(xlsx_path: Path) -> Path | None:
    own = xlsx_path.with_suffix(".meta")
    if own.exists():
        return own
    dir_meta = xlsx_path.parent / (xlsx_path.parent.name + ".meta")
    if dir_meta.exists():
        return dir_meta
    return None


def discover_works(src: Path) -> tuple[list[WorkGroup], list[WorkGroup]]:
    """Returns (vernacular_works, latin_works)."""
    used_ids: set[str] = set()

    def make_id(candidate: str) -> str:
        candidate = candidate.strip().strip("_") or "Work"
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
        i = 2
        while f"{candidate}-{i}" in used_ids:
            i += 1
        wid = f"{candidate}-{i}"
        used_ids.add(wid)
        return wid

    vern: list[WorkGroup] = []
    lat: list[WorkGroup] = []

    for d in sorted(p for p in src.iterdir() if p.is_dir()):
        xlsx_files = sorted((f for f in d.glob("*.xlsx") if not f.name.startswith("~$")), key=_natural_key)
        # bucket files by title (not by .meta path) so multi-file "Kleinere"
        # texts that carry one .meta per .xlsx but share a title (e.g. the
        # Wachtendonck Psalms, the Freckenhorster Heberegister) still merge
        # into one work with many sections
        groups: dict[str, list[Path]] = defaultdict(list)
        metas: dict[str, dict] = {}
        mps: dict[str, Path] = {}
        for f in xlsx_files:
            mp = find_meta_for(f)
            if mp is None:
                continue
            meta = read_meta(mp)
            if "topic" not in meta:          # bare collection-label placeholder
                continue
            title = meta.get("text", mp.stem)
            groups[title].append(f)
            metas[title] = meta             # representative meta (content is
            mps[title] = mp                 # identical across a title group)

        for title, files in groups.items():
            files = sorted(files, key=_natural_key)
            meta = metas[title]
            mp = mps[title]
            is_dir_level = mp.name == d.name + ".meta"
            if is_dir_level:
                candidate = d.name
                if candidate.startswith("DDD-AD-"):
                    candidate = candidate[len("DDD-AD-"):]
                if candidate.startswith("Z-"):
                    candidate = candidate[2:]
            else:
                candidate = files[0].stem.split("_")[0]
            wid = make_id(candidate)
            wg = WorkGroup(wid, meta, files)
            if meta.get("language", "").strip() == "lat.":
                lat.append(wg)
            else:
                vern.append(wg)

    return vern, lat


# ── conversion ────────────────────────────────────────────────────────────────

def _chapter_value(rows: list[list], ci: int) -> str | None:
    for r in rows[1:]:
        if ci < len(r) and r[ci]:
            return str(r[ci]).strip()
    return None


def _filename_section(f: Path) -> str:
    return _sanitize_section(f.stem)


def compute_sections(wg: WorkGroup, file_rows: dict[Path, list[list]],
                      file_hm: dict[Path, dict[str, int]]) -> dict[Path, str]:
    """One section id per file, guaranteed unique within the work.

    Prefers the sheet's own 'chapter' column (nicer ids: '1'..'9', roman
    numerals, ...), with a fold-in of any outer numeral the filename
    carries when the chapter column only encodes an intra-book chapter
    (Otfrid: book.chapter, both books restart at 1). But the 'chapter'
    column's meaning varies a lot across this corpus — for some works
    (e.g. Murbacher Hymnen, one file per hymn) it is a constant, not a
    locator at all. If chapter-based ids collide anywhere in the work,
    the whole work falls back to filename-derived ids instead, rather
    than mixing styles file-by-file.
    """
    if len(wg.files) == 1:
        return {wg.files[0]: "1"}

    candidates: dict[Path, str] = {}
    for f in wg.files:
        hm = file_hm.get(f, {})
        rows = file_rows.get(f, [])
        sec = None
        if "chapter" in hm:
            chapter_val = _chapter_value(rows, hm["chapter"])
            if chapter_val is not None:
                digit_runs = re.findall(r"\d+", f.stem)
                if len(digit_runs) > 1:
                    try:
                        if int(digit_runs[-1]) == int(chapter_val):
                            sec = "-".join(digit_runs)
                    except ValueError:
                        pass
                if sec is None:
                    sec = chapter_val
        if sec is None:
            sec = _filename_section(f)
        candidates[f] = sec

    if len(set(candidates.values())) == len(candidates):
        return candidates
    return {f: _filename_section(f) for f in wg.files}


def convert_work(wg: WorkGroup) -> tuple[list[dict], dict[str, list[str]]]:
    """Returns (token_rows, verse_edition_tokens) for one work.
    verse_edition_tokens: ref -> [(text_or_None_marker_for_continuation)]
    Actually returns ref -> list of (kind, value) display units; see caller."""
    token_rows: list[dict] = []
    verse_units: dict[str, list[tuple[str, str]]] = defaultdict(list)  # ref -> [(mode, text)]

    file_rows: dict[Path, list[list]] = {}
    file_hm: dict[Path, dict[str, int]] = {}
    for f in wg.files:
        try:
            rows = read_xlsx_rows(f)
        except Exception as e:
            print(f"    ! failed to read {f}: {e}", file=sys.stderr)
            continue
        if not rows:
            continue
        hm = header_map(rows[0])
        if "text" not in hm:
            continue
        file_rows[f] = rows
        file_hm[f] = hm

    sections = compute_sections(wg, file_rows, file_hm)

    for f in wg.files:
        rows = file_rows.get(f)
        if rows is None:
            continue
        hm = file_hm[f]
        section = sections[f]

        # pick the verse-locator tier for this file
        if "verse" in hm:
            tier = "verse"
        elif "subchapter" in hm:
            tier = "subchapter"
        elif "line_m" in hm:
            tier = "line_m"
        elif "line" in hm:
            tier = "line"
        else:
            tier = None

        # cur_tier_verse tracks the forward-filled locator column value, once
        # one has actually appeared. Until then (or for the whole file, if
        # the column never carries a real value at all — e.g. the Notker
        # Boethius page/line-only files) a punctuation-based sentence
        # counter bridges the gap, so every token still lands on a verse.
        cur_tier_verse: str | None = None
        sent_counter = 1

        ei, ti, li, pli, pi, icli, ici, ci, doci, tri, ifi, langi = (
            hm.get("edition"), hm.get("text"), hm.get("lemma"), hm.get("posLemma"),
            hm.get("pos"), hm.get("inflectionClassLemma"), hm.get("inflectionClass"),
            hm.get("clause"), hm.get("document"), hm.get("translation"),
            hm.get("inflection"), hm.get("lang"),
        )
        tier_i = hm.get(tier) if tier else None

        for r in rows[1:]:
            def cell(i):
                return r[i].strip() if i is not None and i < len(r) and r[i] else ""

            text = cell(ti)
            if not text:
                continue

            if tier_i is not None:
                v = cell(tier_i)
                if v and v != "n/a":
                    cur_tier_verse = v

            pos_raw = cell(pi)
            verse_id = cur_tier_verse if cur_tier_verse is not None else f"s{sent_counter}"
            if cur_tier_verse is None and pos_raw == "$.":
                sent_counter += 1

            ref = f"{wg.work_id}.{section}.{verse_id}"

            edition = cell(ei)
            pos = map_pos(pos_raw)
            feats = build_features(pos_raw, cell(ifi))
            # lemma/stem_class/gloss carry the same '¦'-joined-alternatives
            # convention as pos/inflection (ambiguous annotation) — take
            # the first reading as canonical everywhere, consistently,
            # else identical lemmata fragment into spurious duplicates
            # (e.g. "quedan" vs "quedan¦quedan¦quedan").
            lemma = _first_alt(cell(li))

            token_rows.append({
                "ref": ref,
                "surface": text,
                "lemma": lemma,
                "pos": pos,
                "features": json.dumps(feats, ensure_ascii=False, separators=(",", ":")),
                "stem_class": _first_alt(cell(ici)) or _first_alt(cell(icli)),
                "edition": edition,
                "clause": cell(ci),
                "lang": cell(langi),
                "_gloss": _first_alt(cell(tri)),
            })

            mode = "new" if edition else "cont"
            verse_units[ref].append((mode, edition if edition else text, pos))

    return token_rows, verse_units


def render_verse_text(units: list[tuple[str, str, str]]) -> str:
    """Join the diplomatic ('edition') spelling of each manuscript word in
    order. A manuscript word occasionally gets split across several
    analysis tokens (a clitic or compound segmented for tagging, e.g.
    'nihabe' -> ni + habe); only the first of those tokens carries the
    full diplomatic spelling in `edition` ('new'), the rest ('cont') are
    already fully represented by it and contribute nothing further here —
    concatenating their own `text` on top would double up the spelling
    (e.g. 'nihabe' + 'habe' -> 'nihabehabe')."""
    parts: list[str] = []
    for mode, text, pos in units:
        if mode == "cont":
            continue
        if not parts:
            parts.append(text)
        elif pos == "punct":
            parts[-1] = parts[-1] + text
        else:
            parts.append(text)
    return " ".join(parts)


# ── Latin parallel alignment (best effort) ────────────────────────────────────

LATIN_PAIRS = {
    "Isidor": "Isidor_Latein",
    "Tatian": "Tatian_Latein",
    "Benediktiner_Regel": "Benediktiner_Regel_Latein",
    "Murbacher_Hymnen": "Murbacher_Hymnen_Latein",
}


def build_latin_index(lat_works: list[WorkGroup]) -> dict[str, dict[str, str]]:
    """dir-cleaned-name -> {section -> joined latin text}"""
    idx: dict[str, dict[str, str]] = {}
    for wg in lat_works:
        file_rows: dict[Path, list[list]] = {}
        file_hm: dict[Path, dict[str, int]] = {}
        for f in wg.files:
            try:
                rows = read_xlsx_rows(f)
            except Exception:
                continue
            if not rows:
                continue
            hm = header_map(rows[0])
            if "text" not in hm:
                continue
            file_rows[f] = rows
            file_hm[f] = hm

        sections = compute_sections(wg, file_rows, file_hm)
        by_section: dict[str, list[str]] = defaultdict(list)
        for f, rows in file_rows.items():
            hm = file_hm[f]
            section = sections[f]
            ti = hm.get("text")
            for r in rows[1:]:
                text = r[ti].strip() if ti is not None and ti < len(r) and r[ti] else ""
                if text:
                    by_section[section].append(text)
        idx[wg.work_id] = {sec: " ".join(toks) for sec, toks in by_section.items()}
    return idx


# ── main build ────────────────────────────────────────────────────────────────

def build(src: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    print(f"scanning {src} …")
    vern_works, lat_works = discover_works(src)
    print(f"  {len(vern_works)} vernacular works, {len(lat_works)} Latin-parallel works")

    latin_idx = build_latin_index(lat_works)

    all_tokens: list[dict] = []
    all_verse_units: dict[str, list[tuple[str, str, str]]] = {}
    works_meta: dict[str, dict] = {}
    groups_used: set[str] = set()
    n_errors = 0

    for i, wg in enumerate(vern_works, 1):
        try:
            tokens, verse_units = convert_work(wg)
        except Exception as e:
            print(f"  ! error converting work {wg.work_id}: {e}", file=sys.stderr)
            n_errors += 1
            continue
        all_tokens.extend(tokens)
        for ref, units in verse_units.items():
            all_verse_units.setdefault(ref, []).extend(units)

        sections = list(dict.fromkeys(t["ref"].split(".", 2)[1] for t in tokens))
        if len(sections) < len(wg.files):
            print(f"  ! {wg.work_id}: {len(wg.files)} files but only "
                  f"{len(sections)} distinct sections — possible section collision",
                  file=sys.stderr)
        sections.sort(key=_section_sort_key)
        gk = group_key(wg.meta)
        groups_used.add(gk)
        works_meta[wg.work_id] = {
            "title": wg.meta.get("text", wg.work_id),
            "group": gk,
            "topic": wg.meta.get("topic", ""),
            "form": wg.meta.get("form", ""),
            "depository": wg.meta.get("depository", ""),
            "time": wg.meta.get("time", ""),
            "time_sort": parse_time(wg.meta.get("time", "")),
            "sections": sections,
        }
        if i % 20 == 0 or i == len(vern_works):
            print(f"  converted {i}/{len(vern_works)} works …", end="\r", flush=True)
    print()

    # ── lexicon ───────────────────────────────────────────────────────────────
    print("building lexicon …")
    gloss_counter: dict[str, Counter] = defaultdict(Counter)
    lemma_pos: dict[str, Counter] = defaultdict(Counter)
    lemma_sc: dict[str, Counter] = defaultdict(Counter)
    for t in all_tokens:
        lemma = t["lemma"]
        if not lemma:
            continue
        if t["_gloss"]:
            gloss_counter[lemma][t["_gloss"]] += 1
        if t["pos"]:
            lemma_pos[lemma][t["pos"]] += 1
        if t["stem_class"]:
            lemma_sc[lemma][t["stem_class"]] += 1

    lexicon = {}
    for lemma in lemma_pos.keys() | gloss_counter.keys():
        gloss = gloss_counter[lemma].most_common(1)
        pos = lemma_pos[lemma].most_common(1)
        sc = lemma_sc[lemma].most_common(1)
        lexicon[lemma] = {
            "pos": pos[0][0] if pos else "",
            "stem_class": sc[0][0] if sc else "",
            "gloss_de": gloss[0][0] if gloss else "",
            "notes": "",
        }

    # ── write tokens.tsv ─────────────────────────────────────────────────────
    print("writing tokens.tsv …")
    tok_path = out / "tokens.tsv"
    with open(tok_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "ref", "surface", "lemma", "pos", "features", "stem_class",
            "edition", "clause", "lang",
        ], delimiter="\t")
        w.writeheader()
        for t in all_tokens:
            w.writerow({k: t[k] for k in w.fieldnames})

    # ── write verses.tsv ─────────────────────────────────────────────────────
    print("writing verses.tsv …")
    ver_path = out / "verses.tsv"
    with open(ver_path, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["ref", "text", "parallel", "translation"])
        latin_attached: set[tuple[str, str]] = set()
        for ref, units in all_verse_units.items():
            text = render_verse_text(units)
            work_id, section, _ = ref.split(".", 2)
            parallel = ""
            lat_wid = LATIN_PAIRS.get(work_id)
            if lat_wid and (work_id, section) not in latin_attached:
                parallel = latin_idx.get(lat_wid, {}).get(section, "")
                if parallel:
                    latin_attached.add((work_id, section))
            w.writerow([ref, text, parallel, ""])

    # ── write lexicon.json ───────────────────────────────────────────────────
    print("writing lexicon.json …")
    (out / "lexicon.json").write_text(
        json.dumps(lexicon, ensure_ascii=False, separators=(",", ":")))

    # ── write works.json ─────────────────────────────────────────────────────
    print("writing works.json …")
    groups_out = [{"key": k, "label": lbl} for k, lbl in GROUPS if k in groups_used]
    (out / "works.json").write_text(json.dumps(
        {"groups": groups_out, "works": works_meta},
        ensure_ascii=False, indent=1))

    # ── validation summary ───────────────────────────────────────────────────
    print()
    print("── summary ──────────────────────────────────")
    print(f"  works:   {len(works_meta)}")
    print(f"  tokens:  {len(all_tokens)}")
    print(f"  verses:  {len(all_verse_units)}")
    print(f"  lexicon: {len(lexicon)} lemmata")
    print(f"  errors:  {n_errors}")
    by_group = Counter(w["group"] for w in works_meta.values())
    for k, lbl in GROUPS:
        if by_group.get(k):
            print(f"    {lbl:<40} {by_group[k]:>4} works")


def main():
    args = sys.argv[1:]
    src, out = DEFAULT_SRC, DEFAULT_OUT
    i = 0
    while i < len(args):
        if args[i] == "--src":
            src = Path(args[i+1]); i += 2
        elif args[i] == "--out":
            out = Path(args[i+1]); i += 2
        else:
            i += 1
    build(src, out)


if __name__ == "__main__":
    main()
