# Tieout — Payment Reconciliation Engine

Tieout is a payment reconciliation engine for self-funded health-plan TPAs. It ingests two records of money movement — the **ledger** (what the books say should have moved) and the **bank statement** (what actually posted) — matches them automatically, and routes only genuine exceptions to a human reviewer. It also exposes a **cash-position surface** that computes each employer group's available balance and pending claims liability directly from the reconciled ledger — no separate balance system.

The industry runs on Excel macros. Tieout is the bank-rec macro productized: a working prototype with measurable precision/recall, a human-exception workflow, and a second surface that answers "can this group cover its incoming claims" from the same data. It is not a production system.

---

## Reconciliation Scorecard (seed=42)

Measured against seeded ground truth — the engine never reads `ground_truth_link` during matching; the scorecard is computed afterwards by comparing engine output to the true labels. That separation is what makes the numbers credible.

| Metric | Value |
|--------|-------|
| Precision | 99.8% |
| Recall | 98.4% |
| F1 | 99.1% |
| Auto-matched (confidence ≥ 0.80) | 235 / 345 events — **68.1%** |
| Routed to human review | 110 / 345 events — 31.9% |

Dataset: 345 bank events against ~3,000 ledger entries across 25 employer groups, 90 days of activity.

### Per-exception-type breakdown

| Exception | Events | Recall | Auto-cleared | Review | Notes |
|-----------|--------|--------|-------------|--------|-------|
| `clean` | 75 | 100% | 75 | 0 | Exact amount + reference in descriptor + date ≤ 3 days |
| `many_to_one` | 87 | 100% | 87 | 0 | Reference-anchored batch sum; ~32 claim payments per batch |
| `one_to_many` | 38 | 100% | 38 | 0 | Two partial bank events sum to one ledger entry |
| `unreferenced_inbound` | 20 | 100% | 20 | 0 | Scored above threshold on amount+date alone |
| `timing` | 19 | 89.5% | 0 | 19 | Amount + counterparty match; 5–14 day lag; 2 missed |
| `short_over_funding` | 18 | 83.3% | 0 | 18 | ±5% amount variance; human confirms wire vs. error |
| `reversal` | 66 | 33.3% | 22 | 44 | Original "PMT" leg auto-clears; return + reissue legs quarantined — see Known Limitations |
| `bank_only_noise` | 22 | n/a | 0 | 22 | No ledger counterpart; correctly left unmatched |

---

## Two Surfaces, One Ledger

Tieout exposes two views off the same reconciled data.

**Reconciliation queue** (`/queue`): bank events matched against ledger entries. Every match gets a confidence score; anything below 0.80 routes to a human reviewer who can accept, manually match, split, write off, flag, or reopen. Every action writes an audit trail. Ops additions:

- **Employer-group filter** — scope the table to one group's exceptions; integrates with the cash-position drill-down so clicking a shortfall group navigates directly to its open exceptions
- **Stale high-value alert** — amber banner fires when any open exception is ≥ $50,000 and has been open ≥ 14 days
- **CSV export** — downloads the current filtered view (up to 1,000 rows) as `tieout-exceptions-YYYY-MM-DD.csv`

**Cash position** (`/cash-position`): per-group balance and coverage status derived from the same reconciled ledger. A group's funded balance is the net of bank-*confirmed* credits (employer_funding, stop_loss_reimbursement, admin_fee) minus cleared debits (claim_payment, stop_loss_premium). Pending claims liability is the sum of adjudicated claim_payment entries whose ACH batch has not yet settled — money owed but not yet bank-confirmed. In the seeded data, employer_funding is set at 125% of regular claims (the prefunded buffer), so healthy groups carry a positive funded balance; a shortfall means pending liability exceeds that available balance.

This is good system design because the two surfaces share a single source of truth. "Cleared" means the same thing in both: a ledger entry linked to a reconciliation_match with status in `{matched, resolved, partially_resolved}`. There is no parallel balance system to drift out of sync.

---

## Architecture and Data Flow

