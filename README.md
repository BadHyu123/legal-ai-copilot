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

- [ ] **Sprint 1** — Data pipeline foundation (crawler, parsing, chunking, embedding) — *in progress, structure scaffolded*
- [ ] **Sprint 2** — Core RAG pipeline (hybrid search, re-ranking, /ask endpoint)
- [ ] **Sprint 3** — Frontend + session management
- [ ] **Sprint 4** — Evaluation (RAGAS) + contract review (stretch)
