#!/bin/bash
# One-command setup: clone → install → pull model → ready to run
# Usage: bash setup.sh [model_name]
# Example: bash setup.sh qwen2.5:72b

set -e

MODEL="${1:-qwen2.5:32b}"

echo "=== e_AI Private Query Problem: Setup ==="
echo "Target model: $MODEL"
echo ""

# 1. Python dependencies
echo "--- Installing Python dependencies ---"
pip install -r requirements.txt
echo ""

# 2. Check/install Ollama
if ! command -v ollama &> /dev/null; then
    echo "--- Installing Ollama ---"
    curl -fsSL https://ollama.com/install.sh | sh
    echo ""
fi

# 3. Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "--- Starting Ollama ---"
    ollama serve &
    sleep 3
fi

# 4. Pull model
echo "--- Pulling model: $MODEL ---"
ollama pull "$MODEL"
echo ""

# 5. Verify
echo "--- Verifying setup ---"
python3 -c "
from llm_backend import init_backend, call_llm
init_backend('ollama', '$MODEL')
resp = call_llm('Say hello in one word.')
print(f'Model responded: {resp[:50]}')
print('Setup OK.')
"

echo ""
echo "=== Ready ==="
echo ""
echo "Run experiments:"
echo "  python run_benchmarks.py --benchmark all --backend ollama --model $MODEL"
echo "  python run_benchmarks.py --benchmark C --cover-version v5 --samples 50 --backend ollama --model $MODEL"
echo "  python run_benchmarks.py --benchmark E --backend ollama --model $MODEL"
echo ""
echo "Compare models:"
echo "  python compare_profiles.py --backend ollama --model $MODEL"
echo ""
echo "Results saved to: results/"
