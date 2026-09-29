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

## Prepare a release

Use a pull request for any version change. For example, when preparing
`0.2.0`:

```bash
git switch master
git pull --ff-only origin master
git switch -c chore/release-0.2.0
```

Update `VERSION` to `0.2.0`, update user-facing documentation if required,
run the local checks, and open a pull request. Merge only after CI succeeds.

Do not create the tag before the release-preparation pull request is merged.

## Publish a release

1. Open the repository's **Releases** page on GitHub.
2. Select **Draft a new release**.
3. Create the tag `fork-v<version>` from `master`, for example
   `fork-v0.2.0`.
4. Use `PocketKid Fork <version>` as the release title.
5. Do not mark the stable release as a pre-release.
6. Generate the release notes, review them, and publish the release.
7. Wait for the **Publish release image** workflow to succeed.
8. Confirm the versioned image and its digest in GitHub Packages.

Publishing the release creates the tag. Do not create a second local tag for
the same version.

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
