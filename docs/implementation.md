# Implementation design

Planned technical behaviour; no agent, tools, runtime databases, or UI are
implemented yet. Business terminology and decision precedence live in
[the domain model](domain.md).

## Responsibility boundaries

- Retrieved business policies supply applicable delivery-dispute and history rules.
- Agent system instructions govern explanations, citations, uncertainty, and untrusted text.
- Python/backend controls enforce ownership, scope, action eligibility, approval, revalidation, and duplicate prevention.

These responsibilities are now documented separately:

- [Business corpus](../policies/README.md): three retrieval documents, five rules.
- [Agent instructions](../instructions/seller-support-agent.md): always-on model guidance.
- [Backend controls](backend-controls.md): code-enforced requirements, not retrieval sources.
- [Rule catalog](rule-catalog.md): primary source and category for all 13 rule IDs.

The split is documentation only; runtime loading and enforcement remain to be
implemented. Application controls must work even when retrieval fails or a model
ignores instructions. The rule catalog and handoff are not model context.

## Access enforcement

Seller identity comes from the application session, never from the prompt. Before
returning any order details or calling downstream order-specific tools, the order
tool must check ownership. Not-found and unauthorised orders have the same public
response. Private fixtures may include other sellers' records to exercise this.

## Recommendation shape

The later agent should produce a structured object with:

| Field | Meaning |
| --- | --- |
| `case_id` | Stable case identifier |
| `decision` | One of the decision labels in `domain.md` |
| `summary` | Plain-language finding, with uncertainty |
| `evidence_refs` | Record/field references, e.g. `tracking:TRK-1042.status` |
| `policy_refs` | Retrieved business-rule references only: rule ID, version, and `business_policy` source type |
| `rule_refs` | Supporting references across all categories: rule ID, version, and source type from the rule catalog |
| `missing_information` | Explicit unresolved facts |
| `proposed_action` | Null or a structured `submit_carrier_investigation_request` proposal |
| `approval_required` | True only when there is a proposed executable action |
| `buyer_reply_draft` | Optional unsent draft; no unsupported promises |

A proposal includes order ID, reason, evidence references, policy version, and a
stable proposal ID. Approval is bound to that proposal, not an arbitrary chat
message. The executing tool derives seller identity from the trusted session.

All `policy_refs` also appear in `rule_refs`. A control-only response, such as
ownership denial, can have empty `policy_refs` and an ACCESS-02 `rule_refs` entry.
An eligible investigation proposal includes EVIDENCE-01 as a business-policy
reference and ACTION-01 as a backend-control reference. Do not describe both as
retrieved company policy. Trusted control references should be attached by code;
applicable instruction references can be attached by the response/evaluation layer.

## Tool interface

Planned tools: `get_order`, `get_tracking`, `get_resolution_history`, and
`submit_carrier_investigation_request`. Policy retrieval is read-only.

Active support-case lookup/reuse is also required before starting a new assessment;
it may be handled by the application rather than exposed as an LLM tool. See
[backend controls](backend-controls.md). Case reuse, existing-request lookup by
seller/order, and write idempotency are separate protections.

## Execution contract

1. Read tools are allowed during agent assessment; business action writes need
   explicit UI approval. Internal audit events and workflow checkpoints do not
   require seller approval.
2. Immediately before execution, fetch current ownership, applicable policy,
   delivery status, resolution history, and decision-relevant tracking evidence.
   Compare them with the facts supporting the approved proposal. This catches
   changes during the human approval wait, such as newly available delivery proof.
3. If a decision-relevant fact or applicable policy changed, invalidate the old
   proposal and reassess. Example: new proof changes `propose_carrier_investigation` into
   `human_review`, so create nothing. If reassessment still recommends an executable
   action, present a new proposal and get fresh approval. An irrelevant carrier
   note edit alone need not invalidate a proposal. Rule 2 checks; rule 3 handles
   the result. For the MVP these can be a small deterministic pre-execution guard.
