# Gothic Corpus Conversion Spec

Describes what the conversion script must produce from wulfila.be (or any
Gothic source) so the shared explorer engine can drive it unchanged.

---

## Target layout

```
corpus/gothic/
  tokens.tsv        one row per token — primary input for all build steps
  verses.tsv        one row per verse — text + optional parallel / translation
  lexicon.json      dictionary headwords with glosses
  books.json        hierarchy metadata (book order, full names, chapter counts)
```

The build scripts (`build_concordance.py`, `build_paradigms.py`,
`build_gravity.py`) will be extended to accept a `--corpus gothic` flag that
reads from this directory and writes derived files alongside it:

```
corpus/gothic/
  concordance.tsv   (generated)
  paradigms/        (generated)
  gravity.json      (generated)
```

---

## 1. tokens.tsv

Tab-separated with header. One row per token, in verse order.

| column | type | example | notes |
|--------|------|---------|-------|
| `ref` | string | `Jn.3.16` | `Book.chapter.verse`  — see §Book IDs |
| `surface` | string | `gaf` | form as it appears; preserve Gothic script (Latin transliteration) |
| `lemma` | string | `giban` | dictionary headword; use the canonical form from wulfila.be |
| `pos` | string | `verb` | see §POS tags |
| `features` | JSON | `{"tense":"PST","mood":"IND","person":"3","number":"SG","voice":"ACT"}` | see §Features |
| `stem_class` | string | `strong-V` | see §Stem classes; empty string if unknown |

Features must be a valid JSON object on a single line with no tab characters.
If a token has no morphological analysis, use `{}`.

---

## 2. verses.tsv

Tab-separated with header. One row per verse.

| column | type | notes |
|--------|------|-------|
| `ref` | string | same `Book.chapter.verse` key as tokens.tsv |
| `text` | string | full verse text (Gothic, space-separated tokens) |
| `parallel` | string | parallel Greek text if available; empty otherwise |
| `translation` | string | English translation if available; empty otherwise |

If wulfila.be does not provide a ready verse string, reconstruct it by joining
the surface forms for that ref in token order, separated by spaces.

---

## 3. lexicon.json

```json
{
  "giban": {
    "pos": "verb",
    "stem_class": "strong-V",
    "gloss_en": "give",
    "gloss_de": "geben",
    "notes": ""
  },
  "frauja": {
    "pos": "noun",
    "stem_class": "an-stem",
    "gender": "M",
    "gloss_en": "lord, master",
    "gloss_de": "Herr",
    "notes": ""
  }
}
```

`gloss_en` is required. `gloss_de` is strongly preferred (Gothic scholarship
is largely German). `notes` can hold anything — etymology, cross-references.

---

## 4. books.json

```json
{
  "order": ["Mt","Mk","Lk","Jn","Rom","1Co","2Co","Gal","Eph","Phil",
            "Col","1Th","2Th","1Ti","2Ti","Tit","Phm","Neh","Skeir","Cal"],
  "names": {
    "Mt":   "Matthew",
    "Mk":   "Mark",
    "Lk":   "Luke",
    "Jn":   "John",
    "Rom":  "Romans",
    "1Co":  "1 Corinthians",
    "2Co":  "2 Corinthians",
    "Gal":  "Galatians",
    "Eph":  "Ephesians",
    "Phil": "Philippians",
    "Col":  "Colossians",
    "1Th":  "1 Thessalonians",
    "2Th":  "2 Thessalonians",
    "1Ti":  "1 Timothy",
    "2Ti":  "2 Timothy",
    "Tit":  "Titus",
    "Phm":  "Philemon",
    "Neh":  "Nehemiah",
    "Skeir":"Skeireins",
    "Cal":  "Calendar"
  },
  "chapters": {
    "Mt": 28, "Mk": 16, "Lk": 24, "Jn": 21,
    "Rom": 16, "1Co": 16, "2Co": 13, "Gal": 6,
    "Eph": 6, "Phil": 4, "Col": 4, "1Th": 5,
    "2Th": 3, "1Ti": 6, "2Ti": 4, "Tit": 3,
    "Phm": 1, "Neh": 1, "Skeir": 8, "Cal": 1
  }
}
```

