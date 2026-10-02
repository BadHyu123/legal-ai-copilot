# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Luôn trả lời người dùng bằng tiếng Việt.** Code, tên biến và commit message giữ nguyên theo quy ước hiện có của repo.

Hệ thống RAG chạy local, trả lời câu hỏi về Luật Lao động và Luật Thuế Việt Nam kèm trích dẫn. Thiết kế đầy đủ: `docs/architecture.md` (comment trong code trích số mục của tài liệu này, ví dụ "Section 2.3"). Tiến độ sprint và checklist chạy thật lần đầu nằm trong `README.md` — cập nhật khi hoàn thành công việc.

## Lệnh thường dùng

Chưa có linter/formatter. Test chỉ là self-check bằng assert cho logic thuần (không cần model/Qdrant/Ollama): `cd backend && python -m tests.test_logic`, `cd crawler && python -m tests.test_logic`, `python eval/run_eval.py --selftest`. Đo chất lượng thật (cần Qdrant đã có dữ liệu): `python eval/run_eval.py` (Recall/Hit@3/MRR, gợi ý ngưỡng fallback, latency), thêm `--llm` để đo Faithfulness (judge 7B, ~45 phút). Mọi thay đổi retrieval/model nên được so sánh bằng script này.

Máy dev: Windows, chưa có Docker; toàn bộ stack đã chạy thật ngoài Docker theo mục "Running without Docker" trong README. Dùng `127.0.0.1` thay `localhost` (localhost trên Windows chậm ~2s mỗi request).

```bash
cp .env.example .env
docker-compose up --build frontend backend vector-db   # toàn bộ stack (UI :3000, API :8000, Qdrant :6333)
docker-compose --profile crawler run law-crawler       # job crawl offline (không tự khởi động)

cd frontend && npm install && npm run dev               # chỉ UI; `npm run build` để kiểm tra kiểu
```

Ollama **không** nằm trong compose — chạy trên máy host (`ollama pull qwen2.5:3b-instruct` — 3B là mặc định vì GPU 4GB; 7B tràn VRAM, ~60s mỗi câu); backend gọi qua `host.docker.internal`.

Mỗi module crawler có smoke test trong `__main__`. Chạy từ thư mục `crawler/` để package `crawler` được tìm thấy:

```bash
cd crawler
python -m crawler.sources.luatvietnam       # fetch thật (danh sách văn bản cố định)
python -m crawler.parser
python -m crawler.chunker
python -m crawler.embedder                  # Qdrant in-memory, tải model embedding
python -m crawler.sources.vanban_chinhphu   # phân trang ASP.NET postback (không gửi kèm nút submit)
```

Smoke test backend: `curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"session_id":"test","question":"..."}'`.

Chạy backend ngoài Docker: `cd backend && uvicorn app.main:app --reload`. Settings (`backend/app/core/config.py`) đọc `.env` theo thư mục hiện tại và mặc định dùng hostname/đường dẫn của Docker (`vector-db`, `/data/crawler_state/...`), nên cần override `VECTOR_DB_HOST`, `SESSION_DB_PATH`, `OLLAMA_BASE_URL` khi chạy local.

## Kiến trúc

Ba thành phần nối với nhau bằng một hợp đồng dữ liệu:

1. **Crawler** (`crawler/`, batch offline) — pipeline trong `main.py`: lấy danh sách văn bản cố định (ưu tiên văn bản hợp nhất VBHN) từ luatvietnam.vn (`sources/luatvietnam.py`; thuvienphapluat.vn chặn bot bằng Cloudflare nên đã bỏ — không tìm cách vượt) → đối chiếu với cơ sở dữ liệu văn bản của vanban.chinhphu.vn (chỉ ghi log, không chặn ingest) → phát hiện thay đổi bằng hash → HTML sang Markdown có cấu trúc → chia chunk theo Điều, Điều dài thì tách theo Khoản → embed bằng `vietnamese-sbert` → upsert vào Qdrant.
2. **Backend** (`backend/`, FastAPI) — thành phần duy nhất giao tiếp với Qdrant, session store SQLite và LLM. `/ask` (`api/routes/ask.py`) điều phối: tải lịch sử → hybrid search → rerank → kiểm tra fallback → LLM → trích dẫn → lưu hội thoại.
3. **Frontend** (`frontend/`, Next.js 14 app router, không dùng thư viện UI) — giao diện chat gọi `/ask` và `/sessions/{id}/messages`.

Các quy tắc xuyên suốt nhiều file:

- **Hợp đồng metadata của chunk**: `shared/metadata_schema.py` (`ChunkMetadata`: `luat`, `dieu`, `khoan`, `chu_de`, ...) là payload crawler ghi vào Qdrant và backend đọc ra để trích dẫn. Chỉ dùng stdlib. Khóa định danh `luat|dieu|khoan` dùng cho cả point ID trong embedder lẫn khử trùng lặp RRF trong `retrieval.py` — sửa thì sửa cả hai.
- **Model embedding phải khớp** giữa `crawler/crawler/embedder.py` và `backend/app/services/retrieval.py` (cùng qua `EMBEDDING_MODEL`), nếu không vector search sẽ so sánh sai không gian.
- **Hybrid search**: vector search của Qdrant + `rank_bm25` in-memory trên toàn bộ corpus (lấy qua `vector_store.scroll_all()`, cache TTL 15 phút), gộp bằng reciprocal rank fusion. Cố ý — text index của Qdrant là lọc boolean, không phải điểm BM25 có xếp hạng.
- **Chống bịa đặt nằm ở phía retrieval**: nếu điểm rerank cao nhất thấp hơn `RERANK_RELEVANCE_THRESHOLD` (`.env` → `config.py`, `0.3` — hiệu chỉnh bằng `eval/run_eval.py` cho bge-reranker-base; đổi reranker thì phải chạy lại eval và chọn lại ngưỡng), `/ask` trả về câu fallback cố định *mà không gọi LLM*. Trích dẫn lấy từ các chunk đã retrieve, không parse từ output của LLM.
- **Session**: file SQLite tại `SESSION_DB_PATH` (mount volume, không có container riêng) là nguồn dữ liệu gốc của tin nhắn. localStorage trong `lib/session.ts` của frontend chỉ lưu danh sách session ID/tiêu đề cho sidebar.
- **Import `shared/`**: cả hai Dockerfile build từ thư mục gốc repo. Chỉ `chunker.py` thêm `shared/` vào `sys.path` (`parents[2] / "shared"`); module khác cần `metadata_schema` thì import `crawler.chunker` trước. Dockerfile của crawler copy file theo đúng cấu trúc repo (`/app/crawler/crawler`, `/app/shared`) để đường dẫn này đúng ở cả hai nơi — đổi cấu trúc thư mục thì sửa cả hai.
- Các model/client nặng (SentenceTransformer, CrossEncoder, QdrantClient) là biến global lazy-load; giữ import bên trong hàm getter để app khởi động được khi chưa có chúng.

## Quy ước

- Chuỗi hiển thị cho người dùng (câu trả lời, fallback, lỗi ở frontend) bằng tiếng Việt.
- Thiết kế frontend có chủ đích (xem "Frontend design notes" trong README): serif Spectral cho câu trả lời AI/trích dẫn, IBM Plex Sans cho phần giao diện, tag trích dẫn màu đồng thau, fallback dùng màu dịu (không gây báo động). Design token nằm trong `frontend/src/app/globals.css`. Các lựa chọn này ưu tiên hơn skill `design-taste-frontend` (skill đó cấm serif/màu đồng thau làm mặc định và hướng tới landing page, không phải UI chat).