4. The mock backend checks for an existing resolution and creates a carrier investigation request
   as one indivisible database operation (a transaction with a uniqueness constraint).
   This prevents two overlapping calls from both seeing "none" and creating two.
   Enforce at most one carrier investigation request per seller/order across the MVP, regardless
   of support case IDs. An existing completed refund blocks creation too. Closed
   carrier investigation requests require human review. The UI reuses active cases, but database
   protection is still necessary for duplicate submissions and future cases.
5. Retry a failed/timed-out `submit_carrier_investigation_request` tool call using the same
   approved proposal's stable idempotency key. The backend may have created the
   carrier investigation request before its reply was lost; the retry must return that original
   result, not create another. Persist the key before calling the tool. This is
   execution retry, not the seller approving again. Resuming the approval interrupt
   only continues the workflow; if recovery replays a write, use the same key.
   Check for a previously committed result before treating an existing resolution
   as a reason to invalidate the original successful action. Authenticate and
   authorise before returning a saved result. Retain the key/result mapping after
   success so later repeated invocations return that same result. Existing-request
   lookup uses seller/order across cases, not only a case's optional request ID.
6. Record approval, proposal, execution result, and timestamps in an audit trail.
   Rejection makes no business action change, but does record a rejection event.
   Persist workflow state separately so the application can resume after restart.

## Retry budget

Read retries and write retries are different. Read lookups may retry a transient
failure without a write idempotency key. CASE-011 makes both the initial tracking
call and its one retry fail, to exercise `insufficient_evidence`. Write retries
occur during action execution and require the key described in execution rule 5.
Allow at most two attempts per tool operation: one initial call plus one retry.
Retry transient failures only; do not retry access denial or policy rejection.
After an unresolved write timeout, keep the outcome unconfirmed for reconciliation,
rather than automatically issuing further writes. This budget is an engineering
choice, not policy.

See [the evaluation guide](../evals/README.md) for the CASE-011 timeout fixture.

## Audit trail versus workflow persistence

Planned storage uses two local, self-managed SQLite files: `business.sqlite` for
business records and append-only `audit_events`, and `checkpoints.sqlite` for the
LangGraph checkpointer's own tables. SQLite is file-based; a separate networked
database server is unnecessary for this MVP. File names are runtime design
choices, not existing files. Both stores must survive application restarts.

The audit trail explains what happened, why, and who approved it. It is not the
mechanism used to reconstruct graph execution. Checkpoints persist workflow state
and pending interrupts. Business records and the idempotency mapping establish
whether a write already committed. Do not infer action success merely from an
attempt event, and do not replay the audit log to resume the graph.

Each audit event includes event ID, timestamp, actor, case ID, proposal ID where
applicable, and structured details. Log evidence references and policy versions
for assessments, approvals/rejections, revalidation results, execution attempts,
and confirmed or unconfirmed outcomes. Execution attempts include a unique
attempt ID and the proposal's stable idempotency key.

The caller usually does not know a backend-generated carrier request ID before
the first response. Log its attempt ID and idempotency key before submission.
The mock backend allocates the request ID during creation and records a
`carrier_request_created` audit event with that ID in the same transaction as the
request and idempotency result. Thus a lost response cannot hide a committed
creation from the backend audit trail. The caller records the request ID when it
learns the result, either on the initial response or reconciliation/retry. Retries
may have new attempt IDs but must retain the same idempotency key.

Use native LangGraph `interrupt()` for approval and a persistent SQLite
checkpointer; resume with `Command(resume=...)` and the same thread ID. A resumed
interrupt node restarts from its beginning, so keep action submission in a later
node and make audit-event writes safe against duplicate recording during replay.
Backend idempotency remains necessary if a write is replayed after a crash.

## UI terminology

Use "Assessing delivery complaint..." while the agent gathers evidence. After
successful action execution, say "Carrier investigation request submitted" and
show the returned request ID. Do not claim the carrier has started investigating.
The seed request `INV-7001` has status `open`, meaning it is an existing unresolved
request; this is not confirmation of any particular activity by the carrier.

## Acceptance criteria

Use [the execution scenarios](../evals/execution_scenarios.md) to verify approval,
recovery, revalidation, and duplicate prevention. Audit and workflow persistence
are separate concerns even though both persist data.
