/**
 * @pse/stealth-address-ops-advisor
 *
 * Profile-based transaction risk analysis for stealth address operations.
 * Evaluates transactions against the 6 deanonymization heuristics from
 * arxiv 2308.01703 (ACM Web Conference 2024).
 */

// Types
export type {
  AnalysisResult,
  OverallRisk,
  Profile,
  ProfileHeuristic,
  ProfileSkill,
  RiskAlert,
  Severity,
  StealthTx,
} from "./types.js";

// Analyzer
export {
  analyzeTransaction,
  formatResult,
  loadProfile,
  checkH1SameEntity,
  checkH2GasFingerprint,
  checkH3Timing,
  checkH4Funding,
  checkH5SelfSend,
  checkH6UniqueAmount,
} from "./analyzer.js";
export type { AnalyzeOptions } from "./analyzer.js";

// Kohaku middleware
export {
  withOpsAdvisor,
  OpsAdvisorBlockedError,
} from "./kohaku-middleware.js";
export type { OpsAdvisorConfig } from "./kohaku-middleware.js";
