"""Release preparation isolation and upload integrity guards; no network/signing."""

import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import publish_release as publish


class PublishingTests(unittest.TestCase):
    def test_package_version_maps_to_valid_git_tag(self):
        tag = publish.source_tag("1.0+ppa1~ubuntu26.04.1")
        self.assertEqual(tag, "v1.0+ppa1_ubuntu26.04.1")
        subprocess.run(["git", "check-ref-format", f"refs/tags/{tag}"], check=True)

    def test_revision_includes_deleted_history_and_other_ubuntu_versions_do_not_match(self):
        self.assertEqual(publish.next_version("1.0", [
            "1.0+ppa2~ubuntu26.04.1", "1.0+ppa9~ubuntu24.04.1",
            "2.0+ppa8~ubuntu26.04.1"]), "1.0+ppa3~ubuntu26.04.1")
        with self.assertRaises(ValueError):
            publish.next_version("1.0; command", [])

    def test_history_follows_pagination_and_includes_deleted(self):
        urls = []

        def fetch(url):
            urls.append(url)
            if url == publish.API:
                return {"private": False, "publish": True}
            if "status=Deleted" in url:
                return {"entries": [{"source_package_version": "1.0+ppa3~ubuntu26.04.1"}],
                        "next_collection_link": publish.API + "?next-page"}
            return {"entries": []}

        with patch.object(publish, "fetch", side_effect=fetch):
            self.assertEqual(len(publish.publications()), 1)
        self.assertIn(publish.API + "?next-page", urls)
        self.assertTrue(any("status=Superseded" in url for url in urls))

    def test_dirty_source_is_refused_before_network_or_clone(self):
        with patch.object(publish, "run", return_value=" M file"), \
                patch.object(publish, "plan") as plan:
            with self.assertRaisesRegex(ValueError, "uncommitted"):
                publish.prepare(Path("/tmp/unused-publishing-test"))
            plan.assert_not_called()

    def test_prepare_uses_clean_commit_and_excludes_ignored_output(self):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "development"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            (source / ".gitignore").write_text("output/\n")
            (source / "output").mkdir()
            (source / "output" / "private").write_text("must not be copied")
            subprocess.run(["git", "-C", str(source), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(source), "-c", "user.name=Test",
                            "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
                            "commit", "-qm", "fixture"], check=True)
            revision = publish.run("git", "rev-parse", "HEAD", cwd=source)
            info = {"version": "1.0+ppa1~ubuntu26.04.1", "product": "1.0", "revision": revision}
            original_run = publish.run
            original_subprocess = subprocess.run

            def command(*args, **kwargs):
                if args[0] == "make":
                    return ""
                return original_run(*args, **kwargs)

            def external(args, **kwargs):
                if args[0] == "dch":
                    self.assertEqual(kwargs["env"]["DEBEMAIL"], publish.EMAIL)
                    return subprocess.CompletedProcess(args, 0)
                return original_subprocess(args, **kwargs)

            with patch.object(publish, "ROOT", source), \
                    patch.object(publish, "plan", return_value=info), \
                    patch.object(publish, "run", side_effect=command), \
                    patch.object(subprocess, "run", side_effect=external):
                publish.prepare(base / "release")
            clone = base / "release/source"
            self.assertFalse((clone / "output").exists())
            self.assertEqual(original_run("git", "rev-parse", "HEAD", cwd=clone), revision)
            self.assertEqual(original_run("git", "config", "user.signingkey", cwd=clone), publish.KEY)
            self.assertEqual(json.loads((base / "release/release.json").read_text()), info)

    def test_wrong_signer_is_rejected(self):
        with patch.object(publish, "run", return_value="[GNUPG:] VALIDSIG WRONG 2026 0 0 4 0 1 10 00 WRONG"):
            with self.assertRaisesRegex(ValueError, "publisher"):
                publish.verify_signature(Path("source.dsc"), Path("/tmp"))

    def test_tampered_upload_is_rejected_before_lintian(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            version = "1.0+ppa1~ubuntu26.04.1"
            prefix = root.parent / f"{publish.PACKAGE}_{version}"
            Path(f"{prefix}_source.changes").write_text(
                f"Source: {publish.PACKAGE}\nVersion: {version}\nArchitecture: source\n"
                "Checksums-Sha256:\n " + "0" * 64 + " 4 tampered.buildinfo\n")
            (root.parent / "tampered.buildinfo").write_bytes(b"oops")

            def command(*args, **kwargs):
                if args[:2] == ("dpkg-parsechangelog", "-S"):
                    return version if args[2] == "Version" else "resolute"
                return ""

            with patch.object(publish, "run", side_effect=command), \
                    patch.object(publish, "verify_signature"), \
                    patch.object(subprocess, "run") as external:
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    publish.inspect(root)
                external.assert_not_called()


if __name__ == "__main__":
    unittest.main()
