# Altdeutsch Corpus Conversion Spec

Describes what `build_altdeutsch.py` produces from the *Referenzkorpus
Altdeutsch* (DDD-AD v1.2, Excel export) so the shared explorer engine
(`explorer.py`) and the generic derived-data builder (`build_corpus.py`)
can drive it unchanged, the same way they already drive the Gothic module
(see `docs/gothic_spec.md`, which this spec mirrors in format, but *not*
in how the data is distributed — see §License).

---

## §License

The DDD-AD corpus is **not** openly licensed. Its own access page states:

> Copyright (c) 2023, Institut für deutsche Sprache und Linguistik, HU
> Berlin; alle Rechte vorbehalten [all rights reserved]
> — https://www.deutschdiachrondigital.de/rea/zugang/ (checked 2026-08)

"Free to use without registration" there describes browsing their own
ANNIS search interface, not a grant to redistribute exports. No LICENSE,
README, or citation file ships with the Excel or graphANNIS downloads
either. Treat both the raw Excel export and everything
`build_altdeutsch.py` derives from it as **not for redistribution** —
specifically:

- **Nothing under `corpus/altdeutsch/` is committed to this repo.** The
  whole directory is gitignored (unlike `corpus/gothic/`, where the
  tracked `tokens.tsv`/etc. *are* the intended distribution mechanism).
- To run this module on another machine, get the source Excel export onto
  it yourself (outside of git — e.g. `rsync`/`scp` directly, or a copy of
  `corpus/altdeutsch/` once already converted) and run the build steps
  below locally there. Don't publish either the raw export or the
  converted `tokens.tsv`/`verses.tsv`/`lexicon.json`/`works.json`.
- Before serving `altdeutschweb.py` publicly (the way `vedanture`/
  `gothicweb.py` are), that's worth a deliberate decision, not a default —
  either confirm reuse terms with HU Berlin or keep the deployment
  access-restricted.

### Getting the source data

The Excel export used here (DDD-AD v1.2) currently lives, extracted, at
`/u/aap/lib/ad/excel/DDD-AD-1.2` (from `/u/aap/lib/ad/excel-v1.2.zip`);
there's also a graphANNIS/GraphML export at `/u/aap/lib/ad/graphannis-v1.2.zip`
(not what `build_altdeutsch.py` reads, but the same underlying corpus, in
case a future conversion wants richer structure than the flat Excel sheets
carry). To re-obtain it or check current terms, the project's own page is
https://www.deutschdiachrondigital.de/rea/zugang/ — that's also where the
license wording in §License above was checked.

---

## Target layout

```
corpus/altdeutsch/                  (gitignored — see §License)
  tokens.tsv        one row per token — primary input for all build steps
  verses.tsv        one row per verse — text + optional parallel / translation
  lexicon.json       dictionary headwords with glosses
  works.json         hierarchy metadata (dialect groups → works → sections)
```

`build_corpus.py corpus/altdeutsch` (unmodified, generic) then writes,
alongside these:

```
corpus/altdeutsch/
  concordance.tsv   (generated)
  paradigms/        (generated)
  gravity.json      (generated)
```

Only the *code* (`build_altdeutsch.py`, `altdeutsch.py`,
`altdeutschweb.py`, this spec) is tracked in the repo. The source Excel
tree (`/u/aap/lib/ad/excel/DDD-AD-1.2`, 1944 `.xlsx` files) and everything
under `corpus/altdeutsch/` stay local to whichever machine you put them
on.

---

## Source shape (as found)

Each `.xlsx` has one sheet, one row per token. Header columns vary (53
distinct shapes across the corpus) but always include a common core:

`edition, text, lang, lemma, posLemma, pos, inflectionClassLemma,
inflectionClass, clause, document, translation, inflection`

plus a variable subset of locator columns: `chapter, subchapter, verse,
line, line_m, writer, page, rhyme`.

- `document` / `chapter` / `subchapter` / `verse` are forward-fill-once:
  populated on the first row of a new reference, blank on continuation
  rows.
