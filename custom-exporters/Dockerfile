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
ENV LOG_LEVEL=WARNING
ENV LOG_RETENTION_DAYS=7

# 주기 완화로 /tmp runc 임시파일 축적 감소, TCP 체크로 리소스 최소화
HEALTHCHECK --interval=90s --timeout=5s --retries=2 --start-period=15s \
    CMD python -c "import socket; s=socket.create_connection(('127.0.0.1',9101), timeout=3); s.close()" || exit 1

USER nobody

ENTRYPOINT ["python", "exporter.py"]
