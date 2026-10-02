from typing import Optional
from pydantic import BaseModel


class AskRequest(BaseModel):
    session_id: str
    question: str


class Citation(BaseModel):
    luat: str
    dieu: str
    khoan: Optional[str] = None
    # The cited chunk's own text and source page, so the user can verify
    # the citation without leaving the chat (architecture doc, Section 1.3).
    text: str = ""
    source_url: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    is_fallback: bool = False  # true when no relevant article was found (Section 2.6 / 3.13)
