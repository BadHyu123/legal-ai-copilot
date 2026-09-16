"""
Hash-based change detection (architecture doc, Section 3.5).

Keeps a hash/version identifier of each previously ingested document.
On each run: fetch only listing pages, compare hash against the stored
one, and only re-parse/re-embed documents that are new or changed.

State is persisted to CRAWLER_STATE_DIR (see .env.example) so it
survives across container restarts (mounted as a volume in
docker-compose.yml).
"""

import hashlib
import json
import os
from pathlib import Path

STATE_DIR = Path(os.environ.get("CRAWLER_STATE_DIR", "/data/crawler_state"))
STATE_FILE = STATE_DIR / "document_hashes.json"


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _hash_of(document) -> str:
    return hashlib.sha256(document.raw_html.encode("utf-8")).hexdigest()


def filter_changed(documents: list) -> list:
    """Return only documents whose content hash differs from the stored one.

    TODO (Sprint 1): wire this up against the real RawDocument objects
    returned by the source adapters once list_documents() is implemented.
    """
    state = _load_state()
    changed = []
    for doc in documents:
        if state.get(doc.url) != _hash_of(doc):
            changed.append(doc)
    return changed


def mark_ingested(document) -> None:
    """Persist the current hash for a document after successful ingestion."""
    state = _load_state()
    state[document.url] = _hash_of(document)
    _save_state(state)
