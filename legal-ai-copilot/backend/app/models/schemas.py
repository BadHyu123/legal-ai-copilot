from typing import Optional
from pydantic import BaseModel


class AskRequest(BaseModel):
    session_id: str
    question: str


class Citation(BaseModel):
    luat: str
    dieu: str
    khoan: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    is_fallback: bool = False  # true when no relevant article was found (Section 2.6 / 3.13)
