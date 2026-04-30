/**
 * Kohaku SDK integration sketch -- ops advisor as middleware.
 *
 * The stealth address ops advisor is NOT a Kohaku plugin (it does not
 * implement shield/transfer/unshield). Instead it wraps any plugin
 * instance as middleware, intercepting operations to run risk analysis
 * before they execute.
 *
 * Pattern:
 *   const plugin = await createMyPlugin(host, params);
 *   const advised = withOpsAdvisor(plugin, profile);
 *   // advised.prepareShield(...) now runs risk analysis first
 *   // advised.lastAnalysis contains the most recent result
 */

// In a real integration this import would be:
//   import type { PluginInstance } from "@kohaku/plugins";
// For this sketch we declare the minimal shape locally so the project
// typechecks without depending on the Kohaku monorepo.

import type { AnalysisResult, Profile, StealthTx } from "./types.js";
import { analyzeTransaction } from "./analyzer.js";

/**
 * Minimal PluginInstance shape matching Kohaku's plugin base
 * (packages/plugins/src/base.ts). The real type is heavily generic;
 * we only need the method names for interception.
 */
interface PluginInstance {
  instanceId: () => Promise<string>;
  prepareShield?: (...args: unknown[]) => Promise<unknown>;
  prepareShieldMulti?: (...args: unknown[]) => Promise<unknown>;
  prepareTransfer?: (...args: unknown[]) => Promise<unknown>;
  prepareTransferMulti?: (...args: unknown[]) => Promise<unknown>;
  prepareUnshield?: (...args: unknown[]) => Promise<unknown>;
  prepareUnshieldMulti?: (...args: unknown[]) => Promise<unknown>;
  balance?: (...args: unknown[]) => Promise<unknown>;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

export interface OpsAdvisorConfig {
  /** Block when overall risk is critical. Default: true. */
  blockOnCritical: boolean;
  /** Block when transaction is flagged as deanonymized. Default: true. */
  blockOnDeanonymized: boolean;
  /** Callback invoked with the analysis result before an operation proceeds. */
  onAnalysis?: (result: AnalysisResult) => void;
  /** Override block decision. Return true to allow, false to block. */
  overrideBlock?: (result: AnalysisResult) => boolean;
}

const DEFAULT_CONFIG: OpsAdvisorConfig = {
  blockOnCritical: true,
  blockOnDeanonymized: true,
};

// ---------------------------------------------------------------------------
// Risk analysis error
// ---------------------------------------------------------------------------

export class OpsAdvisorBlockedError extends Error {
  public readonly analysis: AnalysisResult;

  constructor(analysis: AnalysisResult) {
    const alertSummary = analysis.alerts
      .filter((a) => a.severity === "critical")
      .map((a) => `${a.heuristicId}: ${a.signal}`)
      .join("; ");
    super(
      `Operation blocked by ops advisor (risk: ${analysis.overallRisk}). ${alertSummary}`,
    );
    this.name = "OpsAdvisorBlockedError";
    this.analysis = analysis;
  }
}

// ---------------------------------------------------------------------------
// Transaction extraction helpers
// ---------------------------------------------------------------------------

/**
 * Extract a StealthTx from operation parameters.
 *
 * In a real integration this would inspect the Kohaku operation's asset,
 * addresses, and on-chain context (block gas stats, deposit pool, etc.).
 * This sketch shows the shape of the extraction; actual field mapping
 * depends on the specific plugin's operation format.
 */
function extractStealthTx(
  _operationType: "shield" | "transfer" | "unshield",
  _args: unknown[],
): StealthTx | null {
  // Sketch: real implementation would extract fields from args based on
  // the operation type. For example:
  //
  //   shield:    deposit from public address into stealth pool
  //   transfer:  private-to-private (internal)
  //   unshield:  withdraw from stealth pool to public address
  //
  // Each maps differently onto StealthTx fields. The unshield case is
  // the most privacy-sensitive since it exposes a public withdrawal address.
  //
  // Returning null means "cannot analyze this operation" (skip advisor).
  return null;
}

// ---------------------------------------------------------------------------
// Middleware core
// ---------------------------------------------------------------------------

function shouldBlock(
  result: AnalysisResult,
  config: OpsAdvisorConfig,
): boolean {
  if (config.overrideBlock) {
    return !config.overrideBlock(result);
  }
  if (config.blockOnDeanonymized && result.deanonymized) {
    return true;
  }
  if (config.blockOnCritical && result.overallRisk === "critical") {
    return true;
  }
  return false;
}

async function adviseOperation<T>(
  operationType: "shield" | "transfer" | "unshield",
  args: unknown[],
  profile: Profile,
  config: OpsAdvisorConfig,
  state: { lastAnalysis: AnalysisResult | null },
  originalFn: (...a: unknown[]) => Promise<T>,
): Promise<T> {
  const tx = extractStealthTx(operationType, args);

  if (tx) {
    const result = analyzeTransaction(tx, profile);
    state.lastAnalysis = result;

    if (config.onAnalysis) {
      config.onAnalysis(result);
    }

    if (shouldBlock(result, config)) {
      throw new OpsAdvisorBlockedError(result);
    }
  }

  // Proceed with the original operation
  return originalFn(...args);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Wraps a Kohaku plugin instance with the stealth address ops advisor.
 *
 * Intercepts prepareShield, prepareTransfer, and prepareUnshield to run
 * risk analysis before execution. Returns the wrapped plugin with an
 * additional `lastAnalysis` property.
 *
 * Usage:
 *   const plugin = await createMyPlugin(host, params);
 *   const profile = loadProfile("stealth_address_ops.json");
 *   const advised = withOpsAdvisor(plugin, profile);
 *
 *   try {
 *     const op = await advised.prepareUnshield(asset, toAddress);
 *   } catch (e) {
 *     if (e instanceof OpsAdvisorBlockedError) {
 *       console.log("Blocked:", e.analysis.alerts);
 *     }
 *   }
 *
 *   // Inspect last analysis even when not blocked
 *   console.log(advised.lastAnalysis);
 */
export function withOpsAdvisor<T extends PluginInstance>(
  plugin: T,
  profile: Profile,
  config: Partial<OpsAdvisorConfig> = {},
): T & { lastAnalysis: AnalysisResult | null } {
  const fullConfig: OpsAdvisorConfig = { ...DEFAULT_CONFIG, ...config };
  const state = { lastAnalysis: null as AnalysisResult | null };

  // Create a proxy that intercepts the three operation methods.
  // All other properties/methods pass through unchanged.
  const handler: ProxyHandler<T> = {
    get(target, prop, receiver) {
      if (prop === "lastAnalysis") {
        return state.lastAnalysis;
      }

      const value = Reflect.get(target, prop, receiver);

      if (typeof value !== "function") {
        return value;
      }

      const fn = value as (...a: unknown[]) => unknown;

      // Intercept the prepare* methods
      const opMap: Record<string, "shield" | "transfer" | "unshield"> = {
        prepareShield: "shield",
        prepareShieldMulti: "shield",
        prepareTransfer: "transfer",
        prepareTransferMulti: "transfer",
        prepareUnshield: "unshield",
        prepareUnshieldMulti: "unshield",
      };

      const opType = opMap[prop as string];
      if (opType) {
        return (...args: unknown[]) =>
          adviseOperation(
            opType,
            args,
            profile,
            fullConfig,
            state,
            fn.bind(target) as (...a: unknown[]) => Promise<unknown>,
          );
      }

      // Pass through all other methods
      return fn.bind(target);
    },
  };

  return new Proxy(plugin, handler) as T & {
    lastAnalysis: AnalysisResult | null;
  };
}
