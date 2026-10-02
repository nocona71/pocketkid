# Releasing the PocketKid fork

This fork has its own release sequence. Upstream PocketKid versions remain
owned by `pernastefano/pocketkid` and are not reused as fork versions.

## Version identity

- `VERSION` is the single source for the fork's semantic version.
- Git tags use the namespaced form `fork-v<version>`, for example
  `fork-v0.1.0`.
- The upstream base is recorded separately as an exact commit in
  `pocketkid/config.py` and displayed in App Info.
- A release branch is not used. Normal releases are made from tested commits
  on `master`.

For a stable release `0.1.0`, the workflow publishes these image tags:

- `ghcr.io/nocona71/pocketkid:0.1.0` — immutable release version;
- `ghcr.io/nocona71/pocketkid:0.1` — latest patch in the minor line;
- `ghcr.io/nocona71/pocketkid:latest` — latest stable release;
- `ghcr.io/nocona71/pocketkid:sha-<commit>` — commit-specific build.

A floating major tag is added after the project reaches `1.0.0`. It is
intentionally omitted for `0.x` because minor releases may still be breaking.

## Automated checks

Whenever a GitHub Pull Request targets this fork's `master` branch, and whenever a commit is pushed to this fork's `master`, the fork's CI workflow runs:

1. the Python test suite;
2. a temporary Docker image build;
3. a smoke test that starts Gunicorn from the image and checks the HTTP response.

A cross-repository pull request targeting `pernastefano/pocketkid:master` is governed by the upstream repository's workflows and does not trigger this fork's `pull_request` workflow.

Publishing a GitHub Release runs the checks again before the image is pushed.
The release workflow also verifies that:

- the release tag equals `fork-v` plus the value in `VERSION`;
- the version is a stable three-part semantic version;
- the tagged commit is contained in `master`;
- the built container reports the expected fork version.

The exact image that passes the container tests is pushed with OCI metadata
and receives a GitHub artifact attestation tied to its registry digest.

The same checks can be run locally:

```bash
./scripts/check
./scripts/container-smoke --build
```

## What triggers what

| Event or change | CI | GitHub release | GHCR image |
| --- | --- | --- | --- |
| Pull request opened or updated for `master` | Runs | No | No |
| Any commit pushed to `master` | Runs; Release Please also evaluates the commits | Only if a release PR is subsequently merged | Only after a release is created |
| Release-worthy Conventional Commit subject merged to `master` | Runs | Release Please opens or updates a release PR; merging it creates the release | Published after the release is created |
| Non-release commit or unparseable commit subject pushed to `master` | Runs | No release PR from that commit | No image |
| Stable GitHub Release published manually | Release checks run | Already published manually | Published if tag and version validation passes |
| Release Please workflow manually dispatched | Release Please evaluates commits | Only if it creates a release PR that is later merged | Only after a release is created |

There is no separate automatic image build for every push to `master`: a release must be created first. A successful Release Please workflow run does not necessarily mean a release PR was created; it can finish successfully after finding no release-worthy commits. In that case, regular CI still runs, but no release or image is produced.

## Prepare a release

Use Conventional Commit subjects on the commit that lands on `master`. With
squash merging, set the pull request title to that subject; with another merge
method, make sure the resulting commit subject follows the same format. A
subject such as `docs/upstream pr workflow` is not parseable and will not
trigger a release. In particular:

- `fix: ...` produces a patch release;
- `feat: ...` produces a minor release;
- a `BREAKING CHANGE:` footer or `!` marker produces a major release;
- documentation, maintenance, and other commits without a release-worthy type
  do not trigger a release.

After release-worthy changes are merged into `master`, Release Please creates
or updates a release pull request containing the next `VERSION` and
`CHANGELOG.md`. Review and merge that pull request when the accumulated changes
should be released. Do not update `VERSION` in ordinary feature pull requests.

## Publish a release

Merging the Release Please pull request creates the namespaced
`fork-v<version>` tag and GitHub Release. The same workflow then calls
**Publish release image**, which retests, builds, smoke-tests, publishes, and
attests the image.

Manually publishing a correctly named stable GitHub Release remains supported
as a recovery path. Do not move or overwrite an existing release tag.

## Verify the result

Pull the immutable version tag, not `latest`, for verification or production
rollout:

```bash
docker pull ghcr.io/nocona71/pocketkid:0.2.0
docker image inspect ghcr.io/nocona71/pocketkid:0.2.0 --format '{{json .RepoDigests}}'
```

When GitHub CLI is authenticated, verify the build provenance with:

```bash
gh attestation verify \
  oci://ghcr.io/nocona71/pocketkid:0.2.0 \
  --repo nocona71/pocketkid
```

For Docker Compose deployments, set the immutable image version in `.env`:

```dotenv
POCKETKID_IMAGE_TAG=0.2.0
```

Then pull and start it without rebuilding:

```bash
docker compose pull
docker compose up -d
```

## Failed release workflow

Do not move or overwrite a published release tag. Diagnose the failed job,
apply the fix through a new pull request, increment at least the patch version,
and publish a new release. This keeps every published version reproducible.

Long-lived release branches should only be introduced if the fork later needs
to maintain multiple supported major or minor versions in parallel.
