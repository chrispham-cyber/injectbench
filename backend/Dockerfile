# Backend image: the read-only FastAPI service over saved runs.
# Build context is the repo root (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

# Install deps first so this layer is cached unless requirements change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + the data the API needs at import/serve time.
# (evals/results -- the saved runs -- is a runtime volume, not baked in.)
COPY backend ./backend
COPY corpus ./corpus
COPY evals/judge_validation.yaml ./evals/judge_validation.yaml

EXPOSE 8000
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
