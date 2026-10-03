"""Centralized settings, loaded from environment / .env (see .env.example)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    vector_db_host: str = "vector-db"
    vector_db_port: int = 6333
    vector_db_collection: str = "legal_articles"

    session_db_path: str = "/data/crawler_state/session.db"

    embedding_model: str = "keepitreal/vietnamese-sbert"
    # Multilingual cross-encoder: bge-reranker-base (English/Chinese) left
    # 31% of everyday-phrased questions below any usable threshold on the
    # held-out set; v2-m3 separates in-scope from out-of-scope cleanly
    # (eval/run_eval.py, 2026-10-03).
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    # Cross-encoder input cap (tokens). v2-m3 defaults to 8192, which made
    # long chunks cost up to ~25 s on CPU; 512 covers the Article header +
    # lead-in + clause that decide relevance (384 vs 512: same accuracy).
    reranker_max_length: int = 512
    # Dynamic int8 on CPU: ~2x faster than fp32 (14 s -> 7 s for 10 pairs),
    # same dev-set accuracy. The GPU can't take it: 3B LLM + v2-m3 fp16
    # don't fit in 4 GB VRAM.
    reranker_int8: bool = True
    # Below this top rerank score, /ask returns the fixed fallback without
    # calling the LLM. Picked for v2-m3 on the dev set, where out-of-scope
    # tops out at 0.05 and in-scope starts at 0.50: kept low in that gap,
    # since wrongly refusing a real question costs more and the LLM's own
    # "không tìm thấy" (ask.is_refusal) is a second gate. Scores aren't
    # comparable across rerankers: re-pick it if the model changes.
    rerank_relevance_threshold: float = 0.2
    # The LLM restates the question in legal terms (and makes follow-ups
    # standalone) before retrieval: "bán cổ phiếu" -> "chuyển nhượng
    # chứng khoán". ~0.7 s on the 3B.
    query_rewrite: bool = True

    llm_provider: str = "ollama"  # ollama | external_api
    ollama_base_url: str = "http://host.docker.internal:11434"
    # 3B, not the architecture doc's 7B: on the 4 GB-VRAM dev GPU the 7B
    # spills to CPU (3.4 tok/s, ~60 s per answer, misses the < 10 s target),
    # while the 3B fits fully (58 tok/s) and still scores Faithfulness 0.83
    # (eval/run_eval.py --llm, 2026-10-02). Use 7B on a GPU with >= 8 GB.
    ollama_model: str = "qwen2.5:3b-instruct"
    external_llm_api_key: str = ""

    backend_port: int = 8000
    log_level: str = "info"

    class Config:
        env_file = ".env"


settings = Settings()
