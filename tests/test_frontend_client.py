"""Run dependency-free JavaScript routing/polling contracts alongside the Python suite."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_frontend_client_routes_each_service_and_handles_real_job_lifecycle():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to verify the optional frontend integration example")
    project = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [node, "--test", "examples/frontend/client.test.mjs"],
        cwd=project, text=True, capture_output=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
