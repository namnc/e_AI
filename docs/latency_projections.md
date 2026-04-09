# Latency Projections for Local LLM Inference

## Measured Baseline (M1 Pro, 16GB, Qwen 2.5 7B Q4_K_M)

| Stage | Latency | Tokens |
|---|---|---|
| Regex sanitization (with normalization) | 0.2 ms | Unicode normalization + regex passes |
| Cover generation (k=4) | 0.2 ms | — |
| Local decomposition | 23 s | ~200 tok out @ 8.7 tok/s |
| Cloud API (Haiku, parallel) | 2 s | ~200 tok out |
| Local synthesis | 19 s | ~300 tok out @ 15.8 tok/s |
| **Total (cloud API)** | **~44 s** | |

## Projections by Hardware

Inference speed for quantized models scales with memory bandwidth and compute cores. Approximate generation speeds for Q4_K_M quantization:

| Hardware | 7B tok/s | 14B tok/s | 32B tok/s | Unified Memory |
|---|---|---|---|---|
| M1 Pro (measured) | 8-16 | ~5-10 | ~3-5 | 16 GB |
| M2 Pro | 15-25 | ~8-15 | ~5-8 | 16-32 GB |
| M3 Pro | 20-30 | ~12-20 | ~7-12 | 18-36 GB |
| M4 Pro | 25-40 | ~15-25 | ~10-18 | 24-48 GB |
| M4 Max | 50-80 | ~30-50 | ~15-30 | 36-128 GB |

### Projected Pipeline Latency (14B model, cloud API for knowledge queries)

| Hardware | Decompose (~200 tok) | Cloud (parallel) | Synthesize (~300 tok) | **Total** |
|---|---|---|---|---|
| M1 Pro | ~30 s | 2 s | ~40 s | **~72 s** |
| M4 Pro (14B) | ~10 s | 2 s | ~15 s | **~27 s** |
| M4 Max (14B) | ~5 s | 2 s | ~8 s | **~15 s** |
| M4 Max (32B) | ~12 s | 2 s | ~18 s | **~32 s** |

### Projected Pipeline Latency (7B model with regex pre-filter, cloud API)

Using a faster 7B model for decomposition (accepts 30% param leakage risk, mitigated by regex pre-filter):

| Hardware | Decompose | Cloud | Synthesize | **Total** |
|---|---|---|---|---|
| M4 Pro (7B) | ~6 s | 2 s | ~9 s | **~17 s** |
| M4 Max (7B) | ~3 s | 2 s | ~5 s | **~10 s** |

## Interactive Threshold

For advisory queries (not time-critical), **<30 s is acceptable** — comparable to a web search + reading time. For real-time DeFi decisions (liquidation avoidance), **<10 s is needed**.

| Target | Hardware Required | Model | Achievable Today? |
|---|---|---|---|
| <60 s | M1 Pro | 7B | Yes (measured: 44s) |
| <30 s | M4 Pro | 14B | Yes (projected: 27s) |
| <15 s | M4 Max | 14B | Yes (projected: 15s) |
| <10 s | M4 Max | 7B + regex pre-filter | Yes (projected: 10s) |

## Trend

Apple Silicon inference speed has roughly doubled each generation (M1→M2→M3→M4). If this continues, an M5 Pro (expected ~2027) would run a 14B model at ~30-50 tok/s, bringing the full pipeline under 15s on mid-tier hardware. The latency constraint is a temporary engineering limitation, not a fundamental one.
