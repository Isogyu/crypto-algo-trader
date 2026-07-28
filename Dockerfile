FROM python:3.11-slim

WORKDIR /app

# Install build dependencies and the project
COPY pyproject.toml README.md ./
COPY algo_trader ./algo_trader

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[test]"

# Create data directory for tax logs
RUN mkdir -p /app/algo_trader/data

CMD ["python", "-m", "algo_trader.src.main", "--paper"]