Only include books that are actually present in the corpus. Chapter counts
above are the Biblical maximums; use actual attested counts if shorter.

---

## §Book IDs

The `ref` field uses `BookAbbrev.chapter.verse` — all three parts required.

```
Jn.3.16      John chapter 3 verse 16
Skeir.1.1    Skeireins section 1 verse 1
```

Book abbreviations are case-sensitive and must match the keys in `books.json`.

Verse numbering follows standard biblical versification where applicable.
For non-biblical texts (Skeireins, Calendar), use whatever sectioning the
source provides, consistently.

---

## §POS tags

Use these exact strings in the `pos` column:

| tag | meaning |
|-----|---------|
| `noun` | substantive |
| `verb` | finite verb, infinitive, participle |
| `adj` | adjective (strong or weak) |
| `pron` | pronoun (personal, demonstrative, relative, interrogative) |
| `adv` | adverb |
| `prep` | preposition |
| `conj` | conjunction |
| `ptcl` | particle (including negation `ni`) |
| `num` | numeral |
| `name` | proper name |
| `interj` | interjection |

---

## §Features

Features are per-token morphological properties, encoded as a JSON object
with lowercase keys and uppercase values (matching the RV corpus convention).

### Nominal features (noun, adj, pron, name, num)

| key | values |
|-----|--------|
| `case` | `NOM` `ACC` `GEN` `DAT` `VOC` `INS` |
| `number` | `SG` `PL` `DU` |
| `gender` | `M` `F` `N` |

Adjectives also carry strong/weak distinction — encode as:

| key | values |
|-----|--------|
| `strength` | `STR` `WK` |

### Verbal features (verb)

| key | values |
|-----|--------|
| `tense` | `PRS` `PST` |
| `mood` | `IND` `OPT` `IMP` |
| `voice` | `ACT` `PASS` |
| `person` | `1` `2` `3` |
| `number` | `SG` `PL` `DU` |

Infinitives: `{"mood":"INF","voice":"ACT"}` — omit person/number/tense.
Participles: include `{"tense":"PRS"|"PST", "voice":"ACT"|"PASS"}` plus
nominal features (case/number/gender) for the form's agreement.

For gerundives / verbal nouns, use pos `noun` with a note in `stem_class`.

---

## §Stem classes

### Nouns / adjectives

| class | example |
|-------|---------|
| `a-stem` | dags (m), waurd (n) |
| `ja-stem` | hairdeis (m) |
| `wa-stem` | triggws (m) |
| `ō-stem` | giba (f) |
| `jō-stem` | bandi (f) |
| `wō-stem` | |
| `i-stem` | gasts (m/f) |
| `u-stem` | sunus (m), handus (f) |
| `an-stem` | guma (m), hanin (m) |
| `ōn-stem` | tuggō (f) |
| `n-stem` | hairtō (n) |
| `r-stem` | fadar (m) — kinship terms |
| `nd-stem` | nasjands — present participle nouns |
| `consonant-stem` | reiks, etc. |

### Verbs

| class | description |
|-------|-------------|
| `strong-I` through `strong-VII` | ablaut classes (I = greiпan type, etc.) |
| `weak-I` | jan-verbs (nasjan) |
| `weak-II` | ōn-verbs (salbon) |
| `weak-III` | ain-verbs (haban) |
| `weak-IV` | nan-verbs (fullnan) |
| `pret-pres` | preterite-present (kann, wait, mag, etc.) |
| `anomalous` | wisan, gaggan, iddja, wiljan, etc. |

---

## Validation checklist

Before handing off the data:

1. Every `ref` in tokens.tsv appears in verses.tsv
2. All `pos` values are from the §POS list above
3. All feature keys/values match the §Features table
4. All `stem_class` values are from §Stem classes or empty string
5. `lemma` strings are consistent — the same headword is always spelled
   the same way across all tokens (case-sensitive)
6. `lexicon.json` has an entry for every distinct `lemma` in tokens.tsv
7. `books.json` has an entry for every distinct book prefix in refs
