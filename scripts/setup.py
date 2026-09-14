#!/usr/bin/env python3
"""Install a backend-pinned environment before any application imports."""
import argparse
import base64
import configparser
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv
import zipfile
sys.dont_write_bytecode = True

from hardware import BACKENDS, choose_backend, detect_gpus, is_wsl, prerequisites, validate_platform

ROOT = Path(__file__).resolve().parents[1]
INDEXES = {"cpu": "cpu", "cuda": "cu128", "rocm": "rocm6.4", "xpu": "xpu"}
VERSIONS = {"torch": "2.8.0", "torchaudio": "2.8.0", "torchvision": "0.23.0"}
CHECKPOINT = "melband_roformer_instvox_duality_v2.ckpt"
CHECKPOINT_URL = "https://huggingface.co/pcunwa/Mel-Band-Roformer-InstVoc-Duality/resolve/main/" + CHECKPOINT


def run(command, dry_run=False, **kwargs):
    command = [str(item) for item in command]
    print("+ " + shlex.join(command), flush=True)
    if not dry_run:
        subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def check_backend(backend):
    import torch
    import torchaudio
    import torchvision
    expected = INDEXES[backend]
    for module in (torch, torchaudio, torchvision):
        if module.__version__ != VERSIONS[module.__name__] + "+" + expected:
            raise RuntimeError(f"Wrong {module.__name__} build: {module.__version__}; expected {VERSIONS[module.__name__]}+{expected}")
    if backend == "rocm" and not torch.version.hip:
        raise RuntimeError("Requested ROCm but this torch build has no HIP runtime")
    if backend == "cuda" and (torch.version.hip or not torch.version.cuda):
        raise RuntimeError("Requested NVIDIA CUDA but this is not a CUDA build")
    device = "cuda" if backend in ("cuda", "rocm") else backend
    if device != "cpu" and not getattr(torch, device).is_available():
        raise RuntimeError(f"{backend} runtime unavailable; CPU fallback is disabled. "
                           + prerequisites(backend))
    tensor = torch.ones((32, 32), device=device)
    result = tensor @ tensor
    # XPU can expose a device and execute simple arithmetic while a missing
    # OpenCL ICD prevents oneDNN/attention kernels from running.
    query = torch.ones((1, 2, 16, 32), device=device)
    attention = torch.nn.functional.scaled_dot_product_attention(query, query, query)
    convolution = torch.nn.functional.conv1d(
        torch.ones((1, 2, 16), device=device), torch.ones((2, 2, 3), device=device))
    if device != "cpu":
        getattr(torch, device).synchronize()
    if (result.cpu()[0, 0].item() != 32
            or not torch.allclose(attention.cpu(), torch.ones((1, 2, 16, 32)))
            or not torch.allclose(convolution.cpu(), torch.full((1, 2, 14), 6.0))):
        raise RuntimeError(f"{backend} neural tensor computation failed")
    print(f"Backend check passed: torch {torch.__version__}, device={result.device}; matmul, SDPA and Conv1d passed")


def portable_whisper(python, env, dry_run):
    # Whisper's Linux metadata unconditionally asks for NVIDIA Triton. Remove
    # only that requirement, not code or other dependencies, before resolution.
    if dry_run:
        run([python, "-m", "pip", "wheel", "--no-deps", "openai-whisper==20250625", "--wheel-dir", "<temporary-wheel-directory>"], True)
        print("Repack Whisper wheel: remove only Requires-Dist: triton; regenerate wheel RECORD; install --no-deps.")
        return
    with tempfile.TemporaryDirectory(prefix="domeoke-whisper-") as temp:
        temp = Path(temp)
        run([python, "-m", "pip", "wheel", "--no-deps", "openai-whisper==20250625", "--wheel-dir", temp], env=env)
        wheel = next(temp.glob("openai_whisper-*.whl"))
        with zipfile.ZipFile(wheel) as archive:
            entries = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
        metadata = next(name for name in entries if name.endswith(".dist-info/METADATA"))
        entries[metadata] = b"\n".join(line for line in entries[metadata].split(b"\n") if not line.lower().startswith(b"requires-dist: triton"))
        record = next(name for name in entries if name.endswith(".dist-info/RECORD"))
        rows = io.StringIO(newline="")
        writer = csv.writer(rows)
        for name, data in entries.items():
            if name != record:
                digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
                writer.writerow((name, "sha256=" + digest, len(data)))
        writer.writerow((record, "", ""))
        entries[record] = rows.getvalue().encode()
        with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        run([python, "-m", "pip", "install", "--no-deps", "--force-reinstall", wheel], env=env)


