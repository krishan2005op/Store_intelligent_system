# Docker image will be finalized after API, pipeline, and dependency installation commands exist.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY pipeline ./pipeline
COPY dashboard ./dashboard

CMD ["python", "-m", "app.main"]

