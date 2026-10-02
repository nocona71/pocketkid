# PocketKid development and release workflow

This document defines the target workflow for PocketKid so that local development stays simple while validation, PR checks, and production image publication remain reliable and repeatable.

## Goals

- Keep local development in a single, reproducible environment: the devcontainer.
- Use GitHub as the source of truth for validation and release automation.
- Keep the local command surface minimal.
- Make every production image proven before publishing.
- Favor a lean automation model over custom workflow complexity.

## Core principle

The project should be developed in the devcontainer, and all important gates should live in GitHub Actions.

Developers should not need a complex local toolchain or custom shell orchestration just to validate a branch.

## Split of concerns

Use GitHub for:

- pull request and release validation
- release images in GHCR
- provenance-backed image publishing

Keep local Docker builds for:

- development
- debugging
- quick smoke validation

This separation keeps the feedback loop short for developers while keeping the release artifact authoritative, tested, and provenance-backed.

## Workflow use cases and triggers

This view distinguishes manually initiated actions from automation. `make` commands run in the devcontainer; `gh` commands require an authenticated CLI environment or can be done in the GitHub UI. Production rollout is operator-managed.

```mermaid
flowchart TB
    subgraph DEV["Developer use cases"]
        Dev(("👤<br/>Developer"))
        App["Run app<br/><b>make dev</b>"]
        Test["Run checks<br/><b>make test</b>"]
        Coverage["Local coverage report<br/><b>make coverage</b>"]
        LocalSmoke["Build and smoke local image<br/><b>make smoke</b>"]
        OpenPR["Push branch and open PR<br/><b>gh pr create</b> or GitHub UI"]
        ReviewPR["Review checks and merge PR<br/><b>gh pr checks</b>, then <b>gh pr merge</b>"]
        ReviewRelease["Review and merge release PR<br/>GitHub UI or <b>gh pr merge</b>"]
        Manual["Dispatch workflow manually<br/><b>gh workflow run ci.yml</b><br/>or <b>gh workflow run release-please.yml</b>"]
    end

    subgraph PRFLOW["Pull request workflows"]
        PREvent["PR opened, edited, synchronized, or reopened"]
        Link["Issue-link workflow<br/>feature/bug PRs need closing issue reference<br/>doc and maintenance PRs are exempt"]
        CI["CI workflow<br/>pull_request to master, push to master, workflow_dispatch"]
        Checks["<b>./scripts/check</b><br/>tests, Python syntax, locale JSON, JavaScript"]
        CISmoke["Build and smoke-test container<br/>runs after checks pass"]
        MergeFeature["Feature PR merged to master"]
    end

    subgraph RELEASE["Release Please and image publishing"]
        RP["Release Please workflow<br/>push to master or workflow_dispatch"]
        ReleasePR["Create or update release PR"]
        ReleaseCI["When release PR is created<br/>automatically dispatch ci.yml on its branch"]
        MergeRelease["Release PR merged to master"]
        TagRelease["Create version tag and GitHub Release"]
        CallPublish["workflow_call with release_tag"]
        ManualRelease["Manually publish stable release<br/>GitHub UI or <b>gh release create</b>"]
        Publish["docker-publish<br/>validate, check, build, smoke-test, push, attest"]
        GHCR["GHCR versioned and floating tags"]
    end

    subgraph OPS["Operator-managed production rollout"]
        Operator(("👤<br/>Operator"))
        Pull["Pull immutable image tag"]
        Compose["<b>docker compose pull</b><br/>then <b>docker compose up</b>"]
        Runtime["Production runtime"]
    end

    Dev --> App
    Dev --> Test
    Dev --> Coverage
    Dev --> LocalSmoke
    Dev --> OpenPR
    Dev --> Manual
    Dev --> ManualRelease
    OpenPR --> PREvent
    PREvent --> Link
    PREvent --> CI
    CI --> Checks
    Checks --> CISmoke
    Link --> ReviewPR
    CISmoke --> ReviewPR
    ReviewPR --> MergeFeature
    ReleasePR --> ReviewRelease
    ReviewRelease --> MergeRelease
    MergeFeature -->|push to master| CI
    MergeFeature -->|push to master| RP
    Manual -->|workflow_dispatch| CI
    Manual -->|workflow_dispatch| RP
    RP --> ReleasePR
    ReleasePR --> ReleaseCI
    ReleaseCI --> CI
    MergeRelease -->|push to master| RP
    RP -->|when release_created is true| TagRelease
    RP -->|when release_created is true| CallPublish
    CallPublish --> Publish
    ManualRelease -->|release.published| Publish
    Publish --> GHCR
    GHCR --> Pull
    Operator --> Pull
    Pull --> Compose
    Compose --> Runtime

    classDef manual fill:#fff1cc,stroke:#a65d00,color:#3d2b10
    classDef automatic fill:#d9ecff,stroke:#1769aa,color:#132f4c
    classDef neutral fill:#eef1f4,stroke:#59636e,color:#20252a
    class Dev,App,Test,Coverage,LocalSmoke,OpenPR,ReviewPR,ReviewRelease,Manual,MergeFeature,MergeRelease,ManualRelease,Operator,Pull,Compose manual
    class PREvent,Link,CI,Checks,CISmoke,RP,ReleasePR,ReleaseCI,TagRelease,CallPublish,Publish,GHCR automatic
    class Runtime neutral
```

