/**
 * Stealth Address Ops Analyzer -- TypeScript port of analyzer.py.
 *
 * Loads stealth_address_ops.json profile and evaluates transactions against
 * the 6 deanonymization heuristics from arxiv 2308.01703.
 *
 * Pure TypeScript, no external dependencies.
 */

import { readFileSync } from "node:fs";
import type {
  AnalysisResult,
  OverallRisk,
  Profile,
  RiskAlert,
  StealthTx,
} from "./types.js";

// ---------------------------------------------------------------------------
// Profile loader
// ---------------------------------------------------------------------------

export function loadProfile(path: string): Profile {
  const raw = readFileSync(path, "utf-8");
  return JSON.parse(raw) as Profile;
}

// ---------------------------------------------------------------------------
// Heuristic checks (H1-H6)
// ---------------------------------------------------------------------------

/** H1: Same-entity withdrawal -- sender and receiver in same cluster. */
export function checkH1SameEntity(
  tx: StealthTx,
  profile: Profile,
): RiskAlert[] {
  const alerts: RiskAlert[] = [];
  const h = profile.heuristics.H1_same_entity_withdrawal;

  if (tx.addressCluster.has(tx.withdrawalAddress)) {
    alerts.push({
      heuristicId: "H1",
      heuristicName: h.name,
      severity: h.severity,
      confidence: 0.95,
      signal: "Withdrawal address is in sender's address cluster",
      recommendation: h.recommendations[0].description,
    });
  }
  return alerts;
}

/** H2: Gas price fingerprinting. */
export function checkH2GasFingerprint(
  tx: StealthTx,
  profile: Profile,
  blockMedianGas: number = 30.0,
  blockStdGas: number = 5.0,
): RiskAlert[] {
  const alerts: RiskAlert[] = [];
  const h = profile.heuristics.H2_gas_price_fingerprinting;

  const zScore =
    Math.abs(tx.gasPriceGwei - blockMedianGas) / Math.max(blockStdGas, 0.1);
  if (zScore > 2.0) {
    alerts.push({
      heuristicId: "H2",
      heuristicName: h.name,
      severity: h.severity,
      confidence: Math.min(0.5 + zScore * 0.1, 0.95),
      signal: `Gas price ${tx.gasPriceGwei.toFixed(1)} gwei is ${zScore.toFixed(1)} std devs from block median (${blockMedianGas.toFixed(1)})`,
      recommendation: h.recommendations[0].description,
      skill: "gas_randomizer",
    });
  }
  return alerts;
}

/** H3: Timing correlation -- short dwell time between deposit and spend. */
export function checkH3Timing(
  tx: StealthTx,
  profile: Profile,
): RiskAlert[] {
  const alerts: RiskAlert[] = [];
  const h = profile.heuristics.H3_timing_correlation;

  const dwellHours = (tx.spendTimestamp - tx.depositTimestamp) / 3600;
  if (dwellHours < 1) {
    alerts.push({
      heuristicId: "H3",
      heuristicName: h.name,
      severity: "critical",
      confidence: 0.9,
      signal: `Spend occurred ${dwellHours.toFixed(1)}h after deposit (< 1h threshold)`,
      recommendation: h.recommendations[0].description,
      skill: "timing_delay",
    });
  } else if (dwellHours < 6) {
    alerts.push({
      heuristicId: "H3",
      heuristicName: h.name,
      severity: "high",
      confidence: 0.6,
      signal: `Spend occurred ${dwellHours.toFixed(1)}h after deposit (< 6h threshold)`,
      recommendation: h.recommendations[0].description,
      skill: "timing_delay",
    });
  }
  return alerts;
}

/** H4: Funding linkability -- stealth address gas funded from known address. */
export function checkH4Funding(
  tx: StealthTx,
  profile: Profile,
): RiskAlert[] {
  const alerts: RiskAlert[] = [];
  const h = profile.heuristics.H4_funding_linkability;

  if (tx.gasFundingSource !== "paymaster" && tx.gasFundingSource !== "relay") {
    const confidence = tx.gasFundingSource !== "fresh" ? 0.95 : 0.3;
    alerts.push({
      heuristicId: "H4",
      heuristicName: h.name,
      severity: h.severity,
      confidence,
      signal: `Stealth address gas funded from ${tx.gasFundingSource}`,
      recommendation: h.recommendations[0].description,
      skill: "paymaster",
    });
  }
  return alerts;
}

/** H5: Self-transfer detection. */
export function checkH5SelfSend(
  tx: StealthTx,
  profile: Profile,
): RiskAlert[] {
  const alerts: RiskAlert[] = [];
  const h = profile.heuristics.H5_self_transfer;

  if (tx.isSelfSend) {
    alerts.push({
      heuristicId: "H5",
      heuristicName: h.name,
      severity: "critical",
      confidence: 1.0,
      signal: "Self-transfer detected: sender is the stealth address owner",
      recommendation: h.recommendations[0].description,
    });
  }
  return alerts;
}

