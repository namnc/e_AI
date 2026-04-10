#!/bin/bash
# Run all benchmarks and print a summary table.
# Usage:
#   ./run_all.sh                              # non-LLM benchmarks only
#   ./run_all.sh ollama qwen2.5:7b            # all benchmarks with Ollama
#   ./run_all.sh anthropic claude-haiku-4-5    # all benchmarks with Anthropic

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
BACKEND_ARG=""

if [ $# -ge 2 ]; then
    BACKEND_ARG="--backend $1 --model $2"
    echo "Backend: $1 | Model: $2"
elif [ $# -eq 1 ]; then
    BACKEND_ARG="--backend $1"
    echo "Backend: $1 (default model)"
fi

echo "============================================"
echo "  Private Query Problem — Full Benchmark Run"
echo "============================================"
echo ""

# Always run these (no LLM needed)
echo ">>> Sanitizer unit tests"
$PYTHON test_sanitizer.py
echo ""

echo ">>> Sanitizer completeness audit"
$PYTHON test_sanitizer_audit.py 2>&1 | tail -5 || echo "  (audit reported non-zero leaks — see above; continuing)"
echo ""

echo ">>> Simulation F (economic damage model — no LLM needed)"
$PYTHON run_benchmarks.py --benchmark F 2>&1 | tail -20
echo ""

echo ">>> Classifier validation (n=1000, no LLM needed)"
if $PYTHON -c "import torch, transformers, sklearn" 2>/dev/null; then
    $PYTHON classifier_validation.py run --n-sets 1000 2>&1 | grep -A20 "CLASSIFIER VALIDATION"
else
    echo "  SKIPPED: missing dependencies (torch, transformers, scikit-learn)"
    echo "  Install with: pip install torch transformers scikit-learn"
fi
echo ""

# LLM-dependent benchmarks
if [ -n "$BACKEND_ARG" ] || [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo ">>> Benchmark A (sensitivity classification, n=50)"
    $PYTHON run_benchmarks.py --benchmark A --samples 50 $BACKEND_ARG 2>&1 | tail -10
    echo ""

    echo ">>> Benchmark B (decomposition quality)"
    $PYTHON run_benchmarks.py --benchmark B $BACKEND_ARG 2>&1 | tail -8
    echo ""

    echo ">>> Benchmark C v5 (template indistinguishability, n=20)"
    $PYTHON run_benchmarks.py --benchmark C --cover-version v5 $BACKEND_ARG 2>&1 | tail -15
    echo ""

    echo ">>> Benchmark C2 (deployed-pipeline detectability, n=20)"
    $PYTHON run_benchmarks.py --benchmark C2 $BACKEND_ARG 2>&1 | tail -10
    echo ""

    echo ">>> Benchmark D (answer quality — template rewrite only, n=15)"
    $PYTHON run_benchmarks.py --benchmark D --samples 15 $BACKEND_ARG 2>&1 | tail -10
    echo ""

    echo ">>> Benchmark D2 (full pipeline A/B, n=5)"
    $PYTHON run_benchmarks.py --benchmark D2 --samples 5 $BACKEND_ARG 2>&1 | tail -10
    echo ""

    echo ">>> Simulation E (session composition)"
    $PYTHON run_benchmarks.py --benchmark E $BACKEND_ARG 2>&1 | tail -25
    echo ""
else
    echo ">>> Skipping LLM-dependent benchmarks (A, B, C, D, D2, E)"
    echo "    Usage: ./run_all.sh ollama qwen2.5:7b"
    echo "    Or set ANTHROPIC_API_KEY"
    echo ""
fi

echo "============================================"
echo "  All benchmarks complete."
echo "  Results saved to results/"
echo "============================================"