- `lang` marks the *token's* actual language (`goh` = Old High German,
  `osx` = Old Saxon, `lat` = Latin, `lat-osx`/mixed for a few rune-name
  glosses). Interlinear/mixed texts (Otfrid, Tatian, Isidor) freely
  interleave Latin lemmata/headings with vernacular text in the same file.
- `edition` is the diplomatic manuscript word; `text` is the token as
  segmented for analysis. A clitic/compound split for analysis has
  `edition` on its first token only (continuation tokens: `edition=None`).
- `inflection` is a `_`-joined bag of morphological tags, **order not
  fixed** across POS categories, sometimes with a trailing `?` (uncertain
  reading) or a whole alternate reading joined by `¦` (ambiguous
  annotation — corpus convention, not a typo).
- Sentence-final punctuation is consistently tagged `pos=$.` (STTS
  convention; `$,` = comma, `$(` = other/bracket).

Known rough edges, tolerated rather than special-cased: Excel lock files
(`~$*.xlsx`, skipped outright), ~12 files with a duplicated `edition`/
`text` column pair (first occurrence wins), a few files with the header
typo `infection` for `inflection`, a handful of near-empty rubric/heading
sheets (just `edition`/`text`/`document`/`page`, no linguistic annotation
— imported as a heading-only pseudo-token).

---

## 1. tokens.tsv

| column | example | notes |
|---|---|---|
| `ref` | `Isidor.1.3` | `WorkID.section.verse` — see §Ref scheme |
| `surface` | `uuort` | the `text` cell, as annotated |
| `lemma` | `wort` | dictionary headword |
| `pos` | `noun` | coarse tag — see §POS tags |
| `features` | `{"case":"NOM","number":"SG"}` | see §Features |
| `stem_class` | `A_NEUT` | `inflectionClass`, passthrough |
| `edition` | `uuort` | diplomatic form; empty on a continuation token |
| `clause` | `CF_U_M` | passthrough, corpus's own clause-type code |
| `lang` | `goh` | `goh` / `osx` / `lat` / mixed, passthrough |

`features` is a JSON object on one line, `{}` if nothing decoded.

---

## 2. verses.tsv

| column | notes |
|---|---|
| `ref` | same key as tokens.tsv |
| `text` | reconstructed by joining `edition` forms in token order (continuation tokens concatenate directly, no space; punctuation attaches to the preceding word) |
| `parallel` | aligned Latin line, where a `*_Latein` counterpart exists and lines up by `document`+`chapter`/`subchapter`; empty otherwise (best-effort, not guaranteed) |
| `translation` | left empty — this corpus's `translation` column is a per-lemma gloss, not a verse translation; it goes into `lexicon.json` instead |

---

## 3. lexicon.json

```json
{
  "wort": {
    "pos": "noun",
    "stem_class": "A_NEUT",
    "gloss_de": "Wort",
    "notes": ""
  }
}
```

