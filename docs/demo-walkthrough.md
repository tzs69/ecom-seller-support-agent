# Three demo walkthroughs

All statements below follow invented rules. Example wording is illustrative, not
an exact-string requirement. Reset runtime state between walkthroughs.

## 1. Missing proof: CASE-001

**Seller:** "The buyer says this never arrived, but tracking says delivered.
Can we refund them?" Order: `SG-1042`.

**Evidence:** Authorised SG order, SGD 85.00, marked delivered. Tracking agrees,
location matches, but neither a delivery photo nor recipient signature exists.
Resolution history is empty.

**Recommendation:** "The carrier recorded delivery, but no photo or recipient
signature is available. Under EVIDENCE-01 (v1.0), I recommend submitting a carrier investigation request. This does not establish who received the parcel or authorise a
refund. Please review the proposal before I create the carrier investigation request."

**Controls:** Approve / Reject. Approval creates one carrier investigation request and displays
the actual returned ID. Rejection creates nothing. Before approval, the screen
must say "proposed", not "submitted".

**Optional unsent buyer reply:** "We're checking the delivery information for your
order. We'll share an update when we have more information."

## 2. Conflicting evidence: CASE-002

**Seller:** "The buyer says the parcel was delivered somewhere else. Please
investigate." Order: `SG-1043`.

**Evidence:** Destination token is `LOC-B`; carrier delivery token is `LOC-X`.
A photo reference exists, but the app has not inspected the image.

**Recommendation:** "The order destination and recorded delivery location differ.
Under EVIDENCE-02 (v1.0), this needs human review. I have prepared a summary of the
discrepancy; I haven't submitted a carrier investigation request or determined who is at fault."

**Result:** A handoff summary, no executable action and no approval button. Do not
claim to have verified the photo or created an escalation ticket.

## 3. Existing carrier investigation request: CASE-003

**Seller:** "The buyer is asking again about their missing parcel. Submit another
carrier investigation request." Order: `SG-1044`.

**Evidence:** Carrier investigation request `INV-7001` is already open.

**Recommendation:** "Carrier investigation request INV-7001 is already open for this order. Under
HISTORY-01 (v1.0), I won't create another. The recorded status is open; no confirmed
completion date is available."

**Result:** Display the existing record. No executable action or approval button.

## Suggested review order tonight

Read these examples first, then the policy sections they cite. Review the remaining
case/answer pairs for boundaries: proof present, refund completed, missing ID,
unknown/unauthorised order, unsupported market, in-transit order, timeout, and
embedded instructions. Finish with the execution scenarios before starting code.
