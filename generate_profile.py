#!/usr/bin/env python3
"""
Generate a domain profile from a dataset.

This is the main CLI for the meta-framework. Given a JSONL dataset of domain
queries, it uses a local LLM to analyze the dataset, generate protection tools
(sanitizer patterns, domain ontology, cover templates), validate them against
formal properties, and output a domain profile.

Usage:
  python generate_profile.py \
    --dataset data/benchmark_dataset.jsonl \
    --domain defi \
    --backend ollama --model qwen2.5:32b \
    --output domains/defi/generated_profile.json

  python generate_profile.py \
    --dataset data/medical_queries.jsonl \
    --domain medical \
    --backend ollama \
    --output domains/medical/profile.json

  python generate_profile.py \
    --validate-only domains/defi/profile.json \
    --dataset data/benchmark_dataset.jsonl
"""

import argparse
import json
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))


def main():
    parser = argparse.ArgumentParser(
        description="Generate or validate a domain profile for privacy protection.",
    )
    parser.add_argument(
        "--dataset", required=True,
        help="Path to JSONL dataset (required). Each line: {text, label, ...}",
    )
    parser.add_argument(
        "--domain", default="unknown",
        help="Domain name (e.g., 'defi', 'medical', 'legal')",
    )
    parser.add_argument(
        "--backend", default="ollama",
        help="LLM backend: 'ollama' (local, recommended) or 'anthropic'",
    )
    parser.add_argument(
        "--model", default=None,
        help="LLM model name (default: backend-specific)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output path for profile.json (default: domains/<domain>/profile.json)",
    )
    parser.add_argument(
        "--validate-only", default=None, metavar="PROFILE",
        help="Skip generation, just validate an existing profile",
    )
    parser.add_argument(
        "--web-search", action="store_true",
        help="Enable web search to enrich vocabulary and threat model",
    )
    parser.add_argument(
        "--refine", action="store_true", default=True,
        help="Run refinement loop to fix sanitizer false negatives (default: on)",
    )
    parser.add_argument(
        "--no-refine", action="store_true",
        help="Skip refinement loop",
    )
    parser.add_argument(
        "--max-refine-rounds", type=int, default=3,
        help="Maximum refinement iterations (default: 3)",
    )
    parser.add_argument(
        "--skip-validation", action="store_true",
        help="Skip validation after generation",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()
    progress = not args.quiet

    # Validate domain name (prevent path traversal)
    if args.domain and not args.domain.replace("_", "").replace("-", "").isalnum():
        print(f"ERROR: Invalid domain name '{args.domain}'. "
              f"Use only letters, numbers, hyphens, underscores.",
              file=sys.stderr)
        sys.exit(1)

    # --- Validate-only mode ---
    if args.validate_only:
        if not os.path.exists(args.validate_only):
            print(f"ERROR: Profile not found: {args.validate_only}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(args.validate_only) as f:
                json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in {args.validate_only}: {e}", file=sys.stderr)
            sys.exit(1)

        from meta.validation_engine import validate_profile
        print(f"Validating profile: {args.validate_only}")
        report = validate_profile(
            profile_path=args.validate_only,
            dataset_path=args.dataset,
            progress=progress,
        )
        # Write report
        report_path = args.validate_only.replace(".json", "_validation.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nReport written to {report_path}")
        sys.exit(0 if report["overall"] != "FAIL" else 1)

    # --- Full generation pipeline ---

    # Pre-flight: validate input dataset
    from meta.analyzer import load_dataset
    from meta.input_validator import validate_dataset
    preflight_queries = load_dataset(args.dataset)
    input_report = validate_dataset(preflight_queries, progress=progress)

    if input_report["overall"] == "FAIL":
        if progress:
            print(f"\nDataset quality insufficient. Attempting enrichment...")

        # Initialize LLM for enrichment
        from llm_backend import init_backend, is_local
        init_backend(backend=args.backend, model=args.model)

        # Try to enrich the dataset
        from meta.data_enrichment import enrich_dataset
        search_fn = None
        if args.web_search:
            try:
                from meta.web_enrichment import make_ddgs_search
                search_fn = make_ddgs_search(max_results=5)
            except ImportError:
                pass

        preflight_queries, input_report = enrich_dataset(
            queries=preflight_queries,
            domain_name=args.domain,
            search_fn=search_fn,
            progress=progress,
        )

        if input_report["overall"] == "FAIL":
            print(f"\nERROR: Dataset still fails after enrichment: {input_report['reason']}",
                  file=sys.stderr)
            print(f"Provide a better initial dataset (min 20 queries, "
                  f"labeled sensitive + non_sensitive).", file=sys.stderr)
            sys.exit(1)

        # Save enriched dataset for reproducibility
        enriched_path = args.dataset.replace(".jsonl", "_enriched.jsonl")
        with open(enriched_path, "w") as f:
            for q in preflight_queries:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        if progress:
            print(f"Enriched dataset saved to {enriched_path}")

        # LLM already initialized above
        _llm_initialized = True
    else:
        _llm_initialized = False

    # Initialize LLM backend (if not already done during enrichment)
    if not _llm_initialized:
        from llm_backend import init_backend, is_local
        init_backend(backend=args.backend, model=args.model)
    else:
        from llm_backend import is_local

    if not is_local():
        print("WARNING: Using cloud backend for profile generation. "
              "This sends dataset queries to the cloud provider. "
              "Use --backend ollama for privacy-preserving generation.",
              file=sys.stderr)

    # Load feedback from previous runs (if any)
    from meta.feedback import get_prompt_adjustments, save_diagnostics, assess_acceptance
    adjustments = get_prompt_adjustments(args.domain)
    if adjustments and progress:
        print(f"Loaded feedback from previous run: {list(adjustments.keys())}")

    # Use enriched queries if available, otherwise load from disk
    # (preflight_queries may have been enriched by data_enrichment above)
    queries = preflight_queries

    # Phase 1: Analyze dataset (uses in-memory queries, not disk reload)
    from meta.analyzer import analyze_dataset
    profile = analyze_dataset(
        dataset_path=args.dataset,
        domain_name=args.domain,
        progress=progress,
        feedback_adjustments=adjustments if adjustments else None,
        queries_override=queries,  # uses enriched in-memory queries if available
    )

    # Phase 2: Generate patterns (uses same in-memory queries)
    from meta.pattern_generator import generate_all_patterns
    analysis = profile.pop("_analysis", {})
    sensitive_patterns, normalization = generate_all_patterns(
        analysis=analysis,
        queries=queries,
        subdomains=profile["subdomains"],
        progress=progress,
    )
    profile["sensitive_patterns"] = sensitive_patterns
    profile["normalization"] = normalization

    # Add template_slots mapping
    profile["template_slots"] = {
        "MECHANISM": "mechanisms",
        "OPERATION": "operations",
        "OPERATION_A": "operations",
        "OPERATION_B": "operations",
        "TRIGGER": "triggers",
        "METRIC": "metrics",
        "ACTOR": "actors",
        "GENERIC_REF": "generic_refs",
        "RISK_CONCEPT": "risk_concepts",
    }

    # Phase 2b: Web enrichment (optional)
    if args.web_search:
        from meta.web_enrichment import enrich_profile as _enrich, make_ddgs_search
        try:
            search_fn = make_ddgs_search(max_results=5)
            profile = _enrich(profile, search_fn=search_fn, progress=progress)
        except ImportError as e:
            print(f"  [warn] {e}", file=sys.stderr)
            print("  [warn] Skipping web enrichment.", file=sys.stderr)
    else:
        if progress:
            print("\nWeb enrichment skipped (use --web-search to enable)")

    # Phase 2c: Refinement loop
    span_results = analysis.get("span_results")
    if not args.no_refine and span_results:
        from meta.refiner import refine_profile as _refine
        profile, refine_result = _refine(
            profile=profile,
            queries=queries,
            span_results=span_results,
            max_rounds=args.max_refine_rounds,
            progress=progress,
        )
    else:
        refine_result = None
        if progress:
            print("\nRefinement skipped")

    # Phase 2d: Usability refinement
    if not args.no_refine:
        from meta.refiner import refine_usability
        profile, usability_result = refine_usability(
            profile=profile,
            queries=queries,
            max_rounds=2,
            progress=progress,
        )

    # Determine output path
    out_path = args.output
    if out_path is None:
        out_dir = os.path.join(os.path.dirname(__file__), "domains", args.domain)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "profile.json")

    # Write profile
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    print(f"\nProfile written to {out_path}")

    # Phase 3: Validate
    if not args.skip_validation:
        print("\n" + "=" * 60)
        print("VALIDATION")
        print("=" * 60)
        from meta.validation_engine import validate_profile
        report = validate_profile(
            profile=profile,
            queries=queries,
            span_results=span_results,
            progress=progress,
        )

        # Write report
        report_path = out_path.replace(".json", "_validation.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nValidation report written to {report_path}")

        # Update profile validation status
        if report["overall"] == "PASS":
            profile["meta"]["validation_status"] = "validated"
        elif report["overall"] == "MARGINAL":
            profile["meta"]["validation_status"] = "marginal"
        else:
            profile["meta"]["validation_status"] = "draft"

        with open(out_path, "w") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)

        # Save diagnostics for feedback loop
        diag_path = save_diagnostics(args.domain, report)
        if progress:
            print(f"Diagnostics saved to {diag_path}")

        # Acceptance assessment
        acceptance = assess_acceptance(report)
        print(f"\n{'='*60}")
        print(f"ACCEPTANCE: {acceptance['status']}")
        print(f"  {acceptance['reason']}")
        if acceptance["status"] == "REJECTED":
            print(f"  Re-run with a larger model or review failed checks.")
        elif acceptance["status"] == "NEEDS_WORK":
            print(f"  Re-run to use feedback from this run's diagnostics.")
        print(f"{'='*60}")
    else:
        print("Validation skipped (--skip-validation)")

    print("\nDone.")


if __name__ == "__main__":
    main()
