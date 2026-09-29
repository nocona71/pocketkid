The current withdrawal flow is **child request → parent approval → wallet debit and transaction creation**. Children have individual accounts and can view their own wallets. Application checks prevent overdrafts; the declared wallet model has no nonnegative constraint.

This document records a static review of the current implementation, not an implementation proposal. No application code was changed. The review did not start the application, access the database or `.env`, or run tests. References below use repository-relative paths and line numbers from the reviewed source.

1. **Parent and child identities**

   Both roles use `User` in `pocketkid/models.py:9`: integer `id`, unique `username`, `password_hash`, `role`, and preferred language. Routes assign the roles `parent` and `child`. There is no family identifier or parent–child ownership relationship.

   `login()` in `pocketkid/routes.py:95` verifies the password and stores the user's ID in `session["user_id"]`. `current_user()` in `pocketkid/services.py:85` retrieves that ID and loads the database user. `User.verify_password()` in `pocketkid/models.py:16` checks the password hash.

   `Wallet` in `pocketkid/models.py:20` has a required, unique `child_id` foreign key to `User.id`, allowing at most one wallet per linked user. The foreign key does not itself enforce the child's role.

2. **Authorization boundaries**

   `login_required()` in `pocketkid/services.py:131` requires an authenticated user and optionally a specific role. Unauthenticated users redirect to login; users with the wrong role receive a permission message and redirect to the dashboard.

   The child branch of `dashboard()` in `pocketkid/routes.py:149` loads the wallet and filters requests and transactions by the authenticated `user.id`. `child_request_withdrawal()` in `pocketkid/routes.py:242` requires the child role and assigns `child_id=user.id`; it does not accept a target child ID from the form.

   `parent_child_wallet()` (`pocketkid/routes.py:361`) and `parent_manual_movement()` (`pocketkid/routes.py:386`) require the parent role and check that the target user is a child. `parent_decide_request()` (`pocketkid/routes.py:298`) requires the parent role and obtains the wallet owner from the stored request.

   Every parent can administer every child in the installation. There is no per-parent ownership boundary. `get_wallet_by_child()` (`pocketkid/services.py:165`) and `register_transaction()` (`pocketkid/services.py:174`) do not authorize callers; authorization resides in routes.

3. **Current withdrawal flow**

   - The form in `templates/child_dashboard.html:35` submits `amount` and optional `description` to `POST /child/request/withdrawal`. The numeric input has a minimum of `0.01` and no maximum derived from the balance.
   - Before route execution, `app_guardrails()` (`pocketkid/services.py:293`) checks setup state and processes due recurring movements for authenticated requests. Those movements can change balances before withdrawal handling.
   - The child-role decorator authorizes the request. `child_request_withdrawal()` (`pocketkid/routes.py:244`) obtains the current child and calls `parse_amount()` (`pocketkid/services.py:69`), which quantizes to two decimal places and rejects nonpositive values. Invalid input normally produces a flash message and redirect. An empty description receives the translated withdrawal-request label.
   - The route stages an `OperationRequest` with type `withdrawal`, status `pending`, the authenticated child's ID, positive amount, and description. It notifies all parents, commits, and redirects to the dashboard. Submission performs no balance check, reservation, debit, or transaction creation.
   - Approval/rejection forms in `templates/parent_dashboard.html:54` post `decision=approve` or `decision=reject` to `POST /parent/request/<request_id>/decision`.
   - `parent_decide_request()` (`pocketkid/routes.py:300`) requires an existing pending request and a recognized decision. It assigns the current parent to `reviewed_by` and sets `reviewed_at`.
   - Rejection sets status `rejected`, creates a child notification, and commits without a wallet movement (`pocketkid/routes.py:315`).
   - Approval loads the request owner's wallet. In the withdrawal branch (`pocketkid/routes.py:340`), insufficient funds cause a flash error and redirect, leaving the request pending. Otherwise, the route subtracts the amount, marks the request approved, stages a transaction with kind `withdrawal`, negative amount, and the parent as creator, then creates a child notification and commits.

   `OperationRequest` is defined in `pocketkid/models.py:37`. `notify_all_parents()` (`pocketkid/services.py:235`) targets all parent users. `create_notification()` (`pocketkid/services.py:230`) stages the database notification and attempts web push before the enclosing commit. The notification side effect therefore precedes confirmed database persistence.

