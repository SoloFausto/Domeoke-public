from audio_processing.device import get_device, inference_resources
from audio_processing.whisper_backend import load_alignment_model
import os
def generate_word_timestamps(lyrics, audio_file_path, language='en', model_name='large-v3'):
    """
    Generates word-level timestamps from an audio file and a corresponding TXT file using Stable Whisper.

    Args:
        txt_file_path (str): Path to the input TXT file containing lyrics.
        audio_file_path (str): Path to the input audio file.
        language (str): Language of the lyrics. Default is 'en' (English).
        model_name (str): Name of the Stable Whisper model to use. Default is 'large-v3'.
    """
    device = get_device()
    with inference_resources(device):
        return _generate_word_timestamps(lyrics, audio_file_path, language, model_name, device)


def _generate_word_timestamps(lyrics, audio_file_path, language, model_name, device):
    # stable-ts model cycles must become unreachable before releasing the cache.
    model = load_alignment_model(model_name, device)
    # Align the audio with the lyrics
    result = model.align(audio_file_path, lyrics, language=language, regroup=False)
    model.refine(audio_file_path, result)
    audio_filename = os.path.basename(audio_file_path).replace('.wav', '')

    save_path = f"processing/word_level_srt/{audio_filename}.srt"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    # Save the result as an SRT file
    result.to_srt_vtt(save_path, segment_level=False)
    return save_path

# Example usage:
# generate_word_timestamps('base_lyrics/carinio.txt', 'audio/Carinio_instrumental.wav', language='es', model_name='large-v3')
