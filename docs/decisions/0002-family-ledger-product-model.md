# 0002: Use a family-ledger product model

- Status: Accepted
- Date: 2026-09-30

## Context

Upstream PocketKid presents a virtual pocket-money wallet. This fork's primary
use case is different: it keeps a shared tally of money parents and children
owe one another. Wallet language makes a negative balance sound exceptional or
invalid even though it is a normal and useful ledger state here.

The existing Flask routes, SQLAlchemy models, and database values already
implement the required signed arithmetic and authorization boundaries. A broad
internal rename would add migration and upstream-merge risk without changing
the product behavior.

## Decision

PocketKid is presented as a lightweight family ledger / tally book. Each child
has an account containing signed entries and a running balance.

The balance is expressed from the child's perspective:

- positive: money is owed or credited to the child;
- zero: the account is settled;
- negative: money is owed by the child to the family.

A negative balance is not an error. A configured minimum balance can still
prevent a further debit; that is a parent-controlled authorization rule rather
than an available-funds model.

### Preferred terminology

| Existing concept | User-facing term | Treatment |
| --- | --- | --- |
| Wallet | Account or family ledger | Rename in UI and current product documentation. |
| Transaction | Entry; transaction where audit precision helps | Prefer entry in workflows and history; transaction remains acceptable in technical/audit contexts. |
| Deposit | Credit | Rename in UI; a credit increases the signed balance. |
| Withdrawal | Debit | Rename in UI; a debit decreases the signed balance. |
| Available balance | Balance | Remove the implication that the value represents spendable stored funds. |
| Debt | Negative balance or amount owed | Describe the sign without treating it as an invalid state. |
| Overdraft limit | Minimum balance | Describe the actual authorization rule. |
| Money movement / operation | Entry | Prefer the ledger concept. |
| Deposit/withdrawal request | Proposed credit/debit entry | Keep approval behavior while using ledger language. |
| Reward and challenge | Reward and challenge | Retain where that optional workflow is in use. |

### Compatibility boundary

Internal identifiers remain unchanged unless a later feature requires a rename.
This includes `Wallet`, `Transaction`, `OperationRequest`, `deposit`,
`withdrawal`, route names, form values, notification kinds, database table and
column names, and historical migrations. Historical ADRs may also retain the
terms used when they were written.

This boundary is intentional: user-facing copy can express the product model
without schema churn or unnecessary divergence from upstream.

### Rules for future work

New features are evaluated as ledger features:

1. State which signed entries they create or change and how the balance moves.
2. Treat positive, zero, and negative balances as valid unless a configured
   minimum blocks a proposed debit.
3. Use the preferred user-facing terms above.
4. Preserve server-side parent/child account isolation; terminology changes do
   not grant new access or capabilities.
5. Avoid internal renames that add upstream conflicts without user value.

## Consequences

Current UI copy and active product documentation use account, ledger, entry,
credit, debit, signed balance, and minimum balance language. Existing behavior,
database compatibility, request approval, and authorization remain unchanged.

This decision does not introduce double-entry accounting, arbitrary external
creditors or debtors, banking behavior, or a multi-family accounting system.
