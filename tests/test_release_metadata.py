from __future__ import annotations

import os
import re
import unittest

os.environ.setdefault("VAPID_PUBLIC_KEY", "test-public-key")
os.environ.setdefault("VAPID_PRIVATE_KEY", "test-private-key")

from pocketkid.config import (
    APP_REPO_URL,
    APP_UPSTREAM_COMMIT,
    APP_UPSTREAM_REPO_URL,
    PROJECT_VERSION,
    VERSION_FILE,
)


class ReleaseMetadataTests(unittest.TestCase):
    def test_project_version_matches_version_file_and_semver(self):
        stored_version = VERSION_FILE.read_text(encoding="utf-8").strip()

        self.assertEqual(PROJECT_VERSION, stored_version)
        self.assertRegex(PROJECT_VERSION, r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")

    def test_fork_and_upstream_metadata_are_separate(self):
        self.assertEqual(APP_REPO_URL, "https://github.com/nocona71/pocketkid")
        self.assertEqual(APP_UPSTREAM_REPO_URL, "https://github.com/pernastefano/pocketkid")
        self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{40}", APP_UPSTREAM_COMMIT))
        self.assertNotEqual(APP_REPO_URL, APP_UPSTREAM_REPO_URL)


if __name__ == "__main__":
    unittest.main()
