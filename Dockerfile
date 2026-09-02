# Build stage: compile any wheels that need a toolchain.
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt README.md ./
# Build wheels for the core runtime only. Optional stacks (torch, streamlit,
# playwright) are extras and are not baked into the default image.
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# Runtime stage: no compiler, no root.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels

COPY . .
RUN pip install --no-cache-dir --no-deps -e .

# Run as an unprivileged user and give it ownership of the writable dirs.
RUN useradd --create-home --uid 10001 trader \
    && mkdir -p /app/data /app/logs /app/results /app/models \
    && chown -R trader:trader /app
USER trader

RUN python main.py init

EXPOSE 8000 8501

# Paper trading only -- this container never places a real order.
CMD ["python", "main.py", "run", "--name", "AlphaBot", "--rounds", "10"]
