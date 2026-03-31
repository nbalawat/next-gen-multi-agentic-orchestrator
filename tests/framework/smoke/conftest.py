"""Conftest for F4 LLM smoke tests."""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Skip smoke tests if ANTHROPIC_API_KEY is not set."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        skip_marker = pytest.mark.skip(reason="ANTHROPIC_API_KEY not set")
        smoke_dir = os.path.dirname(__file__)
        for item in items:
            # Only skip items that are in the smoke directory
            if str(item.fspath).startswith(smoke_dir):
                item.add_marker(skip_marker)
