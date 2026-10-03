"""
Retrieval evaluation (architecture doc, Section 6.4) — deterministic, no
LLM needed unless --llm is passed. Run from the repo root against a
populated Qdrant:

    python eval/run_eval.py            # retrieval + rerank + threshold
    python eval/run_eval.py --llm      # + answer latency and faithfulness (needs Ollama)
    python eval/run_eval.py --questions eval/questions_holdout.jsonl   # held-out set
    python eval/run_eval.py --llm --no-judge   # latency + end-to-end fallback, minutes not an hour

Reports, for eval/questions.jsonl:
  - Recall@10 of hybrid search and Hit@3 / MRR@3 after reranking, against
    the expected (luat, dieu) — separating "wrong article retrieved" from
    "right article retrieved but reranked away".
  - Top rerank score for in-scope vs. out-of-scope questions, and the
    threshold that best separates them -> RERANK_RELEVANCE_THRESHOLD.
  - Per-stage latency p50/p95.
  - With --llm: Faithfulness (Section 6.2), computed the way RAGAS defines
    it — split the answer into atomic claims, check each against the
    retrieved context, score = supported / total — with a local judge
    model (JUDGE_MODEL, default the 7B) via Ollama structured output.
    The ragas package itself is skipped on purpose: its English prompts
    need strict JSON that small local judges often break, yielding NaN.
Uses the backend's own code paths and settings (.env in the cwd), so it
measures exactly what /ask does.
"""

import json
import os
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.routes.ask import HYBRID_SEARCH_TOP_K, RERANK_TOP_K, find_context, is_refusal  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services import llm  # noqa: E402


JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "qwen2.5:7b-instruct")
_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"claims": {"type": "array", "items": {
        "type": "object",
        "properties": {"claim": {"type": "string"}, "supported": {"type": "boolean"}},
        "required": ["claim", "supported"],
    }}},
    "required": ["claims"],
}
_JUDGE_PROMPT = """Bạn là người chấm điểm độ trung thực (faithfulness) của câu trả lời pháp lý.
Tách CÂU TRẢ LỜI thành các khẳng định độc lập (mỗi khẳng định là một ý về nội dung pháp luật; bỏ qua câu dẫn dắt, câu chào).
Với mỗi khẳng định, "supported" = true CHỈ KHI nội dung đó được suy ra trực tiếp từ NGỮ CẢNH; nếu không có trong ngữ cảnh hoặc sai với ngữ cảnh thì false.

NGỮ CẢNH:
{context}

CÂU TRẢ LỜI:
{answer}"""


def faithfulness(answer: str, context_chunks: list[dict]) -> tuple[float | None, list[dict]]:
    """RAGAS-style faithfulness: supported claims / all claims. None when the
    answer makes no claims (e.g. it says nothing relevant was found)."""
    context = "\n\n".join(c["payload"].get("text", "") for c in context_chunks)
    resp = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json={"model": JUDGE_MODEL, "stream": False, "format": _JUDGE_SCHEMA,
              "options": {"num_ctx": 8192, "temperature": 0},
              "messages": [{"role": "user", "content": _JUDGE_PROMPT.format(context=context, answer=answer)}]},
        timeout=900.0,
    )
    resp.raise_for_status()
    claims = json.loads(resp.json()["message"]["content"]).get("claims", [])
    if not claims:
        return None, []
    return sum(bool(c.get("supported")) for c in claims) / len(claims), claims


def _hit_rank(results: list[dict], q: dict) -> int | None:
    """1-based rank of the first result citing an expected Điều, else None."""
    for rank, r in enumerate(results, 1):
        p = r["payload"]
        if p.get("luat") == q["luat"] and p.get("dieu") in q["dieu"]:
            return rank
    return None


def _pct(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p * (len(values) - 1))))]


def best_threshold(in_scores: list[float], out_scores: list[float]) -> tuple[float, float]:
    """Threshold (midpoint between adjacent observed scores) maximizing
    accuracy of "in-scope >= t, out-of-scope < t". Returns (t, accuracy)."""
    points = sorted(set(in_scores + out_scores))
    candidates = [0.0] + [(a + b) / 2 for a, b in zip(points, points[1:])]
    total = len(in_scores) + len(out_scores)

    def acc(t: float) -> float:
        return (sum(s >= t for s in in_scores) + sum(s < t for s in out_scores)) / total

    # Ties -> lowest threshold: wrongly falling back on a real question is
    # the costlier mistake for a legal assistant than answering an
    # out-of-scope one (which the LLM prompt still guards).
    t = max(candidates, key=lambda c: (acc(c), -c))
    return t, acc(t)


def _selftest() -> None:
    t, acc = best_threshold([0.9, 0.8, 0.4], [0.1, 0.3])
    assert t == 0.35 and acc == 1.0, (t, acc)
    t, acc = best_threshold([0.9, 0.2], [0.5])  # can't separate: keep the real question
    assert t < 0.2 and acc == 2 / 3, (t, acc)
    print("eval selftest OK")


