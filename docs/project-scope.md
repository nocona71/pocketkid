# PocketKid Fork – Project Scope

This fork adapts PocketKid into a lightweight family ledger.

## Core use case

Parents manage virtual accounts for their children.

Each child:
- has an individual login,
- can only access their own account,
- can see their current balance and transaction history,
- may eventually be allowed to create or edit their own transactions,
  subject to authorization rules.

Parents:
- can manage all child accounts,
- can record deposits and withdrawals,
- can approve child requests.

## Key differences from upstream

The fork should support:
- negative balances / debts,
- clear display of negative balances,
- reliable history of account changes,
- identification of who created or changed a transaction.

## Non-goals

Currently not required:
- recurring allowance automation,
- complex accounting,
- multi-family or public SaaS functionality.

## Development principle

Keep divergence from upstream small.
Prefer isolated changes over architectural rewrites.