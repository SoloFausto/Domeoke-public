"""Exercise Compose's real interpolation without starting containers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ComposeBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        standalone = shutil.which("docker-compose")
        if standalone:
            cls.compose = [standalone]
        elif shutil.which("docker") and subprocess.run(
            ["docker", "compose", "version"], capture_output=True
        ).returncode == 0:
            cls.compose = ["docker", "compose"]
        else:
            raise unittest.SkipTest("Docker Compose is not installed")

    def config(self, backend=None):
        env = dict(os.environ)
        env.pop("DOMEOKE_BACKEND", None)
        if backend is not None:
            env["DOMEOKE_BACKEND"] = backend
        return subprocess.run(
            [*self.compose, "--env-file", os.devnull, "-f", str(ROOT / "docker-compose.yml"),
             "config", "--format", "json"],
            env=env, capture_output=True, text=True,
        )

    def test_missing_backend_cannot_silently_build_cpu(self):
        result = self.config()
        self.assertNotEqual(result.returncode, 0)

    def test_explicit_intel_backend_survives_compose_resolution(self):
        result = self.config("xpu")
        self.assertEqual(result.returncode, 0, result.stderr)
        service = json.loads(result.stdout)["services"]["app"]
        self.assertEqual(service["build"]["args"]["DOMEOKE_BACKEND"], "xpu")
        self.assertEqual(service["environment"]["DOMEOKE_DEVICE"], "xpu")
