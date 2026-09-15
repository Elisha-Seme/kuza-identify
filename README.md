# Kuza Connect — Layer 1 Identification Engine (Phase 0 / MVP)

This repository implements **Layer 1 only** of Kuza Connect — the identification
engine — as scoped in **Section 8 (MVP / Phase 0)** of
[`kuza-connect-system-spec.md`](./kuza-connect-system-spec.md). Layers 2 and 3 are
out of scope, as are OCR, a trained context-adjustment model, the USSD channel,
and any live KEMIS/KNEC integration.

The spec is the source of truth. Every service, table, and constraint below cites
the section it comes from.

---

## What's in the box

| Piece | Status | Spec |
|---|---|---|
| Postgres schema + migrations for **every** Section 5 entity | Built | §5 |
| Screening Gateway API (session state, resume, consent gate) | Built, real | §4, §3.4, §7 |
| Adaptive Item Engine (owns the item bank, difficulty-aware selection) | Built, real | §4, §3.4 |
| Nomination Service (teacher/parent, 2e amber-flag checklist) | Built, real | §4, §2 |
| LLM Scoring Service (real Claude API + offline mock fallback) | Built, real | §3.3, §6 |
| Aggregation & Flag Engine (context adjust, spike flags, **no composite**) | Built, real | §3.1, §3.2 |
| Panel Review Dashboard (React) | Built, real | §4 |
| Decision & Audit Log (append-only, DB-enforced immutability) | Built, real | §3.6, §7 |
| Passive Candidate Service (spreadsheet grade mining → signals) | Working skeleton | §3.7, §8 |
| Bias Audit Service (pathway/tier/gender slices) | Skeleton | §4, §7, §3.7 |
| KEMIS Integration Adapter | **Interface + types only** | §6, §8 |
| docker-compose (Postgres + api + dashboard) + seed script | Built | §8 |

---

## Architecture

A **modular monolith**: one FastAPI process with one module per Section 4 service
(`backend/app/services/<service>/`), plus two batch jobs run as CLI scripts
(Passive Candidate, Bias Audit). This keeps local dev to three containers while
preserving the service boundaries from §4. See *Judgment calls* below.

```
backend/
  app/
    core/          config, db, enums (Section 5 value sets, single source of truth)
    models/        SQLAlchemy models — one class per Section 5 entity
    services/
      screening_gateway/     session state, resume, consent gate  (§4, §3.4)
      adaptive_item_engine/  item bank (item_bank.json) + selection (§4)
      nomination/            structured form incl. 2e amber-flags  (§4, §2)
      llm_scoring/           Claude API integration + mock fallback (§3.3)
      aggregation_flag/       context adjustment + spike flag rules (§3.1, §3.2)
      panel_review/          flagged-profile assembly + decision    (§4)
      decision_audit_log/    append-only writer                     (§3.6, §7)
      passive_candidate/     spreadsheet grade-variance mining      (§3.7, §8)
      bias_audit/            pathway/tier/gender slice rates         (§4, §7)
      kemis_adapter/         interface + normalized types ONLY       (§6, §8)
      response_store/        append-only read helpers                (§4)
    providers/whatsapp/      WhatsAppProvider interface + MockWhatsAppProvider (§6)
    api/           FastAPI routers (screening, nomination, panel)
    cli/           seed.py, run_passive_mining.py, run_bias_audit.py
  migrations/      Alembic, 0001…0008 in FK-safe order
dashboard/         React + Vite + TS panel review UI
docker-compose.yml
```

---

## Quick start (docker)

```bash
cp .env.example .env          # optional: add ANTHROPIC_API_KEY for live scoring
docker compose up --build     # starts db + api + dashboard, runs migrations

# in another terminal, seed 3 demo learners across all three pathways:
docker compose run --rm api python -m app.cli.seed
```

- API + interactive docs: <http://localhost:8000/docs>
- Panel dashboard: <http://localhost:5173>
- Bias audit report: `docker compose run --rm api python -m app.cli.run_bias_audit`

