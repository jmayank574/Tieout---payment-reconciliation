"""
Synthetic data generator for Tieout.

Stage 1-2: Writes structural data to DB — bank_account, employer_group, member,
           claim, payment_batch.
Stage 3:   Builds ledger record dicts (NOT written to DB) — these become the
           835 and 820 artifact files that the ingest pipeline will parse.
Stage 4:   Builds bank event record dicts (NOT written to DB) and writes
           ground_truth_link rows with natural refs (bank_reference,
           ledger_natural_ref).  Bank event records become bank_transactions.csv.
Stage 5:   Writes artifact files via artifact_writer.

Ingest (run separately) parses the artifact files, mints its own UUIDs for
ledger_entry and bank_event, then resolves ground_truth_link's natural refs
to those freshly-minted UUIDs.
"""

import calendar
import random
from datetime import timedelta, date
from decimal import Decimal
from uuid import uuid4

from faker import Faker

from backend.config import (
    SEED, NUM_GROUPS, NUM_MEMBERS, NUM_DAYS, EXCEPTION_MIX, EXCEPTION_FLOOR,
    STOP_LOSS_PREMIUM_PEPM_MIN, STOP_LOSS_PREMIUM_PEPM_MAX, STOP_LOSS_REIMB_PROB,
    DATA_DIR,
)

# Employer funding is seeded at this multiple of the group's regular claims total.
# The surplus (buffer above 1.0) makes funded_balance positive for healthy groups.
_EMPLOYER_FUNDING_BUFFER = Decimal("1.25")

# Per-group pending claim fractions (fraction of regular claim volume).
# 15 groups get no pending (healthy), 5 get a small pending (healthy),
# 3 get a moderate pending targeting watch, 2 get a large pending targeting shortfall.
# Must have exactly NUM_GROUPS (25) entries.
_PENDING_FRACS = (
    [Decimal("0")] * 15
    + [Decimal("0.10")] * 5
    + [Decimal("0.22")] * 3
    + [Decimal("0.38")] * 2
)
from backend.db.connection import SessionLocal
from backend.db.models import (
    BankAccount, BankAccountType,
    Claim, ClaimStatus,
    Direction,
    EmployerGroup, ExceptionType,
    GroundTruthLink,
    GroupStatus,
    Member,
    PaymentBatch, PlanType,
)
from backend.seed.artifact_writer import write_artifacts


