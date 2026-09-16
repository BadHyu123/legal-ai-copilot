**Legal AI Copilot**

Architecture Document

*Solo project · 1-month timeline · 4 sprints · Local-first RAG system*

1\. Project Overview

1.1 Business Problem

Looking up the right legal provision is still a slow, manual, and
error-prone process for most people in Vietnam. Legal texts are
scattered across laws, decrees, and circulars, written in dense legal
language, and organized in a strict hierarchical structure (Chapter →
Section → Article → Clause → Point) that is easy to misread. Non-lawyers
--- employees, small business owners, freelancers --- routinely
misinterpret provisions on issues as common as severance pay or personal
income tax, simply because finding and correctly reading the applicable
article is hard.

1.2 Solution

The **Legal AI Copilot** is a personal legal assistant that lets a user
ask a legal question in plain language and get back an answer grounded
in the actual text of the law --- with the exact article and clause
cited --- instead of a generic, potentially made-up response. It also
includes a contract review feature that flags clauses in an uploaded
contract that may conflict with current law or be unfavorable to the
user.

1.3 Problem Statement --- Three Core Challenges

Building a legal assistant is not just \"calling the ChatGPT API.\" It
requires solving three problems that are specific to the legal domain:

1.  **Accuracy (no hallucination)** --- the system must never fabricate
    a legal provision. If the answer isn't grounded in a retrieved
    article, it must say so rather than guess.

2.  **Citability** --- every answer must point to the exact article,
    clause, and law it came from, so the user can verify it
    independently.

3.  **Complex context comprehension** --- legal text has a strict
    hierarchical structure, and naive chunking breaks that structure,
    causing the model to answer based on incomplete or out-of-context
    fragments.

1.4 Project Context

This is a **solo personal project**, built end-to-end together with AI
coding agents, within a **1-month timeline**. It is designed to
demonstrate the ability to independently scope, architect, and ship a
non-trivial AI system --- from data pipeline to a working full-stack
product --- rather than to be a production legal service.

1.5 Goals

-   Answer questions correctly on **Labor Law** and **Tax Law** (with
    emphasis on Tax), citing the exact article/clause.

-   Achieve a RAGAS Faithfulness score above **0.75**.

-   Keep end-to-end response latency under **10 seconds**.

-   Run entirely **locally**, using free/open-source components wherever
    possible.

1.6 Target Users

Individuals without legal training who need quick, trustworthy answers
about labor and tax obligations --- employees checking their rights,
small business owners handling payroll and tax compliance, and
freelancers navigating personal income tax.

1.7 MVP Scope

The MVP covers **Labor Law and Tax Law only** (Tax Law as the primary
focus), running fully **locally** and built within a **1-month,
4-sprint** timeline. Broader legal coverage, multi-user support, and
cloud deployment are explicitly out of scope for the MVP (see Section 7
--- Risks & Known Limitations for the full list of non-goals).

1.8 Technical Highlights

For a technical reviewer, this project is a concrete demonstration of
three skills that matter for AI engineering roles: handling
**long-context, hierarchically structured documents** without breaking
their semantics, implementing **Advanced RAG** (hybrid search +
re-ranking, not just plain vector search), and enforcing **strict
factual accuracy** through anti-hallucination prompting and quantitative
evaluation (RAGAS) rather than a one-off manual sanity check.

1.9 Reading Guide

Section 2 walks through the system architecture that implements this
solution, followed by the data pipeline and RAG design, the technology
choices, the sprint-by-sprint delivery plan, evaluation methodology, and
known limitations.

2\. System Architecture

2.1 Overview

The system follows a layered architecture with clear separation between
**Presentation**, **API/Gateway**, **Business Logic (RAG
Orchestration)**, and **Data** layers. Each layer runs as its own Docker
container, so the MVP is fully deployable on a single local machine via
docker-compose, while still being structured for a future move to
multi-container cloud deployment.

The local topology is as follows:

-   The **Frontend (Next.js)** container serves the chat UI and handles
    PDF uploads for contract review.

