FROM python:3.13-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
COPY vendor/wheels ./vendor/wheels
RUN python -m pip install --disable-pip-version-check \
    --no-index \
    --find-links=/app/vendor/wheels \
    --prefer-binary \
    -r requirements.txt \
    --default-timeout=120 \
    --retries=5

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