**Legend:**

- Gold nodes are manually initiated.
- Blue nodes run automatically after their labeled event.
- Gray nodes are resulting environments.

Manual actions are the listed `make`, authenticated `gh`, and `docker compose` commands or GitHub UI operations. Automatic triggers are PR events, pushes to `master`, `workflow_dispatch`, and release creation. Release Please uses its default `GITHUB_TOKEN`; GitHub suppresses a new workflow run for the resulting `release.published` event, so `workflow_call` is the publishing path for a Release Please release. A manually published stable release triggers the `release.published` path. If Release Please is changed to use a PAT or GitHub App token, both publishing paths can run; the concurrency group serializes runs but does not deduplicate them. Coverage is a local report only; CI and release workflows do not enforce a coverage threshold. The issue-link workflow is a separate PR gate.

## Component view

This view shows the components and dependencies used to develop, test, build, publish, and run PocketKid. Arrows represent dependencies or connections, not workflow order.

```mermaid
flowchart LR
    subgraph HOST["Developer workstation"]
        VSCode["VS Code + Dev Containers"]
        DockerHost["Docker engine"]
        GitAccess["GitHub UI or gh CLI"]
    end

    subgraph WORKSPACE["PocketKid workspace and repository"]
        App["Flask app, tests, templates, static assets"]
        DevTools["Makefile + scripts/check + scripts/container-smoke"]
        DevConfig[".devcontainer configuration"]
        RuntimeReq["requirements.txt"]
        DevReq["requirements-dev.txt\n(runtime requirements + Coverage)"]
        ProdImage["Production Dockerfile"]
        Compose["docker-compose.yml + .env"]
        Actions["CI, PR issue-link, release-please, publish workflows"]
        ReleaseMeta["VERSION + Release Please config/manifest + CHANGELOG"]
    end

    subgraph DEVIMAGE["Devcontainer image"]
        Python["Python 3.12 + runtime packages + Coverage"]
        Node["Node LTS"]
        SystemTools["sqlite3 + git + curl"]
    end

    subgraph GITHUB["GitHub automation"]
        Repo["Repository, branches, issues, pull requests, releases"]
        Runners["GitHub Actions runners"]
        Buildx["Docker Buildx"]
        Publisher["docker-publish workflow"]
    end

    subgraph REGISTRY["Image registry and runtime"]
        GHCR["GHCR versioned image tags"]
        Attestation["Image provenance attestation"]
        Runtime["Operator-managed Docker Compose runtime\napp data volume + health/monitoring outside repo"]
    end

    VSCode -->|builds and opens| DEVIMAGE
    DockerHost -->|builds and runs| DEVIMAGE
    WORKSPACE -->|bind-mounted source| DEVIMAGE
    DevConfig -->|configures build| DEVIMAGE
    DevReq -->|installed in dev image| Python
    RuntimeReq -->|included by dev requirements| Python
    DevTools -->|invokes| App
    DevTools -->|uses| Python
    DevTools -->|JS checks use| Node
    DevTools -->|local image smoke uses| DockerHost
    GitAccess -->|PRs, reviews, merges| Repo
    Actions -->|configured in| Repo
    Repo -->|triggers| Runners
    Runners -->|CI uses runtime dependencies and checks| RuntimeReq
    Runners -->|container checks build| ProdImage
    Runners -->|release image build uses| Buildx
    ReleaseMeta -->|drives version/release PR| Repo
    Runners -->|runs| Publisher
    Publisher -->|uses to build image| Buildx
    Buildx -->|loads image to runner| Runners
    Publisher -->|pushes verified tags| GHCR
    Publisher -->|attests published digest| Attestation
    GHCR -->|published digest| Attestation
    Compose -->|operator pulls image from| GHCR
    Compose -->|starts and configures| Runtime
```

