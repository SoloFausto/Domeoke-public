"""Standard-library-only host discovery; importing this module never imports torch."""
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path

BACKENDS = ("auto", "cpu", "cuda", "rocm", "xpu")
AMD_MATRIX = "https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-6.4.2/docs/compatibility.html"
INTEL_GUIDE = "https://www.intel.com/content/www/us/en/developer/articles/tool/pytorch-prerequisites-for-intel-gpu/2-8.html"


def is_wsl():
    return platform.system() == "Linux" and "microsoft" in platform.release().lower()


def command_output(command):
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def detect_gpus():
    gpus = []
    names = {}
    if platform.system() == "Linux":
        for line in command_output(["lspci", "-D", "-nn"]).splitlines():
            names[line.split()[0]] = line
        for pci in sorted(Path("/sys/bus/pci/devices").glob("*")):
            try:
                if int((pci / "class").read_text().strip(), 16) >> 16 != 3:
                    continue
                vendor = (pci / "vendor").read_text().strip().removeprefix("0x").lower()
                device = (pci / "device").read_text().strip().removeprefix("0x").lower()
            except (OSError, ValueError):
                continue
            if vendor in ("10de", "1002", "8086"):
                gpus.append(dict(vendor=vendor, device=device, name=names.get(pci.name, f"PCI {vendor}:{device}"), source="sysfs"))
    if platform.system() == "Windows" or is_wsl():
        powershell = shutil.which("powershell.exe")
        if not powershell and is_wsl():
            host_shell = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
            if host_shell.exists():
                powershell = str(host_shell)
        if powershell:
            raw = command_output([powershell, "-NoProfile", "-NonInteractive", "-Command",
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-CimInstance Win32_VideoController | Select-Object Name,PNPDeviceID | ConvertTo-Json -Compress"])
            try:
                adapters = json.loads(raw.lstrip("\ufeff")) if raw else []
                for adapter in ([adapters] if isinstance(adapters, dict) else adapters):
                    match = re.search(r"PCI\\VEN_(10DE|1002|8086)&DEV_([0-9A-F]{4})", adapter.get("PNPDeviceID", ""), re.I)
                    if match:
                        vendor, device = (value.lower() for value in match.groups())
                        gpus.append(dict(vendor=vendor, device=device, name=adapter.get("Name", ""), source="Windows host"))
            except (ValueError, TypeError):
                pass
    return gpus


def supported_rocm(gpu):
    # Marketing names matter: shared PCI IDs can include unsupported SKUs.
    name = gpu["name"].upper().replace("(TM)", "").replace("™", "")
    patterns = [r"\bRX 90(?:70(?: XT| GRE)?|60(?: XT)?)\b", r"\bRX 7900 (?:XTX|XT|GRE)\b",
                r"\bRX 7800 XT\b", r"\b(?:AI )?PRO (?:R9700|W7900|W7800|W7700)\b"]
    if not is_wsl():
        patterns.append(r"\bRX 7700 XT\b")
    return gpu["vendor"] == "1002" and any(re.search(pattern, name) for pattern in patterns)


def supported_xpu(gpu):
    # Do not mistake legacy Intel UHD/Iris graphics for an Arc-capable device.
    return gpu["vendor"] == "8086" and ("arc" in gpu["name"].lower()
        or "data center gpu max" in gpu["name"].lower()
        or gpu["device"] in {"e202", "e20b", "56a0", "56a1", "56a2", "56a5", "56a6"})


def choose_backend(requested, gpus):
    if requested != "auto":
        return requested
    # Stable order among eligible accelerators, not unqualified vendor IDs.
    if any(gpu["vendor"] == "10de" for gpu in gpus):
        return "cuda"
    if any(supported_xpu(gpu) for gpu in gpus):
        return "xpu"
    if platform.system() == "Linux" and any(supported_rocm(gpu) for gpu in gpus):
        return "rocm"
    return "cpu"


def validate_platform(backend, gpus, *, image_build=False):
    if platform.system() not in ("Linux", "Windows") or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("This installer supports x86-64 Linux/WSL2 and Windows only. These GPU wheel plans do not support macOS or ARM.")
    if backend == "rocm":
        if platform.system() != "Linux":
            raise RuntimeError("ROCm 6.4 wheels require Linux or supported WSL2, not native Windows. Use --backend cpu or a supported Linux/WSL host.")
        if not image_build and not any(supported_rocm(gpu) for gpu in gpus):
            raise RuntimeError("No officially supported Radeon ROCm 6.4 GPU identified. Generic AMD iGPUs and unknown SKUs are not supported; install pciutils if Linux names are missing. Matrix: " + AMD_MATRIX)
        if not image_build:
            os_info = platform.freedesktop_os_release()
            supported_os = (os_info.get("ID") == "ubuntu" and os_info.get("VERSION_ID") in ("22.04", "24.04")) or (not is_wsl() and os_info.get("ID") == "rhel" and os_info.get("VERSION_ID") == "9.6")
            if not supported_os:
                raise RuntimeError("ROCm 6.4 Radeon requires Ubuntu 22.04/24.04 or native RHEL 9.6. " + AMD_MATRIX)
    if backend == "xpu" and not image_build and not any(supported_xpu(gpu) for gpu in gpus):
        raise RuntimeError("No supported Intel Arc/Max GPU identified; legacy Intel display GPUs do not support this XPU plan. " + INTEL_GUIDE)
    if backend == "cuda" and not image_build and not any(gpu["vendor"] == "10de" for gpu in gpus):
        raise RuntimeError("No physical NVIDIA GPU identified. Use --backend cpu for CPU execution; GPU selection never silently falls back.")


def prerequisites(backend):
    common = "Python 3.10-3.12; FFmpeg, Node.js/npm, Deno (yt-dlp), and PortAudio development libraries/compiler. No host drivers are installed by this script."
    extra = {
        "cpu": "CPU wheels; no GPU driver required.",
        "cuda": "CUDA 12.8-compatible NVIDIA driver (R570+ recommended); Docker additionally needs NVIDIA Container Toolkit. https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html",
        "rocm": "Install AMD ROCm 6.4.2 prerequisites for a matrix-listed Radeon/OS; Linux needs amdgpu, /dev/kfd and /dev/dri permissions. WSL needs Adrenalin 25.8.1 for WSL2, /dev/dxg and ROCm WSL userspace. PyTorch 2.8 wheels are upstream-supported, not AMD's production-validated 2.6 stack. " + AMD_MATRIX,
        "xpu": "Install Intel GPU driver, Level Zero GPU compute runtime (libze1 plus libze-intel-gpu1, formerly intel-level-zero-gpu), and intel-opencl-icd with its ICD registration. libze_intel_gpu.so.1 must be available; the loader alone is insufficient, and SDPA/Conv1d also need OpenCL. Linux requires render-group access. WSL needs current Windows Intel driver, /dev/dxg and Linux userspace runtime. Intel's 2.8 matrix excludes B-series on Ubuntu 24.04/WSL; B-series there is unvalidated and must pass the real runtime check. " + INTEL_GUIDE,
    }
    return common + "\n" + extra[backend]
