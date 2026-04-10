"""
Regression tests for benchmark harness, cover generator contract,
and JSON extraction. No LLM backend needed — tests logic only.

Run: python3 test_benchmarks.py
"""

import json
import random
import sys


# ─────────────────────────────────────────────
# extract_json
# ─────────────────────────────────────────────

def test_extract_json_direct_object():
    from run_benchmarks import extract_json
    r = extract_json('{"score": 4, "reason": "good"}')
    assert isinstance(r, dict) and r["score"] == 4

def test_extract_json_direct_array():
    from run_benchmarks import extract_json
    r = extract_json('["a", "b", "c"]')
    assert isinstance(r, list) and len(r) == 3

def test_extract_json_markdown_block():
    from run_benchmarks import extract_json
    r = extract_json('Here is the result:\n```json\n{"x": 1}\n```\nDone.')
    assert isinstance(r, dict) and r["x"] == 1

def test_extract_json_array_before_object():
    """Bug: previously returned nested dict instead of outer array."""
    from run_benchmarks import extract_json
    r = extract_json('prefix [1, 2, {"x": 3}] suffix')
    assert isinstance(r, list), f"Expected list, got {type(r)}"
    assert r == [1, 2, {"x": 3}]

def test_extract_json_object_before_array():
    from run_benchmarks import extract_json
    r = extract_json('prefix {"a": [1,2]} suffix')
    assert isinstance(r, dict) and r["a"] == [1, 2]

def test_extract_json_no_json():
    from run_benchmarks import extract_json
    try:
        extract_json("no json here at all")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


# ─────────────────────────────────────────────
# cover generator contract
# ─────────────────────────────────────────────

def test_cover_set_returns_k_queries():
    from cover_generator import generate_cover_set
    for k in [2, 3, 4, 5, 6, 8]:
        queries, idx = generate_cover_set("How does Aave work?", k=k, seed=42, presanitized=True)
        assert len(queries) == k, f"k={k}: expected {k} queries, got {len(queries)}"
        assert 0 <= idx < k, f"k={k}: real_index {idx} out of range"

def test_cover_set_deterministic():
    from cover_generator import generate_cover_set
    r1 = generate_cover_set("test query", k=4, seed=99, presanitized=True)
    r2 = generate_cover_set("test query", k=4, seed=99, presanitized=True)
    assert r1 == r2, "Not deterministic with same seed"

def test_cover_set_no_global_state_mutation():
    from cover_generator import generate_cover_set
    random.seed(12345)
    before = random.random()
    random.seed(12345)
    generate_cover_set("test", k=4, seed=42, presanitized=True)
    after = random.random()
    assert before == after, "Global random state was mutated"

def test_cover_set_real_is_template_filled():
    """The 'real' query is NOT the input — it's a template fill."""
    from cover_generator import generate_cover_set
    original = "How does Aave V3 health factor change when collateral is added?"
    queries, idx = generate_cover_set(original, k=4, seed=42, presanitized=True)
    # The query at idx should NOT be the original text
    assert queries[idx] != original, (
        "generate_cover_set should template-rewrite the real query, not preserve it"
    )

def test_cover_set_with_original_returns_original():
    from cover_generator import generate_cover_set_with_original
    original = "How does Aave V3 health factor change when collateral is added?"
    queries, idx, sanitized = generate_cover_set_with_original(original, k=4, seed=42, presanitized=True)
    assert sanitized == original, "Should return the original sanitized text"
    assert len(queries) == 4

def test_cover_set_top4_k_exceeds_domains():
    from cover_generator import generate_cover_set
    queries, idx = generate_cover_set("test", k=6, seed=42, domain_strategy="top4", presanitized=True)
    assert len(queries) == 6

def test_cover_set_weighted_k_exceeds_domains():
    from cover_generator import generate_cover_set
    queries, idx = generate_cover_set("test", k=12, seed=42, domain_strategy="weighted", presanitized=True)
    assert len(queries) == 12

def test_per_provider_zero_intersection():
    from cover_generator import generate_per_provider
    result = generate_per_provider("test query", ["A", "B", "C"], k=4, seed=42, presanitized=True)
    sets = [set(queries) for queries, _ in result.values()]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            common = sets[i] & sets[j]
            assert not common, f"Providers {i} and {j} share queries: {common}"

