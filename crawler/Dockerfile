# Build context is the repo root (see docker-compose.yml) so this
# Dockerfile can also copy ./shared, which lives outside the crawler/ folder.
FROM python:3.11-slim

WORKDIR /app

COPY crawler/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY crawler/crawler/ ./crawler/
COPY shared/ ./shared/

ENTRYPOINT ["python", "-m", "crawler.main"]
