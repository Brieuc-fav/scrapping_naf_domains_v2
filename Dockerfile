# Minimal container for running build_esn_list.py
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (optional curl/ca-certificates for robust HTTPS)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command can be overridden via docker run arguments
# Example:
#   docker run --rm -e SERPER_API_KEY=... esn:latest \
#     python build_esn_list.py --use-recherche --use-serper --serper-key $SERPER_API_KEY \
#       --naf-codes 62.02A,71.12B --per-page 25 --max-pages 80 --outfile /data/out.csv
CMD ["python", "build_esn_list.py", "--help"]
