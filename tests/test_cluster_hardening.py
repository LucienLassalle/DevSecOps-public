"""Le contrôle doit refuser des protections absentes ou contournées."""

import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.check_cluster_hardening import EXPECTED, read_resources, validate


class ClusterHardeningTests(unittest.TestCase):
    def setUp(self):
        self.document = {"items": []}
        for name, (container_name, image, uid) in EXPECTED.items():
            capabilities = {"drop": ["ALL"]}
            if name == "coredns":
                capabilities["add"] = ["NET_BIND_SERVICE"]
            self.document["items"].append({
                "kind": "Deployment",
                "metadata": {"name": name, "namespace": "kube-system"},
                "spec": {
                    "strategy": {"rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1}},
                    "template": {"spec": {
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": uid,
                            "seccompProfile": {"type": "RuntimeDefault"},
                        },
                        "containers": [{
                            "name": container_name, "image": image,
                            "securityContext": {
                                "runAsNonRoot": True,
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": capabilities,
                            },
                        }],
                    }},
                },
            })

    def test_accepts_complete_hardened_cluster(self):
        validate(self.document)

    def test_reads_kubectl_list(self):
        self.assertEqual(read_resources(io.StringIO(json.dumps(self.document))), self.document)

    def test_cli_accepts_multiple_pretty_printed_json_objects(self):
        resources = [{"kind": "ServiceAccount", "metadata": {"name": "coredns"}}]
        resources.extend(self.document["items"])
        content = "\n".join(json.dumps(item, indent=4) for item in resources)
        result = subprocess.run(
            [sys.executable, "scripts/check_cluster_hardening.py"],
            input=content,
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("conforme", result.stdout)

    def test_rejects_trailing_non_json_data(self):
        content = json.dumps(self.document) + "\nmessage inattendu"
        with self.assertRaises(ValueError):
            read_resources(io.StringIO(content))

    def test_rejects_empty_output(self):
        with self.assertRaises(ValueError):
            read_resources(io.StringIO(" \n\t"))

    def test_refuses_missing_component(self):
        self.document["items"].pop()
        with self.assertRaises(ValueError):
            validate(self.document)

    def test_container_cannot_override_non_root_pod_with_root(self):
        pod = self.document["items"][0]["spec"]["template"]["spec"]
        pod["containers"][0]["securityContext"]["runAsUser"] = 0
        with self.assertRaises(ValueError):
            validate(self.document)

    def test_refuses_extra_container_without_validated_protections(self):
        pod = self.document["items"][0]["spec"]["template"]["spec"]
        pod["containers"].append(copy.deepcopy(pod["containers"][0]))
        with self.assertRaises(ValueError):
            validate(self.document)

    def test_refuses_storage_container_with_writable_root(self):
        pod = self.document["items"][2]["spec"]["template"]["spec"]
        pod["containers"][0]["securityContext"]["readOnlyRootFilesystem"] = False
        with self.assertRaises(ValueError):
            validate(self.document)

    def test_refuses_unvalidated_image(self):
        pod = self.document["items"][1]["spec"]["template"]["spec"]
        pod["containers"][0]["image"] = "rancher/mirrored-metrics-server:latest"
        with self.assertRaises(ValueError):
            validate(self.document)

    def test_refuses_extra_linux_capability(self):
        pod = self.document["items"][0]["spec"]["template"]["spec"]
        pod["containers"][0]["securityContext"]["capabilities"]["add"].append("SYS_ADMIN")
        with self.assertRaises(ValueError):
            validate(self.document)


if __name__ == "__main__":
    unittest.main()
