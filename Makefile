# vedanture — build the derived corpus data and run a web explorer.
#
#   make serve         run the Ṛgveda explorer     on http://127.0.0.1:$(PORT)
#   make gothic        run the Gothic explorer     on http://127.0.0.1:$(PORT)
#   make altdeutsch    run the Altdeutsch explorer on http://127.0.0.1:$(PORT)
#   make data              (re)build the gitignored Ṛgveda derived data
#   make gothic-data       (re)build the gitignored Gothic derived data
#   make altdeutsch-data   (re)build the gitignored Altdeutsch derived data
#   make deps          install the one Python dependency (lxml)
#   make distclean     remove the derived corpus data
#
# Derived data (paradigms/, concordance.tsv, gravity.json) is gitignored and
# rebuilt from the tracked sources — except Altdeutsch, where the sources
# themselves aren't tracked either (see the Altdeutsch section below and
# docs/altdeutsch_spec.md §License). Each server binds 127.0.0.1, intended to
# sit behind a reverse proxy. All three share web/; the front-end is
# corpus-driven via /api/config, so run them on different ports / mounts.

PYTHON ?= python3
PORT   ?= 8000

.PHONY: all serve gothic altdeutsch data gothic-data altdeutsch-data deps distclean

all: serve

# ── Ṛgveda ────────────────────────────────────────────────────────────────────
paradigms.json:
	$(PYTHON) build_paradigms.py
paradigms/nouns.json: paradigms.json
	$(PYTHON) split_paradigms.py
concordance.tsv:
	$(PYTHON) build_concordance.py
gravity.json:
	$(PYTHON) build_gravity.py
data: paradigms/nouns.json concordance.tsv gravity.json

serve: data
	$(PYTHON) vedanture.py $(PORT)

# ── Gothic ────────────────────────────────────────────────────────────────────
corpus/gothic/gravity.json:
	$(PYTHON) build_corpus.py corpus/gothic
gothic-data: corpus/gothic/gravity.json

gothic: gothic-data
	$(PYTHON) gothicweb.py $(PORT)

# ── Altdeutsch ─────────────────────────────────────────────────────────────────
# The whole corpus/altdeutsch/ dir is gitignored, source .tsv/.json included —
# the DDD-AD source is © HU Berlin, all rights reserved, not ours to
# redistribute (see docs/altdeutsch_spec.md §License). This target only
# rebuilds the derived paradigms/concordance/gravity; it assumes
# corpus/altdeutsch/tokens.tsv + verses.tsv already exist locally — put them
# there yourself with `python3 build_altdeutsch.py` (needs your own copy of
# the source Excel export) or by copying an already-converted corpus/altdeutsch/
# directly from another machine you control.
corpus/altdeutsch/gravity.json:
	$(PYTHON) build_corpus.py corpus/altdeutsch
altdeutsch-data: corpus/altdeutsch/gravity.json

altdeutsch: altdeutsch-data
	$(PYTHON) altdeutschweb.py $(PORT)

# ── housekeeping ──────────────────────────────────────────────────────────────
deps:
	$(PYTHON) -m pip install lxml

distclean:
	rm -rf paradigms paradigms.json concordance.tsv gravity.json lemmas.tsv \
	       corpus/gothic/paradigms corpus/gothic/concordance.tsv corpus/gothic/gravity.json \
	       corpus/altdeutsch/paradigms corpus/altdeutsch/concordance.tsv corpus/altdeutsch/gravity.json
