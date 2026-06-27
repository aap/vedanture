# vedanture — build the derived corpus data and run a web explorer.
#
#   make serve         run the Ṛgveda explorer on http://127.0.0.1:$(PORT)
#   make gothic        run the Gothic explorer  on http://127.0.0.1:$(PORT)
#   make data          (re)build the gitignored Ṛgveda derived data
#   make gothic-data   (re)build the gitignored Gothic derived data
#   make deps          install the one Python dependency (lxml)
#   make distclean     remove the derived corpus data
#
# Derived data (paradigms/, concordance.tsv, gravity.json) is gitignored and
# rebuilt from the tracked sources. Each server binds 127.0.0.1, intended to sit
# behind a reverse proxy. Both share web/; the front-end is corpus-driven via
# /api/config, so run them on different ports / mounts.

PYTHON ?= python3
PORT   ?= 8000

.PHONY: all serve gothic data gothic-data deps distclean

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

# ── housekeeping ──────────────────────────────────────────────────────────────
deps:
	$(PYTHON) -m pip install lxml

distclean:
	rm -rf paradigms paradigms.json concordance.tsv gravity.json lemmas.tsv \
	       corpus/gothic/paradigms corpus/gothic/concordance.tsv corpus/gothic/gravity.json
