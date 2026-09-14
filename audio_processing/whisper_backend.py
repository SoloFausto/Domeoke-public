"""Backend adapter for stable-ts 2.19.1 / OpenAI Whisper 20250625.

Neural inference and median filtering stay on the selected GPU. DTW backtrace
uses Whisper's CPU implementation outside NVIDIA CUDA; Arc does not support
FP64, so conversion to double must happen after the small cost matrix transfer.
"""

import torch
import torch.nn.functional as F
import stable_whisper
import stable_whisper.alignment as alignment
import stable_whisper.timing as timing
import stable_whisper.whisper_compatibility as compatibility
from whisper.timing import dtw as whisper_dtw, dtw_cpu, median_filter as whisper_median_filter


def _nvidia_tensor(tensor):
    return tensor.device.type == "cuda" and not torch.version.hip


def median_filter(tensor, filter_width):
    if _nvidia_tensor(tensor) or tensor.device.type == "cpu":
        return whisper_median_filter(tensor, filter_width)
    if filter_width <= 0 or filter_width % 2 != 1:
        raise ValueError("Median filter width must be a positive odd number.")
    pad_width = filter_width // 2
    if tensor.shape[-1] <= pad_width:
        return tensor
    ndim = tensor.ndim
    if ndim <= 2:
        tensor = tensor[None, None, :]
    padded = F.pad(tensor, (pad_width, pad_width, 0, 0), mode="reflect")
    result = padded.unfold(-1, filter_width, 1).sort()[0][..., pad_width]
    return result[0, 0] if ndim <= 2 else result


def dtw(tensor):
    if _nvidia_tensor(tensor):
        return whisper_dtw(tensor)
    return dtw_cpu(tensor.cpu().double().numpy())


# stable-ts imports these functions by value in both timing and refinement.
# Dispatch on the tensor, not a global selected device, to support CPU callers too.
compatibility.median_filter = timing.median_filter = alignment.median_filter = median_filter
compatibility.dtw = timing.dtw = dtw


def load_alignment_model(model_name, device):
    model = stable_whisper.load_model(model_name, device="cpu")
    # Sparse COO is unsupported on XPU/MPS. These indices only select attention
    # heads in Python; no model arithmetic needs them resident on the GPU.
    heads = model.alignment_heads
    del model.alignment_heads
    try:
        model.to(device)
    finally:
        model.register_buffer("alignment_heads", heads, persistent=False)
    model.eval()
    return model
