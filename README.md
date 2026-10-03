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
│       ├── sources/           # luatvietnam.vn (law text), vanban.chinhphu.vn (registry cross-check)
│       ├── change_detection.py
│       ├── parser.py          # law-text HTML -> structured Markdown
│       ├── chunker.py         # semantic chunking by Điều/Khoản
│       └── embedder.py        # vietnamese-sbert embedding + upsert
├── shared/                    # Code shared between crawler and backend
│   └── metadata_schema.py     # chunk metadata contract (luật, điều, chủ_đề)
├── eval/                      # Sprint 4: questions.jsonl + run_eval.py (retrieval, threshold, latency, faithfulness)
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

Run the crawler (offline batch job — fetches, chunks, embeds, upserts):

```bash
docker-compose --profile crawler run law-crawler
```

### Running without Docker (how the first live run was done, Windows)

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python -m pip install -r backend/requirements.txt -r crawler/requirements.txt

# Qdrant: unzip the v1.9.0 Windows release into data/qdrant/ and run it from there
# (https://github.com/qdrant/qdrant/releases/tag/v1.9.0 → qdrant-x86_64-pc-windows-msvc.zip)
cd data/qdrant && ./qdrant.exe

# Use 127.0.0.1, NOT localhost: on Windows "localhost" tries IPv6 first and
# every Qdrant/Ollama call stalls ~2 s before falling back (measured: 2.05 s vs 3 ms).
export VECTOR_DB_HOST=127.0.0.1 OLLAMA_BASE_URL=http://127.0.0.1:11434
export HF_HOME=$PWD/data/hf_cache CRAWLER_STATE_DIR=$PWD/data/crawler_state
export SESSION_DB_PATH=$PWD/data/crawler_state/session.db OLLAMA_MODEL=qwen2.5:3b-instruct

