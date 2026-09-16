# Build context is the repo root (see docker-compose.yml) so this
# Dockerfile can also copy ./shared, which lives outside the backend/ folder.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY shared/ ./shared/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
