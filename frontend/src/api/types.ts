export interface Stats {
  by_status: Record<string, number>;
  total_unresolved_amount: string;
  oldest_unresolved_days: number | null;
  total_exceptions: number;
}

export interface ExceptionSummary {
  bank_event_id: string;
  match_id: string;
  posted_date: string;
  amount: string;
  direction: 'debit' | 'credit';
  descriptor: string | null;
  bank_account_id: string;
  match_type: string | null;
  confidence: string | null;
  status: string;
}

export interface ExceptionList {
  items: ExceptionSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface LedgerEntry {
  id: string;
  entry_type: string;
  direction: 'debit' | 'credit';
  amount: string;
  expected_date: string;
  reference: string | null;
  counterparty: string | null;
  allocated_amount?: string;
}

export interface Candidate {
  ledger_entry: LedgerEntry;
  score: number;
  score_reasons: string[];
}

export interface ExceptionDetail {
  bank_event_id: string;
  match_id: string;
  bank_event: {
    id: string;
    amount: string;
    posted_date: string;
    descriptor: string | null;
    direction: 'debit' | 'credit';
    bank_reference: string | null;
    bank_account_id: string;
  };
  match_type: string | null;
  confidence: string | null;
  status: string;
  why_uncertain: string;
  suggested_ledger_entries: LedgerEntry[];
  candidates: Candidate[];
  notes: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
}

export interface AuditEvent {
  id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
  payload: {
    bank_event_id: string;
    before: Record<string, unknown>;
    after: Record<string, unknown>;
    note?: string;
  };
}

export interface ExceptionFilters {
  match_type: string;
  status: string[];
  sort: string;
  amount_min: string;
  amount_max: string;
  page: number;
}

export interface AllocationItem {
  ledger_entry_id: string;
  allocated_amount: string;
}

// ── Cash-position types ──────────────────────────────────────────────────────

export type CoverageStatus = 'healthy' | 'watch' | 'shortfall';

export interface GroupPosition {
  group_id: string;
  group_name: string;
  funded_balance: string;
  pending_claims_liability: string;
  available_to_cover: string;
  coverage_status: CoverageStatus;
  member_count: number;
}

export interface CashPositionSummary {
  total_funded: string;
  total_pending_liability: string;
  groups_in_shortfall: number;
}

export interface CashPositionResponse {
  summary: CashPositionSummary;
  groups: GroupPosition[];
}

export interface CashLedgerEntry {
  id: string;
  entry_type: string;
  direction: 'debit' | 'credit';
  amount: string;
  expected_date: string;
  reference: string | null;
  counterparty: string | null;
  status: string;
}

export interface GroupPositionDetail extends GroupPosition {
  cleared_entries: CashLedgerEntry[];
  pending_entries: CashLedgerEntry[];
}