The development image contains developer tooling; the production image continues to install only `requirements.txt`. GitHub publishes verified images to GHCR but does not deploy them to the production runtime.

---

## Local development model

### Supported development environment

Use the devcontainer as the only supported local workspace.

This is already defined in [.devcontainer/devcontainer.json](../.devcontainer/devcontainer.json).

### Standard local commands

Run these commands in the devcontainer:

```bash
make dev
make test
make coverage
make smoke
```

Coverage is an informational local report; CI does not enforce a coverage threshold.
The equivalent direct commands are:

```bash
python app.py
./scripts/check
python -m coverage run --source=pocketkid -m unittest discover -s tests
python -m coverage report -m
./scripts/container-smoke --build
```

The project should avoid introducing extra local tooling unless it materially reduces friction.

---

## Pull request flow

### Developer workflow

1. Create a branch from `master`.
2. Work in the devcontainer.
3. Run the local checks before pushing.
4. Open the PR with GitHub CLI when ready:

```bash
gh pr create --fill
```

1. Use `gh` to review the checks and merge when green:

```bash
gh pr checks
gh pr merge --squash --delete-branch
```

### Branch protection expectations

Pull requests should require:

- successful CI validation
- no failing required checks
- branch up-to-date status before merge if the repo enforces it

### CI behavior

On PRs targeting `master`, GitHub Actions should run:

- Python unit tests
- Python syntax validation
- JSON validation for locale files
- JavaScript syntax validation
- Docker image build
- container smoke test

This is already implemented by [ci.yml](../.github/workflows/ci.yml).

---

## Release and versioning model

Use `release-please` for release PRs and semantic version bumps.

This keeps versioning and changelog generation automated without requiring manual edits to `VERSION` in normal feature PRs.

The current release automation is defined in [release-please.yml](../.github/workflows/release-please.yml) and [release-please-config.json](../release-please-config.json).

### Release policy

- feature PRs do not directly edit `VERSION`
- release PRs are created by release-please
- merge of the release PR creates the GitHub Release and tag
- the image publication workflow runs after the release is created

This is the right separation of concerns.

---

## Production image flow

The production image pipeline should be strict and reproducible.

### Required checks before publish

When a stable GitHub Release is published, or the reusable image workflow is called, the system:

- validate tag format
- validate `VERSION` format
- validate the tagged commit is on `master`
- rerun the project validation checks
- build the Docker image
- run a smoke test against the container
- publish only the image that passed verification
- generate provenance/attestation metadata

This is already aligned with the current workflow in [docker-publish.yml](../.github/workflows/docker-publish.yml).

### Required tagging model

Use immutable version tags for rollout and verification, for example:

```bash
docker pull ghcr.io/nocona71/pocketkid:0.2.0
```

Then support floating tags such as:

- `:major.minor`
- `:major` if appropriate
- `:latest`
- `:sha-<commit>`

The repo already documents this in [docs/RELEASING.md](./RELEASING.md).

---

## Recommended operational standard

### Standard developer flow

```bash
# in the devcontainer
make dev
make test
make coverage
make smoke
```

### Standard PR flow

```bash
gh pr create --fill
gh pr checks
gh pr merge --squash --delete-branch
```

### Standard release flow

```bash
gh release view
# release-please creates version PR
# merge release PR
# workflow builds and publishes tested image
```

This is intentionally simple and matches the actual strengths of the repo.

---

## What to avoid

The system should avoid:

- custom local release scripts that are not clearly needed
- duplicate validation logic in multiple places
- multiple overlapping release workflows
- publishing images before smoke validation has passed
- maintaining a large set of ad hoc automation wrappers

The repo is already more disciplined than the average small Flask project by keeping validation in one place and publishing only after smoke tests pass.

---

## Final recommendation

PocketKid should keep the current architecture and make it slightly leaner:

- devcontainer as the one supported local environment
- GitHub Actions for validation and release gates
- `gh` for PR creation and merge
- release-please for versioning and changelog PRs
- GHCR publishing only after successful image verification

This is close to the ideal workflow and is already largely in place.
