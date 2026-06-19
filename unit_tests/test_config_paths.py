"""Tests for config path resolution between flat-repo and release-based layouts.

The release-based layout puts the running code under ``<app_root>/releases/<tag>/``
and keeps mutable state (``shared/``, ``current`` symlink) at the app root. Without
the resolver, ``BASE_DIR`` would refer to the release directory and ``DB_PATH``
would point at an empty ``releases/<tag>/shared/db/`` instead of the real shared
database. See https://github.com/anvie/evonic/issues/10.
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# config.py loads .env via envcrypt or dotenv on import. Neither is needed for
# pure path-resolution tests; stub them so this file works in environments
# where project deps are not installed (e.g. CI before pip install).
def _ensure_stub(name: str, **attrs):
    if name in sys.modules:
        return
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod


try:
    import backend.dotenv_loader  # noqa: F401
except ImportError:
    _ensure_stub('backend.dotenv_loader', load_dotenv=lambda *a, **kw: None)

try:
    import envcrypt  # noqa: F401
except ImportError:
    _ensure_stub('envcrypt', load=lambda *a, **kw: None)

class TestModuleLevelExports(unittest.TestCase):
    """Smoke test: APP_ROOT and DB_PATH on the loaded module are coherent."""

    def test_db_path_lives_under_app_root_shared(self):
        import config
        expected_prefix = os.path.join(config.APP_ROOT, 'shared', 'db')
        self.assertTrue(
            config.DB_PATH.startswith(expected_prefix),
            f'DB_PATH={config.DB_PATH!r} not under APP_ROOT/shared/db/',
        )

    def test_log_files_use_app_root(self):
        import config
        # Both log paths default under APP_ROOT/logs/ unless overridden via env.
        if not os.getenv('LLM_API_LOG_FILE'):
            self.assertTrue(config.LLM_API_LOG_FILE.startswith(
                os.path.join(config.APP_ROOT, 'logs')))
        if not os.getenv('EVENT_LOG_FILE'):
            self.assertTrue(config.EVENT_LOG_FILE.startswith(
                os.path.join(config.APP_ROOT, 'logs')))


if __name__ == '__main__':
    unittest.main()
