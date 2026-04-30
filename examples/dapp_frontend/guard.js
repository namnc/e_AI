/**
 * e_AI v2 DApp Frontend Guard
 *
 * JavaScript SDK for DApp frontends. Intercepts contract interactions
 * before they reach the wallet.
 *
 * For Application access method: governance proposals, cross-protocol
 * interactions, DApp-level risk analysis.
 *
 * Usage (in a DApp):
 *   <script src="eai-guard.js"></script>
 *   <script>
 *     const guard = new EAIGuard({ profiles: ['governance_proposal', 'cross_protocol_risk'] });
 *
 *     // Before submitting governance vote
 *     const result = await guard.checkGovernanceProposal(proposalId, governorAddress);
 *     if (result.action === 'block') {
 *       showWarning(result.alerts);
 *       return;
 *     }
 *   </script>
 */

class EAIFrontendGuard {
  constructor(config = {}) {
    this.profiles = config.profiles || {};
    this.onAlert = config.onAlert || ((alerts, action) => {
      console.log(`[e_AI] ${action}:`, alerts);
    });
  }

  /**
   * Check a governance proposal before voting/executing
   */
  async checkGovernanceProposal(calldata, governorAddress) {
    const alerts = [];

    // H1: Treasury drain — large ETH/token transfer
    if (calldata.includes('transfer') || calldata.includes('a9059cbb')) {
      alerts.push({
        profile: 'governance_proposal',
        heuristic: 'H1',
        severity: 'critical',
        confidence: 0.85,
        signal: 'Proposal includes token transfer — verify treasury impact',
        recommendation: 'Check the transfer amount against total treasury balance',
      });
    }

    // H3: Proxy upgrade
    if (calldata.includes('3659cfe6') || calldata.includes('upgradeTo')) {
      alerts.push({
        profile: 'governance_proposal',
        heuristic: 'H3',
        severity: 'critical',
        confidence: 0.9,
        signal: 'Proposal upgrades a proxy contract — new implementation may be malicious',
        recommendation: 'Verify the new implementation contract is verified and audited',
      });
    }

    // H4: Timelock bypass
    if (calldata.includes('setDelay') || calldata.includes('updateDelay')) {
      alerts.push({
        profile: 'governance_proposal',
        heuristic: 'H4',
        severity: 'critical',
        confidence: 0.8,
        signal: 'Proposal modifies timelock delay — may remove safety window',
        recommendation: 'Check new delay value. Reducing below 24h removes meaningful governance protection.',
      });
    }

    const action = alerts.some(a => a.severity === 'critical') ? 'block' : alerts.length > 0 ? 'warn' : 'pass';
    await this.onAlert(alerts, action);
    return { action, alerts };
  }

  /**
   * Check cross-protocol risk before a DeFi interaction
   */
  async checkCrossProtocolRisk(userPositions) {
    const alerts = [];

    // H3: Concentrated exposure
    if (userPositions && userPositions.length > 0) {
      const total = userPositions.reduce((sum, p) => sum + (p.valueUsd || 0), 0);
      for (const pos of userPositions) {
        const pct = (pos.valueUsd || 0) / total;
        if (pct > 0.5) {
          alerts.push({
            profile: 'cross_protocol_risk',
            heuristic: 'H3',
            severity: 'high',
            confidence: 0.8,
            signal: `${(pct * 100).toFixed(0)}% of portfolio in ${pos.protocol} — concentration risk`,
            recommendation: 'Diversify across protocols to reduce single-protocol failure impact',
          });
        }
      }
    }

    const action = alerts.some(a => a.severity === 'critical') ? 'block' : alerts.length > 0 ? 'warn' : 'pass';
    await this.onAlert(alerts, action);
    return { action, alerts };
  }

  /**
   * Check L2 bridge interaction
   */
  async checkBridgeTransaction(fromChain, toChain, amount, tokenAddress) {
    const alerts = [];

    // H1: Same address on both chains
    alerts.push({
      profile: 'l2_bridge_linkage',
      heuristic: 'H1',
      severity: 'high',
      confidence: 0.9,
      signal: `Bridging from ${fromChain} to ${toChain} using same address — identities linked across chains`,
      recommendation: 'Use a different address on the destination chain',
    });

    // H5: NFT/unique token bridge
    if (tokenAddress && tokenAddress !== '0x0000000000000000000000000000000000000000') {
      alerts.push({
        profile: 'l2_bridge_linkage',
        heuristic: 'H5',
        severity: 'critical',
        confidence: 0.95,
        signal: 'Bridging a specific token — creates deterministic link between chains',
        recommendation: 'Consider selling on source chain and re-buying on destination instead of bridging',
      });
    }

    const action = alerts.some(a => a.severity === 'critical') ? 'block' : alerts.length > 0 ? 'warn' : 'pass';
    await this.onAlert(alerts, action);
    return { action, alerts };
  }
}

// --- Demo ---

async function demo() {
  console.log('='.repeat(60));
  console.log('e_AI v2 DApp Frontend Guard Demo');
  console.log('='.repeat(60));

  const guard = new EAIFrontendGuard({
    onAlert: (alerts, action) => {
      console.log(`\n  [Guard] ${action.toUpperCase()}: ${alerts.length} alert(s)`);
      for (const a of alerts) {
        console.log(`    [${a.profile}/${a.heuristic}] ${a.severity}: ${a.signal}`);
        console.log(`    → ${a.recommendation}`);
      }
    },
  });

  // Scenario 1: Governance proposal with proxy upgrade
  console.log('\n--- Scenario 1: Governance proposal with proxy upgrade ---');
  await guard.checkGovernanceProposal('0x3659cfe6...upgradeTo(0xnewImpl)', '0xgovernor');

  // Scenario 2: Portfolio concentration
  console.log('\n--- Scenario 2: Check portfolio concentration ---');
  await guard.checkCrossProtocolRisk([
    { protocol: 'Aave', valueUsd: 50000 },
    { protocol: 'Uniswap', valueUsd: 5000 },
    { protocol: 'Compound', valueUsd: 3000 },
  ]);

  // Scenario 3: Bridge with same address
  console.log('\n--- Scenario 3: Bridge ETH to Arbitrum ---');
  await guard.checkBridgeTransaction('ethereum', 'arbitrum', 10.0, '0x0000000000000000000000000000000000000000');

  console.log('\n' + '='.repeat(60));
}

// Run
demo().catch(console.error);
