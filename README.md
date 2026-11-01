# E-commerce Seller Support Agent

A portfolio project for assessing orders marked delivered when the buyer
reports non-receipt, built with Python, LangGraph, and ChatBedrockConverse.

Current stage: a read-only CLI assessment graph. The model selects read tools and
proposes a structured outcome; Python validates it and renders a verified summary.
No approval UI, business-write tools, persistent cases, audit database, or checkpoint
resumption are implemented yet.

All businesses, orders, policies, and outcomes in this repository are fictional.
These are demo rules, not TikTok Shop or carrier policies.

## Start here

Use Python 3.11 or newer (developed here with Python 3.14). From this checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m seller_support --list-cases
.\.venv\Scripts\python.exe -m pytest -q
```

For a live model run, configure your local `.env` using `.env.example` as a guide:

```dotenv
BEDROCK_MODEL_ID=your-model-or-inference-profile-id
# Optional override; omit to use the profile's region:
# AWS_DEFAULT_REGION=your-bedrock-region
# Required named IAM Identity Center (SSO) profile:
AWS_PROFILE=your-profile
```

The SDK uses `AWS_DEFAULT_REGION` or the selected profile's region.
Authentication is **SSO only**: `AWS_PROFILE` is required
and must resolve directly to an IAM Identity Center credential provider. The app
rejects other credential providers and does not read credential values.

Set up your profile once with `aws configure sso --profile your-profile`, then
sign in with `aws sso login --profile your-profile`. Boto3 manages the resulting
temporary credentials and refresh; no credentials are copied into app settings.

The AWS identity needs `bedrock:InvokeModel` access to the selected model/profile
and any required underlying model resources. Choose an accessible model supporting
Converse tool use; structured assessments use function calling plus Pydantic
validation. Streaming is disabled. Existing process environment variables take
precedence over `.env`. Do not commit credentials. Live runs incur Bedrock charges.

If Bedrock reports that a model does not support on-demand throughput, use an
accessible inference-profile ID in `BEDROCK_MODEL_ID` instead of the base model
ID. AWS errors include their service diagnostic; `--trace` adds workflow events.

```powershell
# For a new setup only; do not overwrite an existing .env:
Copy-Item .env.example .env
# Edit .env locally, sign in to SSO, then:
aws sso login --profile your-profile
.\.venv\Scripts\python.exe -m seller_support --case CASE-001 --trace
```

`--trace` prints tool names, attempts, statuses, and retrieved rule IDs to stderr;
the JSON recommendation goes to stdout. It does not dump raw prompts or carrier
notes. The first three demos are CASE-001 (missing proof), CASE-002 (location
conflict), and CASE-003 (existing carrier request). CASE-006/007/008/009/010 are
handled by deterministic preflight checks without calling Bedrock.

This is a checkout-based demo, not a standalone packaged service. Fixture identity
simulates a trusted seller session; there is no real login/authentication service.
See [the first-flow guide](docs/first-flow.md) for the graph and its boundaries.

## Specifications

1. Read [the scenario and decision table](docs/domain.md).
2. Review [the policy collection](policies/README.md).
3. Walk through [three demo cases](docs/demo-walkthrough.md).
4. Inspect [case inputs](data/cases.json) and [expected resolutions](evals/expected_resolutions.json).
5. Review [approval and recovery scenarios](evals/execution_scenarios.md).

For consistent Python formatting, run `python -m ruff format src tests` from the
activated virtual environment; check imports and common errors with
`python -m ruff check src tests`.

For technical details, read [the implementation design](docs/implementation.md).
For fixture conventions and grading, read [the evaluation guide](evals/README.md).
For rule ownership, read [the rule catalog](docs/rule-catalog.md).

## Layout

| Path | Purpose |
| --- | --- |
| `docs/domain.md` | Terminology, relationships, decision precedence, and evidence rules |
| `docs/implementation.md` | Technical contracts, approval, retries, audit, and persistence |
| `docs/backend-controls.md` | Planned access, scope, approval, eligibility, and duplicate-prevention checks |
| `docs/rule-catalog.md` | Primary sources for all 13 rule IDs |
| `evals/README.md` | Fixture conventions and evaluation guidance |
| `policies/` | Three fictional business-policy retrieval documents, five rule IDs |
| `instructions/seller-support-agent.md` | Always-on agent instructions; not business-policy retrieval content |
| `src/seller_support/` | CLI, models, authorised fixture tools, retrieval, graph, and eligibility validation |
| `tests/` | Offline graph and boundary tests using injected scripted models |
| `data/orders.json` | Synthetic order records for a mock order tool |
| `data/tracking.json` | Structured tracking evidence for a mock tracking tool |
| `data/resolutions.json` | Existing carrier investigation requests and refunds for a mock history tool |
| `data/cases.json` | Twelve seller requests and per-case tool behaviour |
| `evals/expected_resolutions.json` | Evaluator-only decision labels and required evidence |
| `evals/execution_scenarios.md` | Acceptance scenarios for later approval/execution work |

## MVP boundary

The following is the full intended MVP. This first milestone implements only the
read-only assessment portion; it returns a proposal but cannot execute it.

- One Singapore storefront; English; delivered-but-missing complaints.
- Read order, tracking, and resolution history; retrieve applicable policy.
- Recommend a carrier investigation request, human review, a status update, or clarification.
- Only `submit_carrier_investigation_request` performs a business action, after approval; audit/checkpoint writes are internal.
- No refund execution, live integrations, image analysis, or automatic buyer messaging.

Keep `evals/` out of retrieval and model context. Fixtures are read-only seed data;
future demo runs should copy them into a resettable runtime database.