```
make seed
  └── generator.py
        ├── Structural tables: bank_account, employer_group, member, claim, payment_batch
        ├── ground_truth_link with natural refs (bank_reference, ledger_natural_ref)
        └── Raw artifact files → data/raw/
              ├── 835_remittance.json    (one row per paid claim)
              ├── 820_premium.json       (employer funding, admin fees, stop-loss)
              └── bank_transactions.csv  (bank statement rows)

make ingest
  └── ingest/pipeline.py
        ├── Parses all three artifact files
        ├── Writes ledger_entry  (fresh UUIDs; deduped by reference)
        ├── Writes bank_event    (fresh UUIDs; deduped by bank_reference)
        └── Resolves ground_truth_link natural refs → freshly-minted UUIDs

make match
  └── match/engine.py — 6-stage cascade (clears and rebuilds on each run)
        1. Many-to-one   — reference-anchored batch sum for claim payment batches
        2. Exact 1:1     — reference in descriptor → 1.0; amount+date only → 0.95
        3. One-to-many   — two partial events summing to one ledger entry
        4. Reversal      — 3-leg pattern (pay / ACH RTN / reissue)
        5. Fuzzy 1:1     — weighted score: amount (45%) + date (35%) + text (20%)
        6. Leftovers     — unmatched bank events → needs_review

make evaluate
  └── scripts/evaluate.py — scores engine output against ground_truth_link
```

Ingest never reads `ground_truth_link`. The matcher never reads it. Only `evaluate` reads it, strictly after the fact.

### Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.13 |
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (sync) |
| Schema | Pydantic v2 |
| Database | PostgreSQL 15 (Docker, port 5433) |
| Tests | pytest |
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS |
| Data fetching | TanStack Query |
| Animations | Framer Motion |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker Desktop

### Setup

```bash
# 1. Copy and configure environment
copy .env.example .env

# 2. Create venv and install deps
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Start Postgres (port 5433)
make up

# 4. Full pipeline
make seed       # DROP & recreate, generate data, run ingest
make match      # run matching engine
make evaluate   # print scorecard
```

On Windows without make, run directly:

```powershell
$env:PYTHONPATH = "."
.venv\Scripts\python backend/scripts/init_db.py   # seed
.venv\Scripts\python backend/scripts/match.py      # match
.venv\Scripts\python backend/scripts/evaluate.py   # evaluate
```

### Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173
```

The frontend checks `GET /health`; if the backend is unreachable it falls back to a snapshot of real data so the UI can be demoed without a running database.

### Make targets

```
make up           Start Postgres container (localhost:5433)
make down         Stop container
make seed         DROP & recreate schema, generate data, ingest  [DESTRUCTIVE]
make ingest       Re-run ingest only — idempotent, no drop
make match        Run matching engine — clears and rebuilds reconciliation_match
make evaluate     Print precision/recall scorecard vs ground_truth_link
make summary      Row counts, dollar totals, per-group cash positions
make test         Run pytest suite (86 tests across all steps, ~3 min)
```

---

## Engineering Notes

**Money is never a float.** All amounts are `NUMERIC(12,2)` in Postgres and `Decimal` in Python across the entire stack — generator, artifact files, ingest, matcher, evaluator, cash-position service, API responses. There is no cast to float anywhere in the path.

**UUID PKs everywhere.** The ingest pipeline mints its own UUIDs for `ledger_entry` and `bank_event`; it never receives IDs from the generator. `ground_truth_link` is resolved by joining on natural keys after the fact, with no FK constraints on the UUID columns.

**Idempotent ingest and matcher.** Re-running `make ingest` produces zero new rows. Re-running `make match` clears and rebuilds all `reconciliation_match` and `match_ledger_entry` rows, then commits once. Both are safe to run multiple times.

**Bulk-insert seed.** Row-at-a-time insertion took 30–50 seconds; converting to `bulk_save_objects` brought it to a few seconds with identical row counts and dollar totals confirmed by the test suite.

**Cash position is derived, not stored.** Funded balance and pending liability are computed on-request from the `match_ledger_entry` join. The `ledger_entry.status` column (expected/cleared) is not updated by the match engine; clearance is inferred from reconciliation_match status. This means the cash position is always consistent with the latest reconciliation run.

**`source_artifact` is consistently `835` or `820`** on every `ledger_entry` row, reflecting which artifact file the row came from.

**Full audit trail.** Every operator action (accept, match, split, write-off, flag, reopen) writes a structured `audit_log` row with before/after status and the actor identity. The exception detail drawer shows the full timeline.

**91 tests** across six steps, covering: batch-total money conservation, idempotent ingest, round-trip dollar totals, ground-truth resolution, all six match stages, operator resolution workflow, cash-position math (healthy/watch/shortfall), partially_resolved edge case (no double-count), Decimal precision, and an amount-collision anti-test that proves two batches with the same sum and close dates are not cross-matched when trace references differ.

---

## Known Limitations

**Reversals (deliberate simplification).** The generator models a reversal as a single net economic event: one ledger entry (the original obligation) with three bank events (original payment, ACH return, reissue). The matching engine handles the original "PMT" leg via the exact stage (confidence 0.95). Once that ledger entry is consumed, the return and reissue legs have nothing left to match against — the engine explicitly blocks them from fuzzy-matching unrelated entries, so they fall cleanly to needs_review. Per-type recall is 33%. First-class 3-leg reversal matching would require the schema to support 1-ledger→N-bank cardinality in `match_ledger_entry` (currently N-ledger→1-bank). Scoped as future work.

**Synthetic structured artifacts, not true EDI.** The "835" and "820" files are structured JSON shaped like EDI transactions, not actual X12 837/835/820 files. The engine's quality was prioritized over parser fidelity. A production system would need a spec-compliant EDI parser (or a clearinghouse-provided normalized feed).

---

## Assumptions I'd Validate with a Real TPA

**Bank file format.** The engine ingests a flat CSV. Real clearing banks deliver BAI2 or SWIFT MT940 files with structured transaction codes and multi-line memo fields. The descriptor-parsing and fuzzy-text approach may be unnecessary once structured transaction-type codes are available.

**Batch reference conventions.** The many-to-one stage works because the generator embeds the same counter in `bank_reference` (`trace_XXXXXX`) and the descriptor (`ACH BATCH XXXXXX`). Real ACH trace numbers follow NACHA format (18-digit, institution-prefixed) and may appear only partially in bank memo fields, or not at all. The reference-anchor logic needs to be adapted to whatever the specific clearing bank puts in the transaction detail.

**Stop-loss reimbursement references.** The prototype fuzzy-matches stop-loss reimbursements on counterparty name and amount. In practice, carrier reimbursement wires typically reference specific claim numbers or an aggregate loss report. Knowing that format would turn unreferenced fuzzy matches into clean exact matches, improving recall on reimbursements substantially.

**Tolerance windows for short/over-funding.** The ±8% amount tolerance and 21-day date window in the fuzzy stage are defaults, not derived from any real contract. Actual TPAs have contractual wire tolerances (often ±1–2%) and specific settlement calendars. Tighter windows reduce false-positive surface area; confirming the real tolerance values is the single highest-leverage improvement available without changing the engine architecture.

**PEPM proration with mid-month enrollment changes.** The prototype computes admin fees as a flat PEPM rate against current member count. Real billing cycles prorate for members who enroll or terminate mid-month. The funded_balance calculation would need to account for partial-month proration to be accurate for groups with high turnover.

**Cash-position sign convention.** The ledger is recorded from the TPA's perspective: `employer_funding` and `admin_fee` are credits (money received); `claim_payment` and `stop_loss_premium` are debits (money disbursed). If the client's GL records these from the plan's perspective instead, the signs would reverse. Confirming whose ledger this is — TPA or plan — is the first validation step before deploying the cash-position surface.

**Regulatory and audit retention requirements.** The `audit_log` table records every operator action but has no retention policy, archival schedule, or immutability guarantee. A production deployment would need to know how long the TPA is required to retain reconciliation records (ERISA audit trails are typically 6 years) and whether the audit log needs to be tamper-evident.

---

## Database Access

```
Host:     localhost
Port:     5433
Database: tieout
User:     tieout_user
Password: tieout_password
```

Enum columns store lowercase values (`clean`, `reversal`, `many_to_one`, etc.).
