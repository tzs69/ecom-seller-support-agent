# Backend controls

Planned Python/backend responsibilities. No control or tool is implemented yet.
These requirements are not part of the business-policy retrieval corpus. Enforce
them even when the model ignores its instructions or retrieval fails.

## ACCESS-02: Verify ownership

Derive seller identity from the authenticated application session, never chat.
Require an order ID for order-specific lookups. Before returning order details
or accessing related tracking/history, verify ownership. Unknown and unauthorised
orders return the same public error, without exposing existence or private facts.
Do not let evaluation tool overrides bypass ownership validation.

## SCOPE-01: Select applicable policy

Filter business documents by order market and evaluation time, selecting the
latest effective version of each required document. The current corpus covers
SG from 1 October 2026, inclusive, with no end date. Read that applicability from
document metadata; do not trust the model to enforce it.

No applicable coverage produces `unsupported_policy_scope` with no executable
proposal. A missing required document inside otherwise supported coverage is
an evidence gap, not permission to substitute another market's rules.

## EVIDENCE-04: Require available, coherent evidence

Before permitting a new carrier request, require successful order, tracking, and
resolution-history lookups, plus coherent delivered status across order/tracking.
Unknown history blocks a new proposal because duplicate status cannot be checked.
Tracking failures or status disagreements yield `insufficient_evidence`, with
no proposed action. A timeout is not a successful response containing null proof.

Exception: after access/scope checks, successfully retrieved history confirming a
completed refund or existing open carrier request is enough to return
`existing_resolution`. No tracking lookup is necessary merely to decide against
another submission. If tracking has failed, the confirmed status may still be
reported, but no new action is allowed. Follow `docs/domain.md` precedence.

## ACTION-01: Enforce explicit approval

Only `submit_carrier_investigation_request` is an executable business action.
Before execution, validate explicit approval through the application's approval
control, bound to the authenticated seller and exact proposal/order. Approval
must include a reviewable proposal with reason and supporting evidence.

An initial instruction to act is not approval of a proposal that does not yet
exist. Rejection prevents the business action but still records an audit event.
Internal audit/checkpoint writes do not need seller approval. Use native
LangGraph interrupts and persistent checkpoints as specified in the implementation
design; an interrupt is not itself an authorisation check.

## ACTION-02: Revalidate, deduplicate, and retain idempotency results

Immediately before submission, recheck ownership, applicable policy, delivery
status, resolution history, and decision-relevant tracking facts. Changed relevant
facts invalidate the old proposal and trigger reassessment. A replacement
executable proposal requires fresh approval; irrelevant note edits alone do not.

Use one stable idempotency key per approved submission operation; persist it
before calling the write tool. After authentication/authorisation, check for a
previously committed result for that key first. Return the original result on
repeat calls, including calls after successful completion. Keep the mapping
persisted across restarts; do not discard it immediately after success. Do not
reuse a key for a different operation or changed payload.

For a new operation, enforce eligibility and creation atomically. A completed
refund blocks a new request. At most one carrier investigation request may exist
per seller/order across this MVP, including closed requests. Enforce that with
database uniqueness and a transaction, not only a preceding application lookup.
Check existing requests by seller/order across all support cases; a case's optional
request ID is a navigation link, not the sole duplicate-detection mechanism.

Caller attempts have distinct attempt IDs but reuse the approved operation's
idempotency key. On timeout, the write may have committed. Retry/reconcile using
that key within the configured budget; never assume a timeout means failure or
start a fresh operation to work around an unknown result. Preserve request,
idempotency result, and creation audit event in the same business transaction.

## ACTION-03: Restrict executable capabilities

Do not expose refund execution, request reopening, escalation ticket creation,
or buyer-message sending as executable tools in this MVP. Handoffs and buyer
replies are generated drafts only. These are application scope restrictions, not
claims about a real company's policies. Refund idempotency/payment correctness is
outside this workflow; existing refund records are read-only inputs.

Store proposal, approval, attempt, and result separately. Case closure is not
proof of submission, carrier activity, refund authorisation, or payment execution.
Only a confirmed backend result permits a successful-submission status.

## Enforce business eligibility independently of model proposals

| Business rule | Required code check |
| --- | --- |
| SCOPE-02 | Only delivered-but-missing orders enter this procedure |
| EVIDENCE-01 | Missing photo and signature, with no conflicting location, permits an investigation proposal only after all prerequisites pass |
| EVIDENCE-02 | A known location mismatch takes precedence and blocks automatic submission |
| EVIDENCE-03 | Available photo/signature without mismatch routes disputed receipt to human review |
| HISTORY-01 | Completed refunds and existing requests block a new request; closed requests route to human review |

Use the decision table's priority order. Policy text explains the business rule;
code independently validates execution eligibility. Keep both consistent as rules
change rather than allowing model text to serve as the final permission check.

## Reuse active support cases

After verifying ownership, return an existing active case for the seller/order
instead of creating another active case or automatically repeating assessment.
Expose its status, pending proposal, and next step; awaiting approval means the
seller should review that proposal. Revalidate current facts when they approve.
Enforce one active case per seller/order, independently of request uniqueness.

A new historical case can reference the order's earlier request; it cannot
create a second one. Reusing a case, checking request history, and idempotent
submission are distinct controls. A dedicated awaiting-approval fixture remains
to be added; the domain requirement and EXEC-07 already specify case reuse.

## Related implementation specifications

See [the implementation design](implementation.md) for output fields, retry
budgets, audit records, SQLite storage, and checkpoint handling. Acceptance
criteria are in [the execution scenarios](../evals/execution_scenarios.md).