/** H6: Unique amounts -- non-standard amounts narrow anonymity set. */
export function checkH6UniqueAmount(
  tx: StealthTx,
  profile: Profile,
  depositPoolAmounts?: number[],
): RiskAlert[] {
  const alerts: RiskAlert[] = [];
  const h = profile.heuristics.H6_unique_amounts;

  const standardDenoms =
    profile.skills.amount_normalizer.parameters.denominations_eth;
  const isRound = standardDenoms.includes(tx.amountEth);

  if (!isRound) {
    let confidence: number;
    let signal: string;

    if (depositPoolAmounts && depositPoolAmounts.length > 0) {
      const matches = depositPoolAmounts.filter(
        (a) => Math.abs(a - tx.amountEth) < 0.001,
      ).length;
      if (matches <= 1) {
        confidence = 0.95;
        signal = `Amount ${tx.amountEth} ETH is unique in deposit pool (no other matching deposits)`;
      } else if (matches < 5) {
        confidence = 0.7;
        signal = `Amount ${tx.amountEth} ETH has only ${matches} matches in deposit pool`;
      } else {
        return alerts; // enough cover
      }
    } else {
      confidence = 0.5;
      signal = `Amount ${tx.amountEth} ETH is not a standard denomination`;
    }

    // Find nearest standard denomination
    let nearest = standardDenoms[0];
    let nearestDist = Math.abs(tx.amountEth - nearest);
    for (const d of standardDenoms) {
      const dist = Math.abs(tx.amountEth - d);
      if (dist < nearestDist) {
        nearest = d;
        nearestDist = dist;
      }
    }

    alerts.push({
      heuristicId: "H6",
      heuristicName: h.name,
      severity: h.severity,
      confidence,
      signal,
      recommendation: `Round to ${nearest} ETH (${h.recommendations[0].description})`,
      skill: "amount_normalizer",
    });
  }
  return alerts;
}

// ---------------------------------------------------------------------------
// Main analyzer
// ---------------------------------------------------------------------------

export interface AnalyzeOptions {
  depositPoolAmounts?: number[];
  blockMedianGas?: number;
  blockStdGas?: number;
}

/** Run all 6 heuristic checks against a transaction. */
export function analyzeTransaction(
  tx: StealthTx,
  profile: Profile,
  options: AnalyzeOptions = {},
): AnalysisResult {
  const {
    depositPoolAmounts,
    blockMedianGas = 30.0,
    blockStdGas = 5.0,
  } = options;

  const allAlerts: RiskAlert[] = [
    ...checkH1SameEntity(tx, profile),
    ...checkH2GasFingerprint(tx, profile, blockMedianGas, blockStdGas),
    ...checkH3Timing(tx, profile),
    ...checkH4Funding(tx, profile),
    ...checkH5SelfSend(tx, profile),
    ...checkH6UniqueAmount(tx, profile, depositPoolAmounts),
  ];

  // Determine overall risk level (same logic as Python version)
  let overallRisk: OverallRisk = "low";
  let deanonymized = false;

  if (
    allAlerts.some((a) => a.severity === "critical" && a.confidence > 0.8)
  ) {
    overallRisk = "critical";
    deanonymized = true;
  } else if (allAlerts.some((a) => a.severity === "critical")) {
    overallRisk = "high";
  } else if (allAlerts.some((a) => a.severity === "high")) {
    overallRisk = "medium";
  } else if (allAlerts.length > 0) {
    overallRisk = "low";
  }

  return { tx, alerts: allAlerts, overallRisk, deanonymized };
}

// ---------------------------------------------------------------------------
// Formatter
// ---------------------------------------------------------------------------

/** Format analysis result for display (matches Python format_result output). */
export function formatResult(result: AnalysisResult): string {
  const dwellHours =
    (result.tx.spendTimestamp - result.tx.depositTimestamp) / 3600;

  const lines: string[] = [
    `--- Risk Assessment: ${result.overallRisk.toUpperCase()} ---`,
    `Amount: ${result.tx.amountEth} ETH`,
    `Dwell time: ${dwellHours.toFixed(1)}h`,
    `Gas funding: ${result.tx.gasFundingSource}`,
    `Alerts: ${result.alerts.length}`,
  ];

  if (result.deanonymized) {
    lines.push("*** LIKELY DEANONYMIZED ***");
  }

  for (const alert of result.alerts) {
    lines.push("");
    lines.push(
      `  [${alert.heuristicId}] ${alert.heuristicName} (confidence: ${(alert.confidence * 100).toFixed(0)}%)`,
    );
    lines.push(`    Signal: ${alert.signal}`);
    lines.push(`    Action: ${alert.recommendation}`);
    if (alert.skill) {
      lines.push(`    Skill: ${alert.skill}`);
    }
  }

  return lines.join("\n");
}