def install_assets(dry_run):
    run(["npm.cmd" if os.name == "nt" else "npm", "--prefix", ROOT / "lyrics_searcher", "install"], dry_run)
    target = ROOT / "audio_processing" / "results" / CHECKPOINT
    print(f"Checkpoint: {CHECKPOINT_URL} -> {target} (keep existing nonempty file)")
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or not target.stat().st_size:
        partial = target.with_suffix(".download")
        try:
            urllib.request.urlretrieve(CHECKPOINT_URL, partial)
            if not partial.stat().st_size:
                raise RuntimeError("Checkpoint download was empty")
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=BACKENDS, default="auto")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without installing or writing files")
    parser.add_argument("--venv", type=Path, default=ROOT / ".venv")
    parser.add_argument("--image-build", action="store_true", help="Docker build only: explicit backend, defer hardware check until startup")
    parser.add_argument("--skip-assets", action="store_true", help="Only Python dependencies; Docker stages Node/checkpoint separately")
    parser.add_argument("--check", action="store_true", help="Check installed wheel identity and execute a real backend tensor operation")
    args = parser.parse_args()
    if not (3, 10) <= sys.version_info[:2] <= (3, 12):
        parser.error("Python 3.10-3.12 is required by numpy==1.26.4/numba==0.60.0; choose a supported interpreter.")
    if args.image_build and args.backend == "auto":
        parser.error("Docker builds cannot see the host GPU. Run scripts/docker.py on the host to select --backend before building.")
    gpus = [] if args.image_build or args.check else detect_gpus()
    backend = choose_backend(args.backend, gpus)
    if args.check:
        if args.backend == "auto":
            parser.error("--check requires an explicit backend")
        check_backend(backend)
        return
    validate_platform(backend, gpus, image_build=args.image_build)
    print("Detected physical GPUs: " + ("; ".join(gpu["name"] for gpu in gpus) or "none (virtual display adapters excluded)"))
    print(f"Selected backend: {backend}\n{prerequisites(backend)}")
    for name in ("input_audio", "output_audio", "sentence_level_srt", "word_level_srt", "thumbnails", "youtube_video"):
        destination = ROOT / "processing" / name
        if args.dry_run:
            print(f"Ensure processing directory: {destination}")
        else:
            destination.mkdir(parents=True, exist_ok=True)
    if not args.dry_run and not args.image_build:
        missing = [name for name in ("ffmpeg", "node", "npm", "deno") if not shutil.which(name)]
        if missing and not args.skip_assets:
            raise RuntimeError("Install prerequisites first: " + ", ".join(missing))
    directory = args.venv.resolve()
    python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print(f"Create virtual environment: {directory}")
        if not args.dry_run:
            venv.EnvBuilder(with_pip=True).create(directory)
    if python.exists():
        installed = json.loads(subprocess.check_output(
            [str(python), "-c", "import importlib.metadata as m,json; print(json.dumps({d.metadata['Name'].lower(): d.version for d in m.distributions()}))"],
            text=True,
        ))
        incompatible = [name for name, version in VERSIONS.items()
                        if name in installed and installed[name] != version + "+" + INDEXES[backend]]
        foreign_triton = {"cpu": ("triton", "pytorch-triton-rocm", "pytorch-triton-xpu"),
                         "cuda": ("pytorch-triton-rocm", "pytorch-triton-xpu"),
                         "rocm": ("triton", "pytorch-triton-xpu"),
                         "xpu": ("triton", "pytorch-triton-rocm")}[backend]
        incompatible.extend(name for name in foreign_triton if name in installed)
        if incompatible:
            raise RuntimeError("Existing environment has incompatible backend packages: "
                               + ", ".join(incompatible) + ". Choose a fresh --venv path; do not mix vendor runtimes.")
    constraints = directory / "domeoke-constraints.txt"
    pins = [f"{name}=={version}+{INDEXES[backend]}" for name, version in VERSIONS.items()]
    pins += ["numpy==1.26.4", "numba==0.60.0", "openai-whisper==20250625", "stable-ts==2.19.1"]
    if backend != "cuda":
        pins += ["triton<0"]
    print("Persistent pip constraints:\n" + "\n".join(pins))
    if not args.dry_run:
        constraints.write_text("\n".join(pins) + "\n")
        config_path = directory / ("pip.ini" if os.name == "nt" else "pip.conf")
        config = configparser.ConfigParser()
        config.read(config_path)
        if not config.has_section("global"):
            config.add_section("global")
        config.set("global", "constraint", str(constraints))
        with config_path.open("w") as stream:
            config.write(stream)
        (directory / "domeoke-backend").write_text(backend + "\n")
    env = dict(os.environ, PIP_CONSTRAINT=str(constraints), VIRTUAL_ENV=str(directory))
    run([python, "-m", "pip", "install", "--upgrade", "pip"], args.dry_run, env=env)
    run([python, "-m", "pip", "install", *pins[:3], "--index-url", "https://download.pytorch.org/whl/" + INDEXES[backend]], args.dry_run, env=env)
    portable_whisper(python, env, args.dry_run)
    run([python, "-m", "pip", "install", "-r", ROOT / "requirements.txt"], args.dry_run, env=env)
    if backend == "rocm" and is_wsl() and not args.image_build:
        # AMD's WSL instructions require the WSL HSA library, not the Linux copy
        # bundled in upstream torch wheels. This only changes the virtualenv.
        source = Path("/opt/rocm/lib/libhsa-runtime64.so.1.2")
        print(f"Use AMD WSL HSA runtime from {source}")
        if not args.dry_run:
            if not source.exists():
                raise RuntimeError("Install AMD ROCm 6.4.2 WSL userspace first: missing " + str(source))
            torch_lib = next(directory.glob("lib/python*/site-packages/torch/lib"))
            for old in torch_lib.glob("libhsa-runtime64.so*"):
                old.unlink()
            shutil.copy2(source, torch_lib / "libhsa-runtime64.so")
    if not args.image_build:
        run([python, ROOT / "scripts/setup.py", "--backend", backend, "--check"], args.dry_run, env=env)
    else:
        print("GPU verification deferred to container startup (build has no GPU).")
    if not args.skip_assets:
        install_assets(args.dry_run)
    print(f"Run with DOMEOKE_DEVICE={backend}; environment backend recorded in {directory / 'domeoke-backend'}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        sys.exit(1)
