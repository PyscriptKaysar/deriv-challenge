# Debug report

Why each ticket got its intent, articles and escalation decision.

## T1 — `deposit_issue`

- **Intent rules matched:** deposit_issue: 'deposited' (certainty: single)
- **Retrieved:** A1 "Card deposit processing times" (TF-IDF 0.35)
- **Confidence:** 1.0 · **grounded:** True · **flags:** none
- **Escalated:** no — answered from the help article with no risk signals

## T2 — `password_reset`

- **Intent rules matched:** password_reset: 'password', 'reset email' (certainty: single)
- **Retrieved:** A2 "Password reset troubleshooting" (TF-IDF 0.52)
- **Confidence:** 1.0 · **grounded:** True · **flags:** none
- **Escalated:** no — answered from the help article with no risk signals

## T3 — `withdrawal_issue`

- **Intent rules matched:** withdrawal_issue: 'withdrawal' (certainty: single)
- **Retrieved:** A3 "Withdrawal review and declines" (TF-IDF 0.36)
- **Confidence:** 1.0 · **grounded:** True · **flags:** policy_sensitive, account_specific_request
- **Escalated:** yes — withdrawals are policy-sensitive and need an account check; asks about their own account, which only an agent can check

## T4 — `trading_advice_request`

- **Intent rules matched:** trading_advice_request: 'which asset will', 'go up', 'make profit' (certainty: single)
- **Retrieved:** A5 "No investment or trading advice" (TF-IDF 0.32)
- **Confidence:** 1.0 · **grounded:** True · **flags:** advice_request
- **Escalated:** no — trading advice is refused, so no human is needed

## T5 — `account_lock`

- **Intent rules matched:** account_lock: 'locked', 'too many login attempts' (certainty: single)
- **Retrieved:** A4 "Account lock after failed sign-in attempts" (TF-IDF 0.40)
- **Confidence:** 1.0 · **grounded:** True · **flags:** none
- **Escalated:** no — answered from the help article with no risk signals
