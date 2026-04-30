/**
 * Shared types for the Stealth Address Ops Analyzer.
 *
 * Models a stealth-address transaction, risk alerts from the 6
 * deanonymization heuristics (arxiv 2308.01703), and the analysis
 * result that aggregates them.
 */

// ---------------------------------------------------------------------------
// Transaction
// ---------------------------------------------------------------------------

export interface StealthTx {
  depositAddress: string;
  withdrawalAddress: string;
  stealthAddress: string;
  amountEth: number;
  depositTimestamp: number; // unix seconds
  spendTimestamp: number; // unix seconds
  gasPriceGwei: number;
  gasFundingSource: string; // "paymaster" | "self" | "relay" | address
  isSelfSend: boolean;
  addressCluster: Set<string>;
}

// ---------------------------------------------------------------------------
// Risk alert
// ---------------------------------------------------------------------------

export type Severity = "low" | "medium" | "high" | "critical";

export interface RiskAlert {
  heuristicId: string;
  heuristicName: string;
  severity: Severity;
  confidence: number;
  signal: string;
  recommendation: string;
  skill?: string;
}

// ---------------------------------------------------------------------------
// Analysis result
// ---------------------------------------------------------------------------

export type OverallRisk = "low" | "medium" | "high" | "critical";

export interface AnalysisResult {
  tx: StealthTx;
  alerts: RiskAlert[];
  overallRisk: OverallRisk;
  deanonymized: boolean;
}

// ---------------------------------------------------------------------------
// Profile types (matching stealth_address_ops.json shape)
// ---------------------------------------------------------------------------

export interface ProfileHeuristic {
  id: string;
  name: string;
  paper_section: string;
  severity: Severity;
  description: string;
  detection: {
    type: string;
    signals: Array<{
      name: string;
      description: string;
      data_needed: string[];
      confidence: number;
    }>;
    threshold: string;
  };
  recommendations: Array<{
    action: string;
    description: string;
    effectiveness: number;
    user_cost: string;
    skill_required: string | null;
  }>;
  benchmark_scenario?: {
    setup: string;
    metric: string;
    baseline: string;
  };
  fundamental_limitation?: string;
}

export interface ProfileSkill {
  tool: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface Profile {
  meta: {
    domain_name: string;
    version: string;
    generated_by: string;
    validation_status: string;
    source_paper: string;
    baseline_deanon_rate: number;
    target_deanon_rate: number;
  };
  risk_domain: {
    name: string;
    crops_property: string;
    description: string;
    protocols: string[];
    adversary_model: {
      capabilities: string[];
      limitations: string[];
    };
  };
  heuristics: {
    H1_same_entity_withdrawal: ProfileHeuristic;
    H2_gas_price_fingerprinting: ProfileHeuristic;
    H3_timing_correlation: ProfileHeuristic;
    H4_funding_linkability: ProfileHeuristic;
    H5_self_transfer: ProfileHeuristic;
    H6_unique_amounts: ProfileHeuristic;
  };
  skills: {
    timing_delay: ProfileSkill;
    gas_randomizer: ProfileSkill;
    paymaster: ProfileSkill;
    amount_normalizer: ProfileSkill & {
      parameters: { denominations_eth: number[] };
    };
    pool_monitor: ProfileSkill;
    activity_monitor: ProfileSkill;
  };
  combined_benchmark: Record<string, unknown>;
  templates: Record<string, string>;
}
