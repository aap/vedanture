# Textual Gravity

A weighted edge between lemma A and lemma B captures how strongly they
are drawn together in the corpus. Higher weight = more meaningful
proximity. Four components, addable.

---

## 1. Verse co-occurrence

Count the number of verses in which both A and B appear (any form).

    verse_cooccur(A, B) = |{verse : A ∈ verse ∧ B ∈ verse}|

Broadest signal. Every pair of lemmas in the same 3–4 pada hymn verse
gets counted. Noisy for common words.

## 2. Pada co-occurrence

Count shared *padas* (quarter-verse lines, ~8–11 syllables). Same pada
= very tight syntactic neighbourhood; this is where Sanskrit compound
and phrase structure lives.

    pada_cooccur(A, B) = |{pada : A ∈ pada ∧ B ∈ pada}|

Weight higher than verse-level (suggested β ≈ 3α).

## 3. Morphological congruence

Two nominals agree in case + number + gender when they belong to the
same NP or are in coordination / apposition. A nominal and a verb agree
in number (and implicitly person) when subject and predicate.

For each verse where A and B co-occur, look at their attested surface
forms in that verse. If any form of A and any form of B share a feature
bundle, that's a congruent instance:

    congruent nominal pair :  case(a) = case(b)  ∧  number(a) = number(b)
                                                  ∧  gender(a) = gender(b)

    congruent verb-nominal  :  number(verb) = number(nominal)

    morph_congruent(A, B) = Σ_verse  max_congruence(forms_A_in_verse, forms_B_in_verse)

This component uses the morphological annotation directly — it rewards
lemma pairs that are grammatically linked, not merely co-present.

## 4. Rarity (PMI-style) weighting

Common words (ca, iva, na, indra) co-occur with everything and carry
little information. Weight each co-occurrence instance by how surprising
it is:

    surprise(A, B) = log( P(A ∧ B) / (P(A) · P(B)) )
                   = log( verses(A,B) · total_verses / (verses(A) · verses(B)) )

Apply as a multiplier on the verse and pada counts. Negative PMI
(expected from frequency alone) → contribution floored at 0.

---

## Combined score

    gravity(A, B) = α · verse_cooccur(A, B)  · surprise(A, B)
                  + β · pada_cooccur(A, B)   · surprise(A, B)
                  + γ · morph_congruent(A, B)

α, β, γ tuned by feel. Suggested start: α=1, β=3, γ=5.

Stored as top-20 neighbours per lemma, sorted by gravity descending.

---

## What is NOT included (yet)

- **Formulaic repetition**: exact same sequence of lemmas in multiple
  verses (Parry-Lord oral formulas). High signal when present, but
  requires phrase-level indexing.
- **GRA cross-references**: Grassmann's `nrefs` already encode
  lexicographic proximity. Could be a δ component.
- **Semantic role**: case alone doesn't distinguish agent from patient
  in a congruent pair. Would need dependency parsing.

---

## Output format

`gravity.json`  —  `{ lemma: [(neighbour, score), …] }`, top 20 per
lemma, scores normalised 0–1 relative to the lemma's strongest tie.
