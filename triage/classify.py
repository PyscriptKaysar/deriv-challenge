"""CLASSIFY_INTENT: keyword rules that map ticket text to one of the six intents.

Rules, not a model: they're deterministic, free, work without a key, and the
trading-advice check never depends on a model behaving. Anything with a
`classify(text) -> Classification` method can replace RuleClassifier.
"""

import re
from dataclasses import dataclass
from typing import Literal, Protocol

from triage.schemas import Intent

# Checked in this order. Trading advice always wins if it matches at all
# (safety first); otherwise the intent with the most matching patterns wins,
# and a tie goes to whichever comes first here.
PRIORITY: tuple[Intent, ...] = (
    "trading_advice_request",
    "account_lock",
    "password_reset",
    "withdrawal_issue",
    "deposit_issue",
)

_ASSET = r"(?:assets?|stocks?|shares?|coins?|crypto|currenc(?:y|ies)|pairs?|markets?)"

PATTERNS: dict[Intent, tuple[str, ...]] = {
    "trading_advice_request": (
        rf"\bwhich {_ASSET} (?:to|will|should|is going)\b",
        r"\bgo(?:es|ing)? (?:up|down)\b",
        r"\bpredict\w*",
        r"\bforecast\w*",
        r"\b(?:make|making|earn|earning) (?:a |some )?(?:profit|money|returns?)\b",
        r"\bprofit guarantees?\b|\bguaranteed? (?:a )?(?:profits?|returns?)\b",
        r"\b(?:good|best|right) (?:buy|investment|trade|time to (?:buy|sell|trade|invest))\b",
        r"\bshould i (?:buy|sell|invest|trade|hold)\b",
        r"\bbuy or sell\b",
        r"\bsignals?\b",
        r"\b(?:investment|trading|financial) advice\b",
        rf"\b{_ASSET} recommendations?\b|\brecommend\w* (?:an? |which |what )?{_ASSET}",
    ),
    "account_lock": (
        r"\block(?:ed)?\b",
        r"\blocked out\b|\bunlock\w*",
        r"\b(?:too many|repeated|several|multiple|failed) (?:\w+ )?(?:login|log-in|log in|sign-in|sign in|password) attempts\b",
        r"\baccount (?:is |was |got |has been )?blocked\b",
        r"\bcool-?down\b",
    ),
    "password_reset": (
        r"\bpassword\b",
        r"\breset (?:e-?mail|link)s?\b|\b(?:e-?mail|link) to reset\b",
    ),
    "withdrawal_issue": (
        r"\bwithdr[ae]w\w*",
        r"\bcash(?:ing)? ?out\b",
        r"\bpay ?outs?\b",
    ),
    "deposit_issue": (
        r"\bdeposit\w*",
        r"\btop[- ]?ups?\b|\btopped up\b",
        r"\bfund(?:ed|ing)? (?:my|the) account\b",
    ),
}

_COMPILED = {intent: [re.compile(p, re.IGNORECASE) for p in pats] for intent, pats in PATTERNS.items()}


@dataclass(frozen=True)
class Classification:
    intent: Intent
    # Every intent with at least one match -> the text each pattern matched.
    matches: dict[str, tuple[str, ...]]

    @property
    def ranked_intents(self) -> tuple[str, ...]:
        """The chosen intent first, then any others that matched, in priority order."""
        if self.intent == "other":
            return ()
        return (self.intent, *(i for i in self.matches if i != self.intent))

    @property
    def certainty(self) -> Literal["single", "conflict", "none"]:
        if not self.matches:
            return "none"
        return "single" if len(self.matches) == 1 else "conflict"


class Classifier(Protocol):
    def classify(self, text: str) -> Classification: ...


class RuleClassifier:
    def classify(self, text: str) -> Classification:
        matches: dict[str, tuple[str, ...]] = {}
        for intent in PRIORITY:
            found = tuple(m.group(0) for regex in _COMPILED[intent] if (m := regex.search(text)))
            if found:
                matches[intent] = found

        if not matches:
            intent: Intent = "other"
        elif "trading_advice_request" in matches:
            intent = "trading_advice_request"
        else:
            # max() keeps the first of equal counts, and matches is in PRIORITY order.
            intent = max(matches, key=lambda i: len(matches[i]))
        return Classification(intent=intent, matches=matches)
