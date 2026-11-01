# E-commerce Seller Support Agent

A portfolio project for assessing orders marked delivered when the buyer
reports non-receipt. Planned implementation: Python and LangGraph.

Current stage: domain scaffolding. No agent, backend, or UI is implemented yet.

All businesses, orders, policies, and outcomes in this repository are fictional.
These are demo rules, not TikTok Shop or carrier policies.

## Start here

Returning to the project? Read [the handoff checkpoint](docs/handoff.md) first.

1. Read [the scenario and decision table](docs/domain.md).
2. Review [the policy collection](policies/README.md).
3. Walk through [three demo cases](docs/demo-walkthrough.md).
4. Inspect [case inputs](data/cases.json) and [expected resolutions](evals/expected_resolutions.json).
5. Review [approval and recovery scenarios](evals/execution_scenarios.md).

For technical details, read [the implementation design](docs/implementation.md).
For fixture conventions and grading, read [the evaluation guide](evals/README.md).
For rule ownership, read [the rule catalog](docs/rule-catalog.md).

## Layout

| Path | Purpose |
| --- | --- |
| `docs/domain.md` | Terminology, relationships, decision precedence, and evidence rules |
| `docs/implementation.md` | Technical contracts, approval, retries, audit, and persistence |
| `docs/handoff.md` | Current progress, pending work, and next milestone |
| `docs/backend-controls.md` | Planned access, scope, approval, eligibility, and duplicate-prevention checks |
| `docs/rule-catalog.md` | Primary sources for all 13 rule IDs |
| `evals/README.md` | Fixture conventions and evaluation guidance |
| `policies/` | Three fictional business-policy retrieval documents, five rule IDs |
| `instructions/seller-support-agent.md` | Draft always-on agent instructions; not business-policy retrieval content |
| `data/orders.json` | Synthetic order records for a mock order tool |
| `data/tracking.json` | Structured tracking evidence for a mock tracking tool |
| `data/resolutions.json` | Existing carrier investigation requests and refunds for a mock history tool |
| `data/cases.json` | Twelve seller requests and per-case tool behaviour |
| `evals/expected_resolutions.json` | Evaluator-only decision labels and required evidence |
| `evals/execution_scenarios.md` | Acceptance scenarios for later approval/execution work |

## MVP boundary

- One Singapore storefront; English; delivered-but-missing complaints.
- Read order, tracking, and resolution history; retrieve applicable policy.
- Recommend a carrier investigation request, human review, a status update, or clarification.
- Only `submit_carrier_investigation_request` performs a business action, after approval; audit/checkpoint writes are internal.
- No refund execution, live integrations, image analysis, or automatic buyer messaging.

Keep `evals/` out of retrieval and model context. Fixtures are read-only seed data;
future demo runs should copy them into a resettable runtime database.
