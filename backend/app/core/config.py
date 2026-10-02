"""Centralized settings, loaded from environment / .env (see .env.example)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    vector_db_host: str = "vector-db"
    vector_db_port: int = 6333
    vector_db_collection: str = "legal_articles"

    session_db_path: str = "/data/crawler_state/session.db"

    embedding_model: str = "keepitreal/vietnamese-sbert"
    reranker_model: str = "BAAI/bge-reranker-base"
    # Below this top rerank score, /ask returns the fixed fallback without
    # calling the LLM. Calibrated for bge-reranker-base with
    # eval/run_eval.py (2026-10-02): blocks 7/8 out-of-scope questions,
    # wrongly blocks 1/48 in-scope. Re-run the eval and re-pick this value
    # whenever the reranker model changes — scores aren't comparable across
    # models (bge-reranker-v2-m3 separates perfectly at ~0.16).
    rerank_relevance_threshold: float = 0.3

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
