FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Minimal system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Install pinned, compatible versions ---
# (Torch CPU first from PyTorch index, then the rest)
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir torch==2.3.1+cpu -f https://download.pytorch.org/whl/torch_stable.html \
 && pip install --no-cache-dir \
      praw==7.7.1 \
      azure-eventhub==5.11.5 \
      transformers==4.41.2 \
      numpy==1.26.4

# Copy the app
COPY ingest.py .

# Default envs (override at run-time)
ENV KEYWORDS="donald trump,trump" \
    SUBREDDITS="all" \
    BATCH_SIZE=50 \
    FLUSH_SECONDS=5 \
    SLEEP_ON_ERROR=5 \
    TEXT_MAX_CHARS=512

# Run
CMD ["python", "ingest.py"]
