# Tieout Data Model (Step 1)

## Overview

Tieout is a payment reconciliation engine for self-funded health plans. This document describes the Step 1 data foundation: the domain model, table schema, exception taxonomy, and ground truth recording mechanism.

The system ingests two records of money movement:
- **LEDGER (Book)**: What the books say should have moved (`ledger_entry`)
- **BANK (Actual)**: What actually posted to the bank (`bank_event`)

The reconciliation engine matches these two sides and surfaces exceptions to humans. **Step 1 focuses only on the data foundation and synthetic data generation; the matching engine is Step 2.**

---

## Domain Concepts

### Employer Groups
Self-funded employers that hold money in clearing accounts managed by Yuzu (a fiduciary). Each group has:
- A PEPM (per-employee-per-month) admin fee rate
- An optional stop-loss carrier
- A funding bank account (clearing account) where money is deposited

### Members
Employees enrolled in a plan. Used to calculate active headcount for monthly admin fee (PEPM rate × active members that month).

### Bank Accounts
Pooled clearing and operating accounts. Employer funding and claim payments flow through clearing; admin fees and stop-loss flows go through operating.

### Claims
Health insurance claims from members. Only **PAID** claims are batched for ACH transmission.

### Payment Batches
20–50 paid claims grouped into a single ACH transmission from the clearing account. Each batch produces **one outbound bank event** — the source of the `many_to_one` exception type.

**Constraint**: `total_amount` must equal `SUM(claim.paid_amount)` for all claims in the batch.

### Ledger Entries
Book entries (expected movements). Entry types generated:

| entry_type | Direction | Description |
|---|---|---|
| `employer_funding` | CREDIT | Employer wires money to cover paid claims |
| `claim_payment` | DEBIT | One entry per paid claim (reference = claim.id) |
| `admin_fee` | CREDIT | PEPM rate × active members, billed monthly to employer |
| `stop_loss_premium` | DEBIT | Monthly premium paid to stop-loss carrier |
| `stop_loss_reimbursement` | CREDIT | Carrier reimburses Yuzu for large claims |

- **direction**: DEBIT (outflow) or CREDIT (inflow) from Yuzu's perspective
- **status**: EXPECTED (not yet posted) or CLEARED (matched to bank event)
- **reference**: claim.id for claim_payments; invoice ID for admin/stop-loss

### Bank Events
Actual postings to the bank statement. Descriptors are messy and abbreviated (raw bank memos). Every bank event must have at least one `ground_truth_link`.

### Ground Truth Link
**The key evaluation table**: Records the TRUE mapping between bank events and ledger entries, including what exception type applies.

| Scenario | bank_event_id | ledger_entry_id | exception_type |
|---|---|---|---|
| Normal 1:1 match | set | set | `clean` |
| Late posting | set | set | `timing` |
| Batch covers N claims | set (×1) | set (×N) | `many_to_one` |
| One entry → 2 partial posts | set (×2) | set (same) | `one_to_many` |
| Pay / return / reissue | set (×3) | set (same) | `reversal` |
| Wrong amount wired | set | set | `short_over_funding` |
| Unreadable descriptor | set | set | `unreferenced_inbound` |
| Fee/noise with no ledger entry | set | **NULL** | `bank_only_noise` |

---

## Schema

### employer_group
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | VARCHAR(255) | Unique |
| plan_type | ENUM | `ppo`, `hmo`, `hdhp` |
| status | ENUM | `active`, `inactive`, `suspended` |
| pepm_rate | NUMERIC(10,2) | Admin fee per employee per month |
| stop_loss_carrier | VARCHAR(255) | Nullable |
| funding_bank_account_id | UUID | FK → bank_account |

---

### member
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| group_id | UUID | FK → employer_group |
| name | VARCHAR(255) | |
| enrollment_start | DATE | |
| enrollment_end | DATE | NULL if still enrolled |

---

### bank_account
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| name | VARCHAR(255) | Unique |
| type | ENUM | `clearing`, `operating` |
| institution | VARCHAR(255) | Bank name |

---

### claim
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| group_id | UUID | FK → employer_group |
| member_id | UUID | FK → member |
| provider_name | VARCHAR(255) | |
| claim_date | DATE | Date submitted |
| paid_date | DATE | NULL if pending |
| billed_amount | NUMERIC(12,2) | |
| allowed_amount | NUMERIC(12,2) | |
| paid_amount | NUMERIC(12,2) | |
| status | ENUM | `pending`, `paid`, `voided`, `reissued` |
| payment_batch_id | UUID | FK → payment_batch (NULL until batched) |

