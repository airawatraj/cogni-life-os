import unittest
import tempfile
from pathlib import Path

from cogni_life_os.auth import TokenStore
from cogni_life_os.config import Settings
from cogni_life_os.server import serve


class ServerSecurityTests(unittest.TestCase):
    def test_default_token_refused(self):
        with self.assertRaises(ValueError):
            serve(Settings(service_token="dev-local-change-me"), "127.0.0.1", 0)

    def test_non_loopback_bind_refused(self):
        with self.assertRaises(ValueError):
            serve(Settings(service_token="secret-token"), "0.0.0.0", 0)

    def test_token_expiry_revocation_rotation_and_rate_limit(self):
        now = [1000.0]
        with tempfile.TemporaryDirectory() as tmp:
            store = TokenStore(Path(tmp) / "tokens.json", now=lambda: now[0])
            token = store.issue("alice", ttl_seconds=10)
            self.assertTrue(store.verify(token).ok)
            now[0] = 1011.0
            self.assertEqual(store.verify(token).error, "expired_token")
            token2 = store.issue("alice", ttl_seconds=100)
            self.assertTrue(store.verify(token2).ok)
            token3 = store.rotate(token2, "alice", ttl_seconds=100)
            self.assertEqual(store.verify(token2).error, "revoked_token")
            self.assertTrue(store.verify(token3).ok)
            self.assertTrue(store.rate_limit("alice", "127.0.0.1", limit=2, window_seconds=60))
            self.assertTrue(store.rate_limit("alice", "127.0.0.1", limit=2, window_seconds=60))
            self.assertFalse(store.rate_limit("alice", "127.0.0.1", limit=2, window_seconds=60))


if __name__ == "__main__":
    unittest.main()
