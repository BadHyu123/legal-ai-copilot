# Build context is the repo root (see docker-compose.yml) so this
# Dockerfile can also copy ./shared, which lives outside the backend/ folder.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
# CPU-only torch: the host GPU is left to Ollama, and the CUDA wheel
# would add several GB to the image for models this small.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY shared/ ./shared/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
