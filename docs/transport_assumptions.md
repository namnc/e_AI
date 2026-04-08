# Transport Assumptions: Achieving Per-Query-Set Unlinkability

The cover query mechanism (Tier 1) requires that each set of k queries is **unlinkable** to any other set from the same user. If an adversary can correlate sets across rounds, session composition attacks become viable (Section 6.7). This appendix describes concrete steps to achieve unlinkability.

## Requirement

For each query set {q_1, ..., q_k}, the k queries must:
1. Arrive at the cloud provider from **different source IPs** (no shared exit node)
2. Arrive at **different times** (no timing correlation within a set)
3. Not share **session tokens, API keys, or cookies** (no identity linkage)
4. Not be linkable to the user's **subsequent on-chain transaction** (no timing correlation between query and action)

## Concrete Implementation: Tor Circuit Pool

```python
# Pseudocode for a Tor circuit pool manager
class TorCircuitPool:
    def __init__(self, pool_size=20, tor_control_port=9051):
        """Pre-generate a pool of independent Tor circuits."""
        self.circuits = []
        for _ in range(pool_size):
            circuit = tor_controller.create_circuit()
            self.circuits.append(circuit)
    
    def get_k_circuits(self, k=4):
        """Return k circuits with different exit nodes."""
        selected = []
        used_exits = set()
        for circuit in self.circuits:
            exit_node = circuit.exit_fingerprint
            if exit_node not in used_exits:
                selected.append(circuit)
                used_exits.add(exit_node)
            if len(selected) == k:
                break
        # Rotate used circuits out of the pool
        for c in selected:
            self.circuits.remove(c)
            self.circuits.append(tor_controller.create_circuit())
        return selected

    def send_query_set(self, queries, circuits):
        """Send each query over a different circuit with random delay."""
        import random, time
        for query, circuit in zip(queries, circuits):
            delay = random.uniform(0.5, 5.0)  # 0.5-5s random delay
            time.sleep(delay)
            circuit.send(query)
```

### Key properties:
- **Different exit nodes**: Each query in a set exits Tor from a different node, so the cloud sees k different source IPs.
- **Pre-generated circuits**: Circuits are created ahead of time, avoiding the latency spike of on-demand circuit creation (~2-5s per circuit).
- **Random inter-query delay**: Prevents timing correlation between queries in a set.
- **Circuit rotation**: Used circuits are replaced, preventing reuse across sets.

## Alternative: Mixnet Overlay (Nym)

For stronger guarantees than Tor (which is vulnerable to traffic analysis by a global passive adversary), use a mixnet like [Nym](https://nymtech.net/):

- **Poisson mixing**: Each mix node holds messages for a random duration drawn from an exponential distribution, breaking timing correlation even for a global adversary.
- **Cover traffic**: The mixnet generates dummy traffic at constant rate, so query volume is indistinguishable from background noise.
- **Sphinx packet format**: Each query is wrapped in layers of encryption, preventing any single mix node from learning both sender and recipient.

Nym is operational today and has a Rust SDK. Integration adds ~1-3s latency per query but provides stronger unlinkability than Tor.

## Preventing Query-to-Transaction Timing Correlation

Even with per-set unlinkability, an adversary observing both the cloud API and the Ethereum mempool can correlate: "a query about Aave health factors arrived at 2:14pm, and an Aave collateral-add transaction appeared at 2:17pm."

Mitigations:
1. **Random delay injection**: Wait a random 0-30 minutes between receiving the cloud response and executing any on-chain action. (Already described in Section 2.4.)
2. **Batched execution**: Accumulate intended transactions and submit them at fixed intervals (e.g., every hour on the hour), regardless of when the query was made.
3. **Decoy transactions**: Occasionally submit innocuous transactions (e.g., zero-value transfers, token approvals) that are not related to any query, so the adversary cannot distinguish query-triggered transactions from background activity.

## Practical Assessment

| Transport Method | Unlinkability Strength | Latency Overhead | Deployment Complexity |
|---|---|---|---|
| No transport (direct HTTPS) | None | 0 | None |
| Single Tor circuit (all k queries) | Weak (same exit node) | ~2-3s | Low |
| **Tor circuit pool (k independent)** | **Strong** | **~3-8s** | **Medium** |
| Nym mixnet | Very strong | ~5-15s | Medium-high |
| Tor + random delay + batching | Strong (with timing protection) | ~30-60s (delay) | Medium |

**Recommendation**: Tor circuit pool is the practical sweet spot — strong unlinkability with manageable latency. Nym is preferable for high-value positions where the adversary may be a global passive observer. Random delay injection should always be used regardless of transport choice.