(cd crawler && ../.venv/Scripts/python -m crawler.main)          # ~6 min first run
(cd backend && ../.venv/Scripts/uvicorn app.main:app --port 8000)
(cd frontend && npm install && npm run dev)
.venv/Scripts/python eval/run_eval.py [--llm]                    # Sprint 4 metrics
```

Ollama's model store defaults to `C:\Users\<you>\.ollama`; set the user
env var `OLLAMA_MODELS` (here `D:\ollama\models`) if C: is short on space.

## Sprint status

- [x] **Sprint 1** — Data pipeline. Ran live 2026-10-02: 5 laws → 768 chunks in ~2.5 min. Law text now comes from **luatvietnam.vn** (`sources/luatvietnam.py`, fixed list of in-force consolidated texts/VBHN) — thuvienphapluat.vn sits behind a Cloudflare bot challenge and is not worked around. `vanban_chinhphu.py` cross-checks each law against the Government registry (log only).
- [x] **Sprint 2** — Core RAG pipeline (hybrid search + RRF, bge-reranker, Ollama, fallback without calling the LLM). Ran live.
- [x] **Sprint 3** — Chat UI + sessions. `next build` passes; ran live against the real backend. Citation tags open in place to show the cited Điều/Khoản text and a source link.
- [x] **Fixes from a full code read** (before the live run): re-ingesting a law deletes its old points first (no stale Articles/Khoản); Khoản split only on a clean 1, 2, (2a,) 3… sequence (no point-ID collisions); Ollama `num_ctx=8192`, `temperature=0` (the default context silently truncated the system prompt); citations/fallback state persisted with each answer so reloads keep citation tags; follow-up questions retrieve with the previous question too; model warmup on startup; CPU-only torch in images; Qdrant image pinned to `v1.9.0`; HF model cache at `data/hf_cache`. Self-checks: `cd backend && python -m tests.test_logic`, `cd crawler && python -m tests.test_logic`, `python eval/run_eval.py --selftest`.
- [x] **Sprint 4 — Evaluation** (`eval/`), see results below. Contract review (stretch) is **moved to the backlog**: the core targets took the sprint, and a 3B local model is a weak judge of clause risk.

### Sprint 4 results (2026-10-02, `python eval/run_eval.py --llm`)

48 in-scope questions (2/3 tax) + 8 out-of-scope, expected citations at Điều level, in `eval/questions.jsonl`. Full output: `eval/results/2026-10-02.txt`.

| Metric | Result | Target |
|---|---|---|
| Faithfulness (RAGAS method, judge `qwen2.5:7b-instruct`) | **0.863** (47 answers) | > 0.75 |
| End-to-end latency p50 / p95 | **7.6 s** / 15.2 s (rerank 3.7 s on CPU + LLM 3.3 s) | p50 < 10 s |
| Recall@10 (hybrid) / Hit@3 / MRR@3 | 0.98 / 0.94 / 0.89 | — |
| Fallback: out-of-scope blocked / in-scope wrongly blocked | 7 of 8 / 1 of 48 | — |

Faithfulness is computed the way RAGAS defines it (answer → atomic claims → each checked against the retrieved context), implemented directly against Ollama structured output instead of the `ragas` package, whose English JSON prompts small local judges tend to break (NaN scores). The judge is strict: lead-in sentences ("Cá nhân cư trú được xác định như sau:") count as unsupported claims, so the score is conservative.

Decisions taken from the numbers:

- **LLM = `qwen2.5:3b-instruct`**, not the doc's 7B: on the 4 GB dev GPU the 7B spills to CPU (3.4 tok/s, ~60 s per answer); the 3B fits fully (58 tok/s). Use 7B on a GPU with ≥ 8 GB.
- **Fallback threshold = 0.3** for bge-reranker-base (0.2 for v2-m3 since 2026-10-03) (was a 0.0 placeholder, which never fired).
- **BM25 with syllable bigrams**: Recall@10 0.96 → 0.98, Hit@3 0.92 → 0.94.
- **bge-reranker-v2-m3 not adopted (yet)** (adopted 2026-10-03 as int8, see "Accuracy round" below): same Hit@3 (0.94), MRR 0.90, and a *perfect* in/out-of-scope split (out-of-scope max 0.05 vs in-scope min 0.26) — but 9.2 s p50 / 25 s p95 rerank on CPU. Best next upgrade on a bigger GPU (re-pick the threshold, ~0.16).
- Prompt asks for a direct first sentence with the concrete figure/condition: LLM p50 3.9 s → 3.3 s, Faithfulness unchanged (0.832 → 0.830); keeping table rows on one line then took it to 0.863.
- p95 latency (15 s) is not broken down yet; likely contributors are long answers and Ollama reloading the 3B after the judge model held the VRAM. Streaming the answer would hide most of it if p95 matters.

### Accuracy round (2026-10-03): latency budget < 20 s, maximize accuracy

A **held-out set** (`eval/questions_holdout.jsonl`, 19 in-scope + 5
out-of-scope, everyday phrasing like "Sếp có được trừ lương khi đi làm
muộn?") was written *before* any tuning. Its baseline exposed what the dev
set hid: with bge-reranker-base, **6 of 19 real questions fell under the
fallback threshold** (users would have been told "nothing found"), because
the base reranker is weak on Vietnamese and on everyday-vs-statute wording.
Settings were chosen on the dev set only; the held-out set is reported.

| | Dev before | **Dev after** | Held-out before | **Held-out after** |
|---|---|---|---|---|
| Hit@3 / MRR@3 | 0.94 / 0.89 | **0.96 / 0.90** | 0.79 / 0.69 | **0.84 / 0.75** |
| Real questions wrongly refused | 1/48 | **0/48** | 6/19 | **0/19** |
| Out-of-scope refused | 7/8 | **8/8** | 4/5 | 4/5 |
| Faithfulness (7B judge) | 0.863 | 0.843 | n/a | 0.723 (18 answers) |
| Latency p50 / p95 | 7.6 / 15.2 s | **10.0 / 15.4 s** | n/a | **10.8 / 13.2 s** |

What changed (each step measured on the dev set, outputs in `eval/results/2026-10-03-*.txt`):

- **bge-reranker-v2-m3** (multilingual), int8 on CPU with a 512-token cap: same accuracy as fp32 at half the time (~7 s for 10 candidates). The GPU has no room for it next to the LLM.
- **Query rewriting**: the 3B restates the question as one standalone question in legal terms (few-shot, examples on topics absent from both eval sets). The first prompt ("list legal terms") produced Chinese tokens and invented answers ("18 giờ"); asking for a full question fixed that. The same step makes follow-ups standalone and drops the old topic on a topic switch, a bug the UI test caught (an out-of-scope question shipped with tax citations).
- **The cross-encoder scores "question + restatement"**: real questions' scores went from as low as 0.05 to at least 0.37 on held-out.
- **Second fallback gate**: if the answer's first sentence says nothing relevant was found and it cites no Điều, `/ask` returns the fallback without citations (`ask.is_refusal`).

Caveats, stated plainly:

- The 7B judge mislabels correct claims (e.g. "lương thử việc ít nhất 85%" with Điều 26 in context, scored 0), so Faithfulness is noisy at this sample size; the held-out 0.723 is also over 4 more (harder) answers than the run that refused them.
- The 3B also makes real mistakes on hard provisions: it said thưởng Tết is not taxable, and misread the e-invoice duty of household businesses (QLT Điều 26). A stronger generator is the next accuracy lever; on this 4 GB GPU the 7B costs ~60 s per answer.
- Held-out misses: "trừ lương khi đi làm muộn" (Điều 127/102) and "bán cổ phiếu" (Điều 13) are not even in the top 10 candidates, so the gap is in first-stage retrieval (embedding), not the reranker.

### Known gaps / next steps

- VAT law: VBHN 12/VBHN-VPQH (02/2026) predates the 09/2026/QH16 amendments — swap in the newer consolidation when published (`DOCUMENTS` in `luatvietnam.py`).
- Practical tax questions often need decrees/circulars (Nghị định/Thông tư), which aren't ingested yet — the biggest coverage lever.
- `vietnamese-sbert` truncates long chunks (PhoBERT, 256 tokens); `bge-m3` is the candidate if Recall@10 ever drops.
- Registry cross-check: 109/2025/QH15 isn't in the first 18 pages of the "Luật - Pháp lệnh" listing, and the site starts returning its 500 page after ~18 postbacks (the crawler now stops there).
- The Docker path (`docker-compose up ...`) hasn't been run yet — Docker isn't installed on the dev machine; the live run used "Running without Docker" above.

### Frontend design notes

Redesigned 2026-10-03 with the `design-taste-frontend` skill, as an
overhaul of the visual language (same layout, flows and copy intent).
Design read: a chat tool for non-lawyers checking labor and tax rules,
so calm, trust-first and easy to read beats expressive.

- **One typeface, Be Vietnam Pro**: drawn for Vietnamese, so stacked
  diacritics stay legible at body size. Answers are 16px at 1.75 line
  height, capped at ~70 characters per line. The earlier serif/sans pairing
  and brass accent were dropped (generic "premium" defaults).
- **Cool neutrals + one accent (deep teal)**, light and dark via
  `prefers-color-scheme`; all colors are tokens in `globals.css`, contrast
  checked to WCAG AA. Red appears only on real errors.
- **Citations are the product**: each source is a pill ("Điều 10" + law
  name) that opens in place to show the cited text and a link to the
  source page. "Điều N" mentions inside answers are highlighted.
- **States**: an answer-shaped skeleton with an honest elapsed-seconds
  counter while `/ask` runs (it can take 10-20 s), a calm notice with a
  rephrasing hint for the out-of-scope fallback, and an inline error with
  a retry button.
- Answers render light markdown (paragraphs, bullet and numbered lists,
  bold) via `lib/answerFormat.ts` (`node tests/answerFormat.test.ts`).
- Motion only where it carries meaning (new message, waiting, press), all
  disabled under `prefers-reduced-motion`. Icons: Phosphor.
- Enter does not send while a Vietnamese IME (Telex/VNI) is composing.

## Checklist: first live run (done 2026-10-02)

Run end to end without Docker on Windows (see "Running without Docker").
What the live run found and fixed, for whoever re-runs it:

1. thuvienphapluat.vn: Cloudflare challenge on every page → replaced by luatvietnam.vn. vanban.chinhphu.vn PDFs are scans (no text layer); vbpl.vn disallows `/api/`.
2. Parser: inline tags (`<b>`, linked cross-references) split sentences across lines → text is now taken per block element. Heading variants seen live: `Chương I.`, `Chương VI TIỀN LƯƠNG`, `Mục 1 GIAO KẾT…`, `Điều 66 .`.
3. VBHN artifacts: footnote numbers glued to clause numbers (`1.4[4] Lao động nữ…`), amendment-inserted clauses (`1a.`), and the authentication/footnote block after the last Article — all handled; the footnote notes inside Articles ("Khoản này được bổ sung theo…") are kept.
4. Chunker: the lead-in sentence before Khoản 1 (ending in `:`) used to drop the lead-in *and* Khoản 1; now every Khoản chunk carries it. Only Điều 219 of the Labor Code (an amending Article with nested lists) stays one oversized chunk.
5. vanban.chinhphu.vn pagination never worked: the postback replayed the search button, so the server ran a search and returned page 1. Buttons are now left out; one pass checks all laws (~6 s instead of minutes).
6. `localhost` on Windows: +2 s per Qdrant/Ollama request (IPv6 first) → use `127.0.0.1` when running outside Docker.
7. Tables (tax brackets, rate schedules) were flattened to one cell per line; the faithfulness judge then marked a fully correct 5-bracket PIT answer as 0.29. Rows are now kept on one line (`cell | cell | …`).
8. `next@14.2.5` has a published security advisory → bumped to 14.2.35; frontend Docker build uses the lockfile (`npm ci`).
