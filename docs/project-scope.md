# PocketKid Fork – Project Scope

This fork adapts PocketKid into a lightweight family ledger / tally book for
tracking money owed between parents and children. It is not a stored-value
wallet.

## Core use case

Parents manage a signed ledger account for each child. The balance is expressed
from the child's perspective:

- a positive balance is owed or credited to the child;
- zero is settled; and
- a negative balance is owed by the child to the family.

All three states are normal. A configured minimum balance is an authorization
rule for future debits, not a claim that negative balances are invalid.

Each child:
- has an individual login,
- can only access their own account,
- can see their current balance and ledger-entry history,
- may eventually be allowed to create or edit their own entries,
  subject to authorization rules.

Parents:
- can manage all child accounts,
- can record credits and debits,
- can approve proposed child entries.

## Key differences from upstream

The fork should support:
- positive, zero, and negative signed balances,
- clear display of negative balances,
- reliable history of account changes,
- identification of who created or changed an entry.

User-facing copy and new product work follow the terminology in
[Decision 0002](decisions/0002-family-ledger-product-model.md). Existing
internal names such as `Wallet`, `Transaction`, `deposit`, and `withdrawal`
remain where renaming would create avoidable upstream conflicts.

## Non-goals

Currently not required:
- recurring allowance automation,
- double-entry or complex financial accounting,
- multi-family or public SaaS functionality.

## Development principle

Keep divergence from upstream small.
Prefer isolated changes over architectural rewrites.
