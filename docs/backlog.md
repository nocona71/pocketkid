# PocketKid Feature Backlog

This catalog joins the product work identified for the PocketKid fork. GitHub
Issues are the source of truth for live status, discussion, and implementation
links; this document preserves stable feature IDs, priorities, and intended
outcomes. See [Issue and feature management](issue-management.md) for the
workflow.

Recurring allowance automation is intentionally not included. It is not a
current product requirement, even though upstream already contains recurring
movement functionality.

| ID | Priority | Type | Feature | Description / acceptance criteria |
| --- | --- | --- | --- | --- |
| [PK-001](https://github.com/nocona71/pocketkid/issues/11) | P0 | Feature | Negative balances | Permit authorized withdrawals down to a configurable per-child minimum balance, allowing debt when that minimum is negative. |
| [PK-002](https://github.com/nocona71/pocketkid/issues/14) | P0 | UX | Debt display | Clearly distinguish negative balances from positive balances in parent and child views using text as well as color. |
| [PK-003](https://github.com/nocona71/pocketkid/issues/15) | P0 | Security | Child account isolation | A child can only view and interact with their own wallet, transactions, and requests. |
| [PK-004](https://github.com/nocona71/pocketkid/issues/13) | P0 | Quality | Withdrawal-flow tests | Cover positive, zero, and negative balances; parent and child actions; and authorization boundaries. |
| [PK-005](https://github.com/nocona71/pocketkid/issues/12) | P1 | Feature | Child-created transactions | Allow a child to record transactions on their own account, subject to configurable authorization and approval rules. |
| [PK-006](https://github.com/nocona71/pocketkid/issues/20) | P1 | Feature | Transaction editing | Allow permitted users to correct an existing transaction instead of requiring manual compensating entries. |
| [PK-007](https://github.com/nocona71/pocketkid/issues/16) | P1 | Feature | Transaction deletion or reversal | Support controlled reversal of erroneous transactions without silently destroying history. |
| [PK-008](https://github.com/nocona71/pocketkid/issues/19) | P1 | Audit | Actor tracking | Record which authenticated user created, approved, changed, reversed, or deleted a transaction. |
| [PK-009](https://github.com/nocona71/pocketkid/issues/18) | P1 | Audit | Change history | Preserve a reliable audit trail showing what changed, when, and by whom. |
| [PK-010](https://github.com/nocona71/pocketkid/issues/17) | P1 | UX | Transaction details | Show transaction type, amount, date and time, description, creator, approval status, and relevant audit information. |
| [PK-011](https://github.com/nocona71/pocketkid/issues/24) | P1 | Feature | Notes and descriptions | Support useful free-text descriptions for deposits, withdrawals, debts, repayments, and corrections. |
| [PK-012](https://github.com/nocona71/pocketkid/issues/25) | P1 | Feature | Parent direct booking | Allow parents to create deposits and withdrawals without going through the child-request workflow. |
| [PK-013](https://github.com/nocona71/pocketkid/issues/21) | P1 | Feature | Child approval workflow | Allow child-created money movements to require parent approval according to configuration. |
| [PK-014](https://github.com/nocona71/pocketkid/issues/22) | P2 | UX | Debt repayment workflow | Make repayments against a negative balance easy to record and show the remaining debt. |
| [PK-015](https://github.com/nocona71/pocketkid/issues/23) | P2 | UX | Improved account history | Provide a chronological ledger-style history with a running balance. |
| [PK-016](https://github.com/nocona71/pocketkid/issues/27) | P2 | UX | Filtering | Filter history by date, transaction type, status, creator, and amount. |
| [PK-017](https://github.com/nocona71/pocketkid/issues/26) | P2 | Feature | Transaction categories | Support optional categories such as allowance, purchase, loan, repayment, gift, and correction. |
| [PK-018](https://github.com/nocona71/pocketkid/issues/28) | P2 | Feature | Per-child permissions | Configure whether a child may view, create requests, create transactions, or edit their own entries. |
| [PK-019](https://github.com/nocona71/pocketkid/issues/30) | P2 | UX | Mobile-first improvements | Optimize wallet and transaction workflows for phone use. |
| [PK-020](https://github.com/nocona71/pocketkid/issues/29) | P2 | Feature | Export | Export a child's transaction history, initially as CSV. |
| [PK-021](https://github.com/nocona71/pocketkid/issues/33) | P3 | Feature | Notifications | Notify parents about child requests and children when requests are approved or rejected. |
| [PK-022](https://github.com/nocona71/pocketkid/issues/31) | P3 | Feature | Balance thresholds | Optionally warn when a balance drops below a configurable threshold. |
| [PK-023](https://github.com/nocona71/pocketkid/issues/35) | P3 | Feature | Multiple parent accounts | Support multiple parent or administrator accounts with access to the same family wallets. |
| [PK-024](https://github.com/nocona71/pocketkid/issues/32) | P3 | Audit | Admin activity view | Give parents a view of recent account-changing actions across all children. |
| [PK-025](https://github.com/nocona71/pocketkid/issues/34) | P3 | UX | German localization | Provide German UI translations alongside English and Italian. |
| [PK-026](https://github.com/nocona71/pocketkid/issues/37) | P3 | Maintenance | Upstream compatibility | Keep fork-specific behavior isolated so upstream changes can be merged with minimal conflicts. |
| [PK-027](https://github.com/nocona71/pocketkid/issues/40) | P2 | Bug | Push-notification localization | Ensure every push-notification label follows the active language and remove stray status punctuation. |
| [PK-028](https://github.com/nocona71/pocketkid/issues/36) | P1 | Feature | Editable transaction date | Default a new transaction to today while allowing permitted users to record a past effective date. |
| [PK-029](https://github.com/nocona71/pocketkid/issues/39) | P3 | Maintenance | Docker Compose deployment | Provide a documented Docker Compose configuration with persistent application data. |
| [PK-030](https://github.com/nocona71/pocketkid/issues/38) | P1 | Feature | Configurable currency | Display currency anywhere amounts are shown or edited and allow parents to configure it. |

The first coherent delivery slice was `PK-001` through `PK-004`: negative
balances, explicit debt presentation, preserved child isolation, and tests.
The first three are implemented; the test item remains open until the complete
authorization matrix is covered.
