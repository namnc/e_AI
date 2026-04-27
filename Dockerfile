FROM python:3.12-slim

WORKDIR /app

# Install system deps (curl for Ollama install)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copy source
COPY . .

# Default: pull model and run all benchmarks
# Override MODEL env var to change model
ENV MODEL=qwen2.5:32b
ENV BENCHMARK=all

CMD bash -c "\
  ollama serve & \
  sleep 3 && \
  ollama pull \$MODEL && \
  python3 run_benchmarks.py --benchmark \$BENCHMARK --backend ollama --model \$MODEL \
"
