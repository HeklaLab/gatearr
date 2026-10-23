FROM node:24.22.1-bookworm-slim AS cap-runtime
FROM python:3.12-slim-bookworm
COPY --from=cap-runtime /usr/local/bin/node /usr/local/bin/node
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
ARG GATEARR_BUILD_REVISION=
ENV GATEARR_BUILD_REVISION=${GATEARR_BUILD_REVISION}
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 libatomic1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt && groupadd -g 10001 portal && useradd -u 10001 -g portal portal && mkdir /data && chown portal:portal /data
COPY --chown=portal:portal . .
USER portal
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["python", "-m", "app.bootstrap"]
