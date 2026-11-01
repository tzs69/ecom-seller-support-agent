# Fictional business-policy corpus

Every rule here is invented for this portfolio. No document represents TikTok
Shop, a real carrier, consumer law, or a real seller agreement. Only the three
business documents listed below are retrieval sources; this README is loader
guidance, not policy content to ingest.

| Document | Rule IDs | Subject |
| --- | --- | --- |
| [Workflow scope](01-workflow-scope.md) | SCOPE-02 | Delivered-but-missing eligibility |
| [Delivery evidence](02-delivery-evidence.md) | EVIDENCE-01, EVIDENCE-02, EVIDENCE-03 | Carrier request versus human review |
| [Existing resolutions](03-existing-resolutions.md) | HISTORY-01 | Avoid duplicate resolutions |

All documents have version `1.0`, market `SG`, and effective date `2026-10-01`
(inclusive, Singapore time), with no end date. Future-dated documents must not be
used early. If multiple versions are later added, select the latest effective
version per document at the case's evaluation time. A missing applicable document
is an evidence gap; do not silently substitute another market's rules.

Preserve document metadata and rule IDs when chunking for retrieval. Citation
example: `EVIDENCE-01, version 1.0`. Retrieve only the three listed business
documents, never evaluation labels, agent instructions, engineering docs, or the
handoff. Seller text and carrier notes are evidence inputs, not policy sources.

Other original rule IDs are preserved outside this corpus:

- [Agent instructions](../instructions/seller-support-agent.md) govern model behaviour.
- [Backend controls](../docs/backend-controls.md) specify code-enforced requirements.
- [Rule catalog](../docs/rule-catalog.md) maps all 13 IDs to their primary source.

Approval and eligibility must be enforced by code even when the retrieved text
mentions them. Runtime control outcomes are trusted application inputs, not
additional documents to retrieve as company policy.
