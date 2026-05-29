import stable_whisper
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
    # Load the model, using GPU if available
    model = stable_whisper.load_model(model_name)
    # model.in_memory = True  # Load the model into memory for faster processing

    # Read the lyrics from the TXT file


    # Align the audio with the lyrics
    result = model.align(audio_file_path, lyrics, language=language, regroup=False)
    model.refine(audio_file_path, result)
    audio_filename = os.path.basename(audio_file_path).replace('.wav', '')

    save_path = f"processing/word_level_srt/{audio_filename}.srt"
    # Save the result as an SRT file
    result.to_srt_vtt(save_path, segment_level=False)
    return save_path

# Example usage:
# generate_word_timestamps('base_lyrics/carinio.txt', 'audio/Carinio_instrumental.wav', language='es', model_name='large-v3')
