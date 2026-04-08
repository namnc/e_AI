#!/bin/bash
# Run all benchmarks and print a summary table.
# Usage: ./run_all.sh [--backend ollama|anthropic] [--model MODEL]
#
# Benchmark F and the classifier require no LLM backend.
# Benchmarks A, B, C, D, E require either an API key or Ollama.

set -e
cd "$(dirname "$0")"

BACKEND="${1:---backend}"
if [ "$BACKEND" = "--backend" ]; then
    BACKEND_ARG=""
else
    BACKEND_ARG="--backend $1 --model ${2:-qwen2.5:7b}"
    shift 2 2>/dev/null || shift 1
fi

echo "============================================"
echo "  Private Query Problem — Full Benchmark Run"
echo "============================================"
echo ""

# Always run these (no LLM needed)
echo ">>> Benchmark F (damage simulation — no LLM needed)"
python run_benchmarks.py --benchmark F $BACKEND_ARG 2>&1 | tail -20
echo ""

echo ">>> Sanitizer unit tests"
python test_sanitizer.py
echo ""

echo ">>> Classifier validation (n=1000, no LLM needed)"
python classifier_validation.py run --n-sets 1000 2>&1 | grep -A20 "CLASSIFIER VALIDATION"
echo ""

# LLM-dependent benchmarks
if [ -n "$BACKEND_ARG" ] || [ -n "$ANTHROPIC_API_KEY" ]; then
    echo ">>> Benchmark A (sensitivity classification, n=50)"
    python run_benchmarks.py --benchmark A --samples 50 $BACKEND_ARG 2>&1 | tail -10
    echo ""

    echo ">>> Benchmark B (decomposition quality)"
    python run_benchmarks.py --benchmark B $BACKEND_ARG 2>&1 | tail -8
    echo ""

    echo ">>> Benchmark C v5 (cover indistinguishability, n=20)"
    python run_benchmarks.py --benchmark C --cover-version v5 $BACKEND_ARG 2>&1 | tail -15
    echo ""

    echo ">>> Benchmark D (answer quality, n=15)"
    python run_benchmarks.py --benchmark D --samples 15 $BACKEND_ARG 2>&1 | tail -10
    echo ""

    echo ">>> Benchmark E (session composition)"
    python run_benchmarks.py --benchmark E $BACKEND_ARG 2>&1 | tail -25
    echo ""
else
    echo ">>> Skipping LLM-dependent benchmarks (A, B, C, D, E)"
    echo "    Set ANTHROPIC_API_KEY or pass: ./run_all.sh ollama qwen2.5:7b"
    echo ""
fi

echo "============================================"
echo "  All benchmarks complete."
echo "  Results saved to results/"
echo "============================================"
