# syntax=docker/dockerfile:1

FROM python:3.11-slim@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6 AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6 AS runtime
# HOME + these cache dirs must be writable by the non-root user: fastembed /
# huggingface_hub / onnxruntime download the embedding model at first use.
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    FASTEMBED_CACHE_PATH=/home/app/.cache/fastembed \
    HF_HOME=/home/app/.cache/huggingface
WORKDIR /app
COPY --from=build /install /usr/local
COPY app ./app
RUN useradd --uid 10001 --create-home --home-dir /home/app --shell /usr/sbin/nologin app \
    && mkdir -p /home/app/.cache/fastembed /home/app/.cache/huggingface \
    && chown -R app:app /app /home/app
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health', timeout=2).status==200 else sys.exit(1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
