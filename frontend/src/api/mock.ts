/**
 * Snapshot captured from live backend on 2026-06-02.
 * All IDs, amounts, dates, and counts match the seeded database exactly.
 * Regenerate by running: curl http://localhost:8000/exceptions/stats && ...
 */

import type { AuditEvent, CashPositionResponse, ExceptionDetail, ExceptionSummary, GroupPositionDetail, Stats } from './types';

// ── Real /exceptions/stats snapshot ─────────────────────────────────────────

export const MOCK_STATS: Stats = {
  by_status: {
    pending: 0,
    matched: 230,
    reviewed: 0,
    resolved: 4,
    needs_review: 107,
    written_off: 1,
    flagged: 1,
    partially_resolved: 0,
  },
  total_unresolved_amount: '1348577.53',
  oldest_unresolved_days: 91,
  total_exceptions: 343,
};

// ── Real /exceptions?sort=confidence_asc list (curated 20-item snapshot) ────
// Items chosen to cover all match types and the full confidence ramp.

const BA1 = '017ae55d-c1fa-4081-8e56-58bd6612ed3c';
const BA2 = 'f989c900-d244-44b9-be5c-9610f560051c';

export const MOCK_EXCEPTIONS: ExceptionSummary[] = [
  // — Unmatched (confidence 0.00) — worst-first ————————————————————————————
  {
    bank_event_id: '5eb4dd37-f3b0-4822-af89-df4c55dd5c56',
    match_id: '9877b2a1-1387-47a8-8863-06e34e8b1c97',
    posted_date: '2026-03-06',
    amount: '274.80',
    direction: 'credit',
    descriptor: 'INTEREST CREDIT 503',
    bank_account_id: BA1,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: '146c0a3a-3ebb-4429-afb3-17205f60ba43',
    match_id: 'e1686237-e555-436c-b37d-6ebee13257bb',
    posted_date: '2026-03-06',
    amount: '6209.75',
    direction: 'credit',
    descriptor: 'ACH RTN Coverage Partners',
    bank_account_id: BA1,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: '8644edcc-a393-49fd-a2f0-c791e59ff867',
    match_id: 'bd3f20a4-257f-4a0d-9702-c3314e37de48',
    posted_date: '2026-03-08',
    amount: '6209.75',
    direction: 'debit',
    descriptor: 'REISSUE Coverage Partners',
    bank_account_id: BA1,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: 'c50e78ba-e72f-4998-a4c7-125cace46731',
    match_id: '0b37e3b4-6a02-4d58-a630-ea8f4bf587f8',
    posted_date: '2026-04-11',
    amount: '5351.94',
    direction: 'credit',
    descriptor: 'REISSUE Employer Group 4',
    bank_account_id: BA1,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: '9e9e862a-13a2-4ed5-8349-dbe20ce239db',
    match_id: '89d19622-4fb6-4008-bfa8-4add00931a04',
    posted_date: '2026-04-09',
    amount: '5351.94',
    direction: 'debit',
    descriptor: 'ACH RTN Employer Group 4',
    bank_account_id: BA1,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: '5439cfc6-e3f7-4691-93c8-9a1e28fba882',
    match_id: '0c48ee13-a083-4bf1-bad2-01e3ee02c43a',
    posted_date: '2026-04-30',
    amount: '37599.49',
    direction: 'debit',
    descriptor: 'ACH RTN Risk Management Corp.',
    bank_account_id: BA1,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: '7820ef99-220a-4ba7-9b5c-b4b41cf0d959',
    match_id: '117b8d5e-8606-4921-9215-2abb9c02ea0e',
    posted_date: '2026-05-02',
    amount: '37599.49',
    direction: 'credit',
    descriptor: 'REISSUE Risk Management Corp.',
    bank_account_id: BA1,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: '129dc20f-842d-426e-9de3-94e0b7a6f6de',
    match_id: '0f82d03a-dc72-4202-9738-211fceff86b9',
    posted_date: '2026-05-05',
    amount: '9549.15',
    direction: 'credit',
    descriptor: 'ACH RTN StopLoss Inc.',
    bank_account_id: BA1,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: '56328be5-b379-4c5e-9901-788491489e83',
    match_id: '7b2016b0-d66a-4450-abf9-5b12e8468853',
    posted_date: '2026-05-07',
    amount: '9549.15',
    direction: 'debit',
    descriptor: 'REISSUE StopLoss Inc.',
    bank_account_id: BA1,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: 'ecc30e4d-53c9-4b3e-99d9-e116f85afc1c',
    match_id: 'afded8a9-86a2-422c-a28f-0b76a5fc6600',
    posted_date: '2026-06-03',
    amount: '152.15',
    direction: 'debit',
    descriptor: 'WIRE FEE REF38257',
    bank_account_id: BA2,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  {
    bank_event_id: 'd90aabde-fe07-4ae2-b3ec-cd43f3d19d79',
    match_id: '4456ced8-4630-4fb0-9192-48fefdf22c3b',
    posted_date: '2026-06-06',
    amount: '102707.86',
    direction: 'credit',
    descriptor: 'REISSUE Employer Group 3',
    bank_account_id: BA2,
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
  },
  // — Fuzzy (medium confidence, amber zone) ————————————————————————————————
  {
    bank_event_id: 'f75e56f1-6235-4d8f-9027-93f5e49023e9',
    match_id: '17113cdf-9c5f-4869-83f8-266bd64bad29',
    posted_date: '2026-05-07',
    amount: '7863.09',
    direction: 'debit',
    descriptor: 'WIRE Coverage Partners (AMT VAR)',
    bank_account_id: BA1,
    match_type: 'fuzzy',
    confidence: '0.5217',
    status: 'needs_review',
  },
  {
    bank_event_id: 'dc11b1b5-6d33-4b53-bcdb-666373868520',
    match_id: '25327884-933a-4846-8378-68851b91172d',
    posted_date: '2026-06-08',
    amount: '10579.91',
    direction: 'debit',
    descriptor: 'WIRE Risk Management Corp. (AMT VAR)',
    bank_account_id: BA1,
    match_type: 'fuzzy',
    confidence: '0.5570',
    status: 'needs_review',
  },
  {
    bank_event_id: '87c08d51-203b-4bcb-bf58-a77d6d438820',
    match_id: 'da4a4c15-f61f-44db-8458-61a71d74486c',
    posted_date: '2026-03-14',
    amount: '9678.63',
    direction: 'debit',
    descriptor: 'LATE PMT StopLoss Inc.',
    bank_account_id: BA1,
    match_type: 'fuzzy',
    confidence: '0.6245',
    status: 'needs_review',
  },
  {
    bank_event_id: 'cdea721c-df8f-491e-b9d0-37c39fa8156b',
    match_id: '2ace1a20-c5d5-4d9d-b17c-202889e18f8e',
    posted_date: '2026-05-25',
    amount: '42515.57',
    direction: 'credit',
    descriptor: 'LATE PMT Risk Management Corp.',
    bank_account_id: BA1,
    match_type: 'fuzzy',
    confidence: '0.5957',
    status: 'needs_review',
  },
  {
    bank_event_id: 'cb633b28-12d3-4d89-bb80-5e9ee8921bcb',
    match_id: '8383d932-e1ff-49f5-87aa-53704d227b89',
    posted_date: '2026-06-02',
    amount: '325284.32',
    direction: 'credit',
    descriptor: 'WIRE Employer Group 23 (AMT VAR)',
    bank_account_id: BA2,
    match_type: 'fuzzy',
    confidence: '0.6075',
    status: 'needs_review',
  },
  // — Higher confidence (teal zone) ————————————————————————————————————————
  {
    bank_event_id: '046ddc74-e031-427a-9a0d-a525b3bd095c',
    match_id: 'f245ba6a-b89b-4e27-afdb-964a629668ea',
    posted_date: '2026-03-05',
    amount: '16782.49',
    direction: 'debit',
    descriptor: 'WIRE Coverage Partners (AMT VAR)',
    bank_account_id: BA1,
    match_type: 'fuzzy',
    confidence: '0.7563',
    status: 'needs_review',
  },
  {
    bank_event_id: '9d899177-d386-404c-8a2b-64a0e682351d',
    match_id: '7422a80b-bc2f-4da3-bb5e-278e70058f91',
    posted_date: '2026-06-08',
    amount: '14506.72',
    direction: 'debit',
    descriptor: 'LATE PMT Risk Management Corp.',
    bank_account_id: BA1,
    match_type: 'fuzzy',
    confidence: '0.7315',
    status: 'needs_review',
  },
  {
    bank_event_id: '96e2d409-e1d1-41fb-be07-e217a4d51720',
    match_id: 'b167366f-969c-4505-98ef-8d5dca9d78f6',
    posted_date: '2026-06-12',
    amount: '63732.93',
    direction: 'debit',
    descriptor: 'ACH BATCH 000000 32 CLMS',
    bank_account_id: BA2,
    match_type: 'many_to_one',
    confidence: '0.9900',
    status: 'needs_review',
  },
  // — Flagged ——————————————————————————————————————————————————————————————
  {
    bank_event_id: '2a07951c-e946-4146-acb4-439ec15e0d63',
    match_id: '78c17e5c-aa23-4bca-a378-4e2bc94bb73b',
    posted_date: '2026-05-31',
    amount: '193064.33',
    direction: 'credit',
    descriptor: 'WIRE Employer Group 21 (AMT VAR)',
    bank_account_id: BA2,
    match_type: 'fuzzy',
    confidence: '0.7138',
    status: 'flagged',
  },
];

// ── Real /exceptions/{id} detail snapshots ───────────────────────────────────

const DETAIL_MAP: Record<string, ExceptionDetail> = {
  // Flagged fuzzy — $193k employer funding wire
  '2a07951c-e946-4146-acb4-439ec15e0d63': {
    bank_event_id: '2a07951c-e946-4146-acb4-439ec15e0d63',
    match_id: '78c17e5c-aa23-4bca-a378-4e2bc94bb73b',
    bank_event: {
      id: '2a07951c-e946-4146-acb4-439ec15e0d63',
      amount: '193064.33',
      posted_date: '2026-05-31',
      descriptor: 'WIRE Employer Group 21 (AMT VAR)',
      direction: 'credit',
      bank_reference: 'trace_000109',
      bank_account_id: BA2,
    },
    match_type: 'fuzzy',
    confidence: '0.7138',
    status: 'flagged',
    why_uncertain: '±1.2% amount variance (193064.33 vs 190825.90); no reference found in bank descriptor',
    suggested_ledger_entries: [
      {
        id: '8f473ae8-bea6-4674-a0a5-25080772047a',
        entry_type: 'employer_funding',
        direction: 'credit',
        amount: '190825.90',
        expected_date: '2026-06-01',
        reference: 'emp_fund_19ff3699-b951-494e-8fc8-c8c926cc6a36',
        counterparty: 'Employer Group 20',
      },
    ],
    candidates: [
      {
        ledger_entry: {
          id: '96517163-ccf3-4d88-8b97-cbcc7e226d44',
          entry_type: 'employer_funding',
          direction: 'credit',
          amount: '190557.73',
          expected_date: '2026-05-30',
          reference: 'emp_fund_b3cbc4f4-af66-4652-ae55-0b19eecd81bc',
          counterparty: 'Employer Group 21',
        },
        score: 0.7893,
        score_reasons: ['±1.3% amount difference', '1d date difference', 'partial descriptor match'],
      },
      {
        ledger_entry: {
          id: 'feade2f0-b534-43a6-a2b3-96345e5c1ed9',
          entry_type: 'employer_funding',
          direction: 'credit',
          amount: '154526.76',
          expected_date: '2026-05-30',
          reference: 'emp_fund_82622be3-9175-4564-92b0-48af01341c27',
          counterparty: 'Employer Group 24',
        },
        score: 0.4091,
        score_reasons: ['amount outside tolerance', '1d date difference', 'partial descriptor match'],
      },
    ],
    notes: 'demo: needs director sign-off — escalated',
    resolved_by: null,
    resolved_at: null,
  },

  // Many-to-one claim batch — $63k, 32 claims, high confidence
  '96e2d409-e1d1-41fb-be07-e217a4d51720': {
    bank_event_id: '96e2d409-e1d1-41fb-be07-e217a4d51720',
    match_id: 'b167366f-969c-4505-98ef-8d5dca9d78f6',
    bank_event: {
      id: '96e2d409-e1d1-41fb-be07-e217a4d51720',
      amount: '63732.93',
      posted_date: '2026-06-12',
      descriptor: 'ACH BATCH 000000 32 CLMS',
      direction: 'debit',
      bank_reference: 'trace_000000',
      bank_account_id: BA2,
    },
    match_type: 'many_to_one',
    confidence: '0.9900',
    status: 'needs_review',
    why_uncertain: 'batch reference unclear — matched by amount only',
    suggested_ledger_entries: [
      { id: '36b7b3d5-84da-48ec-a8f6-0fb6a96420ca', entry_type: 'claim_payment', direction: 'debit', amount: '2215.56', expected_date: '2026-05-16', reference: 'f7c85152-1c23-4198-99f5-bc7e328f3ad3', counterparty: 'Case LLC' },
      { id: '15e26422-efeb-4832-af0c-05dba30558d3', entry_type: 'claim_payment', direction: 'debit', amount: '1581.00', expected_date: '2026-06-12', reference: '27ef57a3-378f-44fc-be82-072dac9b1d9e', counterparty: 'Snyder-Ellis' },
      { id: '50a76083-9286-48c9-b0c0-c65016b1c481', entry_type: 'claim_payment', direction: 'debit', amount: '1119.97', expected_date: '2026-04-23', reference: '9afe2914-dd6a-4c17-bf9c-9a470ec4e8d2', counterparty: 'Stephens PLC' },
      { id: '8a2585dc-2561-46af-808d-367c170c0e16', entry_type: 'claim_payment', direction: 'debit', amount: '1974.29', expected_date: '2026-05-24', reference: 'd9f7fcd2-92ec-482b-9cae-29913e2485d0', counterparty: 'Burgess-Morrow' },
      { id: 'eb1df2fc-a349-4175-8347-30d322e2bd83', entry_type: 'claim_payment', direction: 'debit', amount: '3478.52', expected_date: '2026-04-22', reference: '341fb972-9e29-4ee7-82c3-c8f0829ad445', counterparty: 'Martin and Sons' },
      { id: 'ac1ae883-efcc-4b29-a1d9-ceb5e6acc811', entry_type: 'claim_payment', direction: 'debit', amount: '2782.48', expected_date: '2026-04-05', reference: '4e5db758-8591-4fb0-ae6a-0c2fd0ae02fd', counterparty: 'Mcdaniel Ltd' },
    ],
    candidates: [],
    notes: 'demo: operator suspects incorrect auto-match',
    resolved_by: null,
    resolved_at: null,
  },

  // Fuzzy stop-loss premium — $7.8k, medium confidence, multiple candidates
  'f75e56f1-6235-4d8f-9027-93f5e49023e9': {
    bank_event_id: 'f75e56f1-6235-4d8f-9027-93f5e49023e9',
    match_id: '17113cdf-9c5f-4869-83f8-266bd64bad29',
    bank_event: {
      id: 'f75e56f1-6235-4d8f-9027-93f5e49023e9',
      amount: '7863.09',
      posted_date: '2026-05-07',
      descriptor: 'WIRE Coverage Partners (AMT VAR)',
      direction: 'debit',
      bank_reference: 'trace_000286',
      bank_account_id: BA1,
    },
    match_type: 'fuzzy',
    confidence: '0.5217',
    status: 'needs_review',
    why_uncertain: '±4.7% amount variance (7863.09 vs 7508.78); no reference found in bank descriptor',
    suggested_ledger_entries: [
      {
        id: 'c57e358e-e038-4ca4-8f4b-0913b5644a93',
        entry_type: 'stop_loss_premium',
        direction: 'debit',
        amount: '7508.78',
        expected_date: '2026-05-05',
        reference: 'sl_prem_824c6d6f-b416-47ab-9934-f61bac3d05db_2026_05',
        counterparty: 'Coverage Partners',
      },
    ],
    candidates: [
      {
        ledger_entry: {
          id: '47a86a20-8341-4773-ab5f-be165d4f48a5',
          entry_type: 'stop_loss_premium',
          direction: 'debit',
          amount: '7075.75',
          expected_date: '2026-05-05',
          reference: 'sl_prem_82622be3-9175-4564-92b0-48af01341c27_2026_05',
          counterparty: 'Coverage Partners',
        },
        score: 0.3951,
        score_reasons: ['amount outside tolerance', '2d date difference', 'partial descriptor match'],
      },
      {
        ledger_entry: {
          id: '42498ef2-8906-4f06-8550-6fac730b3eb4',
          entry_type: 'stop_loss_premium',
          direction: 'debit',
          amount: '6324.90',
          expected_date: '2026-05-06',
          reference: 'sl_prem_c84a2e99-492c-4049-b48e-d5b1be6facb5_2026_05',
          counterparty: 'StopLoss Inc.',
        },
        score: 0.366,
        score_reasons: ['amount outside tolerance', '1d date difference'],
      },
      {
        ledger_entry: {
          id: '9aea83d9-3982-4f66-bc13-05e5fbc9207a',
          entry_type: 'stop_loss_premium',
          direction: 'debit',
          amount: '7305.72',
          expected_date: '2026-05-02',
          reference: 'sl_prem_8b26393b-ee0f-4ee9-97b5-6a5d060ef173_2026_05',
          counterparty: 'Risk Management Corp.',
        },
        score: 0.329,
        score_reasons: ['±7.6% amount difference', '5d date difference', 'partial descriptor match'],
      },
    ],
    notes: null,
    resolved_by: null,
    resolved_at: null,
  },

  // Unmatched — ACH return, no candidates
  '129dc20f-842d-426e-9de3-94e0b7a6f6de': {
    bank_event_id: '129dc20f-842d-426e-9de3-94e0b7a6f6de',
    match_id: '0f82d03a-dc72-4202-9738-211fceff86b9',
    bank_event: {
      id: '129dc20f-842d-426e-9de3-94e0b7a6f6de',
      amount: '9549.15',
      posted_date: '2026-05-05',
      descriptor: 'ACH RTN StopLoss Inc.',
      direction: 'credit',
      bank_reference: 'trace_000150',
      bank_account_id: BA1,
    },
    match_type: 'unmatched',
    confidence: '0.0000',
    status: 'needs_review',
    why_uncertain: 'No ledger counterpart found — possible bank fee, interest, or genuine noise',
    suggested_ledger_entries: [],
    candidates: [],
    notes: null,
    resolved_by: null,
    resolved_at: null,
  },
};

function genericDetail(s: ExceptionSummary): ExceptionDetail {
  return {
    bank_event_id: s.bank_event_id,
    match_id: s.match_id,
    bank_event: {
      id: s.bank_event_id,
      amount: s.amount,
      posted_date: s.posted_date,
      descriptor: s.descriptor,
      direction: s.direction,
      bank_reference: null,
      bank_account_id: s.bank_account_id,
    },
    match_type: s.match_type,
    confidence: s.confidence,
    status: s.status,
    why_uncertain:
      s.match_type === 'unmatched'
        ? 'No ledger counterpart found — possible bank fee, interest, or genuine noise'
        : `low-confidence ${s.match_type ?? 'unknown'} match (score ${parseFloat(s.confidence ?? '0').toFixed(2)})`,
    suggested_ledger_entries: [],
    candidates: [],
    notes: null,
    resolved_by: null,
    resolved_at: null,
  };
}

export function getMockDetail(bankEventId: string): ExceptionDetail {
  if (DETAIL_MAP[bankEventId]) return DETAIL_MAP[bankEventId];
  const summary = MOCK_EXCEPTIONS.find(e => e.bank_event_id === bankEventId);
  return summary ? genericDetail(summary) : genericDetail({
    bank_event_id: bankEventId, match_id: '', posted_date: '2026-06-02',
    amount: '0.00', direction: 'debit', descriptor: null,
    bank_account_id: BA1, match_type: null, confidence: null, status: 'needs_review',
  });
}

// ── Real /audit/{id} snapshot ────────────────────────────────────────────────

const AUDIT_MAP: Record<string, AuditEvent[]> = {
  '2a07951c-e946-4146-acb4-439ec15e0d63': [
    {
      id: '07fff91b-bc62-4381-bdfd-51b6138cb51b',
      actor: 'operator',
      action: 'flag',
      entity_type: 'reconciliation_match',
      entity_id: '78c17e5c-aa23-4bca-a378-4e2bc94bb73b',
      created_at: '2026-06-02T23:24:50.134032',
      payload: {
        bank_event_id: '2a07951c-e946-4146-acb4-439ec15e0d63',
        before: { status: 'needs_review' },
        after: { status: 'flagged', note: 'demo: needs director sign-off — escalated' },
        note: 'demo: needs director sign-off — escalated',
      },
    },
  ],
};

export function getMockAudit(bankEventId: string): AuditEvent[] {
  return AUDIT_MAP[bankEventId] ?? [];
}

// ── Real /cash-position snapshot (2026-06-04, seed=42) ──────────────────────
// Prefunded model: employer_funding = 125% of regular claims, pending claims
// are adjudicated batches whose ACH has not yet settled.

export const MOCK_CASH_POSITION: CashPositionResponse = {
  summary: {
    total_funded: '1400352.24',
    total_pending_liability: '323234.85',
    groups_in_shortfall: 4,
  },
  groups: [
    // — Shortfall (positive funded balance, but pending exceeds it) —
    { group_id: 'cca433aa-4b35-44a2-bd4d-9cd7b7c9f8b2', group_name: 'Employer Group 14', funded_balance: '16087.21',  pending_claims_liability: '20401.04', available_to_cover: '16087.21',  coverage_status: 'shortfall', member_count: 320 },
    { group_id: 'ac2bedf8-4f42-47b7-89ea-36e5042e15fc', group_name: 'Employer Group 2',  funded_balance: '24232.50',  pending_claims_liability: '31699.67', available_to_cover: '24232.50',  coverage_status: 'shortfall', member_count: 320 },
    { group_id: '96b42997-df47-4f72-ba94-86280318b0ed', group_name: 'Employer Group 4',  funded_balance: '25917.67',  pending_claims_liability: '56297.36', available_to_cover: '25917.67',  coverage_status: 'shortfall', member_count: 320 },
    { group_id: '9236dba2-9e42-45f9-924f-511df8a9417c', group_name: 'Employer Group 8',  funded_balance: '49710.31',  pending_claims_liability: '59377.84', available_to_cover: '49710.31',  coverage_status: 'shortfall', member_count: 320 },
    // — Healthy —
    { group_id: 'd9368181-daf0-44fd-b246-c111889ea61b', group_name: 'Employer Group 17', funded_balance: '29731.34',  pending_claims_liability: '0',        available_to_cover: '29731.34',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: 'fc67e828-84b8-4ec0-abb0-03eb760381c5', group_name: 'Employer Group 6',  funded_balance: '30580.37',  pending_claims_liability: '0',        available_to_cover: '30580.37',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '738249c9-d8a0-47bb-805c-fe5766d0162f', group_name: 'Employer Group 3',  funded_balance: '33294.75',  pending_claims_liability: '0',        available_to_cover: '33294.75',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: 'ab1e8f83-08b5-49e2-864b-8cd747ac61c9', group_name: 'Employer Group 24', funded_balance: '34208.35',  pending_claims_liability: '0',        available_to_cover: '34208.35',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '98042184-7929-49d1-8575-fd42fdccc154', group_name: 'Employer Group 7',  funded_balance: '43586.23',  pending_claims_liability: '0',        available_to_cover: '43586.23',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '8890182d-ec8f-4d7a-bda4-5046ee9b033c', group_name: 'Employer Group 16', funded_balance: '44332.91',  pending_claims_liability: '13978.89', available_to_cover: '44332.91',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: 'a508c264-762e-406e-9982-56bcd7986a93', group_name: 'Employer Group 9',  funded_balance: '52890.37',  pending_claims_liability: '0',        available_to_cover: '52890.37',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '1f8b77b0-391e-437a-971f-2725687f8fd5', group_name: 'Employer Group 21', funded_balance: '57530.63',  pending_claims_liability: '18870.81', available_to_cover: '57530.63',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: 'eebf9ba9-5177-44f9-a649-8eb1699a031e', group_name: 'Employer Group 10', funded_balance: '60803.59',  pending_claims_liability: '46732.39', available_to_cover: '60803.59',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '8197ca49-e333-4393-9ee3-c84786ca3a31', group_name: 'Employer Group 19', funded_balance: '61514.04',  pending_claims_liability: '0',        available_to_cover: '61514.04',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: 'ab7da34e-2f9f-4e7e-bc42-76100ddbb464', group_name: 'Employer Group 20', funded_balance: '62651.53',  pending_claims_liability: '18203.37', available_to_cover: '62651.53',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '9b05f76b-1d59-4649-a08d-c2ccd888041d', group_name: 'Employer Group 12', funded_balance: '63106.63',  pending_claims_liability: '0',        available_to_cover: '63106.63',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '0ef642e6-eded-4271-8179-cd434fd94120', group_name: 'Employer Group 11', funded_balance: '64633.32',  pending_claims_liability: '32666.89', available_to_cover: '64633.32',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '27f804fa-69af-4eaa-9763-18238fcdc7c8', group_name: 'Employer Group 18', funded_balance: '68988.77',  pending_claims_liability: '25006.59', available_to_cover: '68988.77',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: 'f7a44ca3-d575-4929-8575-5e46421a9727', group_name: 'Employer Group 22', funded_balance: '72957.08',  pending_claims_liability: '0',        available_to_cover: '72957.08',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '7a314f89-5730-43ef-ac79-19f40f02edb4', group_name: 'Employer Group 5',  funded_balance: '76559.89',  pending_claims_liability: '0',        available_to_cover: '76559.89',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '13f5bcd3-8e91-426c-b708-b0bd4ed6c6e5', group_name: 'Employer Group 25', funded_balance: '78247.62',  pending_claims_liability: '0',        available_to_cover: '78247.62',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '4c84f889-182a-4a06-8be3-d552d031060a', group_name: 'Employer Group 13', funded_balance: '79335.78',  pending_claims_liability: '0',        available_to_cover: '79335.78',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '9c5f37a8-d80c-49f1-8d8a-268da32ff85a', group_name: 'Employer Group 15', funded_balance: '79962.52',  pending_claims_liability: '0',        available_to_cover: '79962.52',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: 'd2fa8ade-38b2-4d7c-b809-bd18ef07dd5a', group_name: 'Employer Group 1',  funded_balance: '91880.13',  pending_claims_liability: '0',        available_to_cover: '91880.13',  coverage_status: 'healthy',   member_count: 320 },
    { group_id: '321b4ee1-ccf9-4a1a-aec4-94eb5ffbe331', group_name: 'Employer Group 23', funded_balance: '97608.70',  pending_claims_liability: '0',        available_to_cover: '97608.70',  coverage_status: 'healthy',   member_count: 320 },
  ],
};

export const MOCK_GROUP_DETAIL: GroupPositionDetail = {
  group_id: '28766725-64af-40e1-b625-a648866a7f1c',
  group_name: 'Employer Group 19',
  funded_balance: '-262587.59',
  pending_claims_liability: '60254.11',
  available_to_cover: '-262587.59',
  coverage_status: 'shortfall',
  member_count: 320,
  cleared_entries: [
    { id: 'demo-0001', entry_type: 'claim_payment',    direction: 'debit',  amount: '3841.22', expected_date: '2026-06-10', reference: 'demo-claim-001', counterparty: 'Riverside Medical', status: 'expected' },
    { id: 'demo-0002', entry_type: 'claim_payment',    direction: 'debit',  amount: '1207.50', expected_date: '2026-06-08', reference: 'demo-claim-002', counterparty: 'Valley Orthopedics', status: 'expected' },
    { id: 'demo-0003', entry_type: 'claim_payment',    direction: 'debit',  amount: '9512.88', expected_date: '2026-06-05', reference: 'demo-claim-003', counterparty: 'St. Luke Hospital', status: 'expected' },
    { id: 'demo-0004', entry_type: 'admin_fee',        direction: 'credit', amount: '5744.61', expected_date: '2026-06-01', reference: 'admin_fee_19_2026_06', counterparty: 'Employer Group 19', status: 'expected' },
    { id: 'demo-0005', entry_type: 'stop_loss_premium',direction: 'debit',  amount: '7305.72', expected_date: '2026-06-02', reference: 'sl_prem_19_2026_06', counterparty: 'Coverage Partners', status: 'expected' },
  ],
  pending_entries: [
    { id: 'demo-p001', entry_type: 'claim_payment', direction: 'debit', amount: '18430.55', expected_date: '2026-06-14', reference: 'demo-batch-pend-01', counterparty: 'Summit Health', status: 'expected' },
    { id: 'demo-p002', entry_type: 'claim_payment', direction: 'debit', amount: '24150.88', expected_date: '2026-06-11', reference: 'demo-batch-pend-02', counterparty: 'Cascade Pharmacy', status: 'expected' },
    { id: 'demo-p003', entry_type: 'claim_payment', direction: 'debit', amount: '17672.68', expected_date: '2026-06-07', reference: 'demo-batch-pend-03', counterparty: 'Metro Urgent Care', status: 'expected' },
  ],
};

// ── Client-side filter/sort/paginate for mock list ───────────────────────────

export function filterMockExceptions(
  items: ExceptionSummary[],
  params: {
    match_type?: string;
    status?: string[];
    sort?: string;
    amount_min?: string;
    amount_max?: string;
    page?: number;
    page_size?: number;
  },
): { items: ExceptionSummary[]; total: number; page: number; page_size: number } {
  let filtered = [...items];

  if (params.status && params.status.length > 0) {
    filtered = filtered.filter(e => params.status!.includes(e.status));
  } else {
    filtered = filtered.filter(e => ['needs_review', 'flagged', 'partially_resolved'].includes(e.status));
  }

  if (params.match_type) {
    filtered = filtered.filter(e => e.match_type === params.match_type);
  }
  if (params.amount_min) {
    const min = parseFloat(params.amount_min);
    filtered = filtered.filter(e => parseFloat(e.amount) >= min);
  }
  if (params.amount_max) {
    const max = parseFloat(params.amount_max);
    filtered = filtered.filter(e => parseFloat(e.amount) <= max);
  }

  if (params.sort === 'amount_desc') {
    filtered.sort((a, b) => parseFloat(b.amount) - parseFloat(a.amount));
  } else if (params.sort === 'date_asc') {
    filtered.sort((a, b) => a.posted_date.localeCompare(b.posted_date));
  } else {
    // confidence_asc — null confidence sorts first (worst)
    filtered.sort((a, b) => {
      const ca = a.confidence == null ? -1 : parseFloat(a.confidence);
      const cb = b.confidence == null ? -1 : parseFloat(b.confidence);
      return ca - cb;
    });
  }

  const page = params.page ?? 1;
  const page_size = params.page_size ?? 20;
  const total = filtered.length;
  const start = (page - 1) * page_size;
  return { items: filtered.slice(start, start + page_size), total, page, page_size };
}