4. **Balance calculation**

   `Wallet.balance` (`pocketkid/models.py:23`) is a stored running total declared as `Numeric(10, 2)`, not a sum calculated from transaction history. `get_wallet_by_child()` (`pocketkid/services.py:165`) creates a missing wallet at zero and immediately commits it.

   `parent_children()` (`pocketkid/routes.py:554`) can create a child with an initial balance; a positive initial balance also creates a transaction. Its amount parser falls back to zero for invalid/nonpositive opening amounts (`pocketkid/routes.py:562`).

   `parent_decide_request()` adds approved rewards/deposits and subtracts approved withdrawals (`pocketkid/routes.py:325`). `parent_manual_movement()` adds deposits or subtracts withdrawals (`pocketkid/routes.py:439`). `process_recurring_movements()` adds a signed amount (`pocketkid/services.py:274`). These callers update the wallet separately from staging transaction rows.

5. **Insufficient-balance enforcement**

   | Path | Function and location | Current result when balance is insufficient |
   |---|---|---|
   | Approval of child withdrawal | `parent_decide_request()`, `pocketkid/routes.py:341` | Flash error and redirect; request stays pending; no withdrawal transaction |
   | Parent manual withdrawal | `parent_manual_movement()`, `pocketkid/routes.py:435` | Flash error and redirect; no movement recorded |
   | Recurring withdrawal | `process_recurring_movements()`, `pocketkid/services.py:266` | Notify parents, advance the scheduled date, and skip that occurrence |

   All three compare the current balance with the positive withdrawal amount using `<`. Withdrawing exactly the balance is allowed. The child submission route has no such guard.

6. **Transaction persistence**

   `Transaction` (`pocketkid/models.py:54`) stores `id`, owning `child_id`, `kind`, signed `amount`, `description`, `created_at`, and nullable `created_by`. The `child` relationship identifies the account owner; `actor` resolves the creator's user ID. Amount is `Numeric(10, 2)` and creation time defaults to the current UTC time.

   `register_transaction()` (`pocketkid/services.py:174`) stages a new row with `db.session.add()`. It neither changes the wallet nor commits. Successful withdrawal approval commits the wallet, request status, transaction, and database notification together in `parent_decide_request()` (`pocketkid/routes.py:354`), subject to the missing-wallet helper's earlier commit described below.

   `Settings` (`pocketkid/config.py:23`) configures SQLite at `data/pocketkid.db`; `db` is the Flask-SQLAlchemy instance (`pocketkid/extensions.py:3`). `create_app()` (`pocketkid/__init__.py:11`) initializes it and creates missing tables.

   Transactions have no originating-request or recurring-movement foreign key, revision number, previous-value snapshot, update timestamp, or deletion audit fields. The stored running balance is not automatically derived or reconciled by `register_transaction()`.

7. **Edit and delete behavior**

   `register_routes()` (`pocketkid/routes.py:41`) contains no transaction-edit or individual transaction-delete endpoint. History views only display entries (`templates/child_dashboard.html:93`, `templates/parent_child_wallet.html:46`). Children submit requests rather than directly creating or editing persisted transactions.

   `delete_child()` (`pocketkid/routes.py:476`) requires a parent and the form value `double_confirmed=1`. It permanently deletes the child's wallet, operation requests, transactions, notifications, and recurring movements before deleting the child and committing. It records no deletion audit. Transaction history is therefore not immutable.

