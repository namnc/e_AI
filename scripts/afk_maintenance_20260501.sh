#!/usr/bin/env bash
# AFK maintenance pass 2026-05-01 (e_AI v2)
# Subset of CLAUDE.md AFK step 5 — safe automatable items only.
# Writes progress to AI_PS/inbox/maintenance_report.md (appended).

set +e  # don't abort on failure; log and continue
REPORT="/Users/nn/Documents/Claude/AI_PS/inbox/maintenance_report.md"
REPO="$HOME/Documents/Claude/Eth_AI/e_AI"
PY=python3
cd "$REPO" || exit 1

log() {
  echo "$@" | tee -a "$REPORT"
}

log ""
log "## Tier 1 — e_AI v2 maintenance pass (RETRY w/ python3)"
log ""
log "Started: $(date -Iseconds)"
log "Branch: $(git branch --show-current)"
log "Working dir: $REPO"
log ""

# (b) Run all domain profile tests
log "### (b) Domain profile tests"
log '```'
PASS=0; FAIL=0
for d in domains/*/test_profile.py; do
  domain=$(basename "$(dirname "$d")")
  [[ "$domain" == "_template" || "$domain" == "_feedback" ]] && continue
  result=$($PY "$d" 2>&1 | tail -3)
  if echo "$result" | grep -qE "(OK|passed|0 failed)"; then
    PASS=$((PASS+1))
    echo "  PASS  $domain" | tee -a "$REPORT"
  else
    FAIL=$((FAIL+1))
    echo "  FAIL  $domain  -- $(echo "$result" | tr '\n' ' ' | head -c 200)" | tee -a "$REPORT"
  fi
done
log "Total: $((PASS+FAIL))  Pass: $PASS  Fail: $FAIL"
log '```'
log ""

# (c) Re-validate all profiles
log "### (c) Profile validation engine"
log '```'
VPASS=0; VFAIL=0
for p in domains/*/profile.json; do
  domain=$(basename "$(dirname "$p")")
  [[ "$domain" == "_template" || "$domain" == "_feedback" ]] && continue
  result=$($PY -m meta.tx_validation_engine "$p" 2>&1 | tail -3)
  if echo "$result" | grep -qE "(Overall: PASS|11/11|VALID|all checks)"; then
    VPASS=$((VPASS+1))
    echo "  VALID  $domain" | tee -a "$REPORT"
  else
    VFAIL=$((VFAIL+1))
    echo "  ISSUE  $domain  -- $(echo "$result" | tr '\n' ' ' | head -c 200)" | tee -a "$REPORT"
  fi
done
log "Total: $((VPASS+VFAIL))  Valid: $VPASS  Issues: $VFAIL"
log '```'
log ""

# (k) Duplicate heuristics across domains
log "### (k) Duplicate heuristics check"
log '```'
if [[ -f scripts/check_duplicate_heuristics.py ]]; then
  $PY scripts/check_duplicate_heuristics.py 2>&1 | tail -30 | tee -a "$REPORT"
else
  log "scripts/check_duplicate_heuristics.py not present — skipped"
fi
log '```'
log ""

# (l) Cross-domain density matrix
log "### (l) Cross-domain density matrix"
log '```'
if [[ -f scripts/cross_domain_density.py ]]; then
  $PY scripts/cross_domain_density.py 2>&1 | tail -30 | tee -a "$REPORT"
else
  log "scripts/cross_domain_density.py not present — skipped"
fi
log '```'
log ""

# Cross-domain benchmark
log "### Cross-domain benchmark"
log '```'
if [[ -f scripts/cross_domain_benchmark.py ]]; then
  $PY scripts/cross_domain_benchmark.py 2>&1 | tail -40 | tee -a "$REPORT"
else
  log "scripts/cross_domain_benchmark.py not present — skipped"
fi
log '```'
log ""

# (u) Confidence calibration sanity check (flag all-same-value profiles)
log "### (u) Confidence calibration sanity"
log '```'
FLAGGED=0
for p in domains/*/profile.json; do
  domain=$(basename "$(dirname "$p")")
  [[ "$domain" == "_template" || "$domain" == "_feedback" ]] && continue
  vals=$($PY -c "
import json
try:
    d = json.load(open('$p'))
    confs = []
    for h in d.get('heuristics', []) if isinstance(d.get('heuristics'), list) else []:
        if isinstance(h, dict) and 'confidence' in h:
            confs.append(h['confidence'])
    print(','.join(str(c) for c in confs))
except Exception as e:
    print('ERR: ' + str(e))
" 2>/dev/null)
  if [[ -n "$vals" && "$vals" != ERR* ]]; then
    uniq_vals=$(echo "$vals" | tr ',' '\n' | sort -u | wc -l | tr -d ' ')
    if [[ "$uniq_vals" -le 1 && -n "$vals" ]]; then
      echo "  FLAG (all-same): $domain confs=[$vals]" | tee -a "$REPORT"
      FLAGGED=$((FLAGGED+1))
    fi
  fi
done
log "Flagged domains: $FLAGGED"
log '```'
log ""

# (d) Generate missing 7b LLM variants — for domains lacking profile_generated.json
log "### (d) Generate missing 7b LLM variants"
log '```'
GENNED=0; SKIPPED=0; ERRORED=0
for d in domains/*/; do
  domain=$(basename "$d")
  [[ "$domain" == "_template" || "$domain" == "_feedback" ]] && continue
  if [[ -f "$d/profile.json" && ! -f "$d/profile_generated.json" ]]; then
    echo "  GEN  $domain ..." | tee -a "$REPORT"
    out=$($PY -m meta.bootstrap_domain "$d" 2>&1 | tail -3)
    if echo "$out" | grep -qiE "(error|fail|traceback)"; then
      ERRORED=$((ERRORED+1))
      echo "    ERR -- $(echo "$out" | tr '\n' ' ' | head -c 200)" | tee -a "$REPORT"
    else
      GENNED=$((GENNED+1))
      echo "    OK -- $(echo "$out" | tr '\n' ' ' | head -c 200)" | tee -a "$REPORT"
    fi
  else
    SKIPPED=$((SKIPPED+1))
  fi
done
log "Generated: $GENNED  Errored: $ERRORED  Skipped (already have): $SKIPPED"
log '```'
log ""

log "Finished: $(date -Iseconds)"
log "---"
