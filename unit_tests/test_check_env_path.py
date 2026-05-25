"""Tests for check_env_path: .env.example and template files should be allowed."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.tools.safety_checker import check_env_path


# ============================================================================
# Template files (.env.example, .env.sample, .env.template) should be allowed
# ============================================================================

def test_env_example_allowed():
    result = check_env_path(".env.example")
    assert result["blocked"] is False


def test_env_sample_allowed():
    result = check_env_path(".env.sample")
    assert result["blocked"] is False


def test_env_template_allowed():
    result = check_env_path(".env.template")
    assert result["blocked"] is False


def test_env_example_in_path_allowed():
    result = check_env_path("/project/config/.env.example")
    assert result["blocked"] is False


def test_env_sample_in_nested_path_allowed():
    result = check_env_path("apps/web/.env.sample")
    assert result["blocked"] is False


# ============================================================================
# Real .env files should still be blocked
# ============================================================================

def test_env_blocked():
    result = check_env_path(".env")
    assert result["blocked"] is True
    assert result["requires_approval"] is True


def test_env_local_blocked():
    result = check_env_path(".env.local")
    assert result["blocked"] is True


def test_env_production_blocked():
    result = check_env_path(".env.production")
    assert result["blocked"] is True


def test_env_development_blocked():
    result = check_env_path(".env.development")
    assert result["blocked"] is True


def test_env_in_path_blocked():
    result = check_env_path("/project/.env")
    assert result["blocked"] is True
