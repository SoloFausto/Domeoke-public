import gc
from types import MethodType
import unittest
import weakref

import torch

from audio_processing.device import inference_resources


def devices():
    result = [torch.device("cpu")]
    if torch.cuda.is_available():
        result.append(torch.device("cuda:0"))
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        result.append(torch.device("xpu:0"))
    return result


class InferenceMemoryTests(unittest.TestCase):
    def setUp(self):
        self.automatic_gc = gc.isenabled()
        gc.disable()

    def tearDown(self):
        if self.automatic_gc:
            gc.enable()

    def memory(self, device):
        if device.type == "cpu":
            return None
        api = getattr(torch, device.type)
        api.synchronize(device)
        return api.memory_allocated(device), api.memory_reserved(device)

    def allocate_stage(self, device, refs, failure=None):
        model = torch.nn.Linear(256, 256).to(device)
        # This is the same ownership cycle stable-ts creates on its models.
        model.align = MethodType(lambda self: None, model)
        activation = torch.ones((512, 512), device=device)
        refs.extend((weakref.ref(model), weakref.ref(activation)))
        if failure is not None:
            try:
                raise ValueError("inner inference failure")
            except ValueError as cause:
                raise failure from cause

    def test_consecutive_stages_release_cycles_and_allocator_blocks(self):
        for device in devices():
            with self.subTest(device=str(device)):
                with inference_resources(device):
                    pass
                baseline = self.memory(device)
                for _ in range(2):
                    refs = []
                    with inference_resources(device):
                        self.allocate_stage(device, refs)
                    self.assertTrue(all(reference() is None for reference in refs))
                    self.assertEqual(self.memory(device), baseline)

    def test_retained_exception_does_not_retain_model_or_activations(self):
        for device in devices():
            with self.subTest(device=str(device)):
                with inference_resources(device):
                    pass
                baseline = self.memory(device)
                refs = []
                failure = RuntimeError("outer inference failure")
                try:
                    with inference_resources(device):
                        self.allocate_stage(device, refs, failure)
                except RuntimeError as error:
                    self.assertIs(error, failure)
                else:
                    self.fail("Inference failure was swallowed")
                # Keep the error and its chained traceback alive during checks.
                self.assertIsNotNone(failure.__traceback__)
                self.assertIsInstance(failure.__cause__, ValueError)
                self.assertTrue(all(reference() is None for reference in refs))
                self.assertEqual(self.memory(device), baseline)
