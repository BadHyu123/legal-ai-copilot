"""
/review — contract review (architecture doc, Section 2.4). Takes an
uploaded contract (PDF, .docx, .txt) or pasted text and streams one JSON
line per clause (NDJSON) as each is reviewed, so the UI shows results as
they come instead of waiting for the whole contract (~8 s per clause).

First line: {"total": N, "skipped": M}, where M clauses past MAX_CLAUSES
are not reviewed (the UI says so). Then one services.review.review_clause()
result per clause, in document order.
"""

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.services import review

router = APIRouter(tags=["review"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/review")
def review_contract(file: UploadFile | None = File(None), text: str = Form("")) -> StreamingResponse:
    if file is not None:
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Tệp quá lớn (tối đa 10 MB).")
        try:
            text = review.extract_text(file.filename or "", data)
        except review.UnreadableDocument as e:
            raise HTTPException(422, str(e))

    clauses = review.split_clauses(text)
    if not clauses:
        raise HTTPException(422, "Không tìm thấy điều khoản nào để rà soát.")
    # ponytail: hard cap (~5 min of CPU per request); review in pages if long contracts matter.
    skipped = max(0, len(clauses) - review.MAX_CLAUSES)
    clauses = clauses[:review.MAX_CLAUSES]

    def stream():
        yield json.dumps({"total": len(clauses), "skipped": skipped}) + "\n"
        for clause in clauses:
            yield json.dumps(review.review_clause(clause), ensure_ascii=False) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")
