#!/usr/bin/env python3
"""Detect the HOST GPU, then build and launch Compose with real device access."""
import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True

from hardware import BACKENDS, choose_backend, detect_gpus, is_wsl, prerequisites, validate_platform

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=BACKENDS, default="auto")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--detach", action="store_true")
    args = parser.parse_args()
    gpus = detect_gpus()
    backend = choose_backend(args.backend, gpus)
    validate_platform(backend, gpus)
    print("Detected: " + ("; ".join(gpu["name"] for gpu in gpus) or "no physical GPUs"))
    print(f"Selected backend: {backend}\n{prerequisites(backend)}")
    service = {"build": {"args": {"DOMEOKE_BACKEND": backend}}, "environment": {"DOMEOKE_DEVICE": backend}}
    if backend == "cuda":
        service["deploy"] = {"resources": {"reservations": {"devices": [{"driver": "nvidia", "count": "all", "capabilities": ["gpu"]}]}}}
    elif backend in ("rocm", "xpu"):
        if platform.system() != "Linux":
            raise RuntimeError("AMD/Intel Docker requires running this launcher inside native Linux or a GPU-enabled WSL2 distribution, with Docker Engine there. Docker Desktop's VM cannot be assumed to expose /dev/dri or /dev/dxg.")
        if is_wsl():
            devices = ["/dev/dxg"]
            service["volumes"] = ["/usr/lib/wsl:/usr/lib/wsl:ro"]
            service["environment"]["LD_LIBRARY_PATH"] = "/usr/lib/wsl/lib:/usr/lib/wsl/drivers"
            if backend == "rocm":
                # Upstream Linux HSA runtime is not WSL-compatible; AMD's host
                # WSL userspace must be mounted ahead of the bundled library.
                source = Path("/opt/rocm/lib/libhsa-runtime64.so.1.2")
                if not source.exists():
                    raise RuntimeError("Install ROCm 6.4.2 WSL userspace first; missing " + str(source))
                service["volumes"].append("/opt/rocm/lib:/opt/rocm-wsl/lib:ro")
                service["environment"]["LD_PRELOAD"] = "/opt/rocm-wsl/lib/libhsa-runtime64.so.1.2"
        else:
            devices = ["/dev/dri"] + (["/dev/kfd"] if backend == "rocm" else [])
        missing = [device for device in devices if not Path(device).exists()]
        if missing:
            raise RuntimeError("GPU device nodes missing: " + ", ".join(missing) + ". Install/configure the vendor host driver first; no CPU fallback.")
        service["devices"] = [f"{device}:{device}" for device in devices]
        groups = set()
        for device in devices:
            paths = Path(device).glob("renderD*") if Path(device).is_dir() else [Path(device)]
            groups.update(str(path.stat().st_gid) for path in paths)
        service["group_add"] = sorted(groups)
    override = {"services": {"app": service}}
    print(json.dumps(override, indent=2))
    with tempfile.TemporaryDirectory(prefix="domeoke-compose-") as directory:
        compose = Path(directory) / "backend.json"
        command = ["docker", "compose", "--project-directory", str(ROOT), "-f", str(ROOT / "docker-compose.yml"), "-f", str(compose), "up", "--build"]
        if args.detach:
            command.append("--detach")
        print("+ " + shlex.join(command))
        if not args.dry_run:
            compose.write_text(json.dumps(override))
            subprocess.run(command, check=True, cwd=ROOT, env={**os.environ, "DOMEOKE_BACKEND": backend})


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"Docker launch failed: {error}", file=sys.stderr)
        sys.exit(1)
