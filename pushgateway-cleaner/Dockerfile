FROM python:3.12-slim
WORKDIR /app
COPY cleaner.py .
ENV STALE_SECONDS=60
ENV CHECK_INTERVAL=20
CMD ["python", "-u", "cleaner.py"]
