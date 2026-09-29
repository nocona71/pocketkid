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

Every pull request to `master`, and every push to `master`, runs:

1. the Python test suite;
2. a Docker image build;
3. a smoke test that starts Gunicorn from the image and checks the HTTP
   response.

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

## Prepare a release

Feature branches should use Conventional Commit subjects. In particular:

- `fix:` produces a patch release;
- `feat:` produces a minor release;
- a breaking-change marker produces a major release.

After changes are merged into `master`, Release Please creates or updates a
release pull request containing the next `VERSION` and `CHANGELOG.md`.
Review and merge that pull request when the accumulated changes should be
released. Do not update `VERSION` in ordinary feature pull requests.

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
