# Issue and Feature Management

PocketKid uses a hybrid, GitHub-native workflow. Repository documents preserve
durable product intent and decisions; GitHub Issues track actionable work and
its live state.

## Sources of truth

The repository keeps durable product intent in files and live plan/status in GitHub.

| Information | Source of truth |
| --- | --- |
| Product boundaries and non-goals | `docs/project-scope.md` |
| Product model and preferred terminology | `docs/decisions/0002-family-ledger-product-model.md` |
| Stable feature IDs and intended outcomes | GitHub Issues |
| Product and architecture decisions | `docs/decisions/` |
| Work status, discussion, and ownership | GitHub Issues |
| Prioritization and delivery view | [PocketKid Fork GitHub Project](https://github.com/users/nocona71/projects/2) |
| Implementation and review | Pull requests |
| Released behavior | `README.md` and `CHANGELOG.md` |

GitHub Issues are the live source of truth for status, ownership, discussion,
reopened items, and completion. Do not duplicate live issue state elsewhere in
repository files. Completed issues remain closed and searchable rather than being
copied into a second "done" list.

## Backlog identifiers

Features use stable IDs in the form `PK-NNN`. Put the ID at the start of every
issue title, for example `[PK-028] Editable transaction date`. IDs are never
reused, even if an item is closed as not planned.

Newly accepted ideas receive the next ID and are created directly in GitHub.
Reports that do not represent product work tracked in issues, such as a narrow
regression, do not require a `PK-NNN` ID.

## Labels and priority

The backlog's Type column maps to one and only one `type:*` label:

- `type:feature`
- `type:ux`
- `type:security`
- `type:quality`
- `type:audit`
- `type:maintenance`
- `type:bug`

Use labels for classification, not workflow state. The GitHub Project's
`Priority` single-select field is the source of truth for operational priority
and supports grouping, filtering, and sorting. Its values are `P0`, `P1`,
`P2`, and `P3`. The Project's `Status` field tracks Todo, In Progress, and
Done. In other words: durable product intent lives in the repository documents;
live execution state lives in GitHub Issues and the Project board.

Add `Size` or `Target` Project fields only when the team actively uses them;
do not duplicate these properties as labels.

## Issue content

An actionable issue states:

1. the user or operational problem;
2. the desired outcome;
3. observable acceptance criteria;
4. security, migration, and upstream-compatibility constraints;
5. explicit non-goals when scope could be misunderstood; and
6. related issues, decisions, or dependencies.

Use a parent issue and sub-issues when a feature cannot reasonably be delivered
and reviewed as one focused pull request. Record blocking relationships in
GitHub rather than only mentioning them in prose.

## Workflow

1. Search existing issues before opening a new item.
2. Capture new reports through an issue form and assign the appropriate type
   label.
3. Triage the outcome, acceptance criteria, priority, and dependencies.
4. Evaluate the proposal against the family-ledger model and preferred
   terminology before accepting wallet-oriented assumptions.
5. Mark an item Ready only when product decisions are resolved and the work is
   small enough to implement safely.
6. Develop one logical feature per branch without working directly on
   `master`.
7. Link the pull request with `Closes #NNN` so GitHub closes the issue when the
   change merges.
8. Every PR for a bug fix or feature change must reference at least one issue
   using GitHub closing syntax such as `Closes #NNN`, `Fixes #NNN`, or
   `Resolves #NNN`.
9. Close historical items as completed only after recording evidence such as a
   commit, test, or current implementation reference.

## Definition of done

An issue is done when its acceptance criteria are met, authorization boundaries
remain intact, relevant tests or checks pass, user-facing documentation is
updated where needed, and the implementing commit or pull request is linked.
Partial implementations remain open with completed criteria checked and the
remaining gap described.

## Maintenance cadence

Review the open issues before planning a delivery slice and after each release.
Close duplicates and obsolete items with a reason, reconsider stale priorities,
and split oversized work. Avoid adding recurring allowance automation unless a
new product decision explicitly brings it into scope.