def main() -> None:
    if "--selftest" in sys.argv:
        return _selftest()
    with_llm = "--llm" in sys.argv
    # --questions eval/questions_holdout.jsonl: the held-out set, written
    # before tuning and never used to choose settings — report it, don't tune on it.
    qfile = Path(sys.argv[sys.argv.index("--questions") + 1]) if "--questions" in sys.argv else ROOT / "eval" / "questions.jsonl"
    questions = [json.loads(l) for l in qfile.read_text(encoding="utf-8").splitlines() if l.strip()]

    # Load models + build the BM25 index before timing anything.
    find_context("khởi động", [])  # also loads the LLM when query_rewrite is on

    rows = []
    timings: dict[str, list[float]] = {"context": [], "llm": [], "end_to_end": []}
    for q in questions:
        t0 = time.perf_counter()
        candidates, reranked = find_context(q["question"], [])
        t2 = time.perf_counter()
        timings["context"].append(t2 - t0)  # (rewrite +) hybrid search + rerank

        top_score = reranked[0]["rerank_score"] if reranked else 0.0
        answer, refused = None, False
        # Same gates as /ask: the threshold, then the LLM's own "không tìm thấy".
        if with_llm and top_score >= settings.rerank_relevance_threshold:
            answer = llm.generate_answer(q["question"], [], reranked)
            timings["llm"].append(time.perf_counter() - t2)
            timings["end_to_end"].append(time.perf_counter() - t0)
            if is_refusal(answer):
                answer, refused = None, True

        row = {"q": q, "top_score": top_score, "reranked": reranked, "answer": answer, "refused": refused,
               "top": [f"{r['payload'].get('dieu')}{', ' + r['payload']['khoan'] if r['payload'].get('khoan') else ''}"
                       f" ({r['payload'].get('luat', '')[:22]})" for r in reranked]}
        if not q.get("out_of_scope"):
            row["recall10"] = _hit_rank(candidates, q) is not None
            row["rank3"] = _hit_rank(reranked, q)
        rows.append(row)

    in_rows = [r for r in rows if not r["q"].get("out_of_scope")]
    out_rows = [r for r in rows if r["q"].get("out_of_scope")]

    print("\n== Misses (expected Điều not in top 3) ==")
    for r in in_rows:
        if r["rank3"] is None:
            print(f"- {r['q']['question']}\n    expected {r['q']['dieu']} | "
                  f"in top10: {r['recall10']} | got: {'; '.join(r['top'])}")

    print("\n== Retrieval ==")
    n = len(in_rows)
    print(f"Recall@{HYBRID_SEARCH_TOP_K} (hybrid): {sum(r['recall10'] for r in in_rows) / n:.2f}")
    print(f"Hit@{RERANK_TOP_K} (reranked):  {sum(r['rank3'] is not None for r in in_rows) / n:.2f}")
    print(f"MRR@{RERANK_TOP_K}:              {sum(1 / r['rank3'] for r in in_rows if r['rank3']) / n:.2f}")

    in_scores = [r["top_score"] for r in in_rows]
    out_scores = [r["top_score"] for r in out_rows]
    print("\n== Top rerank score (fallback threshold) ==")
    print(f"in-scope:     min={min(in_scores):.3f} p10={_pct(in_scores, .1):.3f} median={statistics.median(in_scores):.3f}")
    print(f"out-of-scope: max={max(out_scores):.3f} p90={_pct(out_scores, .9):.3f} median={statistics.median(out_scores):.3f}")
    for r in out_rows:
        print(f"    {r['top_score']:.3f}  {r['q']['question']}")
    t, acc = best_threshold(in_scores, out_scores)
    print(f"Suggested RERANK_RELEVANCE_THRESHOLD={t:.3f} (separation accuracy {acc:.2f}; "
          f"current setting {settings.rerank_relevance_threshold})")
    for r in in_rows:
        if r["top_score"] < max(t, settings.rerank_relevance_threshold):
            print(f"    in-scope below threshold: {r['top_score']:.3f}  {r['q']['question']}")

    print("\n== Latency (seconds) ==")
    for stage, values in timings.items():
        if values:
            print(f"{stage:10s} p50={statistics.median(values):.2f} p95={_pct(values, .95):.2f}")

    if with_llm:
        thr = settings.rerank_relevance_threshold
        blocked = lambda r: r["top_score"] < thr or r["refused"]  # noqa: E731
        print("\n== End-to-end fallback (threshold, then LLM refusal) ==")
        print(f"out-of-scope blocked: {sum(map(blocked, out_rows))}/{len(out_rows)} "
              f"({sum(r['refused'] for r in out_rows)} by the LLM's refusal)")
        print(f"in-scope wrongly blocked: {sum(map(blocked, in_rows))}/{len(in_rows)} "
              f"({sum(r['refused'] for r in in_rows)} by the LLM's refusal)")
        for r in in_rows:
            if r["refused"]:
                print(f"    LLM refused: {r['q']['question']} | context: {'; '.join(r['top'])}")
        for r in out_rows:
            if not blocked(r):
                print(f"    out-of-scope ANSWERED: {r['q']['question']} -> {r['answer'][:200]!r}")

        lengths = [len(r["answer"]) for r in rows if r["answer"]]
        if lengths:
            print(f"answer length (chars): p50={statistics.median(lengths):.0f} max={max(lengths)}")
        if "--no-judge" in sys.argv:  # latency/fallback check only, skips the ~45 min judge
            return

        # Judged after all answers exist, so the judge model never evicts the
        # answer model from VRAM mid-run (that would distort the latency above).
        print(f"\n== Faithfulness (judge: {JUDGE_MODEL}) ==")
        scores = []
        for r in in_rows:
            if r["answer"] is None:
                continue
            score, claims = faithfulness(r["answer"], r["reranked"])
            if score is None:
                continue
            scores.append(score)
            if score < 1:
                print(f"- {score:.2f}  {r['q']['question']}")
                for c in claims:
                    if not c.get("supported"):
                        print(f"      unsupported: {c.get('claim', '')[:160]}")
        if scores:
            print(f"Faithfulness mean={statistics.mean(scores):.3f} over {len(scores)} answers "
                  f"(target > 0.75), model {settings.ollama_model}")


if __name__ == "__main__":
    main()
