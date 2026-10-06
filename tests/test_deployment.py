"""Vérifie le déploiement avec de faux clients, sans modifier un cluster."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipIf(os.name == "nt", "Ces scripts ciblent le runner Linux.")
class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.log = self.root / "calls"
        self.manifest = self.root / "applied.yaml"
        kubeconfig = self.root / "kubeconfig"
        kubeconfig.touch()
        self.image = "ghcr.io/prateor/devsecops@sha256:" + "a" * 64
        kubectl = self.root / "kubectl"
        kubectl.write_text('''#!/usr/bin/env bash
printf '%s\\n' "kubectl $*" >> "$TEST_LOG"
if [[ "$*" == *"get secret"* ]]; then exit "${TEST_SECRET_STATUS:-0}"; fi
if [[ "$*" == *"apply -f"* ]]; then cp "${@: -1}" "$TEST_MANIFEST"; fi
if [[ "$*" == *"rollout status"* ]]; then exit "${TEST_ROLLOUT_STATUS:-0}"; fi
if [[ "$*" == *"get deployment delivery-desk"* ]]; then
  printf '%s' "${TEST_ACTUAL_IMAGE:-$TEST_IMAGE}"
fi
''', encoding="utf-8")
        curl = self.root / "curl"
        curl.write_text('''#!/usr/bin/env bash
printf '%s\\n' "curl $*" >> "$TEST_LOG"
exit "${TEST_CURL_STATUS:-0}"
''', encoding="utf-8")
        kubectl.chmod(0o755)
        curl.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": str(self.root) + os.pathsep + os.environ["PATH"],
            "DELIVERY_KUBECONFIG": str(kubeconfig),
            "TEST_LOG": str(self.log),
            "TEST_MANIFEST": str(self.manifest),
            "TEST_IMAGE": self.image,
        }

    def run_deploy(self, image=None, **overrides):
        return subprocess.run(
            ["bash", "scripts/deploy.sh", image or self.image],
            cwd=Path(__file__).resolve().parents[1],
            env={**self.environment, **overrides},
            capture_output=True,
            text=True,
            check=False,
        )

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_deploys_exact_digest_and_checks_health(self):
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = self.manifest.read_text()
        self.assertIn("image: " + self.image, manifest)
        self.assertNotIn("kind: Service", manifest)
        self.assertNotIn("kind: PersistentVolumeClaim", manifest)
        self.assertIn("/readyz", self.calls())
        self.assertIn("/healthz", self.calls())

    def test_refuses_mutable_tag_before_contacting_cluster(self):
        result = self.run_deploy("ghcr.io/prateor/devsecops:latest")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), "")

    def test_deploys_without_direct_secret_read_permission(self):
        result = self.run_deploy(TEST_SECRET_STATUS="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("get secret", self.calls())

    def test_failed_rollout_does_not_report_healthy_application(self):
        result = self.run_deploy(TEST_ROLLOUT_STATUS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("curl ", self.calls())

    def test_wrong_image_blocks_health_check(self):
        result = self.run_deploy(TEST_ACTUAL_IMAGE="unexpected-image")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("curl ", self.calls())

    def test_health_failure_fails_deployment(self):
        result = self.run_deploy(TEST_CURL_STATUS="22")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
