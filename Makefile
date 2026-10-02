PYTHON ?= python3
ifneq ($(wildcard $(VIRTUAL_ENV)/bin/python),)
PYTHON = $(VIRTUAL_ENV)/bin/python
endif

.PHONY: test coverage smoke dev check

check:
	./scripts/check

smoke:
	./scripts/container-smoke --build

test: check

coverage:
	$(PYTHON) -m coverage run --source=pocketkid -m unittest discover -s tests
	$(PYTHON) -m coverage report -m

dev:
	$(PYTHON) app.py
