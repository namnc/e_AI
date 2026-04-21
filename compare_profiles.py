#!/usr/bin/env python3
"""Compare a generated profile to the hand-crafted DeFi profile.

Documents what the LLM discovered vs what it missed.

Usage:
  python compare_profiles.py domains/defi/profile.json domains/defi_generated/profile.json
"""

import json
import sys


def load(path):
    with open(path) as f:
        return json.load(f)


def compare_sets(label, hand, gen):
    hand_set = set(x.lower() for x in hand)
    gen_set = set(x.lower() for x in gen)
    overlap = hand_set & gen_set
    only_hand = hand_set - gen_set
    only_gen = gen_set - hand_set
    print(f"\n  {label}:")
    print(f"    Hand-crafted: {len(hand_set)}, Generated: {len(gen_set)}, "
          f"Overlap: {len(overlap)}")
    if only_hand:
        print(f"    Missing from generated ({len(only_hand)}):")
        for x in sorted(only_hand)[:20]:
            print(f"      - {x}")
        if len(only_hand) > 20:
            print(f"      ... and {len(only_hand) - 20} more")
    if only_gen:
        print(f"    New in generated ({len(only_gen)}):")
        for x in sorted(only_gen)[:10]:
            print(f"      + {x}")
        if len(only_gen) > 10:
            print(f"      ... and {len(only_gen) - 10} more")
    return len(overlap), len(only_hand), len(only_gen)


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <hand_crafted.json> <generated.json>")
        sys.exit(1)

    hand = load(sys.argv[1])
    gen = load(sys.argv[2])

    print("=" * 70)
    print("PROFILE COMPARISON: Hand-crafted vs Generated")
    print("=" * 70)

    # 1. Subdomains
    hand_sds = set(hand.get("subdomains", {}).keys())
    gen_sds = set(gen.get("subdomains", {}).keys())
    print(f"\nSubdomains:")
    print(f"  Hand-crafted ({len(hand_sds)}): {sorted(hand_sds)}")
    print(f"  Generated ({len(gen_sds)}): {sorted(gen_sds)}")
    print(f"  Overlap: {sorted(hand_sds & gen_sds)}")

    # 2. Entity names
    hand_ents = hand.get("sensitive_patterns", {}).get("entity_names", [])
    gen_ents = gen.get("sensitive_patterns", {}).get("entity_names", [])
    compare_sets("Entity names (protocols)", hand_ents, gen_ents)

    # 3. Templates
    hand_tmpls = hand.get("templates", [])
    gen_tmpls = gen.get("templates", [])
    print(f"\n  Templates:")
    print(f"    Hand-crafted: {len(hand_tmpls)}")
    print(f"    Generated: {len(gen_tmpls)}")

    # 4. Vocabulary depth per shared subdomain
    print(f"\n  Vocabulary comparison (shared subdomains):")
    shared = hand_sds & gen_sds
    total_overlap = 0
    total_missing = 0
    total_new = 0
    for sd in sorted(shared):
        h = hand["subdomains"][sd]
        g = gen["subdomains"][sd]
        for key in ["protocols", "mechanisms", "operations", "metrics"]:
            o, m, n = compare_sets(f"{sd}.{key}", h.get(key, []), g.get(key, []))
            total_overlap += o
            total_missing += m
            total_new += n

    # 5. Sanitizer patterns
    hand_sp = hand.get("sensitive_patterns", {})
    gen_sp = gen.get("sensitive_patterns", {})
    print(f"\n  Sanitizer patterns:")
    for key in ["amount_patterns_icase", "amount_patterns_csense",
                "address_patterns", "timing_patterns"]:
        h_count = len(hand_sp.get(key, []))
        g_count = len(gen_sp.get(key, []))
        print(f"    {key}: hand={h_count}, gen={g_count}")

    # 6. False positives
    compare_sets("False positive words",
                 hand_sp.get("false_positive_words", []),
                 gen_sp.get("false_positive_words", []))

    # 7. Cross-domain vocabulary check (ignoring subdomain assignment)
    print(f"\n  Cross-domain vocabulary (all subdomains pooled):")
    for key in ["protocols", "mechanisms", "metrics"]:
        hand_all = set()
        gen_all = set()
        for sd in hand.get("subdomains", {}).values():
            hand_all.update(x.lower() for x in sd.get(key, []))
        for sd in gen.get("subdomains", {}).values():
            gen_all.update(x.lower() for x in sd.get(key, []))
        overlap = hand_all & gen_all
        missing = hand_all - gen_all
        recall = len(overlap) / max(len(hand_all), 1)
        print(f"    {key}: hand={len(hand_all)}, gen={len(gen_all)}, "
              f"overlap={len(overlap)}, recall={recall:.0%}")

    # Summary
    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"  Vocabulary overlap (shared subdomains): {total_overlap}")
    print(f"  Missing from generated: {total_missing}")
    print(f"  New in generated: {total_new}")
    recall = total_overlap / max(total_overlap + total_missing, 1)
    print(f"  Recall vs hand-crafted (shared subdomains): {recall:.1%}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
