from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_site_production_guard_node_suite():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js não está disponível neste ambiente de testes.")

    raiz = Path(__file__).resolve().parents[1]
    resultado = subprocess.run(
        [node, "--test", "tests/site-production-guard.test.js"],
        cwd=raiz,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert resultado.returncode == 0, (
        "A suíte Node do site-production-guard falhou.\n"
        f"STDOUT:\n{resultado.stdout}\n"
        f"STDERR:\n{resultado.stderr}"
    )