class DataGenerator:
    """Generate synthetic Tieout data with a fully reproducible seed."""

    def __init__(self, seed: int = SEED):
        self.seed = seed
        self.rng = random.Random(seed)
        self.fake = Faker()
        Faker.seed(seed)
        self.session = SessionLocal()

        # DB-persisted objects
        self.created_objects: dict = {
            "groups": [], "members": [], "accounts": [],
            "claims": [], "batches": [], "ground_truth_links": [],
        }

        # In-memory artifact records (not written to DB; go to artifact files)
        self._835_records: list[dict] = []
        self._820_records: list[dict] = []
        self._bank_records: list[dict] = []

        # Queued GroundTruthLink objects — bulk-inserted at end of _generate_bank_records_and_gtl
        self._pending_gtls: list = []

        # batch_id (pre-generated UUID) -> group_id
        self._batch_group_id: dict = {}
        # batch_id -> list[dict] of 835 records for claims in that batch
        self._batch_claim_835_map: dict = {}
        # batch IDs that intentionally have no bank event (pending liability)
        self._pending_batch_ids: set = set()

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    def generate_all(self) -> dict:
        try:
            self._generate_bank_accounts()
            self._generate_employer_groups()
            self._generate_members()
            self._generate_claims_and_payments()
            self._generate_ledger_records()
            self._generate_bank_records_and_gtl()
            write_artifacts(self._835_records, self._820_records, self._bank_records, DATA_DIR)
            self.session.commit()
            result = dict(self.created_objects)
            result["records_835"] = self._835_records
            result["records_820"] = self._820_records
            result["bank_records"] = self._bank_records
            return result
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.close()

    # ------------------------------------------------------------------ #
    # Stage 1 – reference data                                            #
    # ------------------------------------------------------------------ #

    def _generate_bank_accounts(self):
        institutions = ["Chase", "Bank of America", "Wells Fargo", "Citibank"]
        accounts = []
        for i in range(self.rng.randint(2, 4)):
            accounts.append(BankAccount(
                name=f"Clearing Account {i+1}",
                type=BankAccountType.CLEARING,
                institution=self.rng.choice(institutions),
            ))
        for i in range(self.rng.randint(1, 3)):
            accounts.append(BankAccount(
                name=f"Operating Account {i+1}",
                type=BankAccountType.OPERATING,
                institution=self.rng.choice(institutions),
            ))
        self.session.bulk_save_objects(accounts, return_defaults=True)
        self.session.flush()
        self.created_objects["accounts"].extend(accounts)

    def _generate_employer_groups(self):
        plan_types = [PlanType.PPO, PlanType.HMO, PlanType.HDHP]
        carriers = ["StopLoss Inc.", "Risk Management Corp.", "Coverage Partners"]
        funding_acct = next(
            a for a in self.created_objects["accounts"]
            if a.type == BankAccountType.CLEARING
        )
        groups = []
        for i in range(NUM_GROUPS):
            groups.append(EmployerGroup(
                name=f"Employer Group {i+1}",
                plan_type=self.rng.choice(plan_types),
                status=GroupStatus.ACTIVE if self.rng.random() > 0.1 else GroupStatus.INACTIVE,
                pepm_rate=Decimal(str(round(self.rng.uniform(8, 25), 2))),
                stop_loss_carrier=self.rng.choice(carriers) if self.rng.random() > 0.3 else None,
                funding_bank_account_id=funding_acct.id,
            ))
        self.session.bulk_save_objects(groups, return_defaults=True)
        self.session.flush()
        self.created_objects["groups"].extend(groups)

    def _generate_members(self):
        start = date.today() - timedelta(days=365)
        per_group = NUM_MEMBERS // NUM_GROUPS
        members = []
        for group in self.created_objects["groups"]:
            for _ in range(per_group):
                enroll_start = start + timedelta(days=self.rng.randint(0, 200))
                enroll_end = None
                if self.rng.random() < 0.2:
                    enroll_end = enroll_start + timedelta(days=self.rng.randint(30, 365))
                members.append(Member(
                    group_id=group.id,
                    name=self.fake.name(),
                    enrollment_start=enroll_start,
                    enrollment_end=enroll_end,
                ))
        self.session.bulk_save_objects(members, return_defaults=True)
        self.session.flush()
        self.created_objects["members"].extend(members)

    # ------------------------------------------------------------------ #
    # Stage 2 – claims and payment batches                                #
    # ------------------------------------------------------------------ #

    def _generate_claims_and_payments(self):
        today = date.today()
        start_date = today - timedelta(days=NUM_DAYS)
        clearing = self._clearing_account()

        # Build all claims in memory first (pre-set UUID so batch assignment works before DB write)
        claims = []
        for group in self.created_objects["groups"]:
            group_members = [m for m in self.created_objects["members"]
                             if m.group_id == group.id]
            if not group_members:
                continue
            for _ in range(self.rng.randint(50, 200)):
                claim_date = start_date + timedelta(days=self.rng.randint(0, NUM_DAYS))
                member = self.rng.choice(group_members)
                billed = Decimal(str(round(self.rng.uniform(100, 5000), 2)))
                allowed = Decimal(str(round(
                    min(float(billed) * self.rng.uniform(0.8, 1.0), float(billed)), 2
                )))
                paid = Decimal(str(round(float(allowed) * self.rng.uniform(0.7, 1.0), 2)))
                is_paid = self.rng.random() > 0.1
                claims.append(Claim(
                    id=uuid4(),
                    group_id=group.id,
                    member_id=member.id,
                    provider_name=self.fake.company(),
                    claim_date=claim_date,
                    paid_date=claim_date + timedelta(days=self.rng.randint(1, 15)) if is_paid else None,
                    billed_amount=billed,
                    allowed_amount=allowed,
                    paid_amount=paid,
                    status=ClaimStatus.PAID if is_paid else ClaimStatus.PENDING,
                ))

        # Assign batch IDs in memory before any DB writes
        paid_claims = [c for c in claims if c.status == ClaimStatus.PAID]
        batch_size = self.rng.randint(20, 50)
        batches = []
        for i in range(0, len(paid_claims), batch_size):
            chunk = paid_claims[i:i + batch_size]
            batch_total = sum(c.paid_amount for c in chunk)
            batch_date = max(c.paid_date for c in chunk) + timedelta(days=self.rng.randint(0, 3))
            batch_id = uuid4()
            batch = PaymentBatch(
                id=batch_id,
                batch_date=batch_date,
                bank_account_id=clearing.id,
                total_amount=batch_total,
            )
            batches.append(batch)
            self._batch_group_id[batch_id] = chunk[0].group_id
            for claim in chunk:
                claim.payment_batch_id = batch_id

        # Single bulk write per table — payment_batch_id already set on claim objects
        self.session.bulk_save_objects(batches)
        self.session.bulk_save_objects(claims)
        self.session.flush()
        self.created_objects["claims"].extend(claims)
        self.created_objects["batches"].extend(batches)

        # ── Pending batches: adjudicated but not yet ACH-initiated ───────
        # Assign pending-claim fractions to groups using the seeded RNG so
        # the output is reproducible.  Each pending batch gets NO bank event;
        # its claim_payment LEs remain uncleared → pending_claims_liability.
        pending_fracs = list(_PENDING_FRACS)
        self.rng.shuffle(pending_fracs)

        pending_claims: list = []
        pending_batches: list = []
        for group, frac in zip(self.created_objects["groups"], pending_fracs):
            if frac == Decimal("0"):
                continue
            group_regular = [
                c for c in claims
                if c.group_id == group.id and c.status == ClaimStatus.PAID
            ]
            if not group_regular:
                continue
            regular_total = sum(c.paid_amount for c in group_regular)
            target = (regular_total * frac).quantize(Decimal("0.01"))

            # Build pending claims summing to ~target
            batch_claims: list = []
            accumulated = Decimal("0")
            group_members = [m for m in self.created_objects["members"]
                             if m.group_id == group.id]
            while accumulated < target * Decimal("0.95"):
                amount = Decimal(str(round(self.rng.uniform(100, 2500), 2)))
                if accumulated + amount > target * Decimal("1.10"):
                    break
                claim = Claim(
                    id=uuid4(),
                    group_id=group.id,
                    member_id=self.rng.choice(group_members).id,
                    provider_name=self.fake.company(),
                    claim_date=today - timedelta(days=self.rng.randint(1, 14)),
                    paid_date=today - timedelta(days=self.rng.randint(0, 7)),
                    billed_amount=amount,
                    allowed_amount=amount,
                    paid_amount=amount,
                    status=ClaimStatus.PAID,
                )
                batch_claims.append(claim)
                pending_claims.append(claim)
                accumulated += amount

            if not batch_claims:
                continue

            batch_total = sum(c.paid_amount for c in batch_claims)
            pb = PaymentBatch(
                id=uuid4(),
                batch_date=today - timedelta(days=self.rng.randint(0, 5)),
                bank_account_id=clearing.id,
                total_amount=batch_total,
            )
            pending_batches.append(pb)
            self._pending_batch_ids.add(pb.id)
            for c in batch_claims:
                c.payment_batch_id = pb.id

        if pending_claims:
            self.session.bulk_save_objects(pending_batches)
            self.session.bulk_save_objects(pending_claims)
            self.session.flush()
            self.created_objects["claims"].extend(pending_claims)
            self.created_objects["batches"].extend(pending_batches)

    # ------------------------------------------------------------------ #
    # Stage 3 – ledger records (artifact data, not DB rows)               #
    # ------------------------------------------------------------------ #

    def _generate_ledger_records(self):
        """
        Build 835 and 820 artifact record dicts.  Nothing is written to the DB here;
        ingest will parse these files and mint its own UUIDs.

        835 records: one per paid claim (claim_payment).
        820 records: employer_funding, admin_fee, stop_loss_premium, stop_loss_reimbursement.
        """
        today = date.today()
        start_date = today - timedelta(days=NUM_DAYS)
        months = self._month_range(start_date, today)
        clearing_id = str(self._clearing_account().id)
        operating_id = str(self._operating_account().id)

        # 835 — one per paid claim
        for claim in self.created_objects["claims"]:
            if claim.status != ClaimStatus.PAID:
                continue
            rec = {
                "claim_id": str(claim.id),          # natural key → ledger_entry.reference
                "group_id": str(claim.group_id),
                "payment_batch_id": str(claim.payment_batch_id),
                "provider_name": claim.provider_name,
                "paid_amount": str(claim.paid_amount),
                "paid_date": claim.paid_date.isoformat(),
                "bank_account_id": clearing_id,
            }
            self._835_records.append(rec)
            self._batch_claim_835_map.setdefault(claim.payment_batch_id, []).append(rec)

        # 820 — employer_funding (one per group with paid claims).
        # Uses only REGULAR (non-pending) claims and applies _EMPLOYER_FUNDING_BUFFER
        # so the cleared funded_balance is positive for healthy groups.
        for group in self.created_objects["groups"]:
            paid = [
                c for c in self.created_objects["claims"]
                if c.group_id == group.id
                and c.status == ClaimStatus.PAID
                and c.payment_batch_id not in self._pending_batch_ids
            ]
            if not paid:
                continue
            total = (sum(c.paid_amount for c in paid) * _EMPLOYER_FUNDING_BUFFER).quantize(Decimal("0.01"))
            row_ref = f"emp_fund_{group.id}"
            self._820_records.append({
                "row_ref": row_ref,
                "group_id": str(group.id),
                "entry_type": "employer_funding",
                "direction": "credit",
                "amount": str(total),
                "expected_date": (today - timedelta(days=self.rng.randint(1, 5))).isoformat(),
                "counterparty": group.name,
                "source_artifact": "820",
                "bank_account_id": clearing_id,
            })

        # 820 — admin_fee, stop_loss_premium, stop_loss_reimbursement
        for group in self.created_objects["groups"]:
            sl_pepm = Decimal(str(round(self.rng.uniform(
                float(STOP_LOSS_PREMIUM_PEPM_MIN),
                float(STOP_LOSS_PREMIUM_PEPM_MAX),
            ), 2))) if group.stop_loss_carrier else None

            for year, month in months:
                active = self._active_members(group.id, year, month)
                if active == 0:
                    continue

                fee_date = date(year, month, 1) + timedelta(days=self.rng.randint(1, 7))
                row_ref = f"admin_fee_{group.id}_{year}_{month:02d}"
                self._820_records.append({
                    "row_ref": row_ref,
                    "group_id": str(group.id),
                    "entry_type": "admin_fee",
                    "direction": "credit",
                    "amount": str((group.pepm_rate * Decimal(str(active))).quantize(Decimal("0.01"))),
                    "expected_date": fee_date.isoformat(),
                    "counterparty": group.name,
                    "source_artifact": "820",
                    "bank_account_id": operating_id,
                })

                if not group.stop_loss_carrier:
                    continue

                prem_date = date(year, month, 1) + timedelta(days=self.rng.randint(1, 5))
                row_ref = f"sl_prem_{group.id}_{year}_{month:02d}"
                self._820_records.append({
                    "row_ref": row_ref,
                    "group_id": str(group.id),
                    "entry_type": "stop_loss_premium",
                    "direction": "debit",
                    "amount": str((sl_pepm * Decimal(str(active))).quantize(Decimal("0.01"))),
                    "expected_date": prem_date.isoformat(),
                    "counterparty": group.stop_loss_carrier,
                    "source_artifact": "820",
                    "bank_account_id": operating_id,
                })

                if self.rng.random() < STOP_LOSS_REIMB_PROB:
                    reimb_date = date(year, month, self.rng.randint(10, 28))
                    row_ref = f"sl_reimb_{group.id}_{year}_{month:02d}"
                    self._820_records.append({
                        "row_ref": row_ref,
                        "group_id": str(group.id),
                        "entry_type": "stop_loss_reimbursement",
                        "direction": "credit",
                        "amount": str(round(self.rng.uniform(5000, 50000), 2)),
                        "expected_date": reimb_date.isoformat(),
                        "counterparty": group.stop_loss_carrier,
                        "source_artifact": "820",
                        "bank_account_id": operating_id,
                    })

    # ------------------------------------------------------------------ #
    # Stage 4 – bank event records and ground-truth links                 #
    # ------------------------------------------------------------------ #

    def _generate_bank_records_and_gtl(self):
        """
        Build bank event record dicts and write ground_truth_link rows with natural refs.

        Structural many_to_one: one bank record per payment batch.
        Exception pool: assigns types to all 820 records with a guaranteed floor.

        ground_truth_link is written to DB now (with bank_reference +
        ledger_natural_ref).  After ingest runs, the finalize step resolves
        those natural refs to the freshly-minted bank_event_id / ledger_entry_id.
        """
        clearing_id = str(self._clearing_account().id)
        operating_id = str(self._operating_account().id)
        counter = 0

        # ── Structural many_to_one: one bank event per regular payment batch ──
        # Pending batches (self._pending_batch_ids) intentionally get no bank
        # event — their claim_payment LEs remain uncleared = pending_claims_liability.
        for batch in self.created_objects["batches"]:
            if batch.id in self._pending_batch_ids:
                continue  # no bank event → these LEs stay as pending liability

            batch_claims = self._batch_claim_835_map.get(batch.id, [])
            if not batch_claims:
                continue

            total = sum(Decimal(r["paid_amount"]) for r in batch_claims)
            latest = max(date.fromisoformat(r["paid_date"]) for r in batch_claims)
            bank_ref = f"trace_{counter:06d}"

            self._bank_records.append({
                "bank_reference": bank_ref,
                "bank_account_id": clearing_id,
                "posted_date": (latest + timedelta(days=self.rng.randint(0, 2))).isoformat(),
                "amount": str(total),
                "direction": "debit",
                "descriptor": f"ACH BATCH {counter:06d} {len(batch_claims)} CLMS",
            })
            for rec in batch_claims:
                self._add_gtl(bank_ref, rec["claim_id"], ExceptionType.MANY_TO_ONE)
            counter += 1

        # ── Employer funding: always a CLEAN bank event ────────────────────
        # Pulling employer_funding out of the random exception pool guarantees
        # it gets a reference-anchored exact match (confidence 1.0, MATCHED),
        # so it always counts as cleared in the funded_balance calculation.
        for rec in [r for r in self._820_records if r["entry_type"] == "employer_funding"]:
            bank_ref = f"trace_{counter:06d}"
            row_ref = rec["row_ref"]
            self._bank_records.append({
                "bank_reference": bank_ref,
                "bank_account_id": rec["bank_account_id"],
                "posted_date": (
                    date.fromisoformat(rec["expected_date"])
                    + timedelta(days=self.rng.randint(0, 1))
                ).isoformat(),
                "amount": rec["amount"],
                "direction": rec["direction"],
                "descriptor": f"820 {rec.get('counterparty', '')} {row_ref}".strip(),
            })
            self._add_gtl(bank_ref, row_ref, ExceptionType.CLEAN)
            counter += 1

        # ── Exception pool: all 820 records EXCEPT employer_funding ───────
        pool = [rec for rec in self._820_records if rec["entry_type"] != "employer_funding"]
        n = len(pool)

        pool_types = [t for t in EXCEPTION_MIX if t != "many_to_one"]
        non_clean = [t for t in pool_types if t != "clean"]
        floor = min(EXCEPTION_FLOOR, max(1, n // (len(non_clean) + 1)))

        guaranteed = [t for t in non_clean for _ in range(floor)]
        remaining_n = max(0, n - len(guaranteed))
        pool_weights = [EXCEPTION_MIX[t] for t in pool_types]
        total_w = sum(pool_weights)
        pool_weights = [w / total_w for w in pool_weights]
        remainder = self.rng.choices(pool_types, weights=pool_weights, k=remaining_n)

        assignment = guaranteed + remainder
        self.rng.shuffle(assignment)

        for entry, exc_str in zip(pool, assignment):
            exc = ExceptionType(exc_str)
            acc_id = entry["bank_account_id"]
            amount = Decimal(entry["amount"])
            direction = entry["direction"]
            expected_dt = date.fromisoformat(entry["expected_date"])
            row_ref = entry["row_ref"]

            if exc == ExceptionType.CLEAN:
                bank_ref = f"trace_{counter:06d}"
                self._bank_records.append({
                    "bank_reference": bank_ref,
                    "bank_account_id": acc_id,
                    "posted_date": (expected_dt + timedelta(days=self.rng.randint(0, 3))).isoformat(),
                    "amount": str(amount),
                    "direction": direction,
                    "descriptor": f"{entry.get('source_artifact', '')} {entry.get('counterparty', '')} {row_ref}".strip(),
                })
                self._add_gtl(bank_ref, row_ref, ExceptionType.CLEAN)
                counter += 1

            elif exc == ExceptionType.TIMING:
                bank_ref = f"trace_{counter:06d}"
                self._bank_records.append({
                    "bank_reference": bank_ref,
                    "bank_account_id": acc_id,
                    "posted_date": (expected_dt + timedelta(days=self.rng.randint(5, 14))).isoformat(),
                    "amount": str(amount),
                    "direction": direction,
                    "descriptor": f"LATE PMT {entry.get('counterparty', '')}".strip(),
                })
                self._add_gtl(bank_ref, row_ref, ExceptionType.TIMING)
                counter += 1

            elif exc == ExceptionType.ONE_TO_MANY:
                part1 = (amount * Decimal("60") / Decimal("100")).quantize(Decimal("0.01"))
                part2 = amount - part1
                for part in [part1, part2]:
                    bank_ref = f"trace_{counter:06d}"
                    self._bank_records.append({
                        "bank_reference": bank_ref,
                        "bank_account_id": acc_id,
                        "posted_date": (expected_dt + timedelta(days=self.rng.randint(0, 3))).isoformat(),
                        "amount": str(part),
                        "direction": direction,
                        "descriptor": f"PARTIAL {entry.get('counterparty', '')}".strip(),
                    })
                    self._add_gtl(bank_ref, row_ref, ExceptionType.ONE_TO_MANY)
                    counter += 1

            elif exc == ExceptionType.REVERSAL:
                rev_dir = "credit" if direction == "debit" else "debit"
                bank_ref_orig = f"trace_{counter:06d}"; counter += 1
                bank_ref_rtn  = f"trace_{counter:06d}"; counter += 1
                bank_ref_rei  = f"trace_{counter:06d}"; counter += 1
                self._bank_records.append({
                    "bank_reference": bank_ref_orig,
                    "bank_account_id": acc_id,
                    "posted_date": expected_dt.isoformat(),
                    "amount": str(amount), "direction": direction,
                    "descriptor": f"PMT {entry.get('counterparty', '')}".strip(),
                })
                self._bank_records.append({
                    "bank_reference": bank_ref_rtn,
                    "bank_account_id": acc_id,
                    "posted_date": (expected_dt + timedelta(days=3)).isoformat(),
                    "amount": str(amount), "direction": rev_dir,
                    "descriptor": f"ACH RTN {entry.get('counterparty', '')}".strip(),
                })
                self._bank_records.append({
                    "bank_reference": bank_ref_rei,
                    "bank_account_id": acc_id,
                    "posted_date": (expected_dt + timedelta(days=5)).isoformat(),
                    "amount": str(amount), "direction": direction,
                    "descriptor": f"REISSUE {entry.get('counterparty', '')}".strip(),
                })
                for bank_ref in [bank_ref_orig, bank_ref_rtn, bank_ref_rei]:
                    self._add_gtl(bank_ref, row_ref, ExceptionType.REVERSAL)

            elif exc == ExceptionType.SHORT_OVER_FUNDING:
                variance = amount * Decimal(str(round(self.rng.uniform(-0.05, 0.05), 6)))
                actual = max((amount + variance).quantize(Decimal("0.01")), Decimal("0.01"))
                bank_ref = f"trace_{counter:06d}"
                self._bank_records.append({
                    "bank_reference": bank_ref,
                    "bank_account_id": acc_id,
                    "posted_date": (expected_dt + timedelta(days=self.rng.randint(0, 2))).isoformat(),
                    "amount": str(actual),
                    "direction": direction,
                    "descriptor": f"WIRE {entry.get('counterparty', '')} (AMT VAR)".strip(),
                })
                self._add_gtl(bank_ref, row_ref, ExceptionType.SHORT_OVER_FUNDING)
                counter += 1

            elif exc == ExceptionType.UNREFERENCED_INBOUND:
                bank_ref = f"trace_{counter:06d}"
                self._bank_records.append({
                    "bank_reference": bank_ref,
                    "bank_account_id": acc_id,
                    "posted_date": (expected_dt + timedelta(days=self.rng.randint(0, 5))).isoformat(),
                    "amount": str(amount),
                    "direction": direction,
                    "descriptor": (
                        f"ACH CREDIT XYZ CORP "
                        f"REF{self.rng.randint(10000000, 99999999)} "
                        f"CO{self.rng.randint(1000, 9999)}"
                    ),
                })
                self._add_gtl(bank_ref, row_ref, ExceptionType.UNREFERENCED_INBOUND)
                counter += 1

            elif exc == ExceptionType.BANK_ONLY_NOISE:
                bank_ref = f"trace_{counter:06d}"
                desc = self.rng.choice([
                    f"BANK SVC CHG {self.rng.randint(100, 999)}",
                    f"INTEREST CREDIT {self.rng.randint(10, 999)}",
                    f"ACH RTN FEE {self.rng.randint(10, 99)}",
                    f"WIRE FEE REF{self.rng.randint(10000, 99999)}",
                ])
                self._bank_records.append({
                    "bank_reference": bank_ref,
                    "bank_account_id": acc_id,
                    "posted_date": (expected_dt + timedelta(days=self.rng.randint(0, 10))).isoformat(),
                    "amount": str(round(self.rng.uniform(10, 500), 2)),
                    "direction": self.rng.choice(["debit", "credit"]),
                    "descriptor": desc,
                })
                # bank_only_noise: ledger_natural_ref = None (no ledger entry to link)
                self._add_gtl(bank_ref, None, ExceptionType.BANK_ONLY_NOISE)
                counter += 1

        # Bulk-insert all ground_truth_link rows queued during this method
        self.session.bulk_save_objects(self._pending_gtls)
        self.session.flush()
        self.created_objects["ground_truth_links"].extend(self._pending_gtls)
        self._pending_gtls = []

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _add_gtl(self, bank_reference: str, ledger_natural_ref, exc_type: ExceptionType):
        self._pending_gtls.append(GroundTruthLink(
            bank_reference=bank_reference,
            ledger_natural_ref=ledger_natural_ref,
            exception_type=exc_type,
        ))

    def _clearing_account(self) -> BankAccount:
        return next(
            a for a in self.created_objects["accounts"]
            if a.type == BankAccountType.CLEARING
        )

    def _operating_account(self) -> BankAccount:
        return next(
            (a for a in self.created_objects["accounts"]
             if a.type == BankAccountType.OPERATING),
            self._clearing_account(),
        )

    def _month_range(self, start: date, end: date) -> list:
        months, cur = [], date(start.year, start.month, 1)
        last = date(end.year, end.month, 1)
        while cur <= last:
            months.append((cur.year, cur.month))
            cur = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        return months

    def _active_members(self, group_id, year: int, month: int) -> int:
        _, last_day = calendar.monthrange(year, month)
        m_start = date(year, month, 1)
        m_end = date(year, month, last_day)
        return sum(
            1 for m in self.created_objects["members"]
            if m.group_id == group_id
            and m.enrollment_start <= m_end
            and (m.enrollment_end is None or m.enrollment_end >= m_start)
        )


def generate_synthetic_data(seed: int = SEED) -> dict:
    """Main entry point: generate all synthetic data, write artifact files."""
    return DataGenerator(seed=seed).generate_all()
