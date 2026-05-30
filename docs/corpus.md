# VedaWeb Data — Overview

The `corpus/` directory holds three git submodules from the
[C-SALT / VedaWeb project](https://vedaweb.uni-koeln.de/) (University of Cologne).

---

## Repository Map

| Repo | Size | What it is |
|------|------|------------|
| `c-salt_vedaweb_tei` | ~317 MB | **Master corpus** — complete Rigveda in TEI-P5 XML with per-word morphological annotation |
| `c-salt_sanskrit_data` | ~526 MB | Sanskrit dictionaries in TEI-P5 (MW, Apte, Grassmann, …) |
| `c-salt_vedaweb_sources` | ~92 MB | Raw source data: text editions, translations, metadata JSON |

---

## The Master Corpus: `c-salt_vedaweb_tei`

Ten files, one per Rigveda book (`rv_book_01.tei` … `rv_book_10.tei`), total ~214 MB of XML.
There is also a corpus header (`vedaweb_corpus.tei`) and a RelaxNG schema (`vedaweb.rng`).

### Text hierarchy

```
<TEI>
  <text> (book)
    <div type="hymn" n="1.1">
      <div type="stanza" n="1.1.1">
        <ab type="zurich">    ← Zurich edition, word-by-word, with morphology
        <ab type="lubotsky">  ← Lubotsky edition
        <ab type="padapatha"> ← Padapāṭha (word-separated)
        <ab type="aufrecht">
        <ab type="eichler">   ← Devanagari
        <ab type="geldner">   ← German translation
        <ab type="griffith">  ← English translation
        … (7+ more editions/translations)
```

### Per-word annotation (Zurich layer)

Every word in the Zurich text carries a `<fs type="zurich_info">` feature structure:

```xml
<fs type="zurich_info" xml:id="b01_h001_01_zur_a_01">
  <f name="surface"><string>agním</string></f>
  <f name="gra_lemma">
    <string match="#lemma_agni_79">agní-</string>   <!-- links to GRA dict entry -->
  </f>
  <f name="gra_gramm"><symbol value="nominal stem"/></f>
  <f name="morphosyntax">
    <fs type="leipzig_glossing_rules">
      <f name="case">  <symbol value="ACC"/></f>
      <f name="gender"><symbol value="M"/></f>
      <f name="number"><symbol value="SG"/></f>
    </fs>
  </f>
</fs>
```

#### Morphological features encoded

| Category | Values |
|----------|--------|
| **case** | NOM ACC GEN DAT ABL LOC INS (VOC) |
| **gender** | M F N |
| **number** | SG DU PL |
| **person** | 1 2 3 |
| **tense** | PRS IPRF AOR FUT COND |
| **mood** | IND IMP OPT |
| **voice** | ACT MED PASS |
| **non-finite** | ta-Ptz. na-Ptz. |
| **gra_gramm** | nominal stem, root, invariable, pronoun |

#### Extra annotation layers per stanza

- **`strata_info`** — chronological layer (Gunkel & Ryan classification: RV, MO, O, N, …)
- **`stanza_properties`** — metrical/chronological classifications from Grassmann, Oldenberg,
  Arnold, Witzel, Wuest

### Lemma linkage

Lemmas are referenced by ID (e.g. `#lemma_agni_79`) and resolve into the Grassmann dictionary
(`gra`) entries in `c-salt_sanskrit_data`. The raw mapping is also available as
`c-salt_vedaweb_sources/rigveda/info/matched_lemmata.json`:

```json
"agním": {
  "lemma": "agní-",
  "pos": "Nominalstamm",
  "meaning": "Feuer; das vergöttlichte Feuer, Gott Agni",
  "lemma_clean": "agní",
  "id_matched": "lemma_agni_79"
}
```

---

## Source Data: `c-salt_vedaweb_sources`

All under `rigveda/`:

```
versions/
  padapatha.json      ← "01.001.01": "agnim | īḷe | puraḥ-hitam | …"
  lubotsky.json
  aufrecht.json
  eichler.json        ← Devanagari
  vnh.json
  zurich.xlsx         ← Zurich DB export (morphological source)
info/
  matched_lemmata.json
  stanza_properties.json
  strata.json
  addressees.json
  leipzig_mapping.json   ← maps German feature labels → Leipzig abbreviations
  grassmann_enum.json
translations/
  de/geldner.json  grassmann.json  otto.json
  en/griffith.json  macdonell.json  mueller.json  oldenberg.json
  fr/renou.json
  ru/elizarenkova.json
```

The `zurich.xlsx` is the ultimate morphological source; the TEI feature structures in
`c-salt_vedaweb_tei` were produced from it by the C-SALT ETL pipeline.

---

## Dictionaries: `c-salt_sanskrit_data`

Seven lexicons encoded in TEI-P5 XML (SLP1 transliteration):

| Sigla | Full title | Entries |
|-------|-----------|---------|
| GRA | Grassmann, *Wörterbuch zum Rig-Veda* | 10,777 |
| MW | Monier-Williams | 31,821 |
| AP90 | Apte, *Practical Sanskrit-English* | 31,751 |
| BHS | Buddhist Hybrid Sanskrit | 17,807 |
| VEI | Vedic Index | 3,834 |
| PWG | Böhtlingk & Roth | 122,731 |
| AE | Apte English-Sanskrit | 11,364 |

Each entry has a stable `xml:id` (e.g. `lemma_agni_79`) that the corpus uses for cross-links.
Each dictionary directory also ships an Elasticsearch mapping JSON and a Kosh API config used
by the live web interface.

---

## Transliteration schemes

| Scheme | Used in |
|--------|---------|
| ISO-15919 | Vedaweb TEI corpus (Zurich, Lubotsky, Padapatha …) |
| SLP1 | All dictionary TEI files |
| Devanagari (Unicode) | Eichler version |

---

## What analysis tasks this data supports

Given the per-word lemma + morphology annotations on every Rigveda word, the following are
directly feasible by querying the TEI XML:

### Concordance / KWIC
XPath over `<fs>` nodes to find all occurrences of a given `gra_lemma` value, then pull the
surrounding stanza text.

### Stem-class queries
The `gra_gramm` field marks stems as `nominal stem`, `root`, `invariable`, `pronoun`.
Grassmann dictionary entries carry a POS/gender tag. To find all *u*-stems: query lemma IDs
whose GRA entry has a form ending in `-u` and POS = nominal — or use the `-` lemma notation
(e.g. `vásu-`, `paśú-`).

### Morphological filtering
Filter by any combination of case/gender/number/tense/mood/voice. Example: all dual nominatives,
all middle-voice aorists, all feminine accusative plurals.

### Verse chronology
Join with `strata_info` or `stanza_properties` to restrict queries to a chronological layer
(e.g. "old" books 2–7 only).

### Translation alignment
Each stanza has parallel text in 9–10 translations, addressable by the same stanza ID.

### Dictionary lookup
Stable lemma IDs let you pull the full GRA (or MW) dictionary entry for any form in the corpus.

---

## Practical entry points

| Goal | File(s) to start with |
|------|-----------------------|
| Morphological queries | `c-salt_vedaweb_tei/rv_book_*.tei` — XPath on `<fs>` |
| Lemma list / concordance keys | `c-salt_vedaweb_sources/rigveda/info/matched_lemmata.json` |
| Feature label reference | `c-salt_vedaweb_sources/rigveda/info/leipzig_mapping.json` |
| Dictionary definitions | `c-salt_sanskrit_data/sa_de/gra/gra.tei` (Grassmann) |
