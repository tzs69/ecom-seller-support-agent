# Rule catalog

All 13 original IDs are preserved. Each ID has one primary definition below;
other documents may reference it or specify complementary enforcement/explanation.
An ID's prefix does not determine its category. Current rule version is `1.0`;
business applicability comes from the policy document's own metadata. This is a
pre-implementation reorganisation, not a new business-policy effective date.

| Rule ID | Primary source type | Primary definition |
| --- | --- | --- |
| ACCESS-01 | `agent_instruction` | [Agent instructions](../instructions/seller-support-agent.md) |
| ACCESS-02 | `backend_control` | [Backend controls](backend-controls.md) |
| SCOPE-01 | `backend_control` | [Backend controls](backend-controls.md) |
| SCOPE-02 | `business_policy` | [Workflow scope](../policies/01-workflow-scope.md) |
| EVIDENCE-01 | `business_policy` | [Delivery evidence](../policies/02-delivery-evidence.md) |
| EVIDENCE-02 | `business_policy` | [Delivery evidence](../policies/02-delivery-evidence.md) |
| EVIDENCE-03 | `business_policy` | [Delivery evidence](../policies/02-delivery-evidence.md) |
| EVIDENCE-04 | `backend_control` | [Backend controls](backend-controls.md) |
| HISTORY-01 | `business_policy` | [Existing resolutions](../policies/03-existing-resolutions.md) |
| ACTION-01 | `backend_control` | [Backend controls](backend-controls.md) |
| ACTION-02 | `backend_control` | [Backend controls](backend-controls.md) |
| ACTION-03 | `backend_control` | [Backend controls](backend-controls.md) |
| ACTION-04 | `agent_instruction` | [Agent instructions](../instructions/seller-support-agent.md) |

## How references are used

- Retrieval and `policy_refs` use only `business_policy` sources.
- Agent instructions are loaded as system instructions, not retrieved as policy.
- Backend controls become code checks; their trusted outcomes may be passed to
  the model for explanation. Source documents themselves need not enter context.
- `rule_refs` records supporting rule ID, version, and source type across all
  categories. References must originate from actual policy matches, control
  outcomes, or applicable instruction rules, rather than invented model citations.
- Evaluations use `required_rule_ids`, because a case may depend on access,
  approval, or instruction rules in addition to retrieved business policy.

The former evaluation field `required_policy_ids` was renamed to
`required_rule_ids` during cleanup. IDs and expected case outcomes are unchanged.
Existing evidence references and rule versions remain valid after source moves.
The former policy files for access and action approval have been removed; use
this catalog to find the relocated definitions instead of ingesting stale copies.
