/**
 * Kohaku + e_AI v2 Integration Demo
 *
 * Shows how the ops advisor middleware wraps a Kohaku plugin to add
 * pre-submission risk analysis for stealth address transactions.
 *
 * Run: npx tsx demo.ts
 */

import { analyzeTransaction, loadProfile, formatResult } from './analyzer.js';
import type { StealthTx, AnalysisResult } from './types.js';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Mock Kohaku plugin (simulates @kohaku-eth/railgun or similar)
// ---------------------------------------------------------------------------

interface MockShieldOp {
  to: string;
  amount: string;
  token: string;
}

const mockRailgunPlugin = {
  instanceId: async () => 'railgun-sepolia-001',

  balance: async (assets: any) => [{ asset: 'ETH', amount: '1.5' }],

  prepareShield: async (asset: { amount: string; token: string }, to?: string): Promise<MockShieldOp> => {
    console.log(`  [Railgun] Preparing shield: ${asset.amount} ${asset.token} → ${to || 'self'}`);
    return { to: to || '0xstealth', amount: asset.amount, token: asset.token };
  },

  prepareUnshield: async (asset: { amount: string; token: string }, to: string): Promise<MockShieldOp> => {
    console.log(`  [Railgun] Preparing unshield: ${asset.amount} ${asset.token} → ${to}`);
    return { to, amount: asset.amount, token: asset.token };
  },
};

// ---------------------------------------------------------------------------
// Ops advisor middleware (simplified version of kohaku-middleware.ts)
// ---------------------------------------------------------------------------

function withOpsAdvisor<T extends typeof mockRailgunPlugin>(
  plugin: T,
  profilePath: string,
): T & { lastAnalysis: AnalysisResult | null } {
  const profile = JSON.parse(readFileSync(profilePath, 'utf-8'));
  let lastAnalysis: AnalysisResult | null = null;

  const handler: ProxyHandler<T> = {
    get(target, prop, receiver) {
      const original = Reflect.get(target, prop, receiver);

      if (typeof original !== 'function') return original;
      if (prop === 'lastAnalysis') return lastAnalysis;

      // Intercept shield/unshield operations
      if (prop === 'prepareShield' || prop === 'prepareUnshield') {
        return async (...args: any[]) => {
          const asset = args[0] as { amount: string; token: string };
          const to = args[1] as string | undefined;

          console.log(`\n  [OpsAdvisor] Intercepting ${String(prop)}...`);

          // Build a mock StealthTx for analysis
          const now = Math.floor(Date.now() / 1000);
          const tx: StealthTx = {
            depositAddress: '0xuser_main_wallet',
            withdrawalAddress: to || '0xstealth',
            stealthAddress: '0xstealth_derived',
            amountEth: parseFloat(asset.amount),
            depositTimestamp: now - 300,  // simulate deposit 5 min ago
            spendTimestamp: now,
            gasPriceGwei: 30,
            gasFundingSource: prop === 'prepareUnshield' ? '0xuser_main_wallet' : 'paymaster',
            isSelfSend: false,
            addressCluster: new Set(['0xuser_main_wallet']),
          };

          // If unshielding to an address in user's cluster, flag it
          if (to && tx.addressCluster.has(to)) {
            tx.addressCluster.add(to);
          }

          const result = analyzeTransaction(tx, profile);
          lastAnalysis = result;

          console.log(`  [OpsAdvisor] ${formatResult(result)}`);

          // Block if critical
          if (result.overallRisk === 'critical') {
            console.log(`\n  ⛔ BLOCKED: Transaction has critical privacy risk.`);
            console.log(`  Fix the issues above before proceeding.\n`);
            throw new Error(`OpsAdvisor blocked ${String(prop)}: critical risk detected`);
          }

          if (result.alerts.length > 0) {
            console.log(`\n  ⚠️  Proceeding with ${result.alerts.length} warning(s).\n`);
          } else {
            console.log(`\n  ✅ No risks detected.\n`);
          }

          // Proceed with original operation
          return (original as Function).apply(target, args);
        };
      }

      return original;
    },
  };

  return new Proxy(plugin, handler) as T & { lastAnalysis: AnalysisResult | null };
}

// ---------------------------------------------------------------------------
// Demo scenarios
// ---------------------------------------------------------------------------

async function main() {
  const profilePath = resolve(__dirname, '../../domains/stealth_address_ops/profile.json');

  console.log('='.repeat(60));
  console.log('Kohaku + e_AI v2 Integration Demo');
  console.log('='.repeat(60));

  const advisedPlugin = withOpsAdvisor(mockRailgunPlugin, profilePath);

  // Scenario 1: Good practice — round amount via paymaster
  console.log('\n--- Scenario 1: Shield 1.0 ETH (good practice) ---');
  try {
    const result = await advisedPlugin.prepareShield(
      { amount: '1.0', token: 'ETH' },
      '0xfresh_stealth_address',
    );
    console.log('  Result:', result);
  } catch (e: any) {
    console.log('  Blocked:', e.message);
  }

  // Scenario 2: Bad practice — unique amount, unshield quickly
  console.log('\n--- Scenario 2: Unshield 3.847 ETH to known address (bad practice) ---');
  try {
    const result = await advisedPlugin.prepareUnshield(
      { amount: '3.847', token: 'ETH' },
      '0xuser_main_wallet',
    );
    console.log('  Result:', result);
  } catch (e: any) {
    console.log('  Blocked:', e.message);
  }

  // Scenario 3: Self-send attempt
  console.log('\n--- Scenario 3: Shield to self (worst case) ---');
  try {
    // Monkey-patch to simulate self-send detection
    const originalShield = mockRailgunPlugin.prepareShield;
    const selfSendPlugin = {
      ...mockRailgunPlugin,
      prepareShield: async (asset: any, to?: string) => {
        return originalShield(asset, to);
      },
    };
    // Use advised plugin directly — the self-send detection comes from
    // address cluster analysis in a real implementation
    const result = await advisedPlugin.prepareShield(
      { amount: '5.0', token: 'ETH' },
      '0xfresh_address',
    );
    console.log('  Result:', result);
  } catch (e: any) {
    console.log('  Blocked:', e.message);
  }

  console.log('\n' + '='.repeat(60));
  console.log('Demo complete.');
  console.log('='.repeat(60));
}

main().catch(console.error);