-   The **Backend API (FastAPI)** container is the single entry point
    for all client requests. It owns the RAG orchestration logic and
    session management, and is the only component that talks to the
    Vector DB, the Session store, and the LLM engine.

-   The **Vector DB** (Qdrant or ChromaDB) stores embedded legal
    articles along with their structured metadata.

-   The **Session store** (SQLite) persists conversation history per
    user session.

-   The **Law crawler** is an offline, batch-run service --- it does not
    participate in the real-time chat flow. It periodically scrapes the
    latest legal texts and writes freshly parsed/chunked/embedded
    documents into the Vector DB.

-   The **LLM engine** sits outside the Docker Compose boundary because,
    depending on cost/latency trade-offs, it may be a locally hosted
    open-source model or a call to an external API. Keeping it outside
    the compose network means it can be swapped without touching the
    rest of the stack.

2.2 Component Responsibility Table

  ------------------------------------------------------------------------------
  Component   Responsibility          Input         Output         Tech (MVP)
  ----------- ----------------------- ------------- -------------- -------------
  Frontend    Chat UI, contract PDF   User          HTTP requests  Next.js
              upload, renders answers messages, PDF to Backend API 
              with citations          files                        

  Backend API Single entry point;     HTTP requests JSON responses FastAPI
              orchestrates retrieval                (answer +      
              → rerank → generation;                citations)     
              manages sessions                                     

  Vector DB   Stores embedded legal   Query         Top-k matching Qdrant /
              articles + metadata;    embeddings    chunks         ChromaDB
              serves similarity                                    
              search                                               

  Session     Persists per-session    Session ID,   Conversation   SQLite
  store       conversation history    messages      history        

  Law crawler Scrapes, parses,        Public legal  New/updated    Python batch
              chunks, and embeds the  data sources  vectors in     script (cron)
              latest legal texts on a               Vector DB      
              schedule                                             

  LLM engine  Generates the final     Prompt        Grounded       Local
              natural-language answer (question +   answer with    open-source
              grounded in retrieved   context)      citations      model or
              context                                              external API
  ------------------------------------------------------------------------------

2.3 Query Processing Sequence

For a typical legal question, the request flows through the system as
follows:

1.  User submits a question through the Frontend chat UI.

2.  Backend API receives the request and loads the relevant session
    history from the Session store.

3.  Backend API embeds the question and issues a **hybrid search**
    (vector similarity + keyword/BM25) against the Vector DB.

4.  The top-10 candidate legal articles returned are passed through a
    **re-ranking** step (cross-encoder) to select the 3 most relevant
    articles.

5.  Backend API builds a prompt combining the question, conversation
    history, and the re-ranked legal context, and sends it to the LLM
    engine.

6.  The LLM engine returns an answer, which the Backend API validates
    for citation format before returning it to the Frontend.

7.  Backend API appends the exchange to the Session store.

2.4 Contract Review Flow (Sprint 4 / stretch goal)

The contract review feature reuses the same backend and Vector DB, but
follows a distinct flow: the user uploads a PDF contract → the Backend
API parses and splits it into clauses → each clause is checked against
the Vector DB for potentially conflicting or unfavorable legal
provisions → clauses flagged as risky are returned to the Frontend,
which highlights them for the user. This flow is deferred to the last
sprint and treated as optional if time allows.

2.5 Container & Communication Design

Each layer is packaged as an independent Docker container (Frontend,
Backend API, Vector DB, Session store, Law crawler), orchestrated
locally with docker-compose. This separation keeps the MVP simple to run
on one machine today, while allowing any single container to be scaled
out or replaced independently later (for example, swapping SQLite for
PostgreSQL, or moving the Vector DB to a managed service).

All internal communication uses REST over JSON:

-   Frontend → Backend API: standard HTTP request/response, one endpoint
    for chat and one for contract upload.

-   Backend API → Vector DB: client SDK calls (Qdrant/ChromaDB native
    client), not raw HTTP.

