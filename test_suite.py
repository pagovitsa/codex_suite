"""Run with Python 3.12+: python test_suite.py. No Docker or OpenAI calls."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from init_suite import initialize

sys.path.insert(0, str(Path(__file__).parent / "broker" / "src"))
from codex_broker.openai_auth import OpenAICompatAuth, OpenAICompatAuthError


class SuiteTests(unittest.TestCase):
    def test_linux_entrypoint_uses_lf(self):
        script = Path(__file__).parent / "broker/scripts/codex-bwrap-no-proc"
        self.assertTrue(script.read_bytes().startswith(b"#!/usr/local/bin/python3\n"))

    def test_keys_preserved_and_bound_to_correct_permissions(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            directory = Path(tmp)
            initialize(directory)
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            initialize(directory)
            self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})
            auth = OpenAICompatAuth(json.loads((directory / "bindings.json").read_text()))
            for name, profile in (("chat", "default"), ("agent", "agent")):
                key = (directory / (name + ".key")).read_text().strip()
                binding = auth.resolve_authorization("Bearer " + key)
                self.assertEqual((binding.owner_id, binding.config_profile, binding.cwd),
                                 ("local", profile, "/workspaces/project"))
            for header in (None, "Bearer invalid", "Bearer " + (directory / "internal.key").read_text().strip()):
                with self.assertRaises(OpenAICompatAuthError):
                    auth.resolve_authorization(header)

    def test_existing_invalid_key_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp) / "internal.key"
            key.write_text("invalid")
            with self.assertRaises(ValueError):
                initialize(tmp)
            self.assertEqual(key.read_text(), "invalid")

    def test_changed_binding_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            initialize(tmp)
            path = Path(tmp) / "bindings.json"
            path.chmod(0o600)
            path.write_text("{}")
            with self.assertRaises(ValueError):
                initialize(tmp)
            self.assertEqual(path.read_text(), "{}")

    def test_client_rejects_redirect_before_sending_credentials(self):
        from client import NoRedirect
        import urllib.error
        import urllib.request
        request = urllib.request.Request("http://localhost/", headers={"Authorization": "Bearer private"})
        with self.assertRaises(urllib.error.HTTPError):
            NoRedirect().redirect_request(request, None, 302, "Found", {}, "https://example.com/")


if __name__ == "__main__":
    unittest.main(verbosity=2)