---

### payment_batch
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| batch_date | DATE | ACH transmission date |
| bank_account_id | UUID | FK → bank_account |
| total_amount | NUMERIC(12,2) | Must equal SUM of claim.paid_amount for batch |

---

### ledger_entry
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| group_id | UUID | FK → employer_group (nullable for noise entries) |
| bank_account_id | UUID | FK → bank_account |
| entry_type | ENUM | `employer_funding`, `claim_payment`, `admin_fee`, `stop_loss_premium`, `stop_loss_reimbursement`, `card_load`, `card_settlement`, `ach_return`, `bank_fee`, `interest` |
| direction | ENUM | `debit`, `credit` |
| amount | NUMERIC(12,2) | |
| expected_date | DATE | When this should post |
| reference | VARCHAR(255) | claim.id for claim_payments; invoice ID for others |
| counterparty | VARCHAR(255) | |
| source_artifact | VARCHAR(255) | `835`, `820` |
| status | ENUM | `expected`, `cleared` |

---

### bank_event
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| bank_account_id | UUID | FK → bank_account |
| posted_date | DATE | |
| amount | NUMERIC(12,2) | |
| direction | ENUM | `debit`, `credit` |
| descriptor | VARCHAR(255) | Raw bank memo (messy) |
| bank_reference | VARCHAR(255) | ACH trace number etc. |

**Constraint**: Every bank_event must have ≥1 ground_truth_link.

---

### ground_truth_link
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| bank_event_id | UUID | FK → bank_event (NOT NULL) |
| ledger_entry_id | UUID | FK → ledger_entry (**NULLABLE** — NULL for bank_only_noise) |
| exception_type | ENUM | See Exception Taxonomy |
| created_at | TIMESTAMPTZ | |

---

### reconciliation_match *(empty in Step 1)*
Populated by the Step 2 matching engine.

| Column | Type | Notes |
|---|---|---|
| id | UUID | |
| bank_event_id | UUID | FK → bank_event |
| match_type | VARCHAR(255) | Populated by matcher |
| confidence | NUMERIC(5,4) | 0.0–1.0 |
| status | ENUM | `pending`, `matched`, `reviewed`, `resolved` |
| resolved_by | VARCHAR(255) | |
| resolved_at | TIMESTAMPTZ | |
| notes | VARCHAR(1024) | |

---

### match_ledger_entry *(empty in Step 1)*
Join table: `reconciliation_match` ↔ `ledger_entry` (many-to-many).

---

### audit_log
| Column | Type | Notes |
|---|---|---|
| id | UUID | |
| actor | VARCHAR(255) | |
| action | VARCHAR(255) | |
| entity_type | VARCHAR(255) | |
| entity_id | UUID | |
| payload | JSONB | |
| created_at | TIMESTAMPTZ | |

---

## Exception Taxonomy

Proportions below are **by count of bank events**, not ledger entries.

### clean (30% target)
1:1 match, same amount, posted 0–3 days after expected_date.

```
Ledger:  CREDIT $50,000  expected 2026-06-01
Bank:    CREDIT $50,000  posted   2026-06-02
→ ground_truth_link: exception_type = clean
```

### timing (5% target)
1:1 match but bank posts 5–14 days late.

```
Ledger:  CREDIT $50,000  expected 2026-06-01
Bank:    CREDIT $50,000  posted   2026-06-10
```

### many_to_one (40% target — structural)
One payment batch covers N claim_payment ledger entries. Generated structurally: every payment batch becomes exactly one outbound bank event whose amount equals the sum of its entries.

```
Ledger:  DEBIT $450  (claim A)
         DEBIT $780  (claim B)
         DEBIT $320  (claim C)   ...32 claims total...
Bank:    DEBIT $63,670  "ACH BATCH 000082 32 CLMS"
→ 32 ground_truth_links, all many_to_one, all pointing to that one bank event
```

### one_to_many (5% target)
One expected ledger entry arrives as two partial bank events (60% + 40%).

```
Ledger:  CREDIT $10,000
Bank:    CREDIT $6,000  (partial 1)
         CREDIT $4,000  (partial 2)
```

### reversal (5% target)
Claim paid, then ACH return, then reissued. All three bank events link to the same ledger entry.

