# coding: utf-8
__author__ = 'Roman Solovyev (ZFTurbo): https://github.com/ZFTurbo/'

import time
import librosa
import sys
import os
import glob
import torch
import soundfile as sf
import numpy as np
from tqdm.auto import tqdm
import torch.nn as nn

# Using the embedded version of Python can also correctly import the utils module.
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from utils.audio_utils import normalize_audio, denormalize_audio
from utils.settings import get_model_from_config, parse_args_inference
from utils.model_utils import demix
from utils.model_utils import prefer_target_instrument, apply_tta
from audio_processing.device import get_device, inference_resources


def load_start_checkpoint(start_check_point, model: torch.nn.Module) -> None:
    """
    Load the starting checkpoint for a model.

    Args:
        args: Parsed command-line arguments containing the checkpoint path.
        model: PyTorch model to load the checkpoint into.
        type_: how to load weights - for train we can load not fully compatible weights
    """
    state_dict = torch.load(start_check_point, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)

def run_wav(audio_file, store_dir, model_type, use_tta, force_cpu,config_path, start_checkpoint, verbose: bool = False):
    """
    Process a folder of audio files for source separation.

    Parameters:
    ----------
    model : torch.nn.Module
        Pre-trained model for source separation.
    args : Namespace
        Arguments containing input folder, output folder, and processing options.
    config : Dict
        Configuration object with audio and inference settings.
    device : torch.device
        Device for model inference (CUDA/ROCm, XPU, MPS, or CPU).
    verbose : bool, optional
        If True, prints detailed information during processing. Default is False.
    """
    device = get_device(force_cpu=force_cpu)
    with inference_resources(device):
        return _run_wav(audio_file, store_dir, model_type, use_tta, device,
                        config_path, start_checkpoint, verbose)


def _run_wav(audio_file, store_dir, model_type, use_tta, device, config_path, start_checkpoint, verbose):
    # Keep models and tensors in this frame so cleanup runs after it exits.
    print("Using device: ", device)


    if device.type == "cuda" and not torch.version.hip:
        torch.backends.cudnn.benchmark = True

    model, config = get_model_from_config(model_type, config_path)

    load_start_checkpoint(start_checkpoint, model)
    print("Instruments: {}".format(config.training.instruments))

    model = model.to(device)

    model.eval()

    path = audio_file
    if not os.path.exists(path):
        print(f"Audio file {path} does not exist.")
        return
    sample_rate = getattr(config.audio, 'sample_rate', 44100)


    instruments = prefer_target_instrument(config)[:]
    os.makedirs(store_dir, exist_ok=True)

    
    print(f"Processing track: {path}")
    try:
        mix, sr = librosa.load(path, sr=sample_rate, mono=False)
    except Exception as e:
        print(f'Cannot read track: {format(path)}')
        print(f'Error message: {str(e)}')
        return

    # If mono audio we must adjust it depending on model
    if len(mix.shape) == 1:
        mix = np.expand_dims(mix, axis=0)
        if 'num_channels' in config.audio:
            if config.audio['num_channels'] == 2:
                print(f'Convert mono track to stereo...')
                mix = np.concatenate([mix, mix], axis=0)

    mix_orig = mix.copy()
    if 'normalize' in config.inference:
        if config.inference['normalize'] is True:
            mix, norm_params = normalize_audio(mix)

    waveforms_orig = demix(config, model, mix, device, model_type=model_type, pbar=True)

    if use_tta:
        waveforms_orig = apply_tta(config, model, mix, waveforms_orig, device, model_type)

    
    instr = 'vocals' if 'vocals' in instruments else instruments[0]
    waveforms_orig['instrumental'] = mix_orig - waveforms_orig[instr]
    if 'instrumental' not in instruments:
        instruments.append('instrumental')

    file_name = os.path.splitext(os.path.basename(path))[0]

    generated_files = list()
    for instr in instruments:
        estimates = waveforms_orig[instr]
        if 'normalize' in config.inference:
            if config.inference['normalize'] is True:
                estimates = denormalize_audio(estimates, norm_params)

        codec = 'wav'
        subtype = 'PCM_16'

        output_path = os.path.join(store_dir, f"{file_name}_{instr}.{codec}")
        sf.write(output_path, estimates.T, sr, subtype=subtype)
        generated_files.append(output_path)
    return generated_files

def split_audio(audio_file):
    generated_files = run_wav(
        audio_file=audio_file,
        store_dir='processing/output_audio/',
        model_type='mel_band_roformer',
        use_tta=False,
        force_cpu=False,
        config_path='audio_processing/configs/config_melbandroformer_instvoc_duality.yaml',
        start_checkpoint='audio_processing/results/melband_roformer_instvox_duality_v2.ckpt',
        verbose=True
    )
    return generated_files
