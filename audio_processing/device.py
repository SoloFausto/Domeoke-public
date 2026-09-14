"""Device selection shared by every inference stage.

ROCm uses PyTorch's ``cuda`` namespace; Intel GPUs use ``xpu``.
Dependencies and system drivers are installed by setup, never at inference time.
"""

from contextlib import contextmanager, nullcontext
from functools import lru_cache
import gc
import logging
import os
import re
import traceback

import torch

logger = logging.getLogger(__name__)


def get_device(force_cpu=False):
    """Select an available backend, or fail if the requested GPU cannot run."""
    requested = "cpu" if force_cpu else os.environ.get("DOMEOKE_DEVICE", "auto").strip().lower()
    return _resolve_device(requested)


@lru_cache(maxsize=None)
def _resolve_device(requested):
    if requested == "auto":
        if torch.cuda.is_available():
            requested = "cuda:0"
        elif hasattr(torch, "xpu") and torch.xpu.is_available():
            requested = "xpu:0"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            requested = "mps"
        else:
            requested = "cpu"
    match = re.fullmatch(r"(cpu|cuda|rocm|xpu|mps)(?::(\d+))?", requested)
    if match is None:
        raise ValueError("DOMEOKE_DEVICE must be auto, cpu, cuda[:N], rocm[:N], xpu[:N], or mps.")
    backend, index = match.groups()
    if backend in ("cpu", "mps") and index is not None:
        raise ValueError(f"Device indices are not supported for {backend}.")
    if backend == "rocm":
        if not torch.version.hip:
            raise RuntimeError("ROCm was requested, but this PyTorch installation is not a ROCm build. Run setup with --backend rocm.")
        backend = "cuda"
    if backend in ("cuda", "xpu"):
        api = getattr(torch, backend, None)
        if api is None or not api.is_available():
            raise RuntimeError(f"{requested} is unavailable. Install the matching PyTorch backend and GPU driver, and expose the GPU to this process/container.")
        index = int(index or 0)
        if index >= api.device_count():
            raise RuntimeError(f"GPU index {index} is unavailable; {backend} reports {api.device_count()} device(s).")
        device = torch.device(backend, index)
        name = api.get_device_name(index)
    elif backend == "mps":
        if not hasattr(torch.backends, "mps") or not torch.backends.mps.is_available():
            raise RuntimeError("MPS was requested but is unavailable.")
        device, name = torch.device("mps"), "Apple Metal"
    else:
        device, name = torch.device("cpu"), "CPU"
    if device.type != "cpu":
        try:
            # Availability alone does not prove the installed wheel supports this GPU.
            sample = torch.ones((2, 2), device=device)
            if (sample @ sample).sum().item() != 8:
                raise RuntimeError("GPU tensor computation returned an incorrect result")
        except Exception as error:
            raise RuntimeError(f"{name} ({device}) was detected but cannot execute PyTorch kernels. Check GPU model, driver and wheel compatibility.") from error
    vendor = "ROCm" if device.type == "cuda" and torch.version.hip else device.type.upper()
    logger.info("Inference device: %s (%s, %s)", name, device, vendor)
    return device


def mixed_precision(device, enabled=True):
    """Use native GPU autocast; preserve float32 on CPU and MPS."""
    device = torch.device(device)
    if enabled and device.type in ("cuda", "xpu"):
        return torch.autocast(device_type=device.type, dtype=torch.float16)
    return nullcontext()


def _release_inference_memory(device):
    # Bound methods installed by stable-ts form cycles around the Whisper model.
    # Collect those before returning unused allocator blocks to the driver.
    gc.collect()
    device = torch.device(device)
    if device.type in ("cuda", "xpu"):
        backend = getattr(torch, device.type)
        with backend.device(device):
            backend.empty_cache()
    elif device.type == "mps":
        torch.mps.empty_cache()


@contextmanager
def inference_resources(device):
    """Release a completed inference stage, including failed model loads.

    Run the model-owning code in a nested function and return only CPU data or
    file paths. Locals in the caller's still-running frame cannot be collected.
    """
    try:
        yield
    except BaseException as error:
        # Preserve traceback locations, but drop tensors held by completed
        # frames, including chained errors. Active caller frames are untouched.
        pending = [error]
        seen = set()
        while pending:
            current = pending.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            traceback.clear_frames(current.__traceback__)
            pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
        try:
            _release_inference_memory(device)
        except Exception:
            logger.exception("Failed to release inference memory while handling an error")
        raise
    else:
        _release_inference_memory(device)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"PyTorch {torch.__version__}; selected device: {get_device()}")
