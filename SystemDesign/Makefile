.PHONY: site clean serve deps help

PYTHON := python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
SITE_DIR := site
DATA_FILE := data.json

help:
	@echo "Knowledge Base Site Generator"
	@echo ""
	@echo "Usage:"
	@echo "  make site    - Generate the static site from markdown files"
	@echo "  make clean   - Remove generated site and data files"
	@echo "  make serve   - Start a local server to preview the site"
	@echo "  make help    - Show this help message"

$(VENV)/bin/activate:
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install markdown

deps: $(VENV)/bin/activate

site: deps
	@echo "Generating site..."
	$(VENV_PYTHON) generate_site.py

clean:
	@echo "Cleaning generated files..."
	rm -rf $(SITE_DIR)
	rm -f $(DATA_FILE)
	@echo "Clean complete."

clean-all: clean
	@echo "Removing virtual environment..."
	rm -rf $(VENV)
	@echo "Full clean complete."

serve: site
	@echo "Starting local server at http://localhost:8000"
	@echo "Press Ctrl+C to stop"
	cd $(SITE_DIR) && $(PYTHON) -m http.server 8000
