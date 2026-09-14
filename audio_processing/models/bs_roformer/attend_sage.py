from functools import lru_cache

import torch

from .attend import Attend as SDPAAttend


sageattn = None
# ROCm also uses torch.cuda; importing Sage's NVIDIA kernels there is unsafe.
if torch.version.cuda is not None and torch.version.hip is None:
    try:
        from sageattention import sageattn
    except (ImportError, OSError):
        pass


@lru_cache(maxsize=None)
def _sage_supports_device(device):
    # Match architectures supported by SageAttention's automatic dispatcher.
    return torch.cuda.get_device_capability(device) in (
        (8, 0), (8, 6), (8, 9), (9, 0), (12, 0), (12, 1),
    )


class Attend(SDPAAttend):
    def flash_attn(self, q, k, v):
        # Sage has no dropout or autograd support. Unsupported inputs go directly
        # to SDPA, without speculative kernel launches or per-forward retries.
        if (
            sageattn is not None
            and q.device.type == 'cuda'
            and torch.version.hip is None
            and q.device == k.device == v.device
            and q.dtype in (torch.float16, torch.bfloat16)
            and q.dtype == k.dtype == v.dtype
            and q.ndim == k.ndim == v.ndim == 4
            and q.shape[:2] == k.shape[:2] == v.shape[:2]
            and k.shape[-2] == v.shape[-2]
            and q.shape[-2] > 0 and k.shape[-2] > 0
            and 0 < q.shape[-1] == k.shape[-1] == v.shape[-1] <= 128
            and q.stride(-1) == k.stride(-1) == v.stride(-1) == 1
            and (not self.training or self.dropout == 0.)
            and (not torch.is_grad_enabled() or not (q.requires_grad or k.requires_grad or v.requires_grad))
            and _sage_supports_device(q.device)
        ):
            return sageattn(
                q, k, v,
                tensor_layout='HND',
                is_causal=False,
                sm_scale=self.scale,
            )
        return super().flash_attn(q, k, v)
