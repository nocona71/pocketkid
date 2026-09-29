# 0001: Allow negative account balances

- Status: Accepted
- Date: 2026-09-29

## Context

PocketKid currently treats a wallet balance as an available-funds limit. A
parent-approved withdrawal, a parent-entered withdrawal, or a recurring
withdrawal is blocked when its amount exceeds the wallet balance.

This fork is a lightweight family ledger rather than a stored-value payment
system. A negative balance represents money the child owes. Preventing a debit
at zero hides that debt instead of recording it.

The existing model can already represent this state: `Wallet.balance` and
`Transaction.amount` are signed decimal values without a nonnegative database
constraint. The restriction is imposed by application checks.

## Decision

Wallet balances may be positive, zero, or negative.

Each wallet has a configurable minimum balance. It defaults to `0.00`, which
preserves PocketKid's original no-overdraft behavior. A parent may set the
minimum to zero or a negative amount for each child. Children can see their
current limit but cannot change it.

All authorized debit paths may reduce a wallet down to that minimum:

- a withdrawal requested by a child and approved by a parent;
- a withdrawal entered directly by a parent; and
- an executed recurring withdrawal.

Child withdrawal requests continue to require parent approval. This decision
does not change authentication, authorization, account ownership, or the rule
that a child can access only their own account.

User-entered withdrawal amounts remain positive magnitudes. The application
subtracts the amount from `Wallet.balance` and records the corresponding
transaction with a negative amount. Deposits remain positive transactions.

A negative balance must be presented clearly as debt in parent and child
views. Color alone is not sufficient; the interface must include a textual
debt indication while retaining the numeric sign.

No interest calculation or automatic debt collection is added.
Negative opening balances are outside the scope of this decision; debt should
arise from recorded debit transactions.

## Consequences

- Debit checks compare the resulting balance with the wallet's configured
  minimum. An attempted debit below that limit is rejected or skipped.
- `Wallet` requires a minimum-balance column and existing databases require a
  migration that initializes it to zero.
- Wallet updates and transaction creation must continue to be committed
  together so the stored balance and history agree.
- Tests must cover the zero default, configured negative limits, exact-limit
  withdrawals, and rejected withdrawals across each debit path.
- Balance displays must distinguish debt from available positive funds.
- Parent and child wallet views must show the configured limit; only parents
  may change it.
- Existing authorization boundaries remain unchanged.

This decision does not introduce transaction editing, immutable audit history,
or a general accounting system. Those concerns require separate decisions.
