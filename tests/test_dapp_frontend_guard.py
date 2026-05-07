"""
DApp frontend guard smoke test.

Codex Phase 5 review #4 / Phase 6H: README advertised
`examples/dapp_frontend/guard.js` as a tested integration surface, but
no CI step exercised it. A regression in that file would slip through
all of v2's CI. This smoke test invokes `node guard.js` and asserts on
the demo's expected output strings.

Wired as `python3 tests/test_dapp_frontend_guard.py` in CI alongside
the other test_*.py files.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUARD_JS = REPO / "examples" / "dapp_frontend" / "guard.js"


@unittest.skipUnless(shutil.which("node"), "node not on PATH")
class TestDappFrontendGuard(unittest.TestCase):
    """Run the demo and assert that each scenario fires the expected alerts.

    The demo is intentionally self-contained — it constructs an
    EAIFrontendGuard, runs three scenarios, and prints alerts. We assert
    the printed output matches the documented behavior rather than
    importing the class (the file isn't a CommonJS module today).
    """

    def setUp(self):
        self.assertTrue(GUARD_JS.exists(),
                        f"DApp frontend guard missing: {GUARD_JS}")

    def _run(self) -> str:
        result = subprocess.run(
            ["node", str(GUARD_JS)],
            capture_output=True, text=True, timeout=20,
            cwd=str(REPO),
        )
        self.assertEqual(result.returncode, 0,
                         f"node guard.js exited {result.returncode}\n"
                         f"stdout: {result.stdout}\nstderr: {result.stderr}")
        return result.stdout

    def test_governance_proposal_proxy_upgrade_blocks(self):
        out = self._run()
        self.assertIn("Scenario 1", out)
        self.assertIn("Proposal upgrades a proxy contract", out)
        # Proxy upgrade is severity:critical → action='block'
        self.assertIn("BLOCK", out.upper())

    def test_cross_protocol_concentration_warns(self):
        out = self._run()
        # The 50000/5000/3000 portfolio = ~86% in Aave → H3 high alert
        self.assertIn("Scenario 2", out)
        self.assertIn("concentration risk", out.lower())

    def test_bridge_same_address_warns(self):
        out = self._run()
        self.assertIn("Scenario 3", out)
        self.assertIn("Bridging from ethereum to arbitrum", out)
        self.assertIn("identities linked across chains", out)


if __name__ == "__main__":
    unittest.main()