-   Backend API → LLM engine: HTTP request with a prompt payload; the
    response contract is the same regardless of whether the engine is
    local or an external API, so the two are interchangeable behind one
    interface.

2.6 Error Handling & Fallback

-   If hybrid search returns no legal article above a relevance
    threshold, the Backend API skips generation and returns a fixed
    fallback message (\"No matching legal provision was found\"), rather
    than letting the LLM improvise.

-   If the LLM engine call times out or errors, the Backend API retries
    once, then returns a clear error state to the Frontend instead of a
    partial or hallucinated answer.

-   All failures are logged with the originating request ID for later
    debugging, since this is a single-developer project without a
    dedicated observability stack.

2.7 Security & Privacy Note

Since the MVP runs entirely locally, uploaded contracts and legal
questions never leave the user's machine unless the LLM engine is
configured to call an external API --- in that case, only the minimal
prompt (question + retrieved legal context) is sent, never the raw
uploaded contract file. This boundary should be called out explicitly in
any future cloud deployment.

2.8 Scalability Note

The current design targets a single local user, but the layering
(separate containers, a single Backend API entry point, a swappable LLM
engine) means the same architecture can grow into a multi-user cloud
deployment later --- for example, by adding an authentication layer at
the API Gateway, moving the Session store to PostgreSQL, and moving the
Vector DB to a managed cluster --- without redesigning the core RAG
flow.

3\. Detailed Design --- Data Pipeline & RAG

3.1 Semantic Chunking Principle

Legal text has a strict hierarchical structure (Chapter → Section →
Article → Clause → Point). Splitting it every fixed N words --- the
naive approach --- routinely cuts a clause in half or merges two
unrelated clauses into one chunk, which causes the model to answer from
incomplete or misleading context. Instead, the pipeline chunks along the
document's own semantic boundaries: each chunk corresponds to one
**Article** (Điều), or one **Clause** (Khoản) when an article is
unusually long, so that a chunk is always a complete, self-contained
legal unit.

3.2 Chunk Metadata Structure

Every chunk carries structured metadata alongside its text, so retrieval
and citation can both key off it directly:

{\
\"luật\": \"Luật Lao động 2019\",\
\"điều\": \"Điều 36\",\
\"chủ_đề\": \"Quyền đơn phương chấm dứt hợp đồng\"\
}

This metadata is what makes the citation guarantee in Section 3.12
possible: the answer never has to \"remember\" where a fact came from,
because the source article is attached to the chunk that produced it.

3.3 Ingestion & Parsing

Source documents (laws, decrees, circulars) are ingested as PDF or Word
files and converted to structured Markdown using a parsing library such
as LlamaParse or Unstructured, chosen specifically because they preserve
heading hierarchy --- which the chunker in 3.1 depends on --- rather
than flattening the document into plain text.

3.4 Crawl Sources

The crawler pulls from two official Vietnamese legal data sources:
**thuvienphapluat.vn** and **vanban.chinhphu.vn**. Both are used
together because thuvienphapluat.vn is more consistently structured for
parsing, while vanban.chinhphu.vn is the authoritative source for
confirming that a document is currently in effect.

3.5 Change Detection Algorithm

Re-crawling every document from scratch on every run would be wasteful
and slow. Instead, the crawler keeps a hash (or version identifier) of
each previously ingested document. On each run, it fetches only the
listing pages, compares the hash/version of each document against the
stored one, and re-parses and re-embeds only documents that are new or
have changed --- not the entire corpus.

3.6 Crawl Frequency

The crawler runs as a **weekly** batch job. Legal texts change far less
often than daily, so a weekly cadence is sufficient to stay current
without adding unnecessary load or complexity to the MVP.

3.7 Embedding Model

The MVP uses keepitreal/vietnamese-sbert as the embedding model ---
free, runs locally, and tuned for Vietnamese. The embedding call is
wrapped behind a single interface in the codebase so it can be swapped
for a different model (for example, a commercial embedding API) later
without changing the retrieval or chunking logic.

3.8 Vector Store Organization

All legal articles are stored in a **single collection** in the Vector
DB, rather than one collection per law. Filtering by law, article, or
topic is done through the metadata fields described in 3.2 (e.g.,
filtering luật = \"Luật Lao động 2019\"), which is simpler to maintain
than managing multiple collections and still supports scoping a search
to a specific law when needed.

3.9 Hybrid Search

Pure vector similarity search misses cases where the user's question
contains an exact identifier --- a decree number, a specific legal term,
or the name of a violation --- that must match precisely rather than
\"semantically.\" The pipeline therefore combines **vector similarity
search** with **keyword/BM25 search**, and merges the two result sets
before re-ranking, so that both semantic intent and exact-term matches
are captured.

3.10 Re-ranking with bge-reranker

The top-10 candidates returned by hybrid search are not equally relevant
--- hybrid search is optimized for recall, not precision. A
**bge-reranker** cross-encoder (open-source, runs locally) re-scores all
10 candidates against the original question and selects the top 3 to
pass forward to the LLM. This step is what keeps the context sent to the
LLM small and genuinely relevant, which directly improves both
faithfulness and latency.

3.11 Prompt Construction

The final prompt sent to the LLM is assembled from three parts, in this
order: (1) the relevant slice of conversation history from the session
store, (2) the top-3 re-ranked legal articles with their metadata, and
(3) the user's current question. Keeping the legal context and the
question clearly separated in the prompt (rather than interleaved) makes
it easier for the model to distinguish \"facts it may cite\" from \"the
question it must answer.\"

3.12 Anti-Hallucination Principles

The system enforces three non-negotiable rules on every generated
answer: it may only answer using the retrieved legal context, it must
always cite the specific article and clause it drew from, and if the
context does not contain a relevant provision, it must say so explicitly
rather than produce a plausible-sounding guess. These are enforced as
system-level constraints on the LLM call, not left to the model's
discretion.

3.13 Out-of-Scope Question Handling

Since the MVP only covers Labor Law and Tax Law, a question about an
unrelated area of law (e.g., criminal law) will not retrieve any
relevant chunk from the Vector DB. In that case, the system returns a
fixed fallback message stating that the question falls outside the
current knowledge base, rather than attempting to answer from the LLM's
general knowledge --- which would break the accuracy guarantee in 3.12.

3.14 Traceability

Because every chunk carries its source metadata end-to-end --- from the
Vector DB, through re-ranking, into the prompt --- the citation shown in
the final answer is never generated separately from the retrieval step;
it is read directly off the same chunk metadata that was used to answer.
This means a citation can always be traced back to a specific,
verifiable retrieval result rather than being a claim the LLM made
independently.

4\. Tech Stack

4.1 Stack by Layer

  -------------------------------------------------------------------------------------
  Layer      Component          Technology                    Why chosen
  ---------- ------------------ ----------------------------- -------------------------
  Frontend   Chat UI + PDF      Next.js                       Smooth chat interface,
             upload                                           good file-upload
                                                              handling, familiar
                                                              full-stack framework

  Backend    API Gateway + RAG  FastAPI                       Lightweight, API-first,
             orchestration                                    async-friendly --- fits a
                                                              solo 1-month build better
                                                              than a full-stack
                                                              framework

  Backend    Session management SQLite                        Zero-setup local storage,
                                                              sufficient for a
                                                              single-user MVP

  RAG / AI   Document parsing   LlamaParse / Unstructured     Preserves legal document
                                                              heading hierarchy needed
                                                              for semantic chunking

  RAG / AI   Embedding model    keepitreal/vietnamese-sbert   Free, runs locally, tuned
                                                              for Vietnamese

  RAG / AI   Vector database    Qdrant / ChromaDB             Free, runs locally,
                                                              supports metadata
                                                              filtering for hybrid
                                                              search

  RAG / AI   Keyword search     BM25                          Exact-match recall for
                                                              decree numbers, legal
                                                              terms, violation names

  RAG / AI   Re-ranking         bge-reranker                  Free, runs locally,
                                                              strong cross-encoder
                                                              re-ranking quality

  RAG / AI   LLM engine         Qwen2.5-7B-Instruct via       Free, runs locally,
                                Ollama (default)              strong Vietnamese
                                                              performance; swappable
                                                              for an external API

  Infra      Containerization   Docker / Docker Compose       Isolates each service,
                                                              makes local setup
                                                              reproducible

  Infra      Data ingestion     Python batch script (weekly   Simple, no extra
                                cron)                         infrastructure needed for
                                                              a weekly crawl
  -------------------------------------------------------------------------------------

4.2 Why Not X

Each free/local choice above was picked over a more common commercial
alternative, for reasons specific to this MVP's constraints (solo
project, 1 month, local, free-tier):

-   **Qdrant/ChromaDB instead of Pinecone** --- Pinecone is cloud-only
    and metered; Qdrant/ChromaDB run locally at no cost, which matches
    the local-first constraint of this MVP.

-   **\`vietnamese-sbert\` instead of OpenAI embeddings** --- an
    API-based embedding model means a per-call cost and a network
    dependency for every single chunk and every query; a local
    Vietnamese-tuned model avoids both and keeps embedding entirely
    offline.

-   **bge-reranker instead of Cohere Rerank** --- Cohere Rerank is a
    paid API; bge-reranker delivers comparable re-ranking quality while
    running locally at no cost.

-   **FastAPI instead of Django** --- Django's batteries-included
    structure (ORM, admin panel, templating) adds setup overhead this
    project doesn't need; FastAPI's API-first, async design fits a lean
    RAG backend built solo in a month.

-   **SQLite instead of PostgreSQL** --- PostgreSQL requires running and
    managing a separate database server; for a single-user local MVP,
    SQLite is a file-based store with zero setup, which is the right
    trade-off until multi-user support is actually needed.

4.3 Swap-ability by Design

Every free/local component in this stack --- the embedding model, the
re-ranker, and the LLM engine in particular --- sits behind a single
interface in the codebase rather than being called directly wherever
it's used. This is a deliberate design choice: it means each one can be
swapped for a paid or cloud-hosted alternative later (e.g., an OpenAI
embedding model, Cohere Rerank, or a hosted LLM API) purely by changing
the implementation behind that interface, without touching the
retrieval, ranking, or generation logic built around it.

5\. Sprint Plan (4 Sprints × 1 Week)

Sprint 1 --- Data Pipeline Foundation

**Sprint Goal:** Have a working ingestion pipeline that turns raw Labor
Law and Tax Law documents into properly chunked, embedded, and
searchable data.

**Backlog:**

-   Set up the Docker Compose skeleton (Frontend, Backend API, Vector
    DB, Session store as empty containers wired together).

-   Build the crawler for thuvienphapluat.vn and vanban.chinhphu.vn,
    including the hash-based change detection.

-   Parse Labor Law and Tax Law documents into structured Markdown
    (LlamaParse/Unstructured), preserving heading hierarchy.

-   Implement semantic chunking by Article/Clause and attach metadata
    (luật, điều, chủ_đề).

-   Generate embeddings with vietnamese-sbert and load chunks into the
    Vector DB.

**Definition of Done:** Running the crawler + ingestion script
end-to-end populates the Vector DB with correctly chunked,
metadata-tagged articles from both laws, verifiable by manually querying
the Vector DB for a known article.

Sprint 2 --- Core RAG Pipeline

**Sprint Goal:** Answer a legal question end-to-end with a grounded,
cited response --- no UI yet.

**Backlog:**

-   Implement hybrid search (vector similarity + BM25) against the
    Vector DB.

-   Integrate bge-reranker to reduce top-10 candidates to top-3.

-   Build the prompt construction step (history + re-ranked context +
    question).

-   Wire up the LLM engine call (Qwen2.5-7B-Instruct via Ollama) behind
    the swappable interface.

-   Implement the anti-hallucination system prompt and the out-of-scope
    fallback response.

-   Expose a single /ask API endpoint on the Backend API that runs the
    full pipeline.

**Definition of Done:** Hitting the /ask endpoint with a real Labor Law
or Tax Law question returns an answer with a correct article/clause
citation, and an out-of-scope question correctly triggers the fallback
message.

Sprint 3 --- Frontend & Session Management

**Sprint Goal:** A usable chat interface backed by persistent
conversation history.

**Backlog:**

-   Build the Next.js chat UI (message list, input box, citation
    display).

-   Implement session creation and the Session store read/write flow in
    the Backend API.

-   Connect the Frontend to the /ask endpoint, including loading and
    error states.

-   Add basic error handling and fallback UI for LLM timeouts or empty
    retrieval results.

-   Manual end-to-end testing across a range of Labor Law and Tax Law
    questions.

**Definition of Done:** A user can have a multi-turn conversation in the
chat UI, see cited answers, and reload the page without losing
conversation history for that session.

Sprint 4 --- Evaluation & Contract Review (Stretch)

**Sprint Goal:** Quantify system quality with RAGAS, and attempt the
contract review feature if time allows.

**Backlog:**

-   Build a RAGAS evaluation set of representative Labor Law and Tax Law
    questions with known correct citations.

-   Run RAGAS Faithfulness, Answer Relevance, and Context Precision
    scoring against the pipeline.

-   Tune retrieval/re-ranking thresholds based on evaluation results to
    reach the Faithfulness \> 0.75 target.

-   Measure and optimize end-to-end latency to stay under the 10-second
    target.

-   **Stretch:** implement PDF contract upload, clause splitting, and
    risk highlighting against the Vector DB (Section 2.4).

**Definition of Done:** RAGAS Faithfulness \> 0.75 and median latency \<
10s are both met and documented; the contract review feature is either
shipped or explicitly moved to the backlog with a note on what remains.

6\. Evaluation & Metrics

6.1 Why RAGAS

Claiming a RAG system \"works well\" is not verifiable on its own. The
RAGAS framework is used to score the pipeline against an evaluation set
of representative questions, so quality is backed by a number rather
than a subjective impression --- this is treated as a core deliverable
of the project, not an afterthought.

6.2 Metrics Tracked

-   **Faithfulness** --- whether the generated answer is actually
    supported by the retrieved legal articles, or contains claims not
    present in the context. This is the primary anti-hallucination
    metric and the main acceptance gate for the MVP.

-   **Answer Relevance** --- whether the answer actually addresses the
    user's specific question, rather than a tangentially related
    provision.

-   **Context Precision** --- whether the articles retrieved by hybrid
    search + re-ranking are genuinely relevant to the question, which
    isolates retrieval quality from generation quality.

-   **Latency** --- measured end-to-end from question submission to
    final answer, tracked separately from the RAGAS scores since it is a
    systems metric, not a quality metric.

6.3 Acceptance Criteria

  -----------------------------------------------------------------------
  Metric                              Target
  ----------------------------------- -----------------------------------
  RAGAS Faithfulness                  \> 0.75

  End-to-end latency                  \< 10 seconds
  -----------------------------------------------------------------------

These two targets, set during initial scoping, are the MVP's formal
Definition of Done for Sprint 4 (Section 5) --- the project is not
considered complete until both are met and documented, even if all
features are implemented.

6.4 Evaluation Process

An evaluation set is built from representative Labor Law and Tax Law
questions, each paired with the article/clause that should be cited in a
correct answer. The pipeline is run against this set, RAGAS scores are
computed per question and averaged, and any question scoring poorly on
Context Precision or Faithfulness is inspected individually to determine
whether the issue is in retrieval (wrong article found) or generation
(right article found, but answer not grounded in it) --- a distinction
that directly determines whether Sprint 4 tuning should focus on the
retrieval/re-ranking stage or the prompt/generation stage.

7\. Risks & Known Limitations

7.1 Non-Goals for the MVP

To keep the 1-month, solo-built scope realistic, the following are
explicitly **out of scope** for this MVP:

-   Coverage of other bodies of law (Civil Law, Business Law, Criminal
    Law, etc.) --- only Labor Law and Tax Law are included.

-   Multi-user support --- the system is designed and tested for a
    single local user; there is no authentication or per-user isolation.

-   Cloud deployment --- the MVP runs entirely on a local machine via
    Docker Compose; moving to cloud infrastructure is a future step, not
    part of this delivery.

-   The contract review feature is a stretch goal for Sprint 4 only, and
    may be deferred to the backlog if time runs out (Section 2.4,
    Section 5).

-   A production-grade observability stack (structured logging, metrics
    dashboards, alerting) --- only basic request-ID logging is included
    (Section 2.6).

7.2 Technical Risks

-   **Legal source drift** --- thuvienphapluat.vn and vanban.chinhphu.vn
    may change their page structure at any time, which would silently
    break the crawler. Mitigation: the weekly crawl job's output size
    and hash-diff count are logged, so a sudden drop to near-zero
    updates is a visible signal that parsing broke, rather than a silent
    gap in the data.

-   **Local LLM quality ceiling** --- a 7B-parameter local model
    (Qwen2.5-7B-Instruct) is weaker than large commercial models, which
    may limit how well it follows the anti-hallucination instructions on
    harder or more ambiguous questions. Mitigation: the LLM engine is
    swappable (Section 4.3), so a stronger model or API can be
    substituted if evaluation scores fall short of the Faithfulness
    target.

-   **Chunking edge cases** --- some articles reference other articles,
    or split a single rule across multiple clauses in a way that doesn't
    fit neatly into one chunk; this can cause a retrieved chunk to be
    technically correct but contextually incomplete. Mitigation: this is
    exactly what the RAGAS Context Precision score in Section 6 is
    designed to surface, so it becomes visible during evaluation rather
    than only in production.

-   **Single point of ingestion failure** --- the crawler is a single
    batch script with no redundancy; if a run fails partway through,
    some documents may be left un-updated until the next scheduled run.
    Given the weekly cadence and the low rate of legal change, this is
    an accepted risk for the MVP rather than something actively
    engineered around.

7.3 Legal & Compliance Risk

This system is a research/portfolio project, not a substitute for
professional legal advice. All answers are generated from publicly
available legal texts and are only as current as the last successful
crawl (Section 3.6); it should not be relied on for time-sensitive or
high-stakes legal decisions without independent verification against the
official source.

8\. Appendix

8.1 Glossary

  -----------------------------------------------------------------------
  Term                 Meaning
  -------------------- --------------------------------------------------
  RAG                  Retrieval-Augmented Generation --- grounding LLM
                       answers in retrieved documents rather than the
                       model's parametric memory

  Hybrid Search        Combining vector similarity search with
                       keyword/BM25 search in a single retrieval step

  Re-ranking           Re-scoring an initial set of retrieved candidates
                       with a more precise (and more expensive) model to
                       select the best few

  RAGAS                An open-source framework for automatically scoring
                       RAG pipelines on metrics like Faithfulness and
                       Context Precision

  Chunk                A single retrievable unit of text stored in the
                       Vector DB, here corresponding to one Article or
                       Clause of law
  -----------------------------------------------------------------------

8.2 Reference Sources

-   thuvienphapluat.vn

-   vanban.chinhphu.vn

-   RAGAS documentation (for evaluation methodology, Section 6)

8.3 Future Extensions (Post-MVP)

-   Expand legal coverage beyond Labor Law and Tax Law (Civil Law,
    Business Law).

-   Add authentication and per-user session isolation for multi-user
    deployment.

-   Move from local Docker Compose to a cloud deployment (managed Vector
    DB, managed Session store).

-   Promote the contract review feature from stretch goal to a fully
    supported, tested capability.

-   Add a proper observability stack (structured logs, metrics
    dashboard, alerting) beyond basic request-ID logging.

8.4 Document History

This document was co-authored through an iterative conversation between
the project author and an AI writing assistant, section by section, with
each section reviewed and refined before moving to the next.