Without an `ANTHROPIC_API_KEY`, the LLM Scoring Service runs a **deterministic
mock scorer** so the whole pipeline works offline. Set the key and the real
Claude integration takes over automatically (and `scoring_model_version` records
the model + prompt version on every `DomainScore`).

## Quick start (no docker)

```bash
# Postgres reachable at DATABASE_URL (see .env.example)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://kuza:kuza@localhost:5432/kuza
alembic upgrade head
python -m app.cli.seed
uvicorn app.main:app --reload            # API on :8000

cd ../dashboard && npm install && npm run dev   # dashboard on :5173
```

Run the tests (needs a migrated DB):

```bash
cd backend && pytest -q
```

---

## How the non-negotiable constraints are enforced

- **Data model matches Section 5 exactly; no person-name / diagnosis / health
  field anywhere.** `backend/app/models/entities.py` mirrors §5 field-for-field.
  `School.name` is retained because it is a *school's* name and is part of §5; the
  "no name" rule concerns persons/learners.
- **No composite / average score anywhere.** The Aggregation Engine
  (`aggregation_flag/engine.py`) computes per-domain adjusted scores and flags on
  the **maximum** single-domain value (`R1_domain_spike_high`) and the **max–min
  spread** (`R2_wide_domain_variance`) — never a mean. There is no composite
  column; a test asserts no `composite/average/overall/total` column exists.
- **CandidateSignal and DomainScore are separate tables.** A `CandidateSignal`
  carries a DB-`CHECK`-enforced `confidence = 'low'` and is never joined into the
  score path. Passive signals are advisory only (§2, §7).
- **The scoring service writes flags and evidence only, never a decision.** LLM
  scoring produces `DomainScore` (score + evidence); the Aggregation Engine writes
  `FlagEvent`. A decision is written **only** by `panel_review.record_decision`
  into `PanelReview`.
- **Every flag → decision path is logged immutably.** `decision_audit_log` is
  append-only; migration `0008` installs a trigger that raises on any `UPDATE`/
  `DELETE`. A flag fires → `flag_fired` entry; a decision is recorded →
  `decision_recorded` entry linking the flag and the review.

---

## The 5-domain item set

`backend/app/services/adaptive_item_engine/item_bank.json` holds a **placeholder**
five-domain set (numerical / verbal / pattern / logical / working-memory), each
item bilingual (en/sw) and phrased to degrade to plain text for USSD later (§3.4).
**Swap this one file for the real prototype items** — nothing else needs to change.

---

## Judgment calls flagged for review

1. **Placeholder item set** — the real prototype 5-item set wasn't in the repo, so
   `item_bank.json` is a clearly-marked stand-in. Replace it with the real items
   (and confirm the five domain names).
2. **Scoring model = `claude-haiku-4-5`** — §3.3 makes per-child cost the driver
   of model choice for screening thousands of learners, so Haiku is the default
   (override via `SCORING_MODEL`). Flagged because the general guidance is to
   default to a larger model.
3. **Modular monolith** rather than 11 deployables — service boundaries preserved
   as modules; batch jobs as CLIs. Change if you want true service separation.
4. **`decision_audit_log` is one table beyond §5's literal entity list** — added
   because §4 and the constraints require a "Decision & Audit Log" that §5's list
   doesn't itself name.
5. **Panel reviews attach to screening sessions.** `PanelReview` and `FlagEvent`
   are session-scoped in §5, so the dashboard's review unit is a flagged session;
   nomination amber-flags and passive signals appear as **evidence** on that
   learner's profile. A pure nomination/passive candidate reaches a *decision*
   only after the learner completes the active screener (consistent with §2's
   "still has to go through the same active screener").
6. **No Redis** — session state lives in Postgres (resume-safe), per §6's
   "Postgres if avoiding an extra service for the pilot."

---

## Explicitly deferred (per Section 8)

OCR pipeline · trained context-adjustment model · USSD channel · live KEMIS/KNEC
integration (adapter interface only) · Layer 2 (development programme) · Layer 3
(showcase) · multi-country support.
