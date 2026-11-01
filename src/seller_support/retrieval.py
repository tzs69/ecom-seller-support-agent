"""Lexical retrieval over the three business-policy documents."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from seller_support.models import RuleRef

POLICY_FILES = (
    "01-workflow-scope.md",
    "02-delivery-evidence.md",
    "03-existing-resolutions.md",
)
REQUIRED_DOCUMENTS = {"POLICY-SCOPE", "POLICY-EVIDENCE", "POLICY-HISTORY"}
REQUIRED_RULES = {"SCOPE-02", "EVIDENCE-01", "EVIDENCE-02", "EVIDENCE-03", "HISTORY-01"}


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    title: str
    text: str
    version: str
    document_id: str
    source: str

    def reference(self) -> RuleRef:
        return RuleRef(
            rule_id=self.rule_id,
            version=self.version,
            source_type="business_policy",
        )

    def payload(self) -> dict:
        return {
            **self.reference().model_dump(),
            "title": self.title,
            "text": self.text,
            "source": self.source,
        }


class PolicyCorpus:
    def __init__(
        self,
        root: Path,
        market: str,
        at: datetime,
    ):
        self.rules: dict[str, PolicyRule] = {}
        documents = set()

        for name in POLICY_FILES:
            path = root / "policies" / name
            if not path.exists():
                continue
            _, header, body = path.read_text(encoding="utf-8").split("---", 2)
            metadata = yaml.safe_load(header)
            start = datetime.fromisoformat(str(metadata["effective_from"]))
            end = metadata.get("effective_to")
            if metadata["market"] != market or at < start:
                continue
            if end and at >= datetime.fromisoformat(str(end)):
                continue

            documents.add(metadata["document_id"])
            chunks = re.split(r"^## ([A-Z]+-\d+): ([^\n]+)\n", body, flags=re.MULTILINE)
            for index in range(1, len(chunks), 3):
                rule_id, title, text = chunks[index : index + 3]
                self.rules[rule_id] = PolicyRule(
                    rule_id=rule_id,
                    title=title.strip(),
                    text=text.strip(),
                    version=str(metadata["version"]),
                    document_id=metadata["document_id"],
                    source=f"policies/{path.name}",
                )

        self.supported = bool(documents)
        self.complete = REQUIRED_DOCUMENTS <= documents and REQUIRED_RULES <= self.rules.keys()

    def search(self, query: str) -> list[PolicyRule]:
        """Return up to three rules from the market/date-filtered corpus.

        Rank by unique lowercase word overlap with each rule's title/text, adding
        100 when its full rule ID appears in the query. Break ties by rule ID.
        No minimum score is required, so zero-overlap rules can fill spare slots.
        """
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))

        def score(rule: PolicyRule) -> int:
            words = set(re.findall(r"[a-z0-9]+", f"{rule.title} {rule.text}".lower()))
            exact_id_bonus = 100 if rule.rule_id.lower() in query.lower() else 0
            return len(terms & words) + exact_id_bonus

        ranked = sorted(self.rules.values(), key=lambda rule: (-score(rule), rule.rule_id))
        return ranked[:3]
