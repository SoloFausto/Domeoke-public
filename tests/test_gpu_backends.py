"""Run with: python -m unittest discover -s tests -v.

Hardware tests exercise each available backend, without downloading model weights.
"""
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

import numpy as np
import torch
from whisper.model import ModelDimensions, Whisper

from scripts import hardware
# The embedded separation models use the same import root as inference.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audio_processing"))

from audio_processing.device import get_device, mixed_precision
from models.bs_roformer.attend import Attend
from models.bs_roformer.attend_sage import Attend as SageAttend
from audio_processing.whisper_backend import dtw, load_alignment_model, median_filter


def available_devices():
    devices = [torch.device("cpu")]
    if torch.cuda.is_available():
        devices.append(torch.device("cuda:0"))
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        devices.append(torch.device("xpu:0"))
    return devices


class HardwareSelectionTests(unittest.TestCase):
    def test_arc_wins_over_unsupported_amd_integrated_gpu(self):
        adapters = [
            {"vendor": "1002", "device": "13c0", "name": "AMD Radeon(TM) Graphics"},
            {"vendor": "8086", "device": "e20b", "name": "Intel(R) Arc(TM) B580 Graphics"},
        ]
        with patch.object(hardware.platform, "system", return_value="Linux"):
            self.assertEqual(hardware.choose_backend("auto", adapters), "xpu")
            self.assertEqual(hardware.choose_backend("auto", adapters[:1]), "cpu")

    def test_supported_radeon_selects_rocm_not_cuda(self):
        adapters = [{"vendor": "1002", "device": "744c", "name": "AMD Radeon RX 7900 XTX"}]
        with patch.object(hardware.platform, "system", return_value="Linux"):
            self.assertEqual(hardware.choose_backend("auto", adapters), "rocm")

    def test_explicit_cpu_override_ignores_invalid_gpu_request(self):
        with patch.dict(os.environ, {"DOMEOKE_DEVICE": "not-a-device"}):
            with self.assertRaises(ValueError):
                get_device()
            self.assertEqual(get_device(force_cpu=True), torch.device("cpu"))

    def test_unavailable_explicit_gpu_never_falls_back(self):
        with patch.dict(os.environ, {"DOMEOKE_DEVICE": "xpu:999999"}):
            with self.assertRaises(RuntimeError):
                get_device()


class PortableInferenceTests(unittest.TestCase):
    def test_attention_scale_and_dropout_match_manual_math(self):
        generator = torch.Generator().manual_seed(42)
        q, k, v = [torch.randn(2, 2, length, 32, generator=generator) for length in (7, 11, 11)]
        for device in available_devices():
            for scale in (None, 0., .37):
                with self.subTest(device=str(device), scale=scale):
                    expected = Attend(flash=False, scale=scale).eval()(q, k, v)
                    inputs = [tensor.to(device) for tensor in (q, k, v)]
                    for cls in (Attend, SageAttend):
                        actual = cls(flash=True, scale=scale).eval()(*inputs)
                        torch.testing.assert_close(actual.cpu(), expected, rtol=1e-4, atol=1e-5)
                    dropout = Attend(flash=True, dropout=1.).train()(*inputs)
                    self.assertEqual(torch.count_nonzero(dropout).item(), 0)

    def test_autocast_accelerates_gpu_without_changing_cpu_precision(self):
        for device in available_devices():
            with self.subTest(device=str(device)):
                tensor = torch.ones(32, 32, device=device)
                with mixed_precision(device):
                    result = tensor @ tensor
                self.assertEqual(result.dtype, torch.float32 if device.type == "cpu" else torch.float16)
                torch.testing.assert_close(result.cpu().float(), torch.full((32, 32), 32.))

    def test_timing_matches_cpu_without_gpu_fp64_or_triton_requirement(self):
        generator = torch.Generator().manual_seed(17)
        values = torch.randn(2, 7, 20, generator=generator)
        cost = torch.rand(6, 18, generator=generator)
        for device in available_devices():
            with self.subTest(device=str(device)):
                torch.testing.assert_close(median_filter(values.to(device), 7).cpu(), median_filter(values, 7))
                np.testing.assert_array_equal(dtw(cost.to(device)), dtw(cost))

    def test_whisper_moves_neural_layers_without_moving_sparse_metadata(self):
        dims = ModelDimensions(n_mels=4, n_audio_ctx=4, n_audio_state=8, n_audio_head=2,
                               n_audio_layer=1, n_vocab=32, n_text_ctx=8, n_text_state=8,
                               n_text_head=2, n_text_layer=1)
        torch.manual_seed(9)
        source = Whisper(dims).eval()
        with torch.no_grad():
            source.decoder.positional_embedding.zero_()
        mel, tokens = torch.randn(1, 4, 8), torch.tensor([[1, 2, 3]])
        with torch.no_grad():
            expected = source(mel, tokens)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "whisper.pt"
            torch.save({"dims": vars(dims), "model_state_dict": source.state_dict()}, checkpoint)
            for device in available_devices():
                with self.subTest(device=str(device)):
                    model = load_alignment_model(str(checkpoint), device)
                    with torch.no_grad():
                        actual = model(mel.to(device), tokens.to(device))
                    torch.testing.assert_close(actual.cpu(), expected, rtol=1e-4, atol=1e-5)
                    self.assertEqual(model.alignment_heads.indices().tolist(), source.alignment_heads.indices().tolist())


if __name__ == "__main__":
    unittest.main()
