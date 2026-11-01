# Approval and recovery acceptance scenarios

Specification only: these have not been implemented or run. Use CASE-001 with
fresh runtime state unless noted. Do not mutate checked-in fixtures during runs.

## EXEC-01: Approve

- Given a carrier investigation request proposal bound to the current seller and evidence,
- when the seller approves it through the approval control,
- then revalidate the proposal and create exactly one carrier investigation request.
- Record the proposal, approval, idempotency key, and returned carrier investigation request ID.
- Only after confirmed success may the agent say the carrier investigation request was submitted.

## EXEC-02: Reject

- Given the same proposal, when the seller rejects it,
- then create no carrier investigation request and preserve the rejection in case history.
- A request to change the proposal generates a new proposal, not execution.

## EXEC-03: Restart while awaiting approval

- Pause at approval, stop the app, and restart using the same case/thread ID.
- Restore the pending proposal from persistent storage.
- No write occurs during startup or before approval.
- Approval executes once; rejection executes zero times.

## EXEC-04: Backend success followed by response timeout

- The backend commits creation, but the caller receives a timeout.
- Retry with the same idempotency key or reconcile the recorded result.
- Return the original carrier investigation request ID and keep exactly one carrier investigation request.
- While the result is unknown, say the outcome is unconfirmed, not failed or opened.

## EXEC-05: Existing resolution appears before approval

- Draft a proposal, then insert a completed refund or open carrier investigation request externally.
- Approve the original proposal.
- Revalidation invalidates it and reports the existing resolution; create nothing.
- Also simulate a competing writer between revalidation and creation: the atomic
  backend constraint must return an existing resolution instead of creating another.

## EXEC-06: Evidence changes before approval

- Draft a missing-proof carrier investigation request proposal, then change the tracking location
  to a token that conflicts with the order destination.
- Approval of the old proposal must not execute it.
- Reassess as human review and show the updated evidence.
- A different replacement proposal, if executable, requires fresh approval.

## EXEC-07: Duplicate submissions for the same order

- Attempt to open support twice for SG-1042 while a case is active. Return the
  existing case instead of creating a second active case.
- Submit approval twice or simulate overlapping creation requests anyway.
- Create at most one carrier investigation request; both requests reconcile to the same result.
- After closing the case, open a later case for the same order. It reports the
  existing carrier investigation request and creates nothing new.
- Per-case idempotency alone is insufficient across historical cases; enforce
  uniqueness per seller/order as well.

## EXEC-08: Policy or access changes before approval

- Draft a proposal, then make the policy inapplicable or revoke order ownership.
- Approval must create nothing. Reassess policy gaps or return the generic
  inaccessible-order response; do not disclose newly unauthorised order details.

## Evaluation reporting

Report recommendation decision accuracy and policy/evidence support separately
from execution safety. The twelve static cases exercise recommendation behaviour;
these scenarios exercise state transitions and actual writes. Never claim an
execution property passed based only on a model's text response.

Use deterministic assertions for action counts, approval binding, identity, and
idempotency. Manually review explanation quality initially. Record observed
latency/cost later; there are no measured performance claims in this scaffold.