One entry per distinct `lemma` in tokens.tsv. `gloss_de` = the most
frequent `translation` value seen for that lemma (this corpus's glosses
are German; there is no English gloss layer, unlike Gothic's `gloss_en`).

---

## 4. works.json

```json
{
  "groups": [
    {"key": "as",     "label": "Altsächsisch"},
    {"key": "anfrk",  "label": "Altniederfränkisch"},
    {"key": "mfrk",   "label": "Mittelfränkisch"},
    {"key": "rhfrk",  "label": "Rheinfränkisch"},
    {"key": "ofrk",   "label": "Ostfränkisch (Fulda)"},
    {"key": "srhfrk", "label": "(Süd-)Rheinfränkisch (Weißenburg)"},
    {"key": "bair",   "label": "Bairisch"},
    {"key": "alem",   "label": "Alemannisch (St. Gallen / Reichenau)"},
    {"key": "unloc",  "label": "Unlokalisiert"}
  ],
  "works": {
    "Isidor": {
      "title": "Isidor",
      "group": "rhfrk",
      "topic": "Religion",
      "form": "Prosa",
      "depository": "Paris, Bibliothèque Nationale",
      "time": "8-9",
      "time_sort": 8.0,
      "sections": ["1","2","3","4","5","6","7","8","9"]
    }
  }
}
```

`groups` is ordered roughly north to south (approximate — dialect regions
don't sit on neat latitude bands; this just keeps e.g. Bairisch/Alemannisch,
the two southernmost groups, from sitting near the top). `group` keys map
`(language_area, dialect)` pairs from each work's `.meta` onto the fixed
group table above (see §Dialect groups), with `language_area`/`dialect`
checked before the coarser `language` field, and one documented override
(see §Dialect groups) for a work whose source metadata is internally
contradictory. Only groups and works actually attested in the converted
corpus are included, per the same convention `docs/gothic_spec.md` states
for `books.json`.

`time_sort` is a float parsed from `time` (century, optionally `.1`/`.2`
for first/second half — `"9.1"` → `9.1`; a range takes its start — `"8-9"`
→ `8.0`; multi-manuscript dates like `"M: 9.2; C: 10.2"` take the first
date mentioned) — `null` when `time` has no parseable date. Front ends sort
works within a group chronologically by this field, undated works last.

---

## §Ref scheme

`ref` = `WorkID.section.verse`, all three parts required, built uniformly
regardless of which locator columns a given file happened to carry:

- `WorkID` — the corpus's own siglum, taken from the `.xlsx` filename
  prefix (`Isidor`→`I`, `Heliand`→`Hel`, `Tatian`→`T`, `Otfrid`→`O`,
  `Genesis`→`Gen`, `AltbairischeBeichte`→`AB`, …). Case-sensitive, must
  match the keys in `works.json`.
- `section` — the file's `chapter` column value when present, else parsed
  from the filename's own numeric/roman suffix. Every `.xlsx` corresponds
  to exactly one section (that's how the source splits files), so this is
  reliable without reading the sheet.
- `verse` — chosen per work by priority, first populated wins:
  1. `verse` column, if present and not just the literal `n/a`
  2. `subchapter` column, if present
  3. `line` / `line_m` column, if present
  4. **punctuation fallback**: a running sentence counter, incrementing
     each time a `pos=$.` token is seen — guarantees every work gets
     verse-level granularity even where the source carries no locator at
     all (this is the common case for the Notker Boethius files, which
     only ever have `page`/`line`... actually those do have `line`, so
     they land on tier 3; the fallback exists for the few files —
     confirmed during conversion, see validation summary — that have
     neither).

---

## §POS tags

Coarse vocabulary, identical to the one already defined for Gothic (so
`build_corpus.py`'s `POS_FILE`/`congruent()` need no changes):

| tag | meaning | source `posLemma` prefixes |
|---|---|---|
| `noun` | substantive | `NA` |
| `name` | proper name | `NE`, `NEO` |
| `adj` | adjective | `ADJ*`, `ADJO*` |
| `verb` | finite/non-finite verb, participle | `VV`, `VA`, `VM` |
| `pron` | pronoun, article, determiner | `PPER`, `DPOS`, `DD*`, `DI*`, `PI*`, `PW*` |
| `adv` | adverb, pronominal adverb | `ADV`, `DW*` |
| `prep` | preposition | `AP*` |
| `conj` | conjunction | `KO*` |
| `ptcl` | particle (negation, verb prefix, `zu`, relative particle, …) | `PTK*` |
| `num` | numeral | `CARD*` |
| `interj` | interjection | `ITJ` |
| `punct` | punctuation | `$.`, `$,`, `$(` |

Where a cell holds multiple `¦`-joined alternatives (ambiguous
annotation), the first alternative is taken as canonical — for both
`pos`/`posLemma` and `inflection`, independently.

---

## §Features

`features` is built by tokenizing the (already-first-alternative)
`inflection` string on `_`, stripping a trailing `?` (uncertainty marker)
from each token, and classifying each remaining token against fixed value
sets — **order-independent**, unlike Gothic's fixed-position tags, because
this corpus's tag order varies by POS family. Unrecognized tokens are
dropped.

| key | recognized values |
|---|---|
| `case` | `NOM` `ACC` `DAT` `GEN` `ABL` `VOC` |
| `number` | `SG` `PL` `DU` |
| `gender` | `MASC`→`M` `FEM`→`F` `NEUT`→`N` |
| `person` | `1` `2` `3` |
| `tense` | `PRES`→`PRS` `PAST`→`PST` `PERF`→`PRF` |
| `mood` | `IND` `SUBJ` `IMP` |
| `voice` | `ACT` `DEP` |
| `degree` | `POS` `COMP` `SUP` |
| `strength` | `ST` `WK` |

Non-finite verb forms (`pos` source `VVINF`/`VAINF`/`VMINF` family) get
`{"mood":"INF"}` regardless of `inflection` content (these rows carry no
person/number). Participles (`VVPP*`/`VAPP*` = past, `VVPS*`/`VAPS*` =
present, excluding the finite `VVFIN` family) additionally get
`{"tense":"PST"}` / `{"tense":"PRS"}` merged in before the bag-of-tokens
decode, so their nominal agreement features (case/number/gender, when
present in `inflection`) still come through.

---

## §Dialect groups

`language_area`/`dialect` from `.meta` → group key, checked in this order
(language_area/dialect first — they're the fields meant for dialect
geography — with the coarser `language` field only as a fallback for the
"no classification" rows):

| `language_area` | `dialect` | group key |
|---|---|---|
| `anfrk.` | (any) | `anfrk` |
| `nd.` | (any) | `as` |
| `obd.` | `bair.` | `bair` |
| `obd.` | `alem.` | `alem` |
| `obd.` | `ofrk.` | `ofrk` |
| `obd.` | `srhfrk.` | `srhfrk` |
| `md.` | `rhfrk.` | `rhfrk` |
| `md.` | `mfrk.` | `mfrk` |
| *(unclassified)*, `language` starts `as.` | | `as` |
| *(unclassified)*, `language` starts `anfrk` | | `anfrk` |
| anything else | | `unloc` |

Checking `language_area` before `language` matters: a work whose
`language` happens to start with `as.` (e.g. `as.ags`) but whose
`language_area` is properly set to `anfrk.` (Sächsisches Taufgelöbnis)
must land in `anfrk`, not be shadowed by the coarser `language` check.

One title-keyed override exists: **Altniederfränkische Psalmen**
(Wachtendonck Psalms) is forced to `anfrk` regardless of what the table
above would produce. Its source `.meta` says `language=as.` but
`language_area=obd.`, `dialect=mfrk.` — self-contradictory (`mfrk.` is a
Mitteldeutsch dialect, not Oberdeutsch) — and this is the *only* work in
the whole corpus with an internally inconsistent area/dialect pair (spot-
checked against every other `(language, language_area, dialect)` triple
actually present). Standard scholarship classifies it Altniederfränkisch;
the override corrects this one confirmed data-entry error rather than
generalizing into a rule that could paper over other, undetected cases.

The four `*_Latein` directories (Isidor, Tatian, Benediktinerregel,
Murbacher Hymnen) are **not** separate works — they feed
`verses.tsv.parallel` for their vernacular counterpart only.

---

## Validation checklist

1. Every `ref` in `tokens.tsv` appears in `verses.tsv`
2. Every distinct `pos` value is from the §POS tags list
3. Every `works.json` work has a `group` from §Dialect groups
4. `lexicon.json` has an entry for every distinct `lemma` in `tokens.tsv`
5. `~$*.xlsx` lock files are excluded from the file count
6. Build script prints a summary (files parsed/skipped/errored, work
   count, token count, verse count) for manual comparison against the
   known totals (174 works, 1944 source files)
