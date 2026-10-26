"""Shared test setup.

The tests run without network, Oracle or Azure: external systems are replaced by fakes,
and files are written to a temporary folder.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture
def repo_root():
    return REPO_ROOT