```
Ledger:  DEBIT $500
Bank:    DEBIT  $500  2026-06-01  "PMT Provider"
         CREDIT $500  2026-06-04  "ACH RTN Provider"
         DEBIT  $500  2026-06-06  "REISSUE Provider"
→ 3 ground_truth_links, all pointing to the same ledger_entry
```

### short_over_funding (5% target)
Employer wires a rounded amount (±5% variance).

```
Ledger:  CREDIT $10,000.00
Bank:    CREDIT $10,250.00
```

### unreferenced_inbound (5% target)
Bank event exists and links to a ledger entry but the descriptor is too garbled to match by text.

```
Ledger:  CREDIT $15,000  (stop_loss_reimbursement, counterparty="StopLoss Inc.")
Bank:    CREDIT $15,000  "ACH CREDIT XYZ CORP REF87654321 CO4892"
```

### bank_only_noise (5% target)
Bank event with **no corresponding ledger entry**: fees, interest, misc charges.

```
Ledger:  [nothing]
Bank:    DEBIT $47  "BANK SVC CHG 412"
→ ground_truth_link: ledger_entry_id = NULL
```

---

## Synthetic Data Generation

### Scale (seed=42 defaults)
| Table | Count |
|---|---|
| employer_group | 25 |
| member | 8,000 |
| claim | ~3,061 |
| payment_batch | ~87 |
| ledger_entry | ~2,950 |
| bank_event | ~343 |
| ground_truth_link | ~3,012 |

### Configuration (`backend/config.py`)

| Variable | Default | Purpose |
|---|---|---|
| `SEED` | 42 | RNG seed — same seed → identical data |
| `NUM_GROUPS` | 25 | Employer groups |
| `NUM_MEMBERS` | 8000 | Total members |
| `NUM_DAYS` | 90 | Days of activity (~3 months) |
| `EXCEPTION_FLOOR` | 10 | Min bank events per non-clean exception type |
| `STOP_LOSS_REIMB_PROB` | 0.15 | Probability of reimbursement per group-month |
| `EXCEPTION_MIX_*` | See `.env.example` | Target proportions by bank event count |

### Generator logic
1. Create bank accounts (2–4 clearing, 1–3 operating)
2. Create employer groups with PEPM rates and optional stop-loss carriers
3. Distribute 8k members across groups
4. Generate 50–200 claims per group; batch PAID claims into groups of 20–50
5. Generate ledger entries:
   - One `employer_funding` per group
   - One `claim_payment` per paid claim (reference = claim.id)
   - One `admin_fee` per group per month
   - One `stop_loss_premium` per group-with-carrier per month
   - Probabilistic `stop_loss_reimbursement` per group-with-carrier per month
6. Generate bank events:
   - **Structural**: one bank event per batch → `many_to_one` (dominant)
   - **Exception pool**: all non-claim entries assigned exception types with guaranteed floor

---

## Sanity Checks (`make summary`)

1. **Batch totals**: `payment_batch.total_amount == SUM(claim.paid_amount)` for every batch
2. **Ground truth completeness**: Every `bank_event` has ≥1 `ground_truth_link`
3. **Noise validation**: All `bank_only_noise` links have `ledger_entry_id = NULL`

---

## Key Design Decisions

1. **UUID PKs** — avoids id-space confusion across tables
2. **DECIMAL(12,2) for all money** — exact arithmetic, no float errors
3. **Nullable `ledger_entry_id`** in `ground_truth_link` — cleanly models bank-only noise
4. **Lowercase enum values** — `values_callable` on every SQLAlchemy `Enum` so Python values match raw SQL strings
5. **Synchronous SQLAlchemy 2.0** — batch jobs don't need async
6. **Drop-and-recreate seed** — idempotent, fast, safe for dev
7. **many_to_one is structural** — every batch is inherently many-to-one; the random exception pool handles only non-claim entries

---

## File References

| File | Purpose |
|---|---|
| `backend/config.py` | All configuration knobs |
| `backend/db/models.py` | ORM model definitions (11 tables) |
| `backend/db/connection.py` | SQLAlchemy engine and session |
| `backend/seed/generator.py` | Synthetic data generator |
| `backend/scripts/init_db.py` | `make seed` — drop/create/populate |
| `backend/scripts/summary.py` | `make summary` — stats and sanity checks |
| `tests/test_step1.py` | Pytest suite (9 tests) |
