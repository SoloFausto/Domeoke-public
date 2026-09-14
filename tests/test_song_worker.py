import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from audio_processing import pipeline


class SongWorkerTests(unittest.TestCase):
    def run_worker_fixture(self, root, body):
        package = root / "audio_processing"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "worker.py").write_text(
            "import argparse, atexit, json, os, pathlib, sys, time\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--result')\n"
            "args = parser.parse_args()\n"
            "json.load(sys.stdin)\n"
            "pathlib.Path('worker.pid').write_text(str(os.getpid()))\n"
            "atexit.register(lambda: pathlib.Path('worker.exited').write_text('done'))\n"
            "print('native library diagnostic output', flush=True)\n"
            "pathlib.Path(args.result).write_text('{}')\n" + body,
            encoding="utf-8",
        )
        with patch.object(pipeline, "ROOT", root):
            return pipeline.process_audio("unused.wav", "Some lyrics", "en")

    def test_result_waits_for_worker_exit_despite_early_result_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_worker_fixture(root, "time.sleep(0.2)\n")
            self.assertEqual((root / "worker.exited").read_text(), "done")
            if os.name == "posix":
                pid = int((root / "worker.pid").read_text())
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)

    def test_failed_worker_cannot_deliver_its_result_file_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(subprocess.CalledProcessError) as raised:
                self.run_worker_fixture(root, "sys.exit(23)\n")
            self.assertEqual(raised.exception.returncode, 23)
            self.assertEqual((root / "worker.exited").read_text(), "done")
