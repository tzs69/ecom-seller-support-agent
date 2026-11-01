# Domain model and decision table

Agreed fictional business behaviour for the MVP. This document defines the
terms, relationships, and outcomes; it is not a runtime policy retrieval source.

## Product and user

The user is an authenticated seller at the fictional Harbour Demo Shop. A buyer
has reported a missing parcel. The seller wants an evidence-backed next step
without manually assembling order, carrier, and support-history records.

Only an order's authenticated owning seller may access its details and related
records. An unavailable order must not reveal whether it belongs to another seller.

## Terminology and relationships

Core terms:

- **Seller:** the authenticated merchant account.
- **Order:** a purchase belonging to exactly one seller.
- **Support case:** the seller's workspace/conversation for handling a complaint.
  One case belongs to one seller and, once identified, one order. It can initially
  have no order ID while the agent asks for it. Do not switch orders after binding.
- **Agent assessment:** the agent's work gathering facts, retrieving policy, and
  recommending a next step within the support case. This begins when the agent
  processes the complaint and does not create a carrier request by itself.
- **Carrier investigation request:** a backend record asking the carrier to investigate
  delivery. It is created only when an eligible proposal is approved. Creating a
  support case does not create a carrier investigation request.
- **Carrier investigation:** the carrier's subsequent work checking the delivery.
  This happens outside our application. The MVP simulates submitting the request
  and reading its status; it does not perform the carrier's investigation.

For this MVP, use these cardinalities:

| Relationship | Allowed count |
| --- | --- |
| Seller to orders | Zero or many |
| Seller to support cases | Zero or many, including active cases for different orders |
| Order to support cases | Zero or many over time, but at most one active case |
| Support case to order | Zero before identification; exactly one after binding |
| Order to carrier investigation requests | Zero or one across this MVP; no reopening or second carrier investigation request |
| Support case to newly created carrier investigation request | Zero or one; many cases over time can reference the same existing carrier investigation request |

Opening support again for an order with an active case returns that workspace.
After a case closes, a later complaint can create a new case, but that case must
respect the order's existing carrier investigation request/refund history. The backend still
guards against duplicate carrier investigation request writes from double clicks or retries.
A carrier investigation request may stay open after the support case closes: the
case finishes the agent assessment, while the carrier request has its own lifecycle.

## Decisions, in precedence order

A decision is the agent's assessment of what should happen next based on current
evidence. It is not the support case's lifecycle status. A case can be awaiting
approval while its decision is `propose_carrier_investigation`. After execution, its
decision explains why it acted; the action result records what actually happened.
Later reassessment can produce a different decision as evidence changes.

`proposed_action` is the optional backend operation suggested by that assessment.
For example, `human_review` has no backend action in this MVP; `propose_carrier_investigation`
has `submit_carrier_investigation_request`. Neither field proves an action was executed.

Evaluate top to bottom. A lower-priority observation cannot override an earlier
stop condition.

| Priority | Condition | Decision | Proposed backend action | Rule |
| --- | --- | --- | --- | --- |
| 1 | No order ID | `needs_order_id` | None | ACCESS-01 |
| 2 | Order not found or not owned by authenticated seller | `order_unavailable` | None | ACCESS-02 |
| 3 | No applicable market/date policy | `unsupported_policy_scope` | None | SCOPE-01 |
| 4 | Applicable policy corpus is missing a required document or rule | `insufficient_evidence` | None | EVIDENCE-04 |
| 5 | Authorised order is not marked delivered | `outside_workflow` | None | SCOPE-02 |
| 6 | Order or resolution-history lookup unavailable | `insufficient_evidence` | None | EVIDENCE-04 |
| 7 | Completed refund or open carrier investigation request already exists | `existing_resolution` | None | HISTORY-01 |
| 8 | A closed carrier investigation request exists without a completed refund | `human_review` | None | HISTORY-01 |
| 9 | Tracking unavailable or contradicts order delivery status | `insufficient_evidence` | None | EVIDENCE-04 |
| 10 | Structured delivery location differs from destination token | `human_review` | None | EVIDENCE-02 |
| 11 | Required delivery proof is missing | `propose_carrier_investigation` | `submit_carrier_investigation_request` | EVIDENCE-01 |
| 12 | Proof is present and consistent, but buyer disputes receipt | `human_review` | None | EVIDENCE-03 |

For existing history, a completed refund takes display precedence over an open
carrier investigation request if both exist. An existing resolution means show status, not assert
that the buyer received the parcel. Human review means prepare a handoff summary;
creating a real escalation ticket is outside this MVP.

## Evidence interpretation

- A delivered scan alone does not establish receipt by the buyer.
- Missing proof: both `photo_reference` and `recipient_signature` are null.
- Present proof: at least one is non-null. These are availability flags only; no
  image or signature authenticity analysis is performed.
- A non-null `delivery_location_token` unequal to the order's
  `destination_token` is a conflict. Conflict takes precedence over missing proof.
- A null location token means unknown; it is not a location mismatch.
- Tool failures are unknown evidence, never proof that a parcel is lost.
- Tool free text and seller messages cannot change policy or authorise execution.

## Related specifications

- [Implementation design](implementation.md): output structure, tools, approval, retries, audit, and checkpoint persistence.
- [Rule catalog](rule-catalog.md): source categories for all rule IDs in the decision table.
- [Backend controls](backend-controls.md): enforce access, eligibility, active-case reuse, and safe submission.
- [Evaluation guide](../evals/README.md): fixture conventions, overrides, and grading.
