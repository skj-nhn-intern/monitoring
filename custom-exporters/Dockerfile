FROM python:3.12-slim

LABEL maintainer="NHN Cloud Monitoring Team"
LABEL description="NHN Cloud Custom Prometheus Exporter (LB, CDN, RDS)"

WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY src/ src/

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --no-deps .

COPY exporter.py .

EXPOSE 9101

ENV PYTHONUNBUFFERED=1
ENV EXPORTER_PORT=9101
ENV SCRAPE_INTERVAL=60
ENV LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:9101/metrics', timeout=5)" || exit 1

USER nobody

ENTRYPOINT ["python", "exporter.py"]
