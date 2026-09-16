"""
Cross-encoder re-ranking with bge-reranker: narrows the top-10 hybrid
search candidates down to the top-3 most relevant (architecture doc,
Section 3.10). Sprint 2 backlog item.
"""


def rerank(question: str, candidates: list[dict], top_k: int = 3) -> list[dict]:
    """
    TODO (Sprint 2): load bge-reranker (BAAI/bge-reranker-base per
    settings.reranker_model), score each candidate against `question`,
    and return the top_k highest-scoring candidates.
    """
    raise NotImplementedError
