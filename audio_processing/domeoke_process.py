import os
import inference
import srt_process
import timestamps
import torchaudio
from speechbrain.inference.classifiers import EncoderClassifier
## Domeoke Processing Script

if __name__ == "__main__":
    audio_file = "processing/input_audio/calle13.mp3"
    lyrics_file = "processing/base_lyrics/calle13.txt"
    audio_filename = os.path.basename(audio_file).replace('.mp3', '')
    generated_files = inference.split_audio(audio_file)
    instrumental_audio = generated_files[1]
    vocals_audio = generated_files[0]
    language_id = EncoderClassifier.from_hparams(source="speechbrain/lang-id-voxlingua107-ecapa", savedir="tmp", run_opts={"device":"cuda"})
    signal = language_id.load_audio(vocals_audio)
    prediction =  language_id.classify_batch(signal)
    detected_language = prediction[3][0].split(":")[0]
    word_level_srt = timestamps.generate_word_timestamps(lyrics_file, vocals_audio, language=detected_language)
    sentence_level_srt = srt_process.word_to_sentence_level_srt(
        srt_file_path=word_level_srt,
        txt_file_path=lyrics_file,
        output_file_path=f"processing/sentence_level_srt/{audio_filename}.srt"
    )
    print(generated_files)