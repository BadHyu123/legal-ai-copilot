# Legal AI Copilot

Local-first RAG system that answers Vietnamese Labor Law and Tax Law
questions with grounded, cited answers, and (stretch) flags risky
contract clauses. See `docs/architecture.md` for the full design.

Solo project · 1-month timeline · 4 sprints.

## Project layout

```
legal-ai-copilot/
├── docker-compose.yml     # Frontend, Backend API, Vector DB (compose-managed)
├── .env.example           # Copy to .env and fill in
├── frontend/               # Next.js chat UI + PDF upload (Sprint 3)
├── backend/                 # FastAPI: RAG orchestration, sessions, /ask endpoint
│   └── app/
│       ├── api/routes/      # HTTP endpoints (health, ask)
│       ├── services/        # retrieval, reranker, llm, session logic
│       ├── db/               # vector store + session store interfaces
│       ├── core/              # settings/config
│       └── models/            # Pydantic schemas
├── crawler/                  # Offline batch crawler (Sprint 1)
│   └── crawler/
│       ├── sources/           # thuvienphapluat.vn, vanban.chinhphu.vn scrapers
│       ├── change_detection.py
│       ├── parser.py          # PDF/Word -> structured Markdown
│       ├── chunker.py         # semantic chunking by Điều/Khoản
│       └── embedder.py        # vietnamese-sbert embedding + upsert
├── shared/                    # Code shared between crawler and backend
│   └── metadata_schema.py     # chunk metadata contract (luật, điều, chủ_đề)
├── data/                      # Local volumes (gitignored, kept empty via .gitkeep)
│   ├── raw/                   # Raw crawled documents
│   ├── processed/             # Parsed Markdown
│   └── crawler_state/         # Change-detection hashes, session DB file
└── docs/
    └── architecture.md
```

## Design decisions made while scaffolding

- **Session store has no separate container.** SQLite is a file, not a
  service — it's mounted as a volume (`./data/crawler_state/session.db`)
  into the Backend API container instead of running as its own empty
  container. This keeps the same swap-to-Postgres path open later
  (Section 2.8 of the architecture doc) without running a container that
  does nothing today.
- **The Law crawler is defined in `docker-compose.yml` but not started
  by default** (`profiles: ["crawler"]`) since it's an offline batch job,
  not part of the always-on chat flow (Section 2.1).
- **The LLM engine (Ollama) runs outside Docker Compose**, per the
  architecture doc — install and run it on the host, then point
  `OLLAMA_BASE_URL` in `.env` at it.

## Getting started

```bash
cp .env.example .env
docker-compose up --build frontend backend vector-db
```

To run the crawler once ingestion code is written (Sprint 1 backlog):

```bash
docker-compose --profile crawler run law-crawler
```

## Sprint status

- [x] **Sprint 1** — Data pipeline foundation, code complete: `thuvienphapluat.py` (crawl + parse attributes), `vanban_chinhphu.py` (effective-date cross-check), `parser.py` (HTML → structured Markdown), `chunker.py` (Điều/Khoản chunking), `embedder.py` (vietnamese-sbert + Qdrant upsert). **Not yet run against live network/services** — see checklist below.
- [x] **Sprint 2** — Core RAG pipeline, code complete: `retrieval.py` (hybrid search — Qdrant vector search + in-memory BM25, merged by reciprocal rank fusion), `reranker.py` (bge-reranker cross-encoder), `llm.py` (Ollama call, anti-hallucination system prompt), `session_store.py` (SQLite history), `/ask` route (full orchestration incl. out-of-scope fallback). Pure-Python logic (RRF merge, prompt building, SQLite history ordering) unit-tested in this sandbox; anything needing the real embedding/reranker models, Qdrant, or Ollama is **not yet run live**.
- [x] **Sprint 3** — Frontend + session management, code complete: chat UI (`frontend/src/app/page.tsx` + components), design tokens in `globals.css` (Spectral serif for AI answers/citations, IBM Plex Sans for UI — see design rationale below), localStorage-backed conversation sidebar (`lib/session.ts`), backend `/sessions/{id}/messages` endpoint so switching conversations reloads real history. **`npm install` could not run in this sandbox (no network)** — only checked with a bracket-balance sanity script and JSON validation, not a real `tsc`/`next build`. Treat the first `npm install && npm run dev` as the actual test.
- [ ] **Sprint 4** — Evaluation (RAGAS) + contract review (stretch)

### Frontend design notes

The chat UI intentionally isn't a generic SaaS-chatbot look: AI answers
and citation tags render in a serif (Spectral) to read as "the voice of
the document," while the UI chrome and the user's own messages use a
sans (IBM Plex Sans) — a deliberate pairing, not decoration, since the
product's whole value is faithfully quoting real statute text. Citations
get their own tag styling (brass/gold accent) rather than being buried
in inline links, since traceable citation is the core value proposition.
The out-of-scope fallback state uses a muted red rule rather than an
alarming red box — it's a known, expected outcome, not an error.

## Checklist: verify on first live run

The crawler was written and unit-tested against synthetic HTML matching
the real site's structure, but this development environment had no
network access, so nothing below was exercised against the live sites,
a real embedding model download, or a real Qdrant instance. Run these
roughly in order:

1. `pip install -r crawler/requirements.txt --break-system-packages`
2. `python -m crawler.sources.thuvienphapluat` — confirms search +
   fetch works and `content_len` looks reasonable (tens of thousands of
   chars for the Labor Code). If `attributes` comes back empty, the
   "Thuộc tính" table cell-pairing logic needs adjusting against real HTML
   (see the CAVEAT in that file's docstring).
3. `python -m crawler.parser` — check the printed Markdown: headings
   should read `# Chương I. ...`, `### Điều N. Title` with body text
   underneath, not run together. If titles look truncated, see the
   "no internal period" caveat in `parser.py`.
4. `python -m crawler.chunker` — check chunk count and that long
   Articles actually get split by Khoản (see `MAX_CHUNK_CHARS`).
5. `python -m crawler.embedder` — in-memory Qdrant smoke test; confirms
   the embedding model downloads and upserts without needing a real
   Qdrant server yet.
6. `python -m crawler.sources.vanban_chinhphu` — the riskiest piece:
   confirms the ASP.NET postback pagination actually finds Bộ luật Lao
   động 2019 (`45/2019/QH14`) a few pages in. If this fails, the
   `GRID_CONTROL_ID` constant likely needs reconfirming against a live
   fetch (see that file's docstring).
7. `docker-compose up vector-db` then `docker-compose --profile crawler
   run law-crawler` — the full crawler pipeline end to end.
8. Install Ollama on the host and pull the model:
   `ollama pull qwen2.5:7b-instruct`, then `docker-compose up backend
   vector-db` and `curl -X POST localhost:8000/ask -H "Content-Type:
   application/json" -d '{"session_id":"test","question":"Điều kiện nghỉ
   thai sản là gì?"}'` — exercises hybrid search, reranking, and the LLM
   call together for the first time.
9. **Calibrate `RERANK_RELEVANCE_THRESHOLD`** in
   `backend/app/api/routes/ask.py` — it's a placeholder (`0.0`) until you
   can see real bge-reranker scores on a few genuinely-relevant vs.
   genuinely-irrelevant questions against this corpus.
10. `cd frontend && npm install && npm run dev` — first real check of
    the chat UI. `docker-compose up frontend backend vector-db` for the
    full stack together (set `NEXT_PUBLIC_API_BASE_URL` in `.env` if the
    backend isn't on `localhost:8000`).
