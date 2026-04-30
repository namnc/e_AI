# e_AI v2 Integration Examples

## Kohaku Wallet SDK (`kohaku_integration/`)

Middleware that wraps any Kohaku plugin with pre-submission risk analysis.

```bash
cd examples/kohaku_integration
npm install
npx tsx demo.ts
```

Intercepts `prepareShield`, `prepareUnshield`, `prepareTransfer` calls. Runs all loaded profiles against the transaction. Blocks on critical risk, warns on medium/high.

## Python: Single Transaction Check

```python
import sys, json
sys.path.insert(0, "/path/to/e_AI")

from domains.stealth_address_ops.analyzer import (
    SteathTx, analyze_transaction, load_profile, format_result
)

profile = load_profile("domains/stealth_address_ops/profile.json")

tx = SteathTx(
    deposit_address="0xaaaa",
    withdrawal_address="0xbbbb",
    stealth_address="0xcccc",
    amount_eth=3.847,
    deposit_timestamp=1700000000,
    spend_timestamp=1700000000 + 600,
    gas_price_gwei=45.0,
    gas_funding_source="0xaaaa",
    address_cluster={"0xaaaa"},
)

result = analyze_transaction(tx, profile)
print(format_result(result))
```

## Python: Full Pipeline (Analyzer + Cover + LLM)

```python
from domains.stealth_address_ops.compiler import compile_analysis
from domains.stealth_address_ops.cover_generator import PoolState
from core.llm_analyzer import LLMAnalyzer

# Load LLM
llm = LLMAnalyzer(profile, backend="ollama", model="qwen2.5:7b")
llm.connect()

# Build pool state (from RPC or cached data)
pool = PoolState(deposits=[
    {"amount_eth": 1.0, "timestamp": now - 3600, "gas_price_gwei": 30},
    {"amount_eth": 5.0, "timestamp": now - 7200, "gas_price_gwei": 28},
    # ...
])

# Full analysis
result = compile_analysis(tx, profile, pool, llm)
print(result.summary)
```

## Python: Multi-Profile Check

```python
import json
from pathlib import Path

# Load all profiles
profiles = {}
for domain_dir in Path("domains").iterdir():
    profile_path = domain_dir / "profile.json"
    if profile_path.exists() and domain_dir.name != "_template":
        with open(profile_path) as f:
            profiles[domain_dir.name] = json.load(f)

# Check a transaction against all relevant profiles
# (real implementation would dispatch based on transaction type)
for name, profile in profiles.items():
    print(f"--- {name} ---")
    # Profile-specific analysis here
```

## Python: Bootstrap a New Domain

```python
# Create a new domain from scratch
python -m meta.bootstrap_domain domains/my_new_domain

# Or just data + tests (no LLM):
python -m meta.bootstrap_domain domains/my_new_domain --skip-llm

# With a specific model:
python -m meta.bootstrap_domain domains/my_new_domain --model qwen2.5:14b
```

## TypeScript: Standalone (No Kohaku)

```typescript
import { analyzeTransaction, loadProfile } from './analyzer.js';
import type { StealthTx } from './types.js';

const profile = loadProfile('domains/stealth_address_ops/profile.json');

const tx: StealthTx = {
    depositAddress: '0xaaaa',
    withdrawalAddress: '0xbbbb',
    stealthAddress: '0xcccc',
    amountEth: 3.847,
    depositTimestamp: Date.now() / 1000 - 600,
    spendTimestamp: Date.now() / 1000,
    gasPriceGwei: 45,
    gasFundingSource: '0xaaaa',
    isSelfSend: false,
    addressCluster: new Set(['0xaaaa']),
};

const result = analyzeTransaction(tx, profile);
// result.overallRisk: 'critical' | 'high' | 'medium' | 'low'
// result.alerts: RiskAlert[]
```

## Browser Extension (Concept)

```javascript
// Content script intercepts wallet signing requests
window.addEventListener('message', (event) => {
    if (event.data.type === 'WALLET_SIGN_REQUEST') {
        // Load offchain_signature profile
        // Decode EIP-712 typed data
        // Check against heuristics
        // Show warning overlay if risky
    }
});
```