8. **Available authenticated-user information**

   `current_user()` (`pocketkid/services.py:85`) makes the authenticated database `User` available, including its `id`, `username`, and `role`. Account owner and acting user are distinct concepts in the models.

   | Action | Identity available and attribution recorded | Source |
   |---|---|---|
   | Child submits withdrawal | Current child; stored as `OperationRequest.child_id`, with no separate requester field | `child_request_withdrawal()`, `pocketkid/routes.py:244` |
   | Parent approves request | Current parent; stored in `reviewed_by` and `Transaction.created_by` | `parent_decide_request()`, `pocketkid/routes.py:300` |
   | Parent rejects request | Current parent; stored in `reviewed_by`; no transaction | `parent_decide_request()`, `pocketkid/routes.py:312` |
   | Manual movement | Current parent; stored in `Transaction.created_by` | `parent_manual_movement()`, `pocketkid/routes.py:388` |
   | Initial positive balance | Current parent; stored in `Transaction.created_by` | `parent_children()`, `pocketkid/routes.py:556` |
   | Recurring execution | Transaction uses the recurring definition's original `created_by`, not the authenticated user whose request triggers execution | `process_recurring_movements()`, `pocketkid/services.py:276` |
   | Child/history deletion | Current parent is available through `current_user()`, but not recorded as a deletion actor | `delete_child()`, `pocketkid/routes.py:478` |

   There is no recorded transaction-edit actor because editing is not implemented. Recurring attribution identifies the definition's creator rather than a distinct execution actor (`RecurringMovement`, `pocketkid/models.py:78`).

9. **Smallest change needed for negative balances**

   As a finding about the existing code, the smallest behavioral change for parent-approved child withdrawals alone would be removal of the insufficient-balance branch in `parent_decide_request()` (`pocketkid/routes.py:341`). The existing subtraction and signed transaction storage already express an overdraft. Parent approval and ownership checks do not need to change.

   Allowing overdrafts across all withdrawal paths would additionally require removing the equivalent blockers in `parent_manual_movement()` (`pocketkid/routes.py:435`) and `process_recurring_movements()` (`pocketkid/services.py:266`). No schema change is indicated by `Wallet` (`pocketkid/models.py:20`), which declares no nonnegative constraint. This identifies the current blockers; no implementation or policy change is made here.

   Movement inputs remain positive magnitudes, with the operation determining the stored sign. Negative opening balances are separately blocked by `parent_children()` (`pocketkid/routes.py:562`) and its form (`templates/parent_children.html:18`).

   `eur_filter()` (`pocketkid/services.py:58`) already formats negative values with a minus sign, but debt-specific presentation is absent. Parent lists hard-code the `positive` class (`templates/parent_dashboard.html:20`, `templates/parent_children.html:37`), and the child balance card still uses the available-balance label (`templates/child_dashboard.html:4`).

10. **Relevant risks**

    These are source-level findings, not demonstrated exploits or reproduced concurrency failures.

    - **Session integrity:** `Settings.SECRET_KEY` (`pocketkid/config.py:24`) has a publicly predictable fallback. Deployment with that fallback would undermine session integrity and user isolation. The effective secret was not inspected.
    - **CSRF:** The withdrawal and approval forms have no CSRF token (`templates/child_dashboard.html:37`, `templates/parent_dashboard.html:54`). `create_app()` (`pocketkid/__init__.py:11`) registers no CSRF protection. `Settings` configures `SameSite="Lax"`, but the inspected flow performs no explicit CSRF-token validation.
    - **Concurrency:** `parent_decide_request()` (`pocketkid/routes.py:300`) checks pending status without an atomic claim. It and `parent_manual_movement()` (`pocketkid/routes.py:388`) use read–modify–write balance updates. `process_recurring_movements()` (`pocketkid/services.py:251`) does not atomically claim due occurrences. Concurrent requests could cause duplicate processing, lost balance updates, or database-lock failures.
    - **Audit retention:** `delete_child()` (`pocketkid/routes.py:478`) erases history. `delete_parent()` (`pocketkid/routes.py:644`) deletes users without preserving an actor snapshot or explicitly handling historical actor references. `Transaction` (`pocketkid/models.py:54`) stores a user reference rather than immutable actor details.
    - **Commit boundaries:** `get_wallet_by_child()` (`pocketkid/services.py:165`) commits when creating a missing wallet, including other pending session changes. `create_notification()` (`pocketkid/services.py:230`) sends push before the enclosing commit, so an external notification can precede a failed database operation.
    - **Amount validation:** In `parse_amount()` (`pocketkid/services.py:69`), comparison with zero occurs outside the exception handler. A `NaN` input can raise `InvalidOperation` instead of producing an ordinary validation failure.
    - **Authorization depends on callers:** Wallet and transaction helpers have no access checks (`pocketkid/services.py:165`, `pocketkid/services.py:174`). Current child routes bind ownership to the authenticated ID, but the helper layer does not independently enforce child isolation.