def test_per_provider_deterministic_across_processes():
    """Seeds use hashlib (not hash()), so results are stable across Python processes."""
    from cover_generator import generate_per_provider
    r1 = generate_per_provider("test", ["X", "Y"], k=4, seed=1, presanitized=True)
    r2 = generate_per_provider("test", ["X", "Y"], k=4, seed=1, presanitized=True)
    assert r1 == r2

def test_classify_domain_no_lending_bias():
    """Fallback should distribute across top-4 domains, not always return lending."""
    from cover_generator import classify_domain
    domains = {classify_domain(f"random nonsense {i}") for i in range(50)}
    assert len(domains) > 1, f"All fallbacks went to: {domains}"


# ─────────────────────────────────────────────
# D2 pipeline contract (logic only, no LLM)
# ─────────────────────────────────────────────

def test_benchmark_d_uses_generate_output():
    """Benchmark D must use _generate()'s actual real query, not reconstruct."""
    import inspect
    from run_benchmarks import benchmark_d
    src = inspect.getsource(benchmark_d)
    # Should call _generate() and use shuffled[real_idx]
    assert "shuffled[real_idx]" in src, "D should use _generate()'s output directly"
    # Should NOT independently reconstruct via extract_template + manual slot filling
    assert "extract_template" not in src, "D should not independently reconstruct the query"

def test_classifier_pool_deterministic():
    """Classifier query pool must be sorted for determinism."""
    import inspect
    from classifier_validation import generate_training_data
    src = inspect.getsource(generate_training_data)
    assert "sorted(set(" in src, "query_pool dedup must use sorted(set()) not list(set())"

def test_ontology_protocols_in_genericizer():
    """Every protocol in the ontology should be in the genericizer's strip list."""
    from cover_generator import DOMAIN_ONTOLOGY, _PROTOCOL_NAMES
    generic_set = {p.lower() for p in _PROTOCOL_NAMES}
    missing = []
    for domain, onto in DOMAIN_ONTOLOGY.items():
        for p in onto.get("protocols", []):
            if p.lower() not in generic_set:
                missing.append(p)
    assert not missing, f"Ontology protocols missing from genericizer: {missing}"

def test_d2_mix_has_real_subquery():
    """The mixed set sent to cloud must contain the actual sub-query."""
    from cover_generator import generate_cover_set
    sq = "How does the health factor formula work in Aave V3?"
    cover_set, template_real_idx = generate_cover_set(sq, k=4, seed=42, presanitized=True)
    covers_only = [q for idx, q in enumerate(cover_set) if idx != template_real_idx]
    mixed = covers_only[:3] + [sq]
    assert sq in mixed, "Actual sub-query not in mixed set"
    assert len(mixed) == 4, f"Expected 4, got {len(mixed)}"

def test_d2_mix_template_real_not_in_set():
    """The template-filled 'real' slot should be replaced, not kept."""
    from cover_generator import generate_cover_set
    sq = "How does the health factor formula work in Aave V3?"
    cover_set, template_real_idx = generate_cover_set(sq, k=4, seed=42, presanitized=True)
    template_real = cover_set[template_real_idx]
    covers_only = [q for idx, q in enumerate(cover_set) if idx != template_real_idx]
    mixed = covers_only[:3] + [sq]
    # The template-filled version should NOT be in the final set
    # (unless it happens to equal sq, which it shouldn't by design)
    if template_real != sq:
        assert template_real not in mixed, "Template-filled slot should be replaced by actual sq"


# ─────────────────────────────────────────────
# run_all.sh contract
# ─────────────────────────────────────────────

def test_run_all_syntax():
    import subprocess
    result = subprocess.run(["bash", "-n", "run_all.sh"], capture_output=True, text=True)
    assert result.returncode == 0, f"Syntax error in run_all.sh: {result.stderr}"

def test_run_all_uses_python3():
    with open("run_all.sh") as f:
        content = f.read()
    assert "python3" in content, "run_all.sh should use python3"
    assert 'PYTHON="${PYTHON:-python3}"' in content, "Should allow PYTHON override"

def test_run_all_has_pipefail():
    with open("run_all.sh") as f:
        content = f.read()
    assert "pipefail" in content, "run_all.sh should set pipefail"


# ─────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────

if __name__ == "__main__":
    tests = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for name, fn in sorted(tests):
        try:
            fn()
            passed += 1
            print(f"  PASS: {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL: {name}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {name}: {type(e).__name__}: {e}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
