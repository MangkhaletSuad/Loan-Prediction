FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system --gid 10001 flowvault && adduser --system --uid 10001 --ingroup flowvault flowvault

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=flowvault:flowvault . ./
RUN mkdir -p /data/storage /data/recycle-bin && chown -R flowvault:flowvault /app /data

USER flowvault

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "60", "app:app"]
