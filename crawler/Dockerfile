# Build context is the repo root (see docker-compose.yml) so this
# Dockerfile can also copy ./shared, which lives outside the crawler/ folder.
FROM python:3.11-slim

WORKDIR /app

COPY crawler/requirements.txt .
# CPU-only torch — see backend/Dockerfile.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Mirror the repo layout (/app/crawler/crawler, /app/shared) so
# chunker.py's parents[2] / "shared" path resolves the same in both.
COPY crawler/crawler/ ./crawler/crawler/
COPY shared/ ./shared/

WORKDIR /app/crawler

ENTRYPOINT ["python", "-m", "crawler.main"]