11. **Missing tests**

    No test files or test configuration were found in the reviewed repository inventory. No tests were run. The following behaviors have no identified automated coverage:

    - Child A cannot access child B's wallet or history; forged child IDs do not redirect a withdrawal request to another owner; children and unauthenticated users cannot invoke parent approval, movement, or deletion routes (`dashboard()`, `child_request_withdrawal()`, `login_required()`).
    - Submission creates only a pending request; rejection creates no transaction; approval stores the expected balance, signed transaction amount, review metadata, and parent actor (`parent_decide_request()`).
    - Below-balance, exact-balance, and above-balance withdrawals in all three guarded paths, including behavior when a wallet already has a negative balance (`parent_decide_request()`, `parent_manual_movement()`, `process_recurring_movements()`).
    - Repeat and concurrent approvals, concurrent wallet updates, and a recurring occurrence executing only once (`parent_decide_request()`, `process_recurring_movements()`).
    - Invalid amount inputs, including `NaN`, rounding, and zero/negative values (`parse_amount()`).
    - Rollback consistency, missing-wallet commit behavior, and deletion/actor-reference retention (`get_wallet_by_child()`, `delete_child()`, `delete_parent()`).
    - Negative-value formatting and balance presentation (`eur_filter()` and the wallet templates cited above). Overdraft acceptance and debt-specific presentation are not current supported behaviors.

12. **Open questions and uncertainties**

    - **Runtime configuration and schema:** The effective session secret, cookie configuration, database contents, and deployed schema were not inspected. Model-level findings do not establish whether an existing database has additional constraints (`Settings`, `pocketkid/config.py:23`; `Wallet`, `pocketkid/models.py:20`).
    - **Concurrency outcomes:** The exact effects of overlapping requests depend on SQLite connection and transaction timing. The identified race conditions were not exercised (`parent_decide_request()`, `parent_manual_movement()`, `process_recurring_movements()`).
    - **Foreign-key enforcement:** The inspected setup does not explicitly enable SQLite foreign-key enforcement (`db`, `pocketkid/extensions.py:3`; `create_app()`, `pocketkid/__init__.py:11`). Whether deleting a referenced parent leaves unresolved historical references or fails under an existing runtime configuration was not tested (`delete_parent()`, `pocketkid/routes.py:644`).
    - **Missing-wallet approval:** Review metadata is assigned before `get_wallet_by_child()` (`pocketkid/routes.py:312`). If the wallet is missing, the helper's commit can persist that metadata before an insufficient-balance rejection, while status remains pending. For an existing wallet, the insufficient-balance branch has no commit. This exceptional path was not exercised.
    - **Ledger consistency:** Agreement between stored wallet balances and transaction totals was not checked against data. The implementation maintains these separately (`Wallet`, `pocketkid/models.py:20`; `register_transaction()`, `pocketkid/services.py:174`).
    - **Product scope:** Whether overdrafts should apply to approved requests, manual movements, recurring movements, and opening balances equally is unspecified. The code currently blocks each as described above.
    - **Future editing and retention:** Child transaction-edit permissions, revision history, and retention of deleted users' attribution are undefined in the current implementation (`Transaction`, `pocketkid/models.py:54`; `delete_child()`, `pocketkid/routes.py:478`). No policy is selected by this document.
