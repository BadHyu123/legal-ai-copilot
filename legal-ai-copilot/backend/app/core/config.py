"""Centralized settings, loaded from environment / .env (see .env.example)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    vector_db_host: str = "vector-db"
    vector_db_port: int = 6333
    vector_db_collection: str = "legal_articles"

    session_db_path: str = "/data/crawler_state/session.db"

    embedding_model: str = "keepitreal/vietnamese-sbert"
    reranker_model: str = "BAAI/bge-reranker-base"

    llm_provider: str = "ollama"  # ollama | external_api
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    external_llm_api_key: str = ""

    backend_port: int = 8000
    log_level: str = "info"

    class Config:
        env_file = ".env"


settings = Settings()
