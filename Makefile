# vedanture — build the derived corpus data and run the web server.
#
#   make serve     run the web server on http://127.0.0.1:$(PORT)
#   make data      (re)build the gitignored derived corpus data
#   make deps      install the one Python dependency (lxml)
#   make distclean remove the derived corpus data
#
# The derived data (paradigms/, concordance.tsv, gravity.json) is gitignored and
# rebuilt from the tracked TEI in corpus/c-salt_vedaweb_tei/. The server binds
# 127.0.0.1, intended to sit behind a reverse proxy (e.g. nginx proxy_pass to it).

PYTHON ?= python3
PORT   ?= 8000

.PHONY: all serve data deps distclean

all: serve

# ── derived corpus data (rebuilt from the TEI) ────────────────────────────────
paradigms.json:
	$(PYTHON) build_paradigms.py

paradigms/nouns.json: paradigms.json
	$(PYTHON) split_paradigms.py

concordance.tsv:
	$(PYTHON) build_concordance.py

gravity.json:
	$(PYTHON) build_gravity.py

data: paradigms/nouns.json concordance.tsv gravity.json

# ── server ────────────────────────────────────────────────────────────────────
serve: data
	$(PYTHON) vedanture.py $(PORT)

# ── housekeeping ──────────────────────────────────────────────────────────────
deps:
	$(PYTHON) -m pip install lxml

distclean:
	rm -rf paradigms paradigms.json concordance.tsv gravity.json lemmas.tsv
