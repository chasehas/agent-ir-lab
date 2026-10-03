# Agent sandbox image for the worked examples: Python plus curl.
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /work
