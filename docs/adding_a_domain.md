# Adding a New Domain to e_AI

## Prerequisites

- Understand the risk you're targeting (paper, incident data, or threat model)
- Know which CROPS property it protects: **C**ensorship resistance, **R**obustness, **O**penness, **P**rivacy, **S**ecurity
- Know which access method it guards: **AI**, **Wallet**, **Application**, **L2**

## Steps

### 1. Create domain directory

```bash
cp -r domains/_template domains/your_domain_name
```

### 2. Edit profile.json

Replace all `CHANGE_ME` fields. Key decisions:

- **Heuristics**: What patterns indicate risk? Each needs detection signals with confidence scores and recommendations with effectiveness estimates.
- **Skills**: What tools can the system invoke? (paymaster, simulator, revoker, etc.)
- **Adversary model**: What can the attacker do? What can't they do?

For v1 profiles (text query analysis): use `core/domain_profile.py` schema.
For v2 profiles (transaction analysis): use `core/tx_profile.py` schema.

### 3. Validate

```bash
# For v2 (transaction analysis) profiles:
python -m meta.tx_validation_engine domains/your_domain/profile.json

# For v1 (text query) profiles:
python -m meta.validation_engine domains/your_domain/profile.json
```

Fix all FAIL checks. MARGINAL is acceptable for draft status.

### 4. Add labeled data (optional but recommended)

Add a JSONL file to `domains/your_domain/data/` with labeled incidents:

```jsonl
{"incident": "User approved unlimited USDC to unverified contract 0x1234", "label": "unlimited_approval"}
{"incident": "Stealth address spent 10 min after deposit", "label": "timing_correlation"}
```

### 5. Write domain-specific analyzer (optional)

If the generic analyzer isn't sufficient, write `domains/your_domain/analyzer.py` with domain-specific checks. Import the profile and implement heuristic checks.

### 6. Add benchmarks

Write benchmark scripts in `domains/your_domain/benchmarks/`. At minimum:
- Synthetic data generation
- Detection rate per heuristic
- False positive rate

### 7. Update README

Fill in the domain README with heuristics table, what needs human effort, and how to improve.

### 8. Auto-generate (alternative to hand-crafting)

If you have a labeled dataset, the meta-framework can generate a draft profile:

```bash
python -m meta.analyzer --dataset your_data.jsonl --domain your_domain_name
python -m meta.refiner --profile domains/your_domain/profile.json
```

The generated profile will need manual review and calibration.
